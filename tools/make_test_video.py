"""Generate a 1080x1920 test-pattern video with four sections:

1. FPS      - frame counter + one cell lit per frame (count the cells)
2. QUALITY  - 1-4 px stripes, zone plate, small text, gradients, moving fine text
3. LAG      - constant-speed bar, a marker that steps one tick per frame, per-frame flicker
4. GENERAL  - spinning wheel, millisecond timer, once-a-second flash synced to a beep

    python tools/make_test_video.py --fps 60 --seconds 15 -o test_60fps.mp4
"""

import argparse
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from toolkit.encode import find_tool  # noqa: E402

W, H = 1080, 1920
HEADER = 120
SEC_H = 450
MARGIN = 40
FONTS = r"C:\Windows\Fonts"

BG = (14, 14, 20)
PANEL = (26, 26, 36)
ACCENT = [(255, 60, 120), (40, 200, 230), (255, 190, 40), (120, 220, 90)]
WHITE, GREY, DIM = (240, 240, 245), (130, 130, 145), (55, 55, 70)


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONTS, name), size)
    except OSError:
        return ImageFont.load_default()


F_TITLE = font("segoeuib.ttf", 46)
F_LABEL = font("segoeuib.ttf", 34)
F_SMALL = font("segoeui.ttf", 24)
F_MONO_BIG = font("consolab.ttf", 64)
F_MONO = font("consola.ttf", 26)


def sec_y(i):
    return HEADER + i * SEC_H


def label(d, i, title, hint):
    y = sec_y(i)
    d.rectangle((0, y, 14, y + SEC_H - 8), fill=ACCENT[i])
    d.text((MARGIN, y + 14), f"{i + 1}  {title}", font=F_LABEL, fill=ACCENT[i])
    d.text((MARGIN, y + SEC_H - 46), hint, font=F_SMALL, fill=GREY)


def zone_plate(size):
    yy, xx = np.mgrid[-1:1:size * 1j, -1:1:size * 1j]
    r2 = xx ** 2 + yy ** 2
    v = 0.5 + 0.5 * np.cos(math.pi * size * 0.5 * r2)
    v[r2 > 1] = 0.08
    return Image.fromarray((v * 255).astype(np.uint8), "L").convert("RGB")


def static_layer(fps):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((MARGIN, 18), "TikTok Test Pattern", font=F_TITLE, fill=WHITE)
    d.text((MARGIN, 74), f"{fps} FPS source  ·  1080x1920  ·  H.264", font=F_SMALL, fill=GREY)
    for i in range(4):
        y = sec_y(i)
        d.rounded_rectangle((8, y + 4, W - 8, y + SEC_H - 8), radius=18, fill=PANEL)

    label(d, 0, "FPS TEST", f"Count lit cells: all {fps} light up each second = full {fps} fps")
    label(d, 1, "QUALITY TEST", "Sharp stripes + smooth gradients = good quality. Blur/banding = compression")
    label(d, 2, "LAG / FRAME PACING", "Bar and marker must move evenly. Jumps or pauses = lag / dropped frames")
    label(d, 3, "GENERAL TEST", "Wheel spins smoothly · timer runs · flash and beep happen together")

    # --- quality section (static parts) ---
    y = sec_y(1) + 70
    x = MARGIN
    for k, width in enumerate((1, 2, 3, 4)):
        bx = x + k * 130
        for sx in range(0, 110, width * 2):
            d.rectangle((bx + sx, y, bx + min(sx + width - 1, 109), y + 109), fill=WHITE)
        d.text((bx + 30, y + 114), f"{width}px", font=F_SMALL, fill=GREY)
    for k, width in enumerate((1, 2)):
        by = y + k * 60
        for sy in range(0, 50, width * 2):
            d.rectangle((x + 540, by + sy, x + 650, by + min(sy + width - 1, 49)), fill=WHITE)
    zp = zone_plate(140)
    img.paste(zp, (W - MARGIN - 150, y - 6))
    gy = y + 150
    grad = np.tile(np.linspace(0, 255, 1000).astype(np.uint8), (34, 1))
    img.paste(Image.fromarray(grad, "L").convert("RGB"), (MARGIN, gy))
    hue = Image.fromarray(np.stack([np.tile(np.linspace(0, 255, 1000).astype(np.uint8), (34, 1)),
                                    np.full((34, 1000), 220, np.uint8),
                                    np.full((34, 1000), 255, np.uint8)], axis=-1), "HSV").convert("RGB")
    img.paste(hue, (MARGIN, gy + 40))
    ty = gy + 84
    for size in (13, 17, 22):
        d.text((MARGIN, ty), "Quality 0123456789 ABCDEFGHIJKLM abcdefghijklm", font=font("segoeui.ttf", size), fill=WHITE)
        ty += size + 6

    # --- lag section: ruler ---
    ry = sec_y(2) + 250
    step = 1000 / fps
    for t in range(fps + 1):
        tx = MARGIN + t * step
        tall = 22 if t % 10 == 0 else 10
        d.line((tx, ry, tx, ry + tall), fill=GREY if t % 10 else WHITE, width=1)
    for t in range(0, fps + 1, 10):
        d.text((MARGIN + t * step - 8, ry + 26), str(t), font=F_SMALL, fill=GREY)
    d.text((W - MARGIN - 480, sec_y(2) + 24), "flicker 1 / 2 frames", font=F_SMALL, fill=GREY)
    return img


