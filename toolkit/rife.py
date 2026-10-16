"""RIFE AI frame interpolation via rife-ncnn-vulkan (GPU, Vulkan)."""

import os

from . import gputool
from .encode import find_rife
from .mp4 import Mp4Error


def _count(folder):
    try:
        return sum(1 for n in os.listdir(folder) if n.endswith(".png"))
    except OSError:
        return 0


def interpolate_dir(in_dir, out_dir, ratio, progress=None, cancel=None, log=None, label=""):
    """Write len(in)*ratio frames (%08d.png) into out_dir."""
    exe, model = find_rife()
    if not exe or not model:
        raise Mp4Error("RIFE (rife-ncnn-vulkan) not found - it is included in the installer version, "
                       "or choose another interpolation.")
    n_in = _count(in_dir)
    if n_in < 2:
        raise Mp4Error("Not enough frames to interpolate.")
    n_out = max(n_in + 1, round(n_in * ratio))
    if log:
        log(f"   RIFE AI: {n_in} -> {n_out} frames{label} ({os.path.basename(model)})")
    os.makedirs(out_dir, exist_ok=True)
    cmd = [exe, "-i", in_dir, "-o", out_dir, "-m", model, "-n", str(n_out), "-f", "%08d.png"]
    code, err = gputool.run(cmd, out_dir, n_out, progress, cancel, cwd=os.path.dirname(exe))
    if code != 0 or _count(out_dir) < n_out * 0.95:
        raise Mp4Error("RIFE failed (update your GPU driver, or choose another interpolation):\n" + err)
    return out_dir
