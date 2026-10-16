"""Prepare step: re-encode with FFmpeg into a TikTok-friendly source.

H.264 High / yuv420p, constant frame rate, optional frame interpolation
(blend, motion-compensated, or RIFE AI), optional enhance filter, optional
9:16 framing, optional trim, CPU or GPU encoder. The result is always valid
input for the FPS patch and the ghost-frame transform.
"""

import os
import shutil
import subprocess
import sys

from .mp4 import Mp4Error

INTERPOLATION = ("none", "blend", "motion", "ai")
RESOLUTIONS = ("1080", "1440", "2160", "keep")
ENCODERS = ("auto", "cpu", "nvidia", "amd", "intel")
ENHANCE = ("off", "light", "strong")
FIT = ("none", "blur", "crop")
COLOR = ("auto", "off")
UPSCALE = ("off", "real", "anime")
# BT.709 / limited range tags written on every output (TikTok reads them)
COLOR_TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]

_ENCODER_CODECS = {"nvidia": "h264_nvenc", "amd": "h264_amf", "intel": "h264_qsv", "cpu": "libx264"}
# gentle denoise: stronger temporal settings smeared game textures into a "painted" look
_ENHANCE_PRE = {"light": "hqdn3d=1:1:2:2", "strong": "hqdn3d=1.5:1.5:3:3"}
# unsharp luma amount keeps the kernel normalised, so brightness is unchanged
_ENHANCE_POST = {
    "light": "unsharp=5:5:0.5:5:5:0.0,eq=contrast=1.03:saturation=1.10",
    "strong": "unsharp=5:5:0.9:5:5:0.0,eq=contrast=1.06:saturation=1.22",
}

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