def draw_frame(base, n, fps, marquee):
    img = base.copy()
    d = ImageDraw.Draw(img)
    t = n / fps

    # 1. FPS
    y = sec_y(0)
    d.text((W - MARGIN - 470, y + 10), f"FRAME {n:05d}", font=F_MONO_BIG, fill=WHITE)
    rows, cols = fps // 30, 30
    cell = (1000 - (cols - 1) * 3) / cols
    ch = min(cell, (230 - (rows - 1) * 6) / rows)
    lit = n % fps
    for k in range(fps):
        r, c = divmod(k, cols)
        cx = MARGIN + c * (cell + 3)
        cy = y + 100 + r * (ch + 6)
        d.rectangle((cx, cy, cx + cell, cy + ch), fill=ACCENT[0] if k == lit else DIM)
    bx = MARGIN + (t % 1.0) * 960
    d.ellipse((bx, y + 340, bx + 44, y + 384), fill=WHITE)

    # 2. QUALITY: moving fine text
    my = sec_y(1) + 372
    off = int(t * 140) % marquee.width
    img.paste(marquee.crop((off, 0, off + W - 2 * MARGIN, marquee.height)), (MARGIN, my))

    # 3. LAG
    y = sec_y(2)
    bar_x = MARGIN + (t * 960) % 1000
    d.rectangle((bar_x, y + 80, bar_x + 14, y + 220), fill=ACCENT[1])
    mx = MARGIN + (n % fps) * (1000 / fps)
    d.polygon([(mx, y + 300), (mx - 10, y + 320), (mx + 10, y + 320)], fill=ACCENT[2])
    d.rectangle((W - MARGIN - 230, y + 16, W - MARGIN - 130, y + 66), fill=WHITE if n % 2 else (0, 0, 0))
    d.rectangle((W - MARGIN - 110, y + 16, W - MARGIN - 10, y + 66), fill=WHITE if (n // 2) % 2 else (0, 0, 0))

    # 4. GENERAL
    y = sec_y(3)
    cx, cy, rad = MARGIN + 170, y + 230, 140
    d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=WHITE, width=4)
    ang = t * math.pi  # half a turn per second
    for s in range(8):
        a = ang + s * math.pi / 4
        d.line((cx, cy, cx + rad * math.cos(a), cy + rad * math.sin(a)), fill=ACCENT[s % 4], width=6)
    d.text((MARGIN + 380, y + 90), f"{int(t // 60):02d}:{t % 60:06.3f}", font=F_MONO_BIG, fill=WHITE)
    flash = (n % fps) < max(1, round(0.06 * fps))
    d.rounded_rectangle((MARGIN + 380, y + 190, MARGIN + 580, y + 330), radius=14,
                        fill=WHITE if flash else DIM)
    d.text((MARGIN + 600, y + 210), "flash = beep", font=F_SMALL, fill=GREY)
    by = y + 260 + 60 * math.sin(t * 2 * math.pi * 0.5)
    bx = MARGIN + 640 + (t * 180) % 340
    d.ellipse((bx, by - 22, bx + 44, by + 22), fill=ACCENT[3])
    return img


def make_marquee():
    text = "  Fine moving text: The quick brown fox jumps over the lazy dog 0123456789 — " * 2
    f = font("segoeui.ttf", 22)
    w = int(f.getlength(text)) + 10
    m = Image.new("RGB", (w + W, 30), PANEL)
    ImageDraw.Draw(m).text((0, 0), text + text, font=f, fill=WHITE)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=60, choices=(30, 60, 120))
    ap.add_argument("--seconds", type=int, default=15)
    ap.add_argument("-o", "--output", default="tiktok_test_60fps.mp4")
    args = ap.parse_args()
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg not found")

    fps, total = args.fps, args.fps * args.seconds
    base = static_layer(fps)
    marquee = make_marquee()
    beep = "aevalsrc='if(lt(mod(t,1),0.06),0.6*sin(2*PI*1000*t),0)':s=48000:d=" + str(args.seconds)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-f", "lavfi", "-i", beep,
           "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-g", str(fps * 2), "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart",
           args.output]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(total):
        proc.stdin.write(draw_frame(base, n, fps, marquee).tobytes())
        if n % fps == 0:
            print(f"\r{n // fps + 1}/{args.seconds} s", end="", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"\nwrote {args.output}")


if __name__ == "__main__":
    main()
