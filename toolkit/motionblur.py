"""Motion blur by frame blending - the technique of f0e/blur.

The video is interpolated to a high frame rate (RIFE), then every output
frame is a weighted blend of the neighbouring interpolated frames:
  frame_gap      = interpolated fps / output fps
  blended frames = frame_gap * blur amount   (odd, as in blur)
Weighting functions follow blur's weighting.py. Blending runs in FFmpeg
(tmix + framestep). blur .cfg files ("key: value" lines) can be imported.
"""

import math

WEIGHTINGS = ("equal", "gaussian_sym", "vegas", "pyramid", "gaussian", "gaussian_reverse",
              "ascending", "descending")


def _normalize(w):
    w = list(w)
    if min(w) < 0:
        w = [x - min(w) + 1 for x in w]
    total = sum(w)
    return [x / total for x in w]


def _scale_range(n, start, end):
    if n <= 1:
        return [start] * n
    return [start + i * (end - start) / (n - 1) for i in range(n)]


def _gaussian(n, mean=2.0, std=1.0, bound=(0.0, 2.0)):
    xs = _scale_range(n, bound[0], bound[1])
    return _normalize(math.exp(-((x - mean) ** 2) / (2 * std ** 2)) for x in xs)


def weights(n, kind="equal"):
    """Blending weights for n frames (oldest first), summing to 1."""
    if kind == "equal":
        return [1 / n] * n
    if kind == "ascending":
        return _normalize(range(1, n + 1))
    if kind == "descending":
        return _normalize(range(n, 0, -1))
    if kind == "pyramid":
        half = (n - 1) / 2
        return _normalize(half - abs(i - half) + 1 for i in range(n))
    if kind == "gaussian":
        return _gaussian(n)
    if kind == "gaussian_reverse":
        return _gaussian(n)[::-1]
    if kind == "gaussian_sym":
        return _gaussian(n, mean=0.0, bound=(-2.0, 2.0))
    if kind == "vegas":
        return _normalize([1] + [2] * (n - 2) + [1] if n % 2 == 0 else [1] * n)
    try:  # custom, e.g. "5, 3, 3, 2, 1" stretched to n frames
        custom = [float(x) for x in str(kind).split(",")]
        idx = _scale_range(n, 0, len(custom) - 0.1)
        return _normalize(custom[int(i)] for i in idx)
    except ValueError:
        return [1 / n] * n


def plan(src_fps, out_fps, interp, amount):
    """Return (interpolated fps, frame gap, blended frame count).

    interp: number (e.g. 600) or multiplier string of the input fps ("5x")."""
    s = str(interp).strip().lower()
    target = float(s[:-1]) * src_fps if s.endswith("x") else float(s)
    gap = max(1, round(target / out_fps))
    frames = int(gap * float(amount))
    if frames > 0 and frames % 2 == 0:
        frames += 1
    return out_fps * gap, gap, min(frames, 1023)


def blend_filter(gap, frames, kind="equal"):
    """FFmpeg filter that blends `frames` neighbours and keeps one frame per `gap`."""
    if frames <= 1:
        return f"framestep={gap}" if gap > 1 else None
    w = " ".join(f"{x:.6f}" for x in weights(frames, kind))
    return f"tmix=frames={frames}:weights='{w}',framestep={gap}"


# ------------------------------------------------------------- blur .cfg


def _bool(v):
    return str(v).strip().lower() in ("true", "1", "yes", "on")


def read_cfg(path):
    """Parse a blur config file into a dict of toolkit Options fields."""
    values = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("[", "-", "#")) or ":" not in line:
                continue
            key, _, value = line.partition(":")
            values[key.strip().lower()] = value.strip()

    out, notes = {}, []
    if "blur" in values:
        out["motion_blur"] = _bool(values["blur"])
    if "blur amount" in values:
        out["blur_amount"] = max(0.0, float(values["blur amount"]))
    if "blur output fps" in values:
        fps = int(float(values["blur output fps"]))
        if fps in (30, 60, 120):
            out["out_fps"] = str(fps)
        else:
            notes.append(f"output fps {fps} is not 30/60/120 - kept your frame-rate choice")
    if "blur weighting" in values:
        w = values["blur weighting"].strip()
        out["blur_weighting"] = w if (w in WEIGHTINGS or "," in w) else "equal"
    if _bool(values.get("interpolate", "true")) and "interpolated fps" in values:
        out["blur_interp"] = values["interpolated fps"].strip()
    if values.get("interpolation method", "rife").strip().lower() not in ("rife", ""):
        notes.append("SVP interpolation is replaced by RIFE (higher quality)")
    if "quality" in values:
        out["prep_crf"] = max(0, min(51, int(float(values["quality"]))))
    if "gpu encoding" in values:
        out["prep_encoder"] = "auto" if _bool(values["gpu encoding"]) else "cpu"
    if _bool(values.get("filters", "false")):
        for key in ("brightness", "saturation", "contrast"):
            if key in values:
                v = float(values[key])
                out[key] = min(1.3, max(0.7, v))  # same limits as encode.GRADE_MIN / GRADE_MAX
                if out[key] != v:
                    notes.append(f"{key} {v:g} limited to {out[key]:g} (stronger values blow out on TikTok)")
    if _bool(values.get("deduplicate", "false")):
        notes.append("deduplicate is not supported yet - frames are used as recorded")
    if _bool(values.get("timescale", "false")):
        notes.append("timescale is not supported - ignored")
    return out, notes
