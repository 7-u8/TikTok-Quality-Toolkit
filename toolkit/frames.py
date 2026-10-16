"""Streaming pipeline for the GPU AI steps (Real-ESRGAN upscale, RIFE frames).

  FFmpeg decoder --raw frames--> chunk of PNGs --Real-ESRGAN--> final size
      --RIFE (with one frame of look-ahead)--> FFmpeg encoder (stdin pipe)

Only one chunk lives on disk at a time, so a 4K / 120 fps export needs a
couple of GB of temporary space instead of tens of GB, whatever the length.
"""

import math
import os
import shutil
import subprocess
import tempfile
from fractions import Fraction

from .color import color_filter
from .encode import NO_WINDOW, trim_args
from .mp4 import Mp4Error

PNG_BYTES_PER_PIXEL = 1.6
CHUNK_BUDGET = 1.2e9  # bytes of temporary PNGs per chunk


def target_size(width, height, short_side):
    """Scale (w, h) so the short side equals short_side, keeping aspect (even numbers)."""
    s = short_side / min(width, height)
    return max(2, round(width * s / 2) * 2), max(2, round(height * s / 2) * 2)


def _chunk_size(w, h, out_w, out_h, upscale_factor, ratio):
    per_frame = PNG_BYTES_PER_PIXEL * (w * h + w * h * upscale_factor ** 2 + out_w * out_h * (1 + ratio))
    k = int(CHUNK_BUDGET // max(per_frame, 1))
    k = max(4, min(48, k))
    # make (k + 1) * ratio a whole number when the ratio allows it (2x, 4x, 2.5x ...)
    den = Fraction(ratio).limit_denominator(12).denominator
    return max(den - 1, (k + 1) // den * den - 1)


def _tail(f):
    f.seek(0, os.SEEK_END)
    f.seek(max(0, f.tell() - 3000))
    return f.read().decode("utf-8", "replace").strip()[-600:]


def stream_encode(ffmpeg, in_file, info, cinfo, fps, encoder_cmd, start=None, end=None, upscale=None,
                  ai_interp=False, work_dir=None, progress=None, cancel=None, log=None):
    """Decode -> AI steps -> encoder_cmd (which reads PNGs from stdin).

    upscale: None or (model, short_side). Returns nothing; raises Mp4Error."""
    from PIL import Image

    src_fps = info.get("fps")
    if not src_fps:
        raise Mp4Error("Could not read the source frame rate.")
    if ai_interp and fps <= src_fps * 1.01:
        raise Mp4Error(f"AI interpolation needs a target FPS above the source ({src_fps:.2f} fps).")
    w, h = info.get("width") or 0, info.get("height") or 0
    if not w or not h:
        raise Mp4Error("Could not read the video size.")
    duration = info.get("duration") or 0
    if duration:
        duration = max(0.1, min(duration, end or duration) - (start or 0))
    n_src = max(1, int(duration * src_fps))

    out_w, out_h, factor = w, h, 1
    if upscale:
        from .esrgan import pick_scale
        out_w, out_h = target_size(w, h, upscale[1])
        factor = pick_scale(upscale[0], out_w / w)
    ratio = fps / src_fps if ai_interp else 1.0
    chunk = _chunk_size(w, h, out_w, out_h, factor, ratio)

    tmp = tempfile.mkdtemp(prefix="tt_stream_", dir=work_dir)
    need = PNG_BYTES_PER_PIXEL * (chunk + 1) * (w * h + w * h * factor ** 2 + out_w * out_h * (2 + ratio))
    free = shutil.disk_usage(tmp).free
    if need * 1.5 > free:
        shutil.rmtree(tmp, ignore_errors=True)
        raise Mp4Error(f"Not enough disk space: the AI steps need about {need * 1.5 / 1e9:.1f} GB "
                       f"of temporary space and {free / 1e9:.1f} GB is free.")
    if log:
        log(f"   AI pipeline: {w}x{h} -> {out_w}x{out_h}, {src_fps:.2f} -> {fps:g} fps, "
            f"{chunk} frames per chunk")

    vf = []
    if cinfo is not None:
        cf = color_filter(cinfo, tmp)
        if cf:
            vf.append(cf)
    # Always state the BT.709 matrix: without it swscale turns YUV into RGB with BT.601, and the
    # frames come back from the AI tools green-shifted and over-saturated once encoded as BT.709.
    vf.append("scale=in_color_matrix=bt709:in_range=tv")
    vf += [f"fps={src_fps:.6f}", f"scale={w}:{h}", "format=rgb24"]
    dec_cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error"] + trim_args(start, end) + [
        "-i", in_file, "-map", "0:v:0", "-vf", ",".join(vf), "-fps_mode", "cfr",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]

    dec_err, enc_err = tempfile.TemporaryFile(), tempfile.TemporaryFile()
    dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE, stderr=dec_err, cwd=tmp, creationflags=NO_WINDOW)
    enc = subprocess.Popen(encoder_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=enc_err,
                           cwd=tmp, creationflags=NO_WINDOW)
    frame_bytes = w * h * 3
    counter = {"src": 0, "name": 0, "fed": 0}
    pending = os.path.join(tmp, "pending")  # final-size frames waiting for RIFE
    os.makedirs(pending)

    def feed(paths):
        for p in paths:
            with open(p, "rb") as f:
                enc.stdin.write(f.read())
            os.remove(p)
            counter["fed"] += 1

    def next_name():
        counter["name"] += 1
        return f"{counter['name']:08d}.png"

    try:
        while True:
            if cancel and cancel():
                raise Mp4Error("Cancelled.")
            batch = os.path.join(tmp, "batch")
            shutil.rmtree(batch, ignore_errors=True)
            os.makedirs(batch)
            got = 0
            while got < chunk:
                data = dec.stdout.read(frame_bytes)
                if len(data) < frame_bytes:
                    break
                Image.frombuffer("RGB", (w, h), data, "raw", "RGB", 0, 1).save(
                    os.path.join(batch, next_name()), compress_level=1)
                got += 1
            at_end = got < chunk
            counter["src"] += got

            ready = batch
            if got and upscale:
                from .esrgan import upscale_dir
                up = os.path.join(tmp, "up")
                shutil.rmtree(up, ignore_errors=True)
                upscale_dir(ffmpeg, batch, up, upscale[0], out_w / w, (out_w, out_h), cancel=cancel,
                            log=log if counter["src"] == got else None)
                ready = up
            new = sorted(os.path.join(ready, n) for n in os.listdir(ready) if n.endswith(".png"))

            if ai_interp:
                for p in new:
                    os.replace(p, os.path.join(pending, os.path.basename(p)))
                frames = sorted(os.path.join(pending, n) for n in os.listdir(pending) if n.endswith(".png"))
                if frames and (at_end or len(frames) > 1):
                    _interpolate_segment(frames, ratio, at_end, tmp, feed, cancel)
            else:
                feed(new)

            if progress:
                progress(min(1.0, counter["src"] / n_src))
            if at_end:
                break

        enc.stdin.close()
        if enc.wait() != 0:
            raise Mp4Error("FFmpeg encoding failed:\n" + _tail(enc_err))
        dec.wait()
        if counter["src"] == 0:
            raise Mp4Error("No frames could be decoded:\n" + _tail(dec_err))
        if log:
            log(f"   AI pipeline: {counter['src']} source frames -> {counter['fed']} output frames")
    except BrokenPipeError:
        enc.wait()
        raise Mp4Error("FFmpeg encoding failed:\n" + _tail(enc_err))
    finally:
        for proc in (dec, enc):
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        if dec.stdout:
            dec.stdout.close()
        dec_err.close()
        enc_err.close()
        shutil.rmtree(tmp, ignore_errors=True)
    return fps if ai_interp else src_fps


