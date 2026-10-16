"""FPS patch: rewrite mvhd/mdhd timing so TikTok's transcoder keeps the frames.

Two modes:

* "method"  - the community "120 FPS method" (ut0ku/120fps-method,
  EditingNews EN-TikTok-60FPS): timescale AND duration are scaled by
  target/source (60 fps -> /2, 120 fps -> /4). The declared length stays the
  same, the declared frame rate drops to the target. Plays normally on phones.
* "slowmo"  - timescale only: the clip becomes a real slow-motion clip
  (2x longer for 60 -> 30). Speed it back up inside TikTok's editor.

Only the header fields are touched; video/audio data is copied untouched.
"""

import os
import shutil
import struct
from fractions import Fraction

from .mp4 import Mp4Error, Mp4File, header_fields, u32, u64

MODES = ("method", "slowmo")


def exact_fps(fps):
    """Turn 59.94 / 29.97 / 23.976 style values into exact NTSC fractions."""
    fps = float(fps)
    for base in (24, 30, 48, 60, 90, 120, 144, 240):
        ntsc = Fraction(base * 1000, 1001)
        if abs(fps - float(ntsc)) < 0.01:
            return ntsc
    return Fraction(fps).limit_denominator(1001)


def detect_fps(path):
    v = Mp4File(path).video
    return v.fps if v else None


def plan_patches(mp4, scale, mode="method", include_audio=True):
    """Return [(abs_offset, byte_size, old, new, label)]."""
    if mode not in MODES:
        raise Mp4Error(f"Unknown mode '{mode}'.")
    if mp4.video is None:
        raise Mp4Error("No video track found in the MP4.")
    buf, base = mp4.buf, mp4.moov_offset
    patches = []

    def add_header(box, label):
        ts_off, dur_off, dsz = header_fields(buf, box)
        old_ts = u32(buf, ts_off)
        new_ts = round(old_ts * scale)
        if not 1 <= new_ts <= 0xFFFFFFFF:
            raise Mp4Error(f"Timescale {old_ts} of {label} cannot be scaled.")
        patches.append((base + ts_off, 4, old_ts, new_ts, f"{label} timescale"))
        if mode == "method":
            old_d = u32(buf, dur_off) if dsz == 4 else u64(buf, dur_off)
            new_d = round(old_d * scale)
            if new_d >= 1 << (8 * dsz):
                raise Mp4Error(f"Duration of {label} cannot be scaled.")
            patches.append((base + dur_off, dsz, old_d, new_d, f"{label} duration"))

    add_header(mp4.mvhd, "movie (mvhd)")
    for i, t in enumerate(mp4.tracks, 1):
        if t.handler == "vide" or include_audio:
            add_header(t.mdhd, f"track {i} [{t.handler}] (mdhd)")

    if mode == "slowmo":
        # Fragmented files: segment indexes carry their own timescale.
        with open(mp4.path, "rb") as f:
            for b in mp4.top:
                if b.type == "sidx":
                    off = b.body + 8  # version/flags(4) reference_ID(4)
                    f.seek(off)
                    old = struct.unpack(">I", f.read(4))[0]
                    patches.append((off, 4, old, max(1, round(old * scale)), "segment index (sidx) timescale"))
    return patches


def patch_fps(in_file, out_file, fps_in=None, fps_out=30, mode="method", include_audio=True):
    """Write a patched copy of in_file. Returns a list of report lines."""
    if os.path.abspath(in_file) == os.path.abspath(out_file):
        raise Mp4Error("Output file must be different from the input file.")
    mp4 = Mp4File(in_file)
    if mp4.video is not None and mp4.video.already_patched:
        raise Mp4Error("This file is already patched - use the original video.")
    if fps_in is None:
        fps_in = mp4.video.fps if mp4.video else None
        if not fps_in:
            raise Mp4Error("Could not detect the source FPS - enter it manually.")
    if float(fps_in) <= float(fps_out):
        raise Mp4Error(f"Source FPS ({float(fps_in):g}) must be higher than target FPS ({float(fps_out):g}).")

    scale = exact_fps(fps_out) / exact_fps(fps_in)
    patches = plan_patches(mp4, scale, mode, include_audio)

    shutil.copyfile(in_file, out_file)
    report = [f"FPS patch ({mode}): {float(fps_in):.3f} -> {float(fps_out):g} fps, scale {float(scale):.5f}"]
    try:
        with open(out_file, "r+b") as f:
            for off, size, old, new, label in patches:
                f.seek(off)
                f.write(new.to_bytes(size, "big"))
                note = "" if old * scale == new else " (rounded)"
                report.append(f"   {label}: {old} -> {new}{note}")
    except Exception:
        _remove(out_file)
        raise
    return report


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
