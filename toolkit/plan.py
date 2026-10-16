"""Turn the simple choices (orientation / quality / frame rate) into a run plan.

The UI only asks three things. Everything else - whether to re-encode,
which AI step to use, whether to reframe - is decided here from the
source video, so the same logic is testable without the GUI.
"""

import os
import subprocess
from dataclasses import replace

from . import motionblur
from .color import needs_fix, probe_color
from .encode import NO_WINDOW, find_rife, find_tool, probe
from .esrgan import find_esrgan

QUALITIES = ("original", "1080", "1440", "2160")
FRAME_RATES = ("original", "30", "60", "120")
ORIENTATIONS = ("vertical", "horizontal")
QUALITY_NAMES = {720: "720p", 1080: "1080p", 1440: "2K", 2160: "4K"}
# Throughput measured on an RTX 5060 Ti (megapixels per second); used for a rough time estimate.
SPEED = {"real": 0.36, "anime": 6.7, "rife": 55.0, "encode": 400.0}


TIKTOK_MAX = 1080  # TikTok downscales anything with a short side above this
SHARPEN = 0.35         # CAS strength for "Sharpen for TikTok"
SHARPEN_SUPER = 0.5    # after a supersampled (AI 2K/4K -> 1080p) render


def ai_frame_rate(src, run):
    """Frame rate RIFE has to produce (None when RIFE is not used)."""
    src_fps = src["fps"] or 30.0
    blur = run.blur_settings()
    if blur:
        ifps, _, _ = motionblur.plan(src_fps, float(run.prep_fps), blur["interp"], blur["amount"])
        return ifps if src_fps < ifps * 0.9 else None
    return float(run.prep_fps) if run.prep_interpolation == "ai" else None


def estimate_seconds(src, run):
    """Rough processing time for the AI steps (None when there are none)."""
    rife_fps = ai_frame_rate(src, run)
    if not run.prepare or (run.prep_upscale == "off" and rife_fps is None):
        return None
    duration = src["duration"] or 0
    if run.trim_start or run.trim_end:
        duration = min(duration, run.trim_end or duration) - (run.trim_start or 0)
    frames_in = max(1.0, duration * (src["fps"] or 30))
    mp_in = src["width"] * src["height"] / 1e6
    short = max(1, src["short"])
    ai_short = run.prep_supersample or int(run.prep_resolution)
    mp_ai = mp_in * (ai_short / short) ** 2 if run.prep_upscale != "off" else mp_in
    mp_out = mp_in * (int(run.prep_resolution) / short) ** 2
    secs = duration * float(run.prep_fps) * mp_out / SPEED["encode"]
    if run.prep_upscale != "off":
        secs += frames_in * mp_in / SPEED[run.prep_upscale]
    if rife_fps:
        secs += duration * rife_fps * mp_ai / SPEED["rife"]
    return secs * 1.7 + 5  # frame I/O between the AI steps (measured: 4 s clip, 1080p -> 2K/60 took 94 s)


def quality_name(short):
    return QUALITY_NAMES.get(int(short), f"{int(short)}p")


def analyze(path):
    """Everything the planner needs to know about a source video."""
    info = probe(path)
    w, h = info.get("width") or 0, info.get("height") or 0
    out = {
        "path": path, "width": w, "height": h, "fps": info.get("fps") or 0.0,
        "duration": info.get("duration") or 0.0, "codec": None, "vfr": False,
        "orientation": "vertical" if h >= w else "horizontal",
        "short": min(w, h) if w and h else 0, "colour": probe_color(path),
    }
    ffprobe = find_tool("ffprobe")
    if ffprobe:
        try:
            r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=codec_name,r_frame_rate,avg_frame_rate", "-of", "csv=p=0", path],
                               capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
            codec, rfr, afr = (r.stdout.strip().splitlines() or [""])[0].split(",")[:3]
            out["codec"] = codec

            def rate(v):
                n, _, d = v.partition("/")
                return float(n) / float(d) if d and float(d) else 0.0
            a, b = rate(rfr), rate(afr)
            out["vfr"] = bool(a and b and abs(a - b) / a > 0.02)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    return out


