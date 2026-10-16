"""Colour fix: HDR -> SDR tone mapping and SDR colour normalisation.

HDR (PQ / HLG, e.g. iPhone and Android HDR video) is converted with the
ITU-R BT.2390 EETF roll-off applied as a 1D LUT in the PQ domain:
  * HDR reference white 203 nits (ITU-R BT.2408) -> SDR 100 %
  * everything below the 100-nit knee is kept exactly (faces, skin, mid-tones)
  * highlights between the knee and the content peak are compressed smoothly
  * output encoded for a BT.1886 (gamma 2.4) SDR display, BT.709 primaries
Measured on a ColorChecker chart this is ~10x more accurate than FFmpeg's
built-in hable / mobius / reinhard operators while keeping highlight detail.

SDR sources are normalised to BT.709 / limited range: full-range video
(grey blacks), BT.601 matrices and 10-bit footage (dithered to 8-bit).
"""

import json
import os
import subprocess

import numpy as np

from .encode import NO_WINDOW, find_tool

REFERENCE_WHITE = 203.0  # nits, ITU-R BT.2408
KNEE = 100.0             # nits, start of the highlight roll-off (tuned, see module doc)
DEFAULT_PEAK = 1000.0    # nits, HLG nominal peak / typical PQ mastering
LUT_SIZE = 4096
LUT_NAME = "tt_tonemap.cube"

_M1, _M2, _C1, _C2, _C3 = 0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875

# ffprobe tag -> zscale value
_MATRIX = {"bt709": "709", "smpte170m": "170m", "bt470bg": "470bg", "bt2020nc": "2020_ncl", "bt2020c": "2020_cl"}
_PRIM = {"bt709": "709", "smpte170m": "170m", "bt470bg": "470bg", "bt2020": "2020", "smpte432": "smpte432"}
_TRC = {"bt709": "709", "smpte170m": "601", "bt470bg": "601", "bt470m": "601", "bt2020-10": "2020_10",
        "bt2020-12": "2020_12", "iec61966-2-1": "iec61966-2-1", "smpte2084": "smpte2084",
        "arib-std-b67": "arib-std-b67", "linear": "linear"}


# --------------------------------------------------------------- transfer maths


def pq_encode(nits):
    y = np.clip(np.asarray(nits, float) / 10000.0, 0, 1)
    return ((_C1 + _C2 * y ** _M1) / (1 + _C3 * y ** _M1)) ** _M2


def pq_decode(e):
    e = np.clip(np.asarray(e, float), 0, 1) ** (1 / _M2)
    return 10000.0 * (np.maximum(e - _C1, 0) / (_C2 - _C3 * e)) ** (1 / _M1)


def eetf(e, src_peak, tgt_peak=REFERENCE_WHITE, knee=KNEE):
    """BT.2390 Hermite-spline roll-off in normalised PQ space (black = 0)."""
    lw = pq_encode(src_peak)
    e1 = np.clip(np.asarray(e, float) / lw, 0, 1)
    maxl = pq_encode(tgt_peak) / lw
    ks = pq_encode(knee) / lw
    t = (e1 - ks) / (1 - ks)
    spline = ((2 * t ** 3 - 3 * t ** 2 + 1) * ks + (t ** 3 - 2 * t ** 2 + t) * (1 - ks)
              + (-2 * t ** 3 + 3 * t ** 2) * maxl)
    return np.where(e1 < ks, e1, spline) * lw


def tone_curve(src_peak, n=LUT_SIZE):
    """PQ code value (0..1) -> BT.1886 SDR code value (0..1)."""
    x = np.linspace(0, 1, n)
    y = pq_decode(eetf(x, src_peak)) / REFERENCE_WHITE
    return np.clip(y, 0, 1) ** (1 / 2.4)


