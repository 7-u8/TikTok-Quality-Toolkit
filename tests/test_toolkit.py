"""End-to-end tests. Need ffmpeg/ffprobe (generated test clips).

    python -m unittest discover -s tests -v
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from toolkit import linkcheck  # noqa: E402
from toolkit.encode import available_encoders, find_rife, find_tool, parse_time, prepare  # noqa: E402
from toolkit.esrgan import find_esrgan  # noqa: E402
from toolkit.i18n import _STRINGS, Translator  # noqa: E402
from toolkit.preview import make_preview  # noqa: E402
from toolkit.fps_patch import patch_fps  # noqa: E402
from toolkit.ghost import ghost_frames  # noqa: E402
from toolkit.inspector import inspect  # noqa: E402
from toolkit.mp4 import Mp4Error, Mp4File  # noqa: E402
from toolkit.pipeline import Options, run  # noqa: E402

FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")


def read(path):
    with open(path, "rb") as f:
        return f.read()


def ut0ku_reference(data, divider):
    """Re-implementation of ut0ku/120fps-method's patch (naive byte search)."""
    data = bytearray(data)
    for name in (b"mvhd", b"mdhd"):
        i = data.find(name)
        while i >= 0:
            pos = i - 4
            ver = data[pos + 8]
            ts = pos + 20 if ver == 0 else pos + 28
            dsz = 4 if ver == 0 else 8
            old_ts = int.from_bytes(data[ts : ts + 4], "big")
            old_d = int.from_bytes(data[ts + 4 : ts + 4 + dsz], "big")
            data[ts : ts + 4] = max(1, old_ts // divider).to_bytes(4, "big")
            data[ts + 4 : ts + 4 + dsz] = (old_d // divider).to_bytes(dsz, "big")
            i = data.find(name, i + 4)
    return bytes(data)


@unittest.skipUnless(FFMPEG and FFPROBE, "ffmpeg/ffprobe not found")
class ToolkitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="tt_test_")
        cls.v60 = cls.make("v60.mp4", "testsrc2=rate=60:size=640x360:duration=3", audio=True)
        cls.v120 = cls.make("v120.mp4", "testsrc2=rate=120:size=640x360:duration=2", audio=True)
        cls.hevc30 = cls.make("hevc30.mp4", "testsrc2=rate=30:size=480x270:duration=2", codec="libx265", audio=True)
        cls.land = cls.make("land.mp4", "testsrc2=rate=30:size=1280x720:duration=4", audio=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    @classmethod
    def make(cls, name, src, codec="libx264", audio=False):
        path = os.path.join(cls.dir, name)
        cmd = [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", src]
        if audio:
            cmd += ["-f", "lavfi", "-i", "sine=duration=5", "-c:a", "aac", "-shortest"]
        cmd += ["-c:v", codec, path]
        subprocess.run(cmd, check=True)
        return path

    def out(self, name):
        return os.path.join(self.dir, name)

    def probe(self, path):
        r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=r_frame_rate,nb_frames", "-of", "csv=p=0", path],
                           capture_output=True, text=True, check=True)
        return r.stdout.strip()

    def decodes(self, path):
        r = subprocess.run([FFMPEG, "-v", "fatal", "-i", path, "-f", "null", "-"], capture_output=True)
        return r.returncode == 0

    def decoded_frames(self, path):
        """Frames FFmpeg actually decodes. Ghost-frame files make FFmpeg 9 exit
        with an error on the 8-byte filler samples (the reference
        tiktok-quality output does exactly the same), so count real frames."""
        r = subprocess.run([FFMPEG, "-i", path, "-map", "0:v:0", "-f", "null", "-"],
                           capture_output=True, text=True, errors="replace")
        counts = [int(x) for x in re.findall(r"frame=\s*(\d+)", r.stderr)]
        return counts[-1] if counts else 0

    # ------------------------------------------------------------- FPS patch

    def test_method_matches_ut0ku_60(self):
        out = self.out("m60.mp4")
        patch_fps(self.v60, out, mode="method")
        expected = ut0ku_reference(read(self.v60), 2)
        self.assertEqual(read(out), expected)
        m = Mp4File(out)
        self.assertAlmostEqual(m.video.fps, 30, places=3)
        self.assertAlmostEqual(m.video.seconds, Mp4File(self.v60).video.seconds, places=2)
        self.assertTrue(self.decodes(out))

    def test_method_matches_ut0ku_120(self):
        out = self.out("m120.mp4")
        patch_fps(self.v120, out, mode="method")
        self.assertEqual(read(out), ut0ku_reference(read(self.v120), 4))
        self.assertAlmostEqual(Mp4File(out).video.fps, 30, places=3)

    def test_refuses_double_patch(self):
        once = self.out("once.mp4")
        patch_fps(self.v60, once, mode="method")
        self.assertTrue(inspect(once)[0].get("patched"))
        with self.assertRaises(Mp4Error):
            patch_fps(once, self.out("twice.mp4"))

    def test_slowmo_doubles_length(self):
        out = self.out("slow.mp4")
        patch_fps(self.v60, out, mode="slowmo")
        m, src = Mp4File(out), Mp4File(self.v60)
        self.assertAlmostEqual(m.video.fps, 30, places=3)
        self.assertAlmostEqual(m.video.seconds, src.video.seconds * 2, places=2)

    def test_video_only_leaves_audio(self):
        out = self.out("vo.mp4")
        patch_fps(self.v60, out, mode="method", include_audio=False)
        self.assertEqual(Mp4File(out).audio.timescale, Mp4File(self.v60).audio.timescale)

    def test_errors(self):
        with self.assertRaises(Mp4Error):
            patch_fps(self.v60, self.v60)
        with self.assertRaises(Mp4Error):
            patch_fps(self.v60, self.out("x.mp4"), fps_in=30, fps_out=30)
        bad = self.out("bad.mp4")
        with open(bad, "wb") as f:
            f.write(b"not a video at all")
        with self.assertRaises(Mp4Error):
            patch_fps(bad, self.out("bad2.mp4"))
        self.assertFalse(os.path.exists(self.out("bad2.mp4")))

    # ---------------------------------------------------------- ghost frames

    def test_ghost(self):
        out = self.out("ghost.mp4")
        ghost_frames(self.v60, out, multiplier=10)
        frames = Mp4File(self.v60).video.sample_count
        self.assertEqual(Mp4File(out).video.sample_count, frames * 10)
        self.assertGreaterEqual(self.decoded_frames(out), frames)

    def test_ghost_rejects_hevc(self):
        with self.assertRaises(Mp4Error):
            ghost_frames(self.hevc30, self.out("g.mp4"))

    # ------------------------------------------------------ inspect/pipeline

    def test_inspect(self):
        info, lines = inspect(self.v60)
        self.assertEqual(info["video"]["codec"], "avc1")
        self.assertAlmostEqual(info["video"]["fps"], 60, places=2)
        self.assertTrue(info["video"]["cfr"])

    def test_full_pipeline_from_hevc30(self):
        opts = Options(prepare=True, prep_fps=60, prep_interpolation="blend", prep_resolution="1080",
                       fps_patch=True, ghost=True, out_dir=self.dir)
        logs = []
        out = run(self.hevc30, opts, log=logs.append)
        self.assertTrue(out.endswith("_tiktok.mp4"))
        m = Mp4File(out)
        self.assertEqual(m.video.codec, "avc1")
        real = m.video.sample_count // opts.ghost_multiplier
        self.assertGreater(real, 100)  # ~2 s at 60 fps
        self.assertGreaterEqual(self.decoded_frames(out), real)
        info, _ = inspect(out)
        self.assertEqual(min(info["video"]["width"], info["video"]["height"]), 1080)

    def test_blocked_save_falls_back(self):
        # Windows "Controlled folder access" makes the first move fail; the file must still be saved
        from unittest import mock
        import toolkit.pipeline as pl
        real_move = shutil.move
        calls = []

        def flaky_move(a, b):
            calls.append(b)
            if len(calls) == 1:
                raise PermissionError("blocked")
            return real_move(a, b)

        fallback = os.path.join(self.dir, "fallback")
        with mock.patch.object(pl.shutil, "move", flaky_move), \
                mock.patch.object(pl, "fallback_folder", lambda: os.makedirs(fallback, exist_ok=True) or fallback):
            logs = []
            out = run(self.v60, Options(fps_patch=True, out_dir=self.dir, suffix="_blocked"), log=logs.append)
        self.assertEqual(os.path.dirname(out), fallback)
        self.assertTrue(os.path.isfile(out))
        self.assertTrue(any("blocked" in m for m in logs))

    def test_output_never_overwrites(self):
        opts = Options(fps_patch=True, out_dir=self.dir, suffix="_dup")
        a = run(self.v60, opts, log=lambda m: None)
        b = run(self.v60, opts, log=lambda m: None)
        self.assertNotEqual(a, b)
        self.assertTrue(os.path.exists(a) and os.path.exists(b))

    # ---------------------------------------------------- prepare features

    def dims(self, path):
        info = Mp4File(path).video
        w, h = inspect(path)[0]["video"]["width"], inspect(path)[0]["video"]["height"]
        return w, h, round(info.fps), round(info.seconds, 1)

    def luma(self, path):
        r = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-vf",
                            "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"],
                           capture_output=True, text=True, check=True)
        vals = [float(x.split("=")[1]) for x in r.stdout.splitlines() if "YAVG" in x]
        return sum(vals) / len(vals)

    def test_fit_blur_and_crop_make_9_16(self):
        for fit in ("blur", "crop"):
            out = self.out(f"fit_{fit}.mp4")
            prepare(self.land, out, fit=fit, encoder="cpu", fps=30)
            self.assertEqual(self.dims(out)[:2], (1080, 1920))

    def test_enhance_keeps_brightness(self):
        out = self.out("enh.mp4")
        prepare(self.land, out, enhance="strong", resolution="keep", encoder="cpu", fps=30)
        self.assertLess(abs(self.luma(out) - self.luma(self.land)), 3)

    def test_trim(self):
        out = self.out("trim.mp4")
        prepare(self.land, out, start=1, end=2.5, encoder="cpu", fps=60, resolution="keep")
        self.assertAlmostEqual(Mp4File(out).video.seconds, 1.5, delta=0.05)
        with self.assertRaises(Mp4Error):
            Options(trim_start=1, prepare=False).validate()
        self.assertEqual(parse_time("1:30"), 90)
        self.assertIsNone(parse_time(""))

    def test_gpu_encoders_detected_honestly(self):
        encs = available_encoders()
        self.assertIn("cpu", encs)
        for e in encs:
            out = self.out(f"enc_{e}.mp4")
            prepare(self.land, out, encoder=e, fps=30, resolution="keep", start=0, end=1)
            self.assertEqual(Mp4File(out).video.codec, "avc1")

    @unittest.skipUnless(find_rife()[0], "RIFE not bundled")
    def test_rife_ai_interpolation(self):
        out = self.out("ai.mp4")
        prepare(self.land, out, fps=60, interpolation="ai", start=0, end=2, resolution="keep")
        m = Mp4File(out)
        self.assertEqual(m.video.sample_count, 120)
        self.assertAlmostEqual(m.video.fps, 60, places=2)
        self.assertAlmostEqual(m.audio.seconds, 2.0, delta=0.05)

    def test_preview_side_by_side(self):
        p = make_preview(self.land, Options(prepare=True, prep_fit="blur", prep_encoder="cpu"))
        w, h, fps, secs = self.dims(p)
        self.assertEqual(h, 960)
        self.assertGreater(w, 960)
        self.assertEqual(fps, 60)


