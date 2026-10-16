"""Real-ESRGAN AI upscaling (realesrgan-ncnn-vulkan, GPU via Vulkan).

Models (chosen by measurement on real TikTok frames, see README):
  real  - realesrgan-x4plus, then blended 60 % AI / 40 % Lanczos. Pure GAN
          output makes skin look plastic; the blend scored higher PSNR than
          either alone (30.7 vs 30.0 Lanczos / 29.2 AI) with 89 % of the
          original detail (Lanczos: 74 %).
  anime - realesr-animevideov3 (x2/x3/x4), unblended. Fast, made for video,
          best for anime / cartoons / stylised games; too painterly for faces.
"""

import os
import shutil
import subprocess
import sys
import time

from .encode import NO_WINDOW, app_dir
from .mp4 import Mp4Error

MODELS = {
    "real": {"name": "realesrgan-x4plus", "scales": (4,), "blend": 0.6},
    "anime": {"name": "realesr-animevideov3", "scales": (2, 3, 4), "blend": 1.0},
}
CHUNK = 60  # frames per batch, keeps temporary 4x frames small on disk


def find_esrgan():
    exe = "realesrgan-ncnn-vulkan" + (".exe" if sys.platform == "win32" else "")
    for base in (os.path.join(app_dir(), "esrgan"), app_dir()):
        path = os.path.join(base, exe)
        if os.path.isfile(path) and os.path.isdir(os.path.join(base, "models")):
            return path
    return shutil.which("realesrgan-ncnn-vulkan")


def pick_scale(model, need):
    """Smallest model scale that reaches the needed factor."""
    scales = MODELS[model]["scales"]
    return next((s for s in scales if s >= need), scales[-1])


def _count(folder):
    try:
        return sum(1 for n in os.listdir(folder) if n.endswith(".png"))
    except OSError:
        return 0


def upscale_dir(ffmpeg, in_dir, out_dir, model, need, size, progress=None, cancel=None, log=None):
    """Upscale every %08d.png in in_dir into out_dir at exactly size=(w, h).

    Works in batches: AI-upscale a batch, blend/resize it to the final size
    with FFmpeg, delete the large intermediate frames, continue."""
    exe = find_esrgan()
    if not exe:
        raise Mp4Error("Real-ESRGAN not found - it is included in the installer version.")
    spec = MODELS[model]
    scale = pick_scale(model, need)
    frames = sorted(n for n in os.listdir(in_dir) if n.endswith(".png"))
    if not frames:
        raise Mp4Error("No frames to upscale.")
    w, h = size
    blend = spec["blend"]
    if log:
        log(f"   AI upscale: {spec['name']} x{scale} -> {w}x{h}"
            + (f", blended {int(blend * 100)}% AI" if blend < 1 else "") + f", {len(frames)} frames")
    os.makedirs(out_dir, exist_ok=True)
    batch_in, batch_up = os.path.join(out_dir, "_in"), os.path.join(out_dir, "_up")
    started, done = time.time(), 0
    for first in range(0, len(frames), CHUNK):
        if cancel and cancel():
            raise Mp4Error("Cancelled.")
        part = frames[first:first + CHUNK]
        for d in (batch_in, batch_up):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
        for name in part:
            os.replace(os.path.join(in_dir, name), os.path.join(batch_in, name))
        _run_esrgan(exe, batch_in, batch_up, spec["name"], scale, len(part), cancel,
                    lambda c: progress and progress((done + c) / len(frames) * 0.9))
        start_no = int(part[0][:8])
        ai = ["-start_number", str(start_no), "-i", os.path.join(batch_up, "%08d.png")]
        if blend < 1:
            graph = (f"[0:v]scale={w}:{h}:flags=lanczos[a];[1:v]scale={w}:{h}:flags=lanczos[b];"
                     f"[a][b]blend=all_expr='A*{blend}+B*{1 - blend:.2f}',format=rgb24[v]")
            inputs = ai + ["-start_number", str(start_no), "-i", os.path.join(batch_in, "%08d.png")]
        else:
            graph = f"[0:v]scale={w}:{h}:flags=lanczos,format=rgb24[v]"
            inputs = ai
        r = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *inputs,
                            "-filter_complex", graph, "-map", "[v]", "-frames:v", str(len(part)),
                            "-start_number", str(start_no), "-compression_level", "1",
                            os.path.join(out_dir, "%08d.png")],
                           capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW)
        if r.returncode != 0:
            raise Mp4Error("Resizing upscaled frames failed:\n" + r.stderr.strip()[-600:])
        done += len(part)
        if progress:
            progress(done / len(frames))
        if log and first == 0 and len(frames) > CHUNK:
            rate = done / max(0.1, time.time() - started)
            log(f"   AI upscale speed ~{rate:.1f} frames/s, about {(len(frames) - done) / rate / 60:.1f} min left")
    for d in (batch_in, batch_up):
        shutil.rmtree(d, ignore_errors=True)
    return out_dir


def _run_esrgan(exe, in_dir, out_dir, model, scale, total, cancel, progress):
    from . import gputool
    cmd = [exe, "-i", in_dir, "-o", out_dir, "-n", model, "-s", str(scale), "-f", "png"]
    code, err = gputool.run(cmd, out_dir, total, lambda f: progress(f * total), cancel, cwd=os.path.dirname(exe))
    if code != 0 or _count(out_dir) < total:
        raise Mp4Error("Real-ESRGAN failed (update your GPU driver, or turn AI upscale off):\n" + err)
