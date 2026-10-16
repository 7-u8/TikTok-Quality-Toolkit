"""Before/after preview of the Prepare step: a short side-by-side clip."""

import os
import tempfile

from .encode import find_tool, prepare, probe, run_ffmpeg
from .mp4 import Mp4Error

PREVIEW_SECONDS = 6


def make_preview(in_file, opts, progress=None, cancel=None, log=None):
    """Render a few seconds with the Prepare settings and stack them next to
    the original (left = before, right = after). Returns the preview path."""
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        raise Mp4Error("FFmpeg not found.")
    info = probe(in_file)
    duration = info["duration"] or PREVIEW_SECONDS
    start = opts.trim_start if opts.trim_start is not None else max(0.0, min(duration * 0.25, duration - PREVIEW_SECONDS))
    end = min(start + PREVIEW_SECONDS, opts.trim_end or duration, duration)
    if end <= start:
        raise Mp4Error("Nothing to preview in the selected range.")

    folder = os.path.join(tempfile.gettempdir(), "TikTokToolkit")
    os.makedirs(folder, exist_ok=True)
    after = os.path.join(folder, "preview_after.mp4")
    out = os.path.join(folder, "preview_before_after.mp4")
    prepare(in_file, after, progress=lambda f: progress and progress(f * 0.8), cancel=cancel, log=log,
            fps=opts.prep_fps, resolution=opts.prep_resolution, interpolation=opts.prep_interpolation,
            crf=opts.prep_crf, encoder=opts.prep_encoder, enhance=opts.prep_enhance, fit=opts.prep_fit,
            color=opts.prep_color, upscale=opts.prep_upscale, orient=opts.prep_orient,
            sharpen=opts.prep_sharpen, grade=opts.grade(), supersample=opts.prep_supersample,
            motion_blur=opts.blur_settings(), start=start, end=end)
    height = 960
    graph = (f"[0:v]fps={opts.prep_fps},scale=-2:{height}:flags=lanczos,setsar=1[a];"
             f"[1:v]scale=-2:{height}:flags=lanczos,setsar=1[b];[a][b]hstack=inputs=2[v]")
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", in_file,
           "-i", after, "-filter_complex", graph, "-map", "[v]", "-map", "1:a:0?",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", "-progress", "pipe:1", "-nostats", "-loglevel", "error", out]
    run_ffmpeg(cmd, end - start, lambda f: progress and progress(0.8 + f * 0.2), cancel, out)
    try:
        os.remove(after)
    except OSError:
        pass
    return out
