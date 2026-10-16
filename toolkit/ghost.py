"""Ghost-frame transform (1080p60 upload trick).

Port of BastienGimbert/tiktok-quality (MIT), itself a byte-for-byte
replica of the "TikTok Enhancer" server output. The declared frame count is
inflated by appending "ghost" samples that all point to one 8-byte filler
NAL unit; the real video data is not re-encoded.

Improvements over the original:
* streams mdat (no full-file load), any mdat header size
* version-0 and version-1 header boxes, movie timescale other than 1000
* keeps VFR timing (appends to stts instead of replacing it)
* only adds the High-profile avcC extension when it is valid and missing
* SEI stripping only when NAL length size is 4 bytes
* audio edit list optional, clear errors for unsupported inputs
"""

import os
import struct

from .mp4 import (
    Box, Mp4Error, Mp4File, children, find, header_fields, mdhd_language_offset,
    parse_elst, parse_stco, parse_stsc, parse_stsz, tkhd_duration_field, u16, u32,
)

PADDING_NAL = b"\x00\x00\x00\x04\x00\x00\x00\x00"
KEEP_NALU_TYPES = {1, 5}  # non-IDR slice, IDR slice
LANG_UND = 0x55C4
DEFAULT_COMMENT = "TK8vY5VqBA6hUlo1yuGvNA"
HIGH_PROFILES = {100, 110, 122, 144}
HIGH_EXT = b"\xfd\xf8\xf8\x00"  # 4:2:0, 8-bit luma/chroma, no SPS-ext
COPY_CHUNK = 4 * 1024 * 1024


def box(typ, content):
    return struct.pack(">I", 8 + len(content)) + typ.encode("latin-1") + content


def raw(buf, b):
    return bytes(buf[b.pos : b.end]) if b is not None else b""


def set_uint(data, off, size, value):
    data[off : off + size] = value.to_bytes(size, "big")


def build_stts(entries):
    return box("stts", struct.pack(">II", 0, len(entries)) + b"".join(struct.pack(">II", *e) for e in entries))


def build_stsc(entries):
    return box("stsc", struct.pack(">II", 0, len(entries)) + b"".join(struct.pack(">III", *e) for e in entries))


def build_stsz(sizes):
    return box("stsz", struct.pack(">III", 0, 0, len(sizes)) + struct.pack(f">{len(sizes)}I", *sizes))


def build_stco(offsets):
    return box("stco", struct.pack(">II", 0, len(offsets)) + struct.pack(f">{len(offsets)}I", *offsets))


def build_ftyp():
    return box("ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2avc1mp41")


def build_hdlr(handler, name):
    return box("hdlr", struct.pack(">II", 0, 0) + handler + b"\x00" * 12 + name.encode() + b"\x00")


def build_udta_comment(comment):
    meta_hdlr = box("hdlr", struct.pack(">II", 0, 0) + b"mdir" + b"appl" + b"\x00" * 9)
    data_box = box("data", struct.pack(">II", 1, 0) + comment.encode("utf-8"))
    cmt = struct.pack(">I", 8 + len(data_box)) + b"\xa9cmt" + data_box
    return box("udta", box("meta", struct.pack(">I", 0) + meta_hdlr + box("ilst", cmt)))


def avcc_has_extension(c):
    """True if avcC content already has bytes after the SPS/PPS lists."""
    p = 6
    for _ in range(c[5] & 0x1F):
        p += 2 + u16(c, p)
    npps = c[p]
    p += 1
    for _ in range(npps):
        p += 2 + u16(c, p)
    return p < len(c)


def split_nalus(sample):
    out, pos = [], 0
    while pos + 4 <= len(sample):
        n = u32(sample, pos)
        if pos + 4 + n > len(sample):
            break
        out.append((sample[pos + 4] & 0x1F, sample[pos : pos + 4 + n]))
        pos += 4 + n
    return out


def need(buf, parent, *path):
    b = find(buf, parent, *path)
    if b is None:
        raise Mp4Error(f"Missing '{'/'.join(path)}' box.")
    return b