def make_plan(src, o):
    """Return (Options to run, list of (message key, params) describing the plan)."""
    src_fps = src["fps"] or 30.0
    short = src["short"] or 1080
    orient = src["orientation"] if o.out_orientation not in ORIENTATIONS else o.out_orientation
    tgt_short = short if o.out_quality == "original" else int(o.out_quality)
    tgt_fps = round(src_fps, 3) if o.out_fps == "original" else int(o.out_fps)

    # The upload is always 1080p: TikTok downscales anything above it (it showed "1440" and
    # lost quality), so 2K / 4K are rendered by the AI at that size and delivered at 1080p,
    # and smaller sources are brought up to 1080p.
    deliver = TIKTOK_MAX
    supersample = tgt_short if tgt_short > TIKTOK_MAX else None
    upscale = "off"
    if find_esrgan() and short * 1.1 < (supersample or deliver):
        upscale = o.upscale_model if o.upscale_model in ("real", "anime") else "off"
    if upscale == "off":
        supersample = None

    reframe = orient != src["orientation"]
    blur = o.motion_blur and o.blur_amount > 0 and find_rife()[0] is not None
    more_frames = tgt_fps > src_fps + 0.5
    fewer_frames = tgt_fps < src_fps - 0.5
    colour = o.prep_color == "auto" and needs_fix(src["colour"])
    hdr = o.prep_color == "auto" and src["colour"]["kind"] != "sdr"
    graded = any(abs(v - 1) > 1e-3 for v in o.grade())

    # Always re-encoded to the upload spec: MP4 + H.264, 1080p, 50,000 kbps CBR.
    prepare = True

    method = o.frames_method
    if method == "ai" and not find_rife()[0]:
        method = "motion"
    trick = o.tiktok_trick and tgt_fps > 31
    sharpen = (SHARPEN_SUPER if supersample else SHARPEN) if o.sharpen else 0.0

    run = replace(
        o,
        prepare=prepare,
        prep_fps=tgt_fps,
        prep_resolution=str(deliver),
        prep_supersample=supersample,
        prep_sharpen=sharpen,
        prep_interpolation=method if (more_frames and not blur) else "none",
        prep_upscale=upscale,
        prep_fit=o.fill_style if reframe else "none",
        prep_orient=orient,
        motion_blur=blur,
        fps_patch=trick,
        source_fps=tgt_fps if prepare else None,
    )

    steps = [("pl_normalize", {})]
    if hdr:
        steps.append(("pl_hdr", {}))
    elif colour:
        steps.append(("pl_colour", {}))
    a = quality_name(short)
    if supersample:
        steps.append(("pl_size_super", {"a": a, "b": quality_name(supersample)}))
    elif tgt_short > TIKTOK_MAX:
        steps.append(("pl_size_cap", {"a": a}))
    elif deliver > short + 2:
        steps.append(("pl_size_ai" if upscale != "off" else "pl_size_up", {"a": a, "b": quality_name(deliver)}))
    elif deliver < short - 2:
        steps.append(("pl_size_down", {"a": a, "b": quality_name(deliver)}))
    else:
        steps.append(("pl_size_same", {"a": a}))
    fa, fb = f"{src_fps:.0f}", f"{tgt_fps:g}"
    if blur:
        ifps, _, nframes = motionblur.plan(src_fps, tgt_fps, o.blur_interp, o.blur_amount)
        steps.append(("pl_blur", {"a": f"{o.blur_amount:g}", "i": f"{ifps:g}", "b": fb}))
    elif more_frames:
        steps.append(({"ai": "pl_fps_ai", "motion": "pl_fps_motion"}.get(method, "pl_fps_blend"), {"a": fa, "b": fb}))
    elif fewer_frames:
        steps.append(("pl_fps_down", {"a": fa, "b": fb}))
    else:
        steps.append(("pl_fps_same", {"a": fa}))
    if reframe:
        steps.append(("pl_reframe_" + o.fill_style, {"o": orient}))
    if sharpen:
        steps.append(("pl_sharpen", {}))
    if graded:
        s, c, b = o.grade()
        steps.append(("pl_grade_vals", {"s": f"{s:g}", "c": f"{c:g}", "b": f"{b:g}"}))
    if o.prep_enhance != "off":
        steps.append(("pl_enhance", {"e": o.prep_enhance}))
    if trick:
        steps.append(("pl_trick", {"b": fb}))
    elif o.tiktok_trick:
        steps.append(("pl_trick_na", {}))
    if o.ghost:
        steps.append(("pl_ghost", {}))
    # warnings about choices that usually make TikTok output worse
    if reframe and o.fill_style == "blur" and src["orientation"] == "horizontal":
        steps.append(("pl_warn_small", {}))
    if any(abs(v - 1) > 0.1 for v in o.grade()):
        steps.append(("pl_warn_grade", {}))
    if blur and tgt_fps > 60:
        steps.append(("pl_warn_blur_hfr", {"b": fb}))
    if not blur and tgt_fps >= src_fps * 3.5:
        steps.append(("pl_warn_fps", {"a": fa, "b": fb}))
    steps.append(("pl_spec", {}))
    secs = estimate_seconds(src, run)
    if secs is not None:
        steps.append(("pl_time", {"m": max(1, round(secs / 60))}) if secs >= 60 else ("pl_time_short", {}))
    return run, steps