def _interpolate_segment(frames, ratio, at_end, tmp, feed, cancel):
    """RIFE over frames; the last frame is look-ahead (kept for the next chunk)
    unless this is the end of the video."""
    from .rife import interpolate_dir
    seg_in, seg_out = os.path.join(tmp, "seg_in"), os.path.join(tmp, "seg_out")
    for d in (seg_in, seg_out):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    keep = None if at_end else frames[-1]
    for i, p in enumerate(frames, 1):
        dst = os.path.join(seg_in, f"{i:08d}.png")
        if p == keep:
            shutil.copyfile(p, dst)
        else:
            os.replace(p, dst)
    n_in = len(frames)
    if n_in == 1:  # a single last frame: nothing to interpolate, repeat it
        src = os.path.join(seg_in, "00000001.png")
        copies = max(1, round(ratio))
        outs = []
        for i in range(copies):
            dst = os.path.join(seg_out, f"{i + 1:08d}.png")
            shutil.copyfile(src, dst)
            outs.append(dst)
        feed(outs)
        return
    emit = (n_in if at_end else n_in - 1) * ratio
    n_out = max(n_in + 1, math.ceil(n_in * ratio))
    interpolate_dir(seg_in, seg_out, n_out / n_in, cancel=cancel)
    outs = sorted(os.path.join(seg_out, n) for n in os.listdir(seg_out) if n.endswith(".png"))
    feed(outs[:max(1, round(emit))])
    for p in outs[round(emit):]:
        os.remove(p)