def ghost_frames(in_file, out_file, multiplier=10, comment=DEFAULT_COMMENT):
    """Write the ghost-frame version of in_file. Returns report lines."""
    if os.path.abspath(in_file) == os.path.abspath(out_file):
        raise Mp4Error("Output file must be different from the input file.")
    if not 2 <= int(multiplier) <= 50:
        raise Mp4Error("Multiplier must be between 2 and 50.")
    multiplier = int(multiplier)

    mp4 = Mp4File(in_file)
    buf = mp4.buf
    if mp4.fragmented:
        raise Mp4Error("Fragmented MP4 is not supported - run the Prepare step first.")
    mdats = [b for b in mp4.top if b.type == "mdat"]
    if len(mdats) != 1:
        raise Mp4Error("File must contain exactly one 'mdat' box - run the Prepare step first.")
    mdat = mdats[0]

    vt = mp4.video
    if vt is None or vt.stbl is None:
        raise Mp4Error("No video track found.")
    if vt.codec != "avc1":
        raise Mp4Error(f"Video codec '{vt.codec}' not supported, H.264 (avc1) needed - run the Prepare step first.")
    stbl = vt.stbl
    if find(buf, stbl, "stco") is None:
        raise Mp4Error("64-bit chunk offsets (files over 4 GB) are not supported.")

    stco_box = need(buf, stbl, "stco")
    stsd_box = need(buf, stbl, "stsd")
    v_chunks = parse_stco(buf, stco_box)
    v_sizes = parse_stsz(buf, need(buf, stbl, "stsz"))
    v_stsc = parse_stsc(buf, need(buf, stbl, "stsc"))
    v_stts = vt.stts
    if not v_sizes or not v_chunks or not v_stts:
        raise Mp4Error("Video track has no samples.")
    for off in v_chunks:
        if not mdat.body <= off < mdat.end:
            raise Mp4Error("Video data outside the 'mdat' box is not supported.")

    orig_frames = len(v_sizes)
    time_delta = v_stts[0][1]
    pad_count = orig_frames * (multiplier - 1)
    v_seconds = vt.seconds or 1

    # --- video sample entry ------------------------------------------------
    entry = next(children(buf, stsd_box.body + 8, stsd_box.end))
    fixed = bytes(buf[entry.body : entry.body + 78])
    sub = list(children(buf, entry.body + 78, entry.end))
    avcc = next((b for b in sub if b.type == "avcC"), None)
    if avcc is None:
        raise Mp4Error("Missing 'avcC' box.")
    avcc_content = bytes(buf[avcc.body : avcc.end])
    nal_len_size = (avcc_content[4] & 3) + 1
    add_ext = avcc_content[1] in HIGH_PROFILES and not avcc_has_extension(avcc_content)
    avcc_new = box("avcC", avcc_content + (HIGH_EXT if add_ext else b""))

    # --- strip SEI from the first sample -------------------------------------
    first_off, first_size = v_chunks[0], v_sizes[0]
    with open(in_file, "rb") as f:
        f.seek(first_off)
        first_sample = f.read(first_size)
    new_first = first_sample
    if nal_len_size == 4:
        kept = [d for t, d in split_nalus(first_sample) if t in KEEP_NALU_TYPES]
        if kept:
            new_first = b"".join(kept)
    sei_removed = first_size - len(new_first)

    total_v_bytes = sum(v_sizes) - sei_removed
    new_v_avg_br = int(total_v_bytes * 8 / v_seconds)
    btrt = next((b for b in sub if b.type == "btrt"), None)
    max_br = u32(buf, btrt.body + 4) if btrt else new_v_avg_br
    btrt_new = box("btrt", struct.pack(">III", 0, max_br, new_v_avg_br))
    keep_sub = [b for b in sub if b.type in ("colr", "pasp")]
    keep_sub += [b for b in sub if b.type not in ("avcC", "colr", "pasp", "btrt")]
    avc1 = box("avc1", fixed + avcc_new + b"".join(raw(buf, b) for b in keep_sub) + btrt_new)
    v_stsd = box("stsd", struct.pack(">II", 0, 1) + avc1)

    v_stbl_head = [
        v_stsd,
        build_stts([tuple(e) for e in v_stts] + [(pad_count, time_delta)]),
        raw(buf, find(buf, stbl, "stss")),
        raw(buf, find(buf, stbl, "sdtp")),
        raw(buf, find(buf, stbl, "ctts")),
        build_stsc([tuple(e) for e in v_stsc] + [(len(v_chunks) + 1, 1, 1)]),
        build_stsz([len(new_first)] + v_sizes[1:] + [len(PADDING_NAL)] * pad_count),
    ]
    minf = need(buf, vt.mdia, "minf")

    def video_trak(stco):
        stbl_b = box("stbl", b"".join(v_stbl_head) + stco)
        minf_b = box("minf", raw(buf, find(buf, minf, "vmhd")) + raw(buf, find(buf, minf, "dinf")) + stbl_b)
        mdia_b = box("mdia", raw(buf, vt.mdhd) + raw(buf, vt.hdlr) + minf_b)
        return box("trak", raw(buf, vt.tkhd) + raw(buf, find(buf, vt.trak, "edts")) + mdia_b)

    # --- audio ---------------------------------------------------------------
    mv_ts = mp4.movie_timescale
    at = mp4.audio
    audio = None
    report_audio = "no audio track"
    if at is not None and at.stbl is not None:
        a_stbl = at.stbl
        a_stco_box = find(buf, a_stbl, "stco")
        if a_stco_box is None:
            raise Mp4Error("Audio uses 64-bit chunk offsets - not supported.")
        a_chunks = parse_stco(buf, a_stco_box)
        a_sizes = parse_stsz(buf, need(buf, a_stbl, "stsz"))
        a_stts = at.stts
        a_ts = at.timescale

        new_a_stts = [tuple(e) for e in a_stts]
        new_a_dur = at.duration
        new_a_dur_mv = at.duration * mv_ts // a_ts
        elst = find(buf, at.trak, "edts", "elst")
        if elst is not None and a_stts and len(a_sizes) > 1:
            entries = parse_elst(buf, elst)
            if len(entries) == 1 and entries[0][1] >= 0:
                seg, media_time = entries[0]
                target_dur = seg * a_ts // mv_ts
                a_delta = a_stts[0][1]
                main_n = len(a_sizes) - 1
                last_delta = target_dur + media_time - main_n * a_delta
                if 0 < last_delta <= a_delta:
                    new_a_stts = [(main_n, a_delta), (1, last_delta)]
                    new_a_dur, new_a_dur_mv = target_dur, seg

        a_bytes = sum(a_sizes)
        old_ticks = sum(c * d for c, d in a_stts) or 1
        new_ticks = sum(c * d for c, d in new_a_stts) or 1
        old_a_br = a_bytes * 8 * a_ts // old_ticks
        new_a_br = a_bytes * 8 * a_ts // new_ticks
        a_stsd = bytearray(raw(buf, need(buf, a_stbl, "stsd")))
        if old_a_br != new_a_br and old_a_br < 1 << 32 and new_a_br < 1 << 32:
            ob, nb = struct.pack(">I", old_a_br), struct.pack(">I", new_a_br)
            p = 0
            while (i := a_stsd.find(ob, p)) != -1:
                a_stsd[i : i + 4] = nb
                p = i + 4

        a_tkhd = bytearray(raw(buf, at.tkhd))
        off, size = tkhd_duration_field(buf, at.tkhd)
        set_uint(a_tkhd, off - at.tkhd.pos, size, new_a_dur_mv)

        a_mdhd = bytearray(raw(buf, at.mdhd))
        _, dur_off, dsz = header_fields(buf, at.mdhd)
        set_uint(a_mdhd, dur_off - at.mdhd.pos, dsz, new_a_dur)
        set_uint(a_mdhd, mdhd_language_offset(buf, at.mdhd) - at.mdhd.pos, 2, LANG_UND)

        a_minf = need(buf, at.mdia, "minf")
        a_stbl_parts = [
            bytes(a_stsd),
            build_stts(new_a_stts),
            raw(buf, need(buf, a_stbl, "stsc")),
            raw(buf, need(buf, a_stbl, "stsz")),
        ]
        a_tail = raw(buf, find(buf, a_stbl, "sgpd")) + raw(buf, find(buf, a_stbl, "sbgp"))

        def audio_trak(stco):
            stbl_b = box("stbl", b"".join(a_stbl_parts) + stco + a_tail)
            minf_b = box("minf", raw(buf, find(buf, a_minf, "smhd")) + raw(buf, find(buf, a_minf, "dinf")) + stbl_b)
            mdia_b = box("mdia", bytes(a_mdhd) + build_hdlr(b"soun", "SoundHandler") + minf_b)
            return box("trak", bytes(a_tkhd) + raw(buf, find(buf, at.trak, "edts")) + mdia_b)

        audio = (audio_trak, a_chunks)
        report_audio = "audio timing aligned to the video" if new_a_stts != [tuple(e) for e in a_stts] else "audio timing kept"

    # --- movie header ----------------------------------------------------------
    off, size = tkhd_duration_field(buf, vt.tkhd)
    v_tkhd_dur = int.from_bytes(buf[off : off + size], "big")
    mvhd = bytearray(raw(buf, mp4.mvhd))
    _, dur_off, dsz = header_fields(buf, mp4.mvhd)
    set_uint(mvhd, dur_off - mp4.mvhd.pos, dsz, max(v_tkhd_dur, new_a_dur_mv) if audio else v_tkhd_dur)
    udta = build_udta_comment(comment)
    ftyp_free = build_ftyp() + struct.pack(">I", 8) + b"free"

    # --- offsets ---------------------------------------------------------------
    def assemble(v_offs, a_offs):
        parts = [bytes(mvhd), video_trak(build_stco(v_offs))]
        if audio:
            parts.append(audio[0](build_stco(a_offs)))
        return box("moov", b"".join(parts) + udta)

    total_v_chunks = len(v_chunks) + pad_count
    moov_size = len(assemble([0] * total_v_chunks, [0] * len(audio[1]) if audio else []))
    new_mdat_start = len(ftyp_free) + moov_size + 8
    mdat_content = (mdat.end - mdat.body) - sei_removed + len(PADDING_NAL)
    if 8 + mdat_content >= 1 << 32 or new_mdat_start + mdat_content >= 1 << 32:
        raise Mp4Error("Output would exceed 4 GB - not supported.")
    first_rel = first_off - mdat.body
    pad_abs = new_mdat_start + mdat_content - len(PADDING_NAL)

    def shift(off, inclusive):
        rel = off - mdat.body
        keep = rel <= first_rel if inclusive else rel < first_rel
        return new_mdat_start + rel - (0 if keep else sei_removed)

    v_offs = [shift(o, True) for o in v_chunks] + [pad_abs] * pad_count
    a_offs = [shift(o, False) for o in audio[1]] if audio else []
    moov = assemble(v_offs, a_offs)
    assert len(moov) == moov_size

    # --- write -----------------------------------------------------------------
    try:
        with open(in_file, "rb") as src, open(out_file, "wb") as dst:
            dst.write(ftyp_free + moov + struct.pack(">I", 8 + mdat_content) + b"mdat")
            _copy(src, dst, mdat.body, first_off)
            dst.write(new_first)
            _copy(src, dst, first_off + first_size, mdat.end)
            dst.write(PADDING_NAL)
    except Exception:
        try:
            os.remove(out_file)
        except OSError:
            pass
        raise

    dropped = [t.handler for t in mp4.tracks if t not in (vt, at)]
    report = [
        f"Ghost frames x{multiplier}: {orig_frames} real -> {orig_frames + pad_count} declared frames",
        f"   first frame SEI stripped: -{sei_removed} bytes" + ("" if nal_len_size == 4 else " (skipped, NAL size != 4)"),
        f"   avcC High-profile extension: {'added' if add_ext else 'not needed'}",
        f"   {report_audio}",
        f"   size: {mp4.file_size:,} -> {os.path.getsize(out_file):,} bytes",
    ]
    if dropped:
        report.append(f"   dropped extra tracks: {', '.join(dropped)}")
    return report


def _copy(src, dst, start, end):
    src.seek(start)
    left = end - start
    while left > 0:
        chunk = src.read(min(COPY_CHUNK, left))
        if not chunk:
            raise Mp4Error("Unexpected end of file.")
        dst.write(chunk)
        left -= len(chunk)