CC = [(115, 82, 68), (194, 150, 130), (98, 122, 157), (87, 108, 67), (214, 126, 44), (80, 91, 166),
      (193, 90, 99), (157, 188, 64), (243, 243, 242), (160, 160, 160), (85, 85, 85), (52, 52, 52)]


@unittest.skipUnless(FFMPEG and FFPROBE, "ffmpeg/ffprobe not found")
class ColourAndUpscaleTest(unittest.TestCase):
    """HDR -> SDR accuracy on a colour chart, colour tags, AI upscale, rotation."""

    W, H = 640, 360

    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.dir = tempfile.mkdtemp(prefix="tt_colour_")
        img = np.full((cls.H, cls.W, 3), 60, np.uint8)
        cls.patches = []
        for i, c in enumerate(CC):
            r, k = divmod(i, 6)
            x0, y0 = 20 + k * 102, 20 + r * 110
            img[y0:y0 + 90, x0:x0 + 90] = c
            cls.patches.append((y0 + 25, y0 + 65, x0 + 25, x0 + 65))
        cls.ref = img.astype(float)
        nits = ((img / 255.0) ** 2.4 @ np.array([[0.6274, 0.3293, 0.0433], [0.0691, 0.9195, 0.0114],
                                                  [0.0164, 0.0880, 0.8956]]).T) * 203.0
        nits[-40:] = np.linspace(203, 1000, cls.W)[None, :, None]  # highlights
        cls.hdr = {}
        from toolkit.color import pq_encode
        for kind, trc in (("pq", "smpte2084"), ("hlg", "arib-std-b67")):
            if kind == "pq":
                code = pq_encode(nits)
            else:
                ys = np.clip(nits / 1000.0, 0, 1) ** (1 / 1.2)
                a, b, c = 0.17883277, 0.28466892, 0.55991073
                code = np.where(ys <= 1 / 12, np.sqrt(3 * ys), a * np.log(np.maximum(12 * ys - b, 1e-9)) + c)
            path = os.path.join(cls.dir, f"hdr_{kind}.mp4")
            subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s",
                            f"{cls.W}x{cls.H}", "-r", "30", "-i", "-", "-vf",
                            "loop=29:1:0,zscale=m=bt2020nc:r=tv:min=gbr:rin=pc,format=yuv420p10le,"
                            f"setparams=color_primaries=bt2020:color_trc={trc}:colorspace=bt2020nc",
                            "-c:v", "libx265", "-x265-params", "log-level=error:crf=4", path],
                           input=(np.clip(code, 0, 1) * 65535).astype(np.uint16).tobytes(), check=True)
            cls.hdr[kind] = path
        cls.lowres = os.path.join(cls.dir, "lowres.mp4")
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=270x480:rate=30:duration=1",
                        "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                        cls.lowres], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def rgb(self, path):
        raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-frames:v", "1", "-vf",
                              "scale=in_color_matrix=bt709:in_range=tv:out_range=pc,format=rgb24",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return self.np.frombuffer(raw, self.np.uint8).reshape(self.H, self.W, 3).astype(float)

    def patch_error(self, img):
        np = self.np
        return np.mean([np.abs(img[a:b, c:d].mean((0, 1)) - self.ref[a:b, c:d].mean((0, 1))).mean()
                        for a, b, c, d in self.patches])

    def tags(self, path):
        return subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                               "stream=color_transfer,color_primaries,color_space", "-select_streams", "v:0",
                               "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()

    def test_hdr_detected_and_tone_mapped_accurately(self):
        from toolkit.color import probe_color
        for kind, path in self.hdr.items():
            self.assertEqual(probe_color(path)["kind"], kind)
            out = os.path.join(self.dir, f"sdr_{kind}.mp4")
            prepare(path, out, fps=30, resolution="keep", encoder="cpu")
            img = self.rgb(out)
            self.assertLess(self.patch_error(img), 4.0, kind)            # colours match the SDR original
            band = img[self.H - 20, 10:self.W - 10].mean(axis=1)
            self.assertGreater(band.max() - band.min(), 8, kind)          # highlight detail kept, not clipped
            self.assertEqual(self.tags(out), "bt709,bt709,bt709")

    def test_colour_off_keeps_hdr_wrong(self):
        out = os.path.join(self.dir, "nofix.mp4")
        prepare(self.hdr["pq"], out, fps=30, resolution="keep", encoder="cpu", color="off")
        self.assertGreater(self.patch_error(self.rgb(out)), 10)

    def test_tone_curve_is_monotonic_and_keeps_shadows(self):
        from toolkit.color import REFERENCE_WHITE, pq_encode, tone_curve
        np = self.np
        y = tone_curve(1000)
        self.assertTrue(np.all(np.diff(y) >= -1e-9))
        x = np.linspace(0, 1, len(y))
        i = np.searchsorted(x, pq_encode(50))  # a 50-nit shadow/mid-tone is mapped exactly
        self.assertAlmostEqual(y[i], (50 / REFERENCE_WHITE) ** (1 / 2.4), delta=0.01)

    def test_inspector_flags_hdr(self):
        info, lines = inspect(self.hdr["hlg"])
        self.assertTrue(info["video"]["colour"]["hdr"])
        self.assertTrue(any("HLG" in line for line in lines))

    @unittest.skipUnless(find_esrgan(), "Real-ESRGAN not bundled")
    def test_ai_upscale_both_models(self):
        for model in ("anime", "real"):
            out = os.path.join(self.dir, f"up_{model}.mp4")
            prepare(self.lowres, out, fps=30, upscale=model, encoder="cpu", end=0.5 if model == "real" else None)
            m = Mp4File(out)
            w, h = inspect(out)[0]["video"]["width"], inspect(out)[0]["video"]["height"]
            self.assertEqual((w, h), (1080, 1920), model)
            self.assertEqual(self.tags(out), "bt709,bt709,bt709")
            self.assertIsNotNone(m.audio)

    @unittest.skipUnless(find_esrgan(), "Real-ESRGAN not bundled")
    def test_upscale_skipped_when_already_hd(self):
        hd = os.path.join(self.dir, "hd.mp4")
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=0.3",
                        "-c:v", "libx264", hd], check=True)
        logs = []
        out = os.path.join(self.dir, "noup.mp4")
        prepare(hd, out, fps=30, resolution="1080", upscale="real", encoder="cpu", log=logs.append)
        self.assertTrue(any("skipped" in line for line in logs))

    def test_rotation_aware_probe(self):
        from toolkit.encode import probe
        rotated = os.path.join(self.dir, "rot.mp4")
        subprocess.run([FFMPEG, "-v", "error", "-y", "-display_rotation", "90", "-i", self.lowres, "-c", "copy",
                        rotated], check=True)
        p = probe(rotated)
        self.assertEqual((p["width"], p["height"]), (480, 270))


