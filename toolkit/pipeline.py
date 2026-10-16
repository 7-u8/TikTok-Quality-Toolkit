"""Run the selected steps on one file: prepare -> FPS patch -> ghost frames."""

import os
import shutil
import tempfile
from dataclasses import dataclass, field, replace

from .encode import prepare, probe
from .fps_patch import patch_fps
from .ghost import DEFAULT_COMMENT, ghost_frames
from .mp4 import Mp4Error


@dataclass
class Options:
    # step 1: FFmpeg prepare
    prepare: bool = False
    prep_fps: float = 60
    prep_resolution: str = "1080"
    prep_interpolation: str = "none"
    prep_crf: int = 16
    prep_encoder: str = "auto"
    prep_enhance: str = "off"
    prep_fit: str = "none"
    prep_color: str = "auto"
    prep_upscale: str = "off"
    prep_orient: str = "vertical"   # frame shape when prep_fit reframes
    prep_supersample: int = None    # AI renders at this short side, delivered at prep_resolution
    prep_sharpen: float = 0.0       # CAS strength after the final scaling
    trim_start: float = None
    trim_end: float = None
    # step 2: FPS patch
    fps_patch: bool = True
    fps_mode: str = "method"
    source_fps: float = None  # None = auto-detect
    target_fps: float = 30
    include_audio: bool = True
    # step 3: ghost frames
    ghost: bool = False
    ghost_multiplier: int = 10
    ghost_comment: str = DEFAULT_COMMENT
    # output
    out_dir: str = None
    suffix: str = "_tiktok"
    language: str = "en"
    # simple UI choices (turned into the prep_* fields by plan.make_plan)
    out_orientation: str = "auto"
    out_quality: str = "1080"
    out_fps: str = "60"
    tiktok_trick: bool = True
    fill_style: str = "blur"
    frames_method: str = "ai"
    upscale_model: str = "real"
    sharpen: bool = True            # "Sharpen for TikTok"
    # motion blur (f0e/blur style) and colour grade
    motion_blur: bool = False
    blur_amount: float = 1.0
    blur_interp: str = "600"        # interpolated fps, or a multiplier of the input fps like "5x"
    blur_weighting: str = "equal"
    saturation: float = 1.0
    contrast: float = 1.0
    brightness: float = 1.0
    extra: dict = field(default_factory=dict)

    def grade(self):
        return (self.saturation, self.contrast, self.brightness)

    def blur_settings(self):
        if not self.motion_blur or self.blur_amount <= 0:
            return None
        return {"amount": self.blur_amount, "interp": self.blur_interp, "weighting": self.blur_weighting}

    def any_step(self):
        return self.prepare or self.fps_patch or self.ghost

    def validate(self):
        if (self.trim_start or self.trim_end) and not self.prepare:
            raise Mp4Error("Trimming needs Step 1 (Prepare) to be enabled.")
        if self.trim_start and self.trim_end and self.trim_end <= self.trim_start:
            raise Mp4Error("Trim end must be after trim start.")


def fallback_folder():
    """A folder Controlled folder access does not protect (the user profile root)."""
    d = os.path.join(os.path.expanduser("~"), "TikTok Toolkit Exports")
    os.makedirs(d, exist_ok=True)
    return d


def output_path(in_file, opts):
    root, _ = os.path.splitext(os.path.basename(in_file))
    folder = opts.out_dir or os.path.dirname(os.path.abspath(in_file))
    candidate = os.path.join(folder, f"{root}{opts.suffix}.mp4")
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{root}{opts.suffix} ({n}).mp4")
        n += 1
    return candidate


def run(in_file, opts, log=print, progress=None, cancel=None, out_file=None):
    """Process one file. Returns the output path."""
    if not opts.any_step():
        raise Mp4Error("Select at least one step.")
    opts.validate()
    if not os.path.isfile(in_file):
        raise Mp4Error(f"File not found: {in_file}")
    out_file = out_file or output_path(in_file, opts)
    if not opts.prepare or opts.prep_color == "off":
        from .color import probe_color
        if probe_color(in_file)["kind"] != "sdr":
            log("WARNING: this is an HDR video - without Step 1 + Colour fix it will look washed out on TikTok.")
    # "normalize" first turns the upload into the standard source (1080p, H.264 High, 50,000 kbps CBR, MP4);
    # every enhancement then works on that file, and the export is encoded to the same spec again.
    steps = [s for s, on in (("normalize", opts.prepare), ("prepare", opts.prepare), ("fps", opts.fps_patch),
                             ("ghost", opts.ghost)) if on]
    tmp = tempfile.mkdtemp(prefix="tiktok_toolkit_")
    try:
        current = in_file
        for i, step in enumerate(steps):
            if cancel and cancel():
                raise Mp4Error("Cancelled.")
            nxt = os.path.join(tmp, f"step{i}_{step}.mp4")
            def sub_progress(frac, i=i):
                if progress:
                    progress((i + frac) / len(steps))
            if step == "normalize":
                src_fps = probe(current)["fps"] or 30.0
                lines = prepare(
                    current, nxt, progress=sub_progress, cancel=cancel, log=log,
                    fps=round(src_fps, 3), resolution="1080", interpolation="none", encoder=opts.prep_encoder,
                    color=opts.prep_color, start=opts.trim_start, end=opts.trim_end, work_dir=tmp,
                )
                lines = ["Normalized: 1080p, H.264 High, 50,000 kbps CBR, MP4 - " + "; ".join(lines)]
            elif step == "prepare":
                lines = prepare(
                    current, nxt, progress=sub_progress, cancel=cancel, log=log,
                    fps=opts.prep_fps, resolution=opts.prep_resolution,
                    interpolation=opts.prep_interpolation, crf=opts.prep_crf,
                    encoder=opts.prep_encoder, enhance=opts.prep_enhance, fit=opts.prep_fit,
                    color="off", upscale=opts.prep_upscale, orient=opts.prep_orient,
                    sharpen=opts.prep_sharpen, grade=opts.grade(), supersample=opts.prep_supersample,
                    motion_blur=opts.blur_settings(),
                    work_dir=tmp,  # colour fix and trim were done by "normalize"
                )
            elif step == "fps":
                src_fps = opts.source_fps
                if src_fps is None and opts.prepare:
                    src_fps = opts.prep_fps
                lines = patch_fps(current, nxt, src_fps, opts.target_fps, opts.fps_mode, opts.include_audio)
            else:
                lines = ghost_frames(current, nxt, opts.ghost_multiplier, opts.ghost_comment)
            for line in lines:
                log(line)
            current = nxt
            if progress:
                progress((i + 1) / len(steps))
        try:
            shutil.move(current, out_file)
        except (PermissionError, FileNotFoundError):
            # Windows "Controlled folder access" blocks unknown apps from writing to
            # Videos / Documents / Desktop. Save to a folder it does not protect instead.
            blocked = os.path.dirname(out_file)
            fallback_dir = fallback_folder()
            out_file = output_path(in_file, replace(opts, out_dir=fallback_dir))
            try:
                shutil.move(current, out_file)
            except OSError as e:
                raise Mp4Error(f"Windows blocked saving to {blocked} and to {fallback_dir} ({e}).")
            log(f"NOTE: Windows (Controlled folder access) blocked saving to {blocked} - "
                f"saved to {fallback_dir} instead. To save next to your videos, allow 'TikTok Quality Toolkit' in "
                "Windows Security > Virus & threat protection > Ransomware protection.")
        return out_file
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
