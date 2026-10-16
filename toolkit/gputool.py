"""Run a frame-folder GPU tool (Real-ESRGAN / RIFE) with progress and cancel.

stderr goes to a temporary file, not a pipe: both tools print a progress
line per tile, which fills a 64 KB pipe on large frames and freezes the
process if nobody reads it while it runs.
"""

import os
import subprocess
import tempfile
import time

from .encode import NO_WINDOW
from .mp4 import Mp4Error


def count_png(folder):
    try:
        return sum(1 for n in os.listdir(folder) if n.endswith(".png"))
    except OSError:
        return 0


def run(cmd, out_dir, total, progress=None, cancel=None, cwd=None):
    """Run cmd until it exits; progress(fraction) from PNGs appearing in out_dir.

    Returns the last 600 characters of stderr."""
    with tempfile.TemporaryFile() as err:
        with subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err, cwd=cwd,
                              creationflags=NO_WINDOW) as proc:
            try:
                while proc.poll() is None:
                    if cancel and cancel():
                        raise Mp4Error("Cancelled.")
                    if progress and total:
                        progress(min(1.0, count_png(out_dir) / total))
                    time.sleep(0.4)
            except BaseException:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                raise
        err.seek(0, os.SEEK_END)
        err.seek(max(0, err.tell() - 4000))
        tail = err.read().decode("utf-8", "replace")
    return proc.returncode, tail.strip()[-600:]
