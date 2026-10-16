"""Command line interface.

  tiktok_toolkit.py                      open the GUI
  tiktok_toolkit.py a.mp4 b.mp4          open the GUI with files loaded
  tiktok_toolkit.py inspect a.mp4        print a report
  tiktok_toolkit.py run a.mp4 [steps]    process files without the GUI
  tiktok_toolkit.py check <tiktok link>  show the frame rates TikTok serves
"""

import argparse
import os
import sys

from . import __version__
from .encode import COLOR, ENCODERS, ENHANCE, FIT, INTERPOLATION, RESOLUTIONS, UPSCALE, parse_time
from .inspector import inspect
from .pipeline import Options, run


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or (argv[0] not in ("run", "inspect", "check", "-h", "--help", "--version")
                    and all(os.path.isfile(a) for a in argv)):
        from .gui import run_gui
        run_gui(argv)
        return 0

    ap = argparse.ArgumentParser(prog="tiktok_toolkit", description="TikTok Quality Toolkit")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("inspect", help="show video info and readiness")
    pi.add_argument("files", nargs="+")

    pc = sub.add_parser("check", help="check a posted TikTok link")
    pc.add_argument("url")
    pc.add_argument("--download", action="store_true", help="download the best stream and inspect it")

    pr = sub.add_parser("run", help="process videos")
    pr.add_argument("files", nargs="+")
    pr.add_argument("--prepare", action="store_true", help="re-encode with FFmpeg first")
    pr.add_argument("--prep-fps", type=float, default=60)
    pr.add_argument("--resolution", choices=RESOLUTIONS, default="1080")
    pr.add_argument("--interpolation", choices=INTERPOLATION, default="none")
    pr.add_argument("--crf", type=int, default=16)
    pr.add_argument("--encoder", choices=ENCODERS, default="auto")
    pr.add_argument("--enhance", choices=ENHANCE, default="off")
    pr.add_argument("--fit", choices=FIT, default="none", help="9:16 framing")
    pr.add_argument("--color", choices=COLOR, default="auto", help="HDR->SDR + colour fix")
    pr.add_argument("--upscale", choices=UPSCALE, default="off", help="Real-ESRGAN AI upscale model")
    pr.add_argument("--trim-start", type=parse_time)
    pr.add_argument("--trim-end", type=parse_time)
    pr.add_argument("--no-fps-patch", action="store_true", help="skip the FPS patch step")
    pr.add_argument("--mode", choices=("method", "slowmo"), default="method")
    pr.add_argument("--fps", type=float, help="source FPS (auto-detected if omitted)")
    pr.add_argument("--target", type=float, default=30)
    pr.add_argument("--video-only", action="store_true", help="do not patch the audio track")
    pr.add_argument("--ghost", action="store_true", help="apply ghost frames (1080p60 trick)")
    pr.add_argument("--multiplier", type=int, default=10)
    pr.add_argument("-o", "--out-dir")
    args = ap.parse_args(argv)

    failed = 0
    if args.cmd == "inspect":
        for f in args.files:
            try:
                print("\n".join(inspect(f)[1]))
            except Exception as e:
                failed += 1
                print(f"{f}: ERROR: {e}", file=sys.stderr)
        return 1 if failed else 0

    if args.cmd == "check":
        return _check(args.url, args.download)

    opts = Options(
        prepare=args.prepare, prep_fps=args.prep_fps, prep_resolution=args.resolution,
        prep_interpolation=args.interpolation, prep_crf=args.crf, prep_encoder=args.encoder,
        prep_enhance=args.enhance, prep_fit=args.fit,
        prep_color=args.color, prep_upscale=args.upscale, trim_start=args.trim_start, trim_end=args.trim_end,
        fps_patch=not args.no_fps_patch, fps_mode=args.mode, source_fps=args.fps,
        target_fps=args.target, include_audio=not args.video_only,
        ghost=args.ghost, ghost_multiplier=args.multiplier, out_dir=args.out_dir,
    )
    for f in args.files:
        print(f"=== {f}")
        try:
            print(f"-> {run(f, opts)}")
        except Exception as e:
            failed += 1
            print(f"ERROR: {e}", file=sys.stderr)
    return 1 if failed else 0


def _check(url, download):
    from . import linkcheck
    try:
        info, session = linkcheck.check(url)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"@{info['author']}  {info['title']}  ({info['duration']}s, via {info['source']})")
    for s in info["streams"]:
        print(f"   {s['name']:<24} {s['width']}x{s['height']:<6} {s['fps'] or '?':>4} fps  "
              f"{s['codec']:<6} {s['mbps']:.2f} Mbps  {s['size'] / 1e6:.1f} MB")
    best = info["best_fps"]
    if download:
        dest = os.path.abspath(f"tiktok_{info['url'].rstrip('/').split('/')[-1].split('?')[0]}.mp4")
        linkcheck.download(info, session, dest)
        print(f"downloaded {dest}")
        result, lines = inspect(dest)
        if "   readiness:" in lines:
            lines = lines[: lines.index("   readiness:")]
        print("\n".join(lines))
        best = best or round((result.get("video") or {}).get("fps") or 0)
    print(f"best frame rate: {best or '?'} fps -> {linkcheck.verdict(best).upper()}")
    return 0