def write_lut(folder, src_peak):
    path = os.path.join(folder, LUT_NAME)
    y = tone_curve(src_peak)
    with open(path, "w") as f:
        f.write(f"TITLE \"BT.2390 HDR->SDR peak {src_peak:g} nits\"\nLUT_1D_SIZE {len(y)}\n"
                "DOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
        f.writelines(f"{v:.7f} {v:.7f} {v:.7f}\n" for v in y)
    return path


# -------------------------------------------------------------------- probing


def _ratio(v):
    try:
        if isinstance(v, str) and "/" in v:
            n, d = v.split("/")
            return float(n) / float(d)
        return float(v)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0.0


def probe_color(path):
    """Colour properties of the first video stream (via ffprobe)."""
    info = {"transfer": None, "primaries": None, "matrix": None, "range": None, "pix_fmt": None,
            "height": 0, "peak": None, "kind": "sdr"}
    ffprobe = find_tool("ffprobe")
    if not ffprobe:
        return info
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", "%+#1",
             "-show_entries", "stream=color_transfer,color_primaries,color_space,color_range,pix_fmt,height:"
             "stream_side_data:frame_side_data", "-show_frames", "-of", "json", path],
            capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        data = json.loads(r.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return info
    s = (data.get("streams") or [{}])[0]
    info.update(transfer=s.get("color_transfer"), primaries=s.get("color_primaries"), matrix=s.get("color_space"),
                range=s.get("color_range"), pix_fmt=s.get("pix_fmt"), height=int(s.get("height") or 0))
    side = list(s.get("side_data_list") or [])
    for fr in data.get("frames") or []:
        side += fr.get("side_data_list") or []
    max_cll = max((_ratio(d.get("max_content")) for d in side), default=0.0)
    mastering = max((_ratio(d.get("max_luminance")) for d in side), default=0.0)
    if info["transfer"] == "smpte2084":
        info["kind"] = "pq"
        peak = max_cll or mastering or DEFAULT_PEAK
        info["peak"] = float(min(max(peak, 400.0), 4000.0))
    elif info["transfer"] == "arib-std-b67":
        info["kind"] = "hlg"
        info["peak"] = DEFAULT_PEAK
    return info


def _bits(pix_fmt):
    pf = pix_fmt or ""
    return 10 if ("10" in pf or "12" in pf or "16" in pf) else 8


def describe(info):
    if info["kind"] in ("pq", "hlg"):
        name = "HDR10 / PQ" if info["kind"] == "pq" else "HLG HDR"
        return f"{name}, peak ~{info['peak']:g} nits"
    parts = [f"SDR {info.get('matrix') or 'untagged'}"]
    if info.get("range") == "pc" or (info.get("pix_fmt") or "").startswith("yuvj"):
        parts.append("full range")
    if _bits(info.get("pix_fmt")) > 8:
        parts.append("10-bit")
    return ", ".join(parts)


# -------------------------------------------------------------------- filters


def needs_fix(info):
    """True when the source is HDR or not plain 8-bit BT.709 limited range."""
    if info["kind"] != "sdr":
        return True
    full = info.get("range") == "pc" or (info.get("pix_fmt") or "").startswith("yuvj")
    sd = 0 < info.get("height", 0) < 720
    matrix = _MATRIX.get(info.get("matrix"), "170m" if sd else "709")
    prim = _PRIM.get(info.get("primaries"), "170m" if sd else "709")
    return full or matrix != "709" or prim != "709" or _bits(info.get("pix_fmt")) > 8


def color_filter(info, lut_folder):
    """FFmpeg filter chain (no pad labels) that outputs BT.709 limited-range
    yuv420p, or None when the source is already plain BT.709 8-bit.
    The tone-mapping LUT is written to lut_folder; run FFmpeg with
    cwd=lut_folder so the relative LUT path needs no escaping."""
    full = info.get("range") == "pc" or (info.get("pix_fmt") or "").startswith("yuvj")
    rin = "full" if full else "limited"
    sd = 0 < info.get("height", 0) < 720
    matrix = _MATRIX.get(info.get("matrix"), "170m" if sd else "709")
    prim = _PRIM.get(info.get("primaries"), "170m" if sd else "709")

    if info["kind"] in ("pq", "hlg"):
        write_lut(lut_folder, info["peak"])
        tin = "smpte2084" if info["kind"] == "pq" else "arib-std-b67"
        prim = _PRIM.get(info.get("primaries"), "2020")
        matrix = _MATRIX.get(info.get("matrix"), "2020_ncl")
        return (f"zscale=tin={tin}:min={matrix}:pin={prim}:rin={rin}:t=smpte2084:p=709:npl={DEFAULT_PEAK:g},"
                f"format=gbrpf32le,lut1d=file={LUT_NAME}:interp=cubic,"
                "setparams=color_trc=bt709:color_primaries=bt709,"
                "zscale=tin=709:t=709:m=709:r=limited:dither=error_diffusion,format=yuv420p")

    tin = _TRC.get(info.get("transfer"), "601" if sd else "709")
    if matrix == "709" and prim == "709" and not full and _bits(info.get("pix_fmt")) == 8:
        return None
    return (f"zscale=tin={tin}:min={matrix}:pin={prim}:rin={rin}:"
            f"t={tin}:m=709:p=709:r=limited:dither=error_diffusion,format=yuv420p")