@unittest.skipUnless(FFMPEG and FFPROBE, "ffmpeg/ffprobe not found")
class PlanTest(unittest.TestCase):
    """The simple UI choices -> run plan decisions."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="tt_plan_")

        def make(name, size, rate, codec="libx264"):
            p = os.path.join(cls.dir, name)
            subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                            f"testsrc2=size={size}:rate={rate}:duration=1", "-pix_fmt", "yuv420p",
                            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                            "-c:v", codec, p], check=True)
            return p
        cls.v1080_60 = make("v1080_60.mp4", "1080x1920", 60)
        cls.h720_30 = make("h720_30.mp4", "1280x720", 30)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def plan(self, path, **kw):
        from toolkit.plan import analyze, make_plan
        src = analyze(path)
        return src, make_plan(src, Options(**kw))

    def test_orientation_detected(self):
        from toolkit.plan import analyze
        self.assertEqual(analyze(self.v1080_60)["orientation"], "vertical")
        self.assertEqual(analyze(self.h720_30)["orientation"], "horizontal")

    def test_always_upload_spec(self):
        # every export is re-encoded to MP4 / H.264 / 1080p / 50,000 kbps CBR
        for src in (self.v1080_60, self.h720_30):
            _, (run_opts, steps) = self.plan(src, out_quality="original", out_fps="original", sharpen=False)
            self.assertTrue(run_opts.prepare)
            self.assertEqual(run_opts.prep_resolution, "1080")
            self.assertIn("pl_spec", [k for k, _ in steps])

    @unittest.skipUnless(find_rife()[0], "RIFE not installed")
    def test_ai_path_keeps_colours(self):
        # the AI path (RGB frames) once decoded BT.709 video with BT.601: green shift + oversaturation
        def chroma(path):
            r = subprocess.run([FFMPEG, "-v", "info", "-i", path, "-vf",
                                "select=eq(n\\,0),signalstats,metadata=print:file=-", "-f", "null", "-"],
                               capture_output=True, text=True).stdout
            return [float(re.search(rf"{k}=([\d.]+)", r).group(1)) for k in ("UAVG", "VAVG", "SATAVG")]

        out = os.path.join(self.dir, "ai_colour.mp4")
        prepare(self.h720_30, out, fps=60, resolution="720", interpolation="ai", encoder="cpu", color="off")
        for a, b in zip(chroma(self.h720_30), chroma(out)):
            self.assertAlmostEqual(a, b, delta=2.0)

    def test_upload_spec_is_cbr_50m(self):
        out = os.path.join(self.dir, "cbr.mp4")
        prepare(self.v1080_60, out, fps=60, resolution="1080", encoder="cpu")
        r = subprocess.run([find_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,height,bit_rate", "-of", "default=nw=1", out],
                           capture_output=True, text=True).stdout
        self.assertIn("codec_name=h264", r)
        self.assertIn("height=1920", r)
        kbps = int(re.search(r"bit_rate=(\d+)", r).group(1)) / 1000
        self.assertGreater(kbps, 40000)

    def test_low_res_30fps_gets_ai_steps(self):
        _, (run_opts, steps) = self.plan(self.h720_30, out_quality="1080", out_fps="60")
        keys = [k for k, _ in steps]
        self.assertTrue(run_opts.prepare)
        self.assertEqual(run_opts.prep_resolution, "1080")
        self.assertEqual(run_opts.prep_fps, 60)
        self.assertEqual(run_opts.prep_fit, "none")   # orientation kept
        if find_esrgan():
            self.assertIn("pl_size_ai", keys)
        if find_rife()[0]:
            self.assertEqual(run_opts.prep_interpolation, "ai")

    def test_orientation_change_reframes(self):
        _, (run_opts, steps) = self.plan(self.h720_30, out_orientation="vertical", out_quality="original",
                                         out_fps="original", fill_style="crop")
        self.assertEqual((run_opts.prep_fit, run_opts.prep_orient), ("crop", "vertical"))
        self.assertIn("pl_reframe_crop", [k for k, _ in steps])

    def test_never_delivers_above_1080(self):
        # TikTok downscales anything above 1080p, so 2K/4K are AI-rendered and delivered at 1080
        _, (run_opts, steps) = self.plan(self.h720_30, out_quality="2160", out_fps="original")
        self.assertEqual(run_opts.prep_resolution, "1080")
        keys = [k for k, _ in steps]
        if find_esrgan():
            self.assertEqual(run_opts.prep_supersample, 2160)
            self.assertIn("pl_size_super", keys)
        else:
            self.assertIn("pl_size_cap", keys)

    def test_warning_for_small_reframe(self):
        _, (_, steps) = self.plan(self.h720_30, out_orientation="vertical", fill_style="blur")
        self.assertIn("pl_warn_small", [k for k, _ in steps])

    def test_trick_only_above_30fps(self):
        _, (run_opts, steps) = self.plan(self.h720_30, out_quality="original", out_fps="original")
        self.assertFalse(run_opts.fps_patch)
        self.assertIn("pl_trick_na", [k for k, _ in steps])

    def test_horizontal_reframe_output_is_16_9(self):
        out = os.path.join(self.dir, "to_h.mp4")
        prepare(self.v1080_60, out, fps=30, resolution="720", fit="blur", orient="horizontal", encoder="cpu")
        info = inspect(out)[0]["video"]
        self.assertEqual((info["width"], info["height"]), (1280, 720))

    @unittest.skipUnless(find_esrgan(), "Real-ESRGAN not bundled")
    def test_large_upscale_does_not_hang(self):
        # big frames make Real-ESRGAN print many progress lines; a full stderr pipe used to freeze it
        out = os.path.join(self.dir, "to4k.mp4")
        prepare(self.h720_30, out, fps=30, resolution="2160", upscale="anime", encoder="auto", end=0.5)
        info = inspect(out)[0]["video"]
        self.assertEqual(min(info["width"], info["height"]), 2160)


class MotionBlurTest(unittest.TestCase):
    def test_brightness_keeps_black_level(self):
        # brightness 1.2 used to be eq brightness=+0.2: every black pixel turned grey on TikTok
        from toolkit.encode import video_filter
        vf = video_filter(60, grade=(1.2, 1.0, 1.2), enhance="strong")
        self.assertIn("gamma=1.200", vf)
        self.assertNotIn("brightness=0.2", vf)
        self.assertNotIn("saturation=1.22", vf)  # enhance boost not stacked on a grade

    def test_weights_sum_to_one(self):
        from toolkit import motionblur
        for kind in motionblur.WEIGHTINGS + ("5, 3, 3, 2, 1",):
            w = motionblur.weights(9, kind)
            self.assertEqual(len(w), 9)
            self.assertAlmostEqual(sum(w), 1.0, places=6)

    def test_plan_matches_blur(self):
        from toolkit import motionblur
        # 60 fps -> 600 fps interpolation, blur amount 1 -> 10 frames, made odd like blur -> 11
        self.assertEqual(motionblur.plan(60, 60, "600", 1.0), (600, 10, 11))
        self.assertEqual(motionblur.plan(60, 60, "5x", 0.5), (300, 5, 3))

    def test_read_cfg(self):
        from toolkit import motionblur
        path = os.path.join(tempfile.mkdtemp(), "x.cfg")
        with open(path, "w", encoding="utf-8") as f:
            f.write("[blur v2]\n- blur\nblur: true\nblur amount: 0.6\nblur output fps: 60\n"
                    "blur weighting: vegas\ninterpolated fps: 480\nquality: 20\nfilters: true\nsaturation: 1.3\n")
        values, _ = motionblur.read_cfg(path)
        self.assertEqual(values["motion_blur"], True)
        self.assertEqual(values["blur_amount"], 0.6)
        self.assertEqual(values["blur_weighting"], "vegas")
        self.assertEqual(values["blur_interp"], "480")
        self.assertEqual(values["prep_crf"], 20)
        self.assertEqual(values["saturation"], 1.3)



class OfflineTest(unittest.TestCase):
    def test_translations_complete(self):
        en, ar = Translator("en"), Translator("ar")
        for key in _STRINGS:
            self.assertTrue(en(key))
            self.assertTrue(ar(key))
        self.assertTrue(ar("step1").startswith(chr(0x202B)))

    def test_extract_url(self):
        self.assertEqual(linkcheck.extract_url("look https://vm.tiktok.com/ZM123/ nice"), "https://vm.tiktok.com/ZM123/")
        with self.assertRaises(Mp4Error):
            linkcheck.extract_url("no link here")
        self.assertEqual(linkcheck.verdict(60), "smooth")
        self.assertEqual(linkcheck.verdict(30), "normal")
        self.assertEqual(linkcheck.verdict(0), "unknown")


@unittest.skipUnless(os.environ.get("TT_NETWORK_TESTS"), "set TT_NETWORK_TESTS=1 to hit TikTok")
class NetworkTest(unittest.TestCase):
    def test_check_public_video(self):
        info, _ = linkcheck.check("https://www.tiktok.com/@tiktok/video/7694797676306615583")
        self.assertTrue(info["streams"])
        self.assertGreater(info["best_fps"], 0)


if __name__ == "__main__":
    unittest.main()
