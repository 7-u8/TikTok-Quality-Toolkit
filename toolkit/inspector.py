"""Inspect an MP4 and say which TikTok tricks it is ready for."""

import os

from .mp4 import Mp4File, find, u32

CODEC_NAMES = {
    "avc1": "H.264", "avc3": "H.264", "hvc1": "H.265/HEVC", "hev1": "H.265/HEVC",
    "av01": "AV1", "vp09": "VP9", "mp4a": "AAC", "Opus": "Opus", "ac-3": "AC-3",
}


def _video_dims(mp4, v):
    stsd = find(mp4.buf, v.stbl, "stsd") if v.stbl else None
    if stsd is None:
        return None, None
    entry = stsd.body + 8  # first sample entry
    w = int.from_bytes(mp4.buf[entry + 32 : entry + 34], "big")
    h = int.from_bytes(mp4.buf[entry + 34 : entry + 36], "big")
    return w, h


def _avc_profile(mp4, v):
    stsd = find(mp4.buf, v.stbl, "stsd")
    entry_size = u32(mp4.buf, stsd.body + 8)
    blob = bytes(mp4.buf[stsd.body + 8 : stsd.body + 8 + entry_size])
    i = blob.find(b"avcC")
    if i < 0:
        return None
    profile, level = blob[i + 5], blob[i + 7]
    name = {66: "Baseline", 77: "Main", 88: "Extended", 100: "High", 110: "High 10",
            122: "High 4:2:2", 144: "High 4:4:4"}.get(profile, str(profile))
    return f"{name} L{level / 10:g}"


TRANSFER = {1: "BT.709", 6: "BT.601", 13: "sRGB", 14: "BT.2020", 15: "BT.2020", 16: "PQ (HDR10)", 18: "HLG (HDR)"}
MATRIX = {1: "BT.709", 5: "BT.601", 6: "BT.601", 9: "BT.2020", 0: "RGB"}


def _colour(mp4, v):
    """Read the nclx 'colr' box of the first sample entry: (transfer, matrix, full_range) or None."""
    stsd = find(mp4.buf, v.stbl, "stsd") if v.stbl else None
    if stsd is None:
        return None
    entry_size = u32(mp4.buf, stsd.body + 8)
    blob = bytes(mp4.buf[stsd.body + 8 : stsd.body + 8 + entry_size])
    i = blob.find(b"colrnclx")
    if i < 0:
        return None
    prim, trc, mat = (int.from_bytes(blob[i + 8 + k : i + 10 + k], "big") for k in (0, 2, 4))
    return {"primaries": prim, "transfer": trc, "matrix": mat, "full": bool(blob[i + 14] & 0x80),
            "hdr": trc in (16, 18)}


def inspect(path):
    """Return (info dict, list of report lines)."""
    mp4 = Mp4File(path)
    v, a = mp4.video, mp4.audio
    info = {
        "size": mp4.file_size,
        "fragmented": mp4.fragmented,
        "faststart": mp4.faststart,
        "mdat_count": mp4.top_types().count("mdat"),
        "video": None,
        "audio": None,
    }
    lines = [os.path.basename(path), f"   size: {mp4.file_size / 1e6:.1f} MB"]

    if v:
        w, h = _video_dims(mp4, v)
        fps = v.fps
        bitrate = mp4.file_size * 8 / v.seconds / 1e6 if v.seconds else 0
        co64 = v.chunk_box is not None and v.chunk_box.type == "co64"
        colour = _colour(mp4, v)
        info["video"] = {
            "codec": v.codec, "width": w, "height": h, "fps": fps, "cfr": v.is_cfr,
            "frames": v.sample_count, "seconds": v.seconds, "timescale": v.timescale, "co64": co64,
            "colour": colour,
        }
        profile = _avc_profile(mp4, v) if v.codec in ("avc1", "avc3") else None
        lines += [
            f"   video: {CODEC_NAMES.get(v.codec, v.codec)}{' ' + profile if profile else ''}, {w}x{h}",
            f"   fps: {fps:.3f} ({'constant' if v.is_cfr else 'VARIABLE'}), {v.sample_count} frames, {v.seconds:.2f}s",
            f"   timescale: {v.timescale}, avg bitrate ~{bitrate:.1f} Mbps",
        ]
        if colour:
            lines.append(f"   colour: {TRANSFER.get(colour['transfer'], colour['transfer'])}, "
                         f"matrix {MATRIX.get(colour['matrix'], colour['matrix'])}, "
                         f"{'full' if colour['full'] else 'limited'} range")
    else:
        lines.append("   video: none")
    if a:
        info["audio"] = {"codec": a.codec, "rate": a.timescale, "seconds": a.seconds}
        lines.append(f"   audio: {CODEC_NAMES.get(a.codec, a.codec)}, {a.timescale} Hz, {a.seconds:.2f}s")
    lines.append(
        f"   container: {'fragmented' if mp4.fragmented else 'regular'}, "
        f"{'moov first (faststart)' if mp4.faststart else 'moov last'}"
    )

    if v and v.already_patched:
        info["patched"] = True
        lines.append(f"   ALREADY PATCHED: plays as {v.fps:.1f} fps but holds {v.header_fps:.1f} fps "
                     "worth of frames - ready to upload, do not patch again.")
        return info, lines

    lines.append("   readiness:")
    for name, ok, why in checks(info):
        lines.append(f"     [{'OK' if ok else '!!'}] {name}{'' if ok else ' - ' + why}")
    return info, lines


def checks(info):
    v = info["video"]
    out = []
    if not v:
        return [("video track", False, "no video track")]
    fps = v["fps"] or 0
    out.append(("high frame rate (>30 fps)", fps > 31,
                f"source is {fps:.1f} fps - use Prepare with interpolation to reach 60"))
    out.append(("constant frame rate", v["cfr"], "variable frame rate - run Prepare to make it constant"))
    short = min(v["width"] or 0, v["height"] or 0)
    out.append(("1080p resolution", short >= 1080,
                f"short side is {short}px - Prepare with AI upscale (Real-ESRGAN) can make it 1080p"))
    colour = v.get("colour") or {}
    out.append(("SDR colours (not HDR)", not colour.get("hdr"),
                "HDR video looks washed out / too dark on TikTok - Prepare with Colour fix converts it"))
    out.append(("standard BT.709 colours",
                not colour or colour.get("hdr") or (colour.get("matrix") in (1, None) and not colour.get("full")),
                "full range or BT.601 colours - Prepare with Colour fix corrects them"))
    out.append(("H.264 (needed for ghost frames)", v["codec"] in ("avc1",),
                f"codec is {v['codec']} - run Prepare to re-encode to H.264"))
    simple = not info["fragmented"] and info["mdat_count"] == 1 and not v["co64"]
    out.append(("simple container (needed for ghost frames)", simple,
                "fragmented / multiple mdat / >4GB - run Prepare to remux"))
    return out