# ----------------------------------------------------------------- tools


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_tool(name):
    """Locate ffmpeg/ffprobe: bundled next to the app, PATH, common folders."""
    exe = name + (".exe" if sys.platform == "win32" else "")
    here = app_dir()
    candidates = [os.path.join(here, "ffmpeg", exe), os.path.join(here, exe),
                  os.path.join(here, "ffmpeg", "bin", exe)]
    found = shutil.which(name)
    if found:
        candidates.append(found)
    if sys.platform == "win32":
        for base in (r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin", r"C:\msys64\ucrt64\bin"):
            candidates.append(os.path.join(base, exe))
    for c in candidates:
        if c and os.path.isfile(c) and _usable(name, c):
            return c
    return None


def find_rife():
    """Return (exe, model_dir) for rife-ncnn-vulkan, or (None, None)."""
    exe = "rife-ncnn-vulkan" + (".exe" if sys.platform == "win32" else "")
    for base in (os.path.join(app_dir(), "rife"), app_dir()):
        path = os.path.join(base, exe)
        if os.path.isfile(path):
            for model in ("rife-v4.6", "rife-v4"):
                if os.path.isdir(os.path.join(base, model)):
                    return path, os.path.join(base, model)
    found = shutil.which("rife-ncnn-vulkan")
    if found:
        model = os.path.join(os.path.dirname(found), "rife-v4.6")
        return found, model if os.path.isdir(model) else None
    return None, None


_checked = {}


def _usable(name, path):
    """Reject wrappers/stubs: must answer -version, ffmpeg must have libx264."""
    if path not in _checked:
        try:
            args = [path, "-hide_banner", "-encoders"] if name == "ffmpeg" else [path, "-hide_banner", "-version"]
            r = subprocess.run(args, capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW)
            out = r.stdout + r.stderr
            _checked[path] = r.returncode == 0 and ("libx264" in out if name == "ffmpeg" else "version" in out)
        except (OSError, subprocess.TimeoutExpired):
            _checked[path] = False
    return _checked[path]


_encoder_ok = {}


def encoder_works(ffmpeg, encoder):
    """Encoders are listed even without the hardware, so try a real encode."""
    codec = _ENCODER_CODECS[encoder]
    if codec not in _encoder_ok:
        try:
            r = subprocess.run(
                [ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=s=320x240:r=30:d=0.2",
                 "-pix_fmt", "yuv420p", "-c:v", codec, "-f", "null", "-"],
                capture_output=True, timeout=30, creationflags=NO_WINDOW)
            _encoder_ok[codec] = r.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _encoder_ok[codec] = False
    return _encoder_ok[codec]


def pick_encoder(ffmpeg, choice="auto"):
    if choice == "auto":
        for enc in ("nvidia", "amd", "intel"):
            if encoder_works(ffmpeg, enc):
                return enc
        return "cpu"
    if choice != "cpu" and not encoder_works(ffmpeg, choice):
        raise Mp4Error(f"The {choice} GPU encoder is not available on this PC - choose Auto or CPU.")
    return choice


def available_encoders():
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        return []
    return ["cpu"] + [e for e in ("nvidia", "amd", "intel") if encoder_works(ffmpeg, e)]


# ------------------------------------------------------------ arguments


def parse_time(text):
    """'90', '1:30', '0:01:30.5' -> seconds (float). Empty -> None."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        parts = [float(p) for p in text.split(":")]
    except ValueError:
        raise Mp4Error(f"Invalid time '{text}' - use seconds or mm:ss.")
    if len(parts) > 3 or any(p < 0 for p in parts):
        raise Mp4Error(f"Invalid time '{text}' - use seconds or mm:ss.")
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def trim_args(start=None, end=None):
    args = []
    if start:
        args += ["-ss", f"{start:.3f}"]
    if end:
        if start and end <= start:
            raise Mp4Error("Trim end must be after trim start.")
        args += ["-to", f"{end:.3f}"]
    return args


# The upload spec people use for TikTok: H.264 in MP4, 1080p, 50,000 kbps constant bitrate (CBR).
UPLOAD_KBPS = 50000
# colour grade limits: beyond these TikTok's processing blows colours out
# (saturation 1.65 turned a green-lit map neon green)
GRADE_MIN, GRADE_MAX = 0.7, 1.3


def encoder_args(encoder, crf, fps, kbps=UPLOAD_KBPS):
    """H.264 High at a constant bitrate (crf is kept for the call signature; CBR ignores it)."""
    gop = max(1, int(round(float(fps))))
    cbr = ["-b:v", f"{kbps}k", "-minrate", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{kbps}k"]
    if encoder == "nvidia":
        v = ["-c:v", "h264_nvenc", "-profile:v", "high", "-preset", "p6", "-tune", "hq",
             "-rc", "cbr", "-spatial-aq", "1", "-bf", "2"] + cbr
    elif encoder == "amd":
        v = ["-c:v", "h264_amf", "-profile:v", "high", "-quality", "quality", "-rc", "cbr"] + cbr
    elif encoder == "intel":
        v = ["-c:v", "h264_qsv", "-profile:v", "high", "-preset", "slower"] + cbr
    else:
        v = ["-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-bf", "2",
             "-x264-params", "nal-hrd=cbr:force-cfr=1"] + cbr
    return v + ["-g", str(gop * 2)]


def video_filter(fps, resolution="1080", interpolation="none", enhance="off", fit="none", color=None,
                 orient="vertical", sharpen=0.0, grade=None, blend=None):
    """Return a -filter_complex graph from [0:v] to [v].

    blend: motion-blur filter applied before the frame-rate change.
    sharpen: CAS strength applied after the final scaling (0 = off).
    grade: (saturation, contrast, brightness) multipliers, 1 = unchanged."""
    pre = [color] if color else []
    if blend:
        pre.append(blend)
    if interpolation == "motion":
        pre.append(f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    elif interpolation == "blend":
        pre.append(f"minterpolate=fps={fps}:mi_mode=blend")
    elif interpolation == "none":
        pre.append(f"fps={fps}")
    # "ai": frames already interpolated by RIFE, nothing to do here
    if enhance in _ENHANCE_PRE:
        pre.append(_ENHANCE_PRE[enhance])
    post = []
    if sharpen and sharpen > 0:
        post.append(f"cas=strength={min(1.0, sharpen):.2f}")
    graded = grade and any(abs(v - 1) > 1e-3 for v in grade)
    if graded:
        sat, con, bri = (min(GRADE_MAX, max(GRADE_MIN, v)) for v in grade)
        # brightness as gamma: lifts the mid-tones but keeps black black and white white.
        # (eq's additive brightness=bri-1 turned 1.2 into +20% on every pixel: grey blacks, clipped highlights)
        post.append(f"eq=saturation={sat:.3f}:contrast={con:.3f}:gamma={max(0.1, bri):.3f}")
    if enhance in _ENHANCE_POST:
        # a colour grade already sets saturation/contrast; don't stack the enhance boost on top
        post.append(_ENHANCE_POST[enhance].split(",eq=")[0] if graded else _ENHANCE_POST[enhance])
    # explicit BT.709 matrix + tags (PNG frames from the AI path are RGB/sRGB-tagged)
    post += ["setsar=1", "scale=out_color_matrix=bt709:out_range=tv", "format=yuv420p",
             "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"]
    head = "[0:v]" + (",".join(pre) if pre else "null")

    if fit in ("blur", "crop"):
        s = 1080 if resolution == "keep" else int(resolution)
        long_side = (s * 16 // 9) // 2 * 2
        w, h = (s, long_side) if orient == "vertical" else (long_side, s)
        if fit == "crop":
            mid = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
            return f"{head},{mid},{','.join(post)}[v]"
        return (
            f"{head},split=2[bg][fg];"
            f"[bg]scale={w // 4}:{h // 4}:force_original_aspect_ratio=increase,crop={w // 4}:{h // 4},"
            f"gblur=sigma=12,eq=brightness=-0.06,scale={w}:{h}[bgb];"
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,{','.join(post)}[v]"
        )
    if resolution != "keep":
        s = int(resolution)
        post.insert(0, f"scale=w='if(gte(iw,ih),-2,{s})':h='if(gte(iw,ih),{s},-2)':flags=lanczos")
    return f"{head},{','.join(post)}[v]"


def build_command(ffmpeg, in_file, out_file, fps=60, resolution="1080", interpolation="none",
                  crf=16, encoder="cpu", enhance="off", fit="none", start=None, end=None,
                  frames_dir=None, frames_rate=None, color=None, orient="vertical", sharpen=0.0, grade=None,
                  blend=None, audio_bitrate="320k"):
    if interpolation not in INTERPOLATION:
        raise Mp4Error(f"Unknown interpolation '{interpolation}'.")
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y"]
    if frames_dir == "-":  # AI output streamed as PNGs on stdin + audio from the original
        cmd += ["-f", "image2pipe", "-c:v", "png", "-framerate", f"{frames_rate or fps:.6f}", "-i", "-"]
        cmd += trim_args(start, end) + ["-i", in_file, "-map", "[v]", "-map", "1:a:0?"]
    elif frames_dir:  # AI output: image sequence + audio from the original
        cmd += ["-framerate", f"{frames_rate or fps:.6f}", "-i", os.path.join(frames_dir, "%08d.png")]
        cmd += trim_args(start, end) + ["-i", in_file, "-map", "[v]", "-map", "1:a:0?"]
    else:
        cmd += trim_args(start, end) + ["-i", in_file, "-map", "[v]", "-map", "0:a:0?"]
    cmd += ["-filter_complex", video_filter(fps, resolution, interpolation, enhance, fit, color, orient,
                                            sharpen, grade, blend)]
    cmd += ["-fps_mode", "cfr", "-r", str(fps)]
    cmd += encoder_args(encoder, crf, fps) + COLOR_TAGS
    cmd += ["-c:a", "aac", "-b:a", audio_bitrate, "-ar", "44100", "-shortest",
            "-map_metadata", "-1", "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", "-loglevel", "error", out_file]
    return cmd


# --------------------------------------------------------------- running


def probe(in_file):
    """Return dict(duration, fps, width, height) using ffprobe (values may be None).

    width/height are as displayed: a portrait phone video stored landscape
    with a 90-degree rotation tag reports its portrait size (FFmpeg rotates
    frames on decode)."""
    import json
    ffprobe = find_tool("ffprobe")
    info = {"duration": None, "fps": None, "width": None, "height": None}
    if not ffprobe:
        return info
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,avg_frame_rate:stream_tags=rotate:stream_side_data=rotation:format=duration",
             "-of", "json", in_file],
            capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        data = json.loads(r.stdout or "{}")
        st = (data.get("streams") or [{}])[0]
        info["duration"] = float((data.get("format") or {}).get("duration") or 0) or None
        info["width"], info["height"] = st.get("width"), st.get("height")
        num, _, den = (st.get("avg_frame_rate") or "0/0").partition("/")
        if den and float(den):
            info["fps"] = float(num) / float(den)
        rot = (st.get("tags") or {}).get("rotate")
        for sd in st.get("side_data_list") or []:
            rot = sd.get("rotation", rot)
        if rot is not None and abs(int(float(rot))) % 180 == 90 and info["width"]:
            info["width"], info["height"] = info["height"], info["width"]
    except (ValueError, OSError, subprocess.TimeoutExpired, TypeError):
        pass
    return info


def run_ffmpeg(cmd, total_seconds, progress=None, cancel=None, out_file=None, cwd=None):
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          errors="replace", cwd=cwd, creationflags=NO_WINDOW) as proc:
        try:
            for line in proc.stdout:
                if cancel and cancel():
                    raise Mp4Error("Cancelled.")
                key, _, value = line.strip().partition("=")
                if key == "out_time_us" and total_seconds and progress and value.isdigit():
                    progress(min(1.0, int(value) / 1e6 / total_seconds))
            err = proc.stderr.read()
            if proc.wait() != 0:
                raise Mp4Error("FFmpeg failed:\n" + err.strip()[-800:])
        except BaseException:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if out_file:
                try:
                    os.remove(out_file)
                except OSError:
                    pass
            raise


def prepare(in_file, out_file, progress=None, cancel=None, log=None, fps=60, resolution="1080",
            interpolation="none", crf=16, encoder="auto", enhance="off", fit="none",
            start=None, end=None, work_dir=None, color="auto", upscale="off", orient="vertical",
            sharpen=0.0, grade=None, supersample=None, motion_blur=None):
    """Run the Prepare step. progress(fraction) is called while encoding.

    supersample: short side for the AI upscale when it is larger than the
    delivered `resolution` (AI renders at 2K/4K, output is downscaled).
    motion_blur: dict(amount, interp, weighting) - frame-blended blur."""
    import tempfile

    from . import color as colormod
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        raise Mp4Error("FFmpeg not found. Install it (winget install Gyan.FFmpeg) or put ffmpeg.exe next to this app.")
    if os.path.abspath(in_file) == os.path.abspath(out_file):
        raise Mp4Error("Output file must be different from the input file.")
    enc = pick_encoder(ffmpeg, encoder)
    info = probe(in_file)
    total = info["duration"]
    if total:
        total = min(total, end or total) - (start or 0)
        if total <= 0:
            raise Mp4Error("Trim start is after the end of the video.")

    cinfo = colormod.probe_color(in_file) if color == "auto" else None
    if cinfo is not None and log:
        log(f"   colour: {colormod.describe(cinfo)}"
            + (" -> SDR BT.709 (BT.2390 tone mapping)" if cinfo["kind"] != "sdr" else " -> BT.709"))

    short = min(info["width"] or 0, info["height"] or 0)
    target_short = 1080 if resolution == "keep" else int(resolution)
    ai_short = max(supersample or 0, target_short)
    do_upscale = bool(upscale in ("real", "anime") and short and short < ai_short * 0.9)
    if upscale in ("real", "anime") and not do_upscale and log:
        log(f"   AI upscale skipped: source is already {short}p (target {ai_short}p)")
    ai_interp = interpolation == "ai"
    ai_fps = fps

    blend = None
    if motion_blur:
        from . import motionblur
        src_fps = info.get("fps") or fps
        ifps, gap, nframes = motionblur.plan(src_fps, fps, motion_blur.get("interp", "600"),
                                             motion_blur.get("amount", 1.0))
        blend = motionblur.blend_filter(gap, nframes, motion_blur.get("weighting", "equal"))
        if src_fps >= ifps * 0.9:  # high-fps recording: blend the real frames, no AI needed
            blend = f"fps={ifps}," + blend if blend else None
            ai_interp, interpolation = False, "none"
        else:
            ai_interp, interpolation, ai_fps = True, "ai", ifps
        if log:
            log(f"   motion blur: {src_fps:.0f} -> {ifps:g} fps"
                + (" (AI)" if ai_interp else "") + f", {nframes} frames blended -> {fps:g} fps")

    opts = dict(fps=fps, resolution=resolution, interpolation=interpolation, crf=crf,
                encoder=enc, enhance=enhance, fit=fit, start=start, end=end, orient=orient,
                sharpen=sharpen, grade=grade, blend=blend)
    tmp = tempfile.mkdtemp(prefix="tt_prep_", dir=work_dir)
    try:
        if do_upscale or ai_interp:
            from .frames import stream_encode
            rate = ai_fps if ai_interp else info["fps"]
            cmd = build_command(ffmpeg, in_file, out_file, frames_dir="-", frames_rate=rate, **opts)
            try:
                stream_encode(ffmpeg, in_file, info, cinfo, ai_fps, cmd, start, end,
                              upscale=(upscale, ai_short) if do_upscale else None, ai_interp=ai_interp,
                              work_dir=tmp, progress=progress, cancel=cancel, log=log)
            except BaseException:
                try:
                    os.remove(out_file)
                except OSError:
                    pass
                raise
        else:
            cf = colormod.color_filter(cinfo, tmp) if cinfo is not None else None
            cmd = build_command(ffmpeg, in_file, out_file, color=cf, **opts)
            run_ffmpeg(cmd, total, progress, cancel, out_file, cwd=tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    parts = [f"H.264 {fps:g} fps", f"encoder {enc}", f"interpolation {interpolation}",
             f"resolution {resolution}", f"{UPLOAD_KBPS} kbps CBR"]
    if cinfo is not None and cinfo["kind"] != "sdr":
        parts.append("HDR->SDR")
    if do_upscale:
        parts.append(f"AI upscale {upscale} at {ai_short}p")
    if motion_blur:
        parts.append(f"motion blur {motion_blur.get('amount', 1.0):g}")
    if sharpen:
        parts.append(f"CAS sharpen {sharpen:.2f}")
    if enhance != "off":
        parts.append(f"enhance {enhance}")
    if fit != "none":
        parts.append(f"{'9:16' if orient == 'vertical' else '16:9'} {fit}")
    if start or end:
        parts.append(f"trim {start or 0:g}s-{end or 'end'}{'s' if end else ''}")
    return ["Prepared with FFmpeg: " + ", ".join(parts)]
