"""Main window (English / Arabic).

Export page: a phone preview that turns with the output orientation, and
three choices - orientation, quality, frame rate. plan.make_plan() decides
everything else from the source video; technical options live in the
Advanced settings dialog.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import webbrowser
from dataclasses import asdict, replace
from tkinter import filedialog, messagebox, ttk

from . import __version__, dnd, linkcheck, motionblur
from . import theme as T
from .color import color_filter
from .encode import ENCODERS, ENHANCE, GRADE_MAX, GRADE_MIN, NO_WINDOW, UPSCALE, find_tool, parse_time
from .i18n import Translator
from .inspector import inspect
from .pipeline import Options, run
from .plan import analyze, make_plan, quality_name
from .preview import make_preview
from .widgets import Button, NavTabs, PhoneView, ProgressLine, Segmented, Switch, compose

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

VIDEO_TYPES = "*.mp4 *.MP4 *.mov *.MOV *.m4v *.mkv *.webm *.avi"
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=webapp&tab=video"
AI_STEPS = {"pl_hdr", "pl_size_ai", "pl_fps_ai", "pl_size_super", "pl_blur"}


# ------------------------------------------------------------------ helpers


def settings_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "TikTokToolkit", "settings.json")


def load_settings():
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data = json.load(f)
        known = Options.__dataclass_fields__
        opts = Options(**{k: v for k, v in data.items() if k in known and k != "extra"})
        for k in ("saturation", "contrast", "brightness"):  # older versions allowed up to 2.0
            setattr(opts, k, min(GRADE_MAX, max(GRADE_MIN, float(getattr(opts, k)))))
        return opts
    except Exception:
        return Options()


def save_settings(opts):
    try:
        os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
        data = asdict(opts)
        data.pop("extra", None)
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, name)


def downloads_dir():
    d = os.path.join(os.path.expanduser("~"), "Videos", "TikTok Toolkit")
    os.makedirs(d, exist_ok=True)
    return d


def open_path(path):
    if sys.platform == "win32" and path:
        os.startfile(path)  # noqa: S606 - opening the user's own output


def fmt_time(seconds):
    if seconds is None:
        return ""
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}" if m else f"{s:g}"


def fmt_duration(seconds):
    seconds = int(round(seconds or 0))
    return f"{seconds // 60}:{seconds % 60:02d}"


def thumbnail(path, src):
    """One frame of the video as a PIL image (HDR already tone-mapped)."""
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg or Image is None:
        return None
    tmp = tempfile.mkdtemp(prefix="tt_thumb_")
    try:
        vf = []
        if src["colour"]["kind"] != "sdr":
            vf += [color_filter(src["colour"], tmp), "scale=in_color_matrix=bt709:in_range=tv"]
        vf.append("scale=w=720:h=720:force_original_aspect_ratio=decrease")
        at = min(1.0, (src["duration"] or 0) * 0.3)
        out = os.path.join(tmp, "frame.png")
        subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", path, "-frames:v", "1",
                        "-vf", ",".join(vf), out], cwd=tmp, capture_output=True, timeout=60, creationflags=NO_WINDOW)
        img = Image.open(out)
        img.load()
        return img.convert("RGB")
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class _DropSink:
    """Adapter so dropped paths arrive in the app's event queue as ('drop', paths)."""

    def __init__(self, events):
        self.events = events

    def put(self, paths):
        self.events.put(("drop", paths))


class Choice:
    """A readonly combobox over (key -> translated label)."""

    def __init__(self, parent, t, keys, prefix, value, width):
        self.labels = {k: t(prefix + k) for k in keys}
        self.var = tk.StringVar(value=self.labels.get(value, next(iter(self.labels.values()))))
        self.widget = ttk.Combobox(parent, textvariable=self.var, values=list(self.labels.values()),
                                   state="readonly", width=width)

    def get(self):
        return {v: k for k, v in self.labels.items()}[self.var.get()]


# ----------------------------------------------------------------------- app


class App:
    def __init__(self, files=()):
        self.root = tk.Tk()
        self.root.geometry("1200x910")
        self.root.minsize(1120, 880)
        try:
            self._icon = tk.PhotoImage(file=resource_path("icon.png"))
            self.root.iconphoto(True, self._icon)
        except Exception:
            self._icon = None
        T.apply(self.root)
        T.dark_title_bar(self.root)

        self.events = queue.Queue()
        self.cancel_flag = threading.Event()
        self.busy = False
        self.opts = load_settings()
        self.files, self.infos, self.current = [], {}, 0
        self.log_lines = []
        self.page = "export"
        self.last_output_dir = None
        self.last_output_file = None
        self.last_download_dir = None
        self.check_result = None
        self.log_win = None
        self.container = None
        self.build()
        self.add_files(files)
        try:
            dnd.enable(self.root, _DropSink(self.events))
        except Exception:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.poll)
        if not find_tool("ffmpeg"):
            self.log(self.t("ffmpeg_missing"))

    # ------------------------------------------------------------- building

    def build(self):
        if self.container is not None:
            self.container.destroy()
        t = self.t = Translator(self.opts.language)
        self.rtl = t.rtl
        self.side, self.far = ("right", "left") if self.rtl else ("left", "right")
        self.anchor = "e" if self.rtl else "w"
        self.justify = "right" if self.rtl else "left"
        self.root.title(f"{t('title')} {__version__}")
        self.container = tk.Frame(self.root, bg=T.BG)
        self.container.pack(fill="both", expand=True)

        hdr = tk.Frame(self.container, bg=T.BG)
        hdr.pack(fill="x", padx=28, pady=(16, 0))
        brand = tk.Frame(hdr, bg=T.BG)
        brand.pack(side=self.side)
        if self._icon is not None:
            self._logo = self._icon.subsample(16)
            tk.Label(brand, image=self._logo, bg=T.BG).pack(side=self.side)
        tk.Label(brand, text=t("title"), bg=T.BG, fg=T.FG, font=(T.FONT, 14, "bold")).pack(side=self.side, padx=10)
        self.nav = NavTabs(hdr, [("export", t("nav_export")), ("check", t("nav_check"))], self.page,
                           self.show_page, rtl=self.rtl)
        self.nav.pack(side=self.side, padx=30, pady=(6, 0))
        tools = tk.Frame(hdr, bg=T.BG)
        tools.pack(side=self.far)
        Button(tools, t("help"), lambda: messagebox.showinfo(t("help"), t("help_text")), kind="ghost",
               bg=T.BG).pack(side=self.far)
        Segmented(tools, [("en", "English"), ("ar", "العربية")], t.lang, self.change_language, bg=T.BG,
                  rtl=self.rtl, height=34, min_w=84).pack(side=self.far, padx=10)

        body = tk.Frame(self.container, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(14, 24))
        self.pages = {"export": self.build_export(body), "check": self.build_check(body)}
        self.show_page(self.page)
        self.refresh()
        self.set_busy(self.busy)

    def pad(self, before=0, after=0):
        return (after, before) if self.rtl else (before, after)

    def label(self, parent, text, size=10, color=None, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=color or T.FG,
                        font=(T.FONT, size, "bold" if bold else "normal"), justify=self.justify, **kw)

    def show_page(self, key):
        self.page = key
        for k, frame in self.pages.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    # --------------------------------------------------------- export page

    def build_export(self, body):
        t = self.t
        page = tk.Frame(body, bg=T.BG)
        lcol, rcol = (1, 0) if self.rtl else (0, 1)
        page.columnconfigure(lcol, minsize=480)
        page.columnconfigure(rcol, weight=1)
        page.rowconfigure(0, weight=1)
        left = tk.Frame(page, bg=T.PANEL)
        right = tk.Frame(page, bg=T.PANEL)
        left.grid(row=0, column=lcol, sticky="nsew", padx=self.pad(0, 8))
        right.grid(row=0, column=rcol, sticky="nsew", padx=self.pad(8, 0))

        # left: phone preview + file
        self.phone = PhoneView(left, size=(480, 430), bg=T.PANEL, on_click=self._phone_click)
        self.phone.pack(pady=(18, 0))
        self.file_name = self.label(left, "", 12, bold=True)
        self.file_name.pack(pady=(2, 0))
        self.file_info = self.label(left, "", 10, T.MUTED)
        self.file_info.pack()
        nav = self.queue_nav = tk.Frame(left, bg=T.PANEL)
        back, fwd = ("›", "‹") if self.rtl else ("‹", "›")
        self.prev_btn = Button(nav, back, lambda: self.step_video(-1), width=38, height=32)
        self.counter = self.label(nav, "", 10, T.MUTED, width=12)
        self.next_btn = Button(nav, fwd, lambda: self.step_video(1), width=38, height=32)
        for w in (self.prev_btn, self.counter, self.next_btn):
            w.pack(side=self.side, padx=4)
        self.all_note = self.label(left, "", 9, T.DIM)
        self.all_note.pack(pady=(4, 0))
        btns = tk.Frame(left, bg=T.PANEL)
        btns.pack(side="bottom", pady=20)
        Button(btns, "+  " + t("add_videos"), self.browse).pack(side=self.side, padx=4)
        self.remove_btn = Button(btns, t("remove"), self.remove_current)
        self.remove_btn.pack(side=self.side, padx=4)
        self.inspect_btn = Button(btns, t("inspect"), self.inspect_current)
        self.inspect_btn.pack(side=self.side, padx=4)

        # right: the three choices, switches, plan, actions
        inner = tk.Frame(right, bg=T.PANEL)
        inner.pack(fill="both", expand=True, padx=32, pady=(20, 18))
        bottom = tk.Frame(inner, bg=T.PANEL)
        bottom.pack(side="bottom", fill="x")
        def caption(key, first=False):
            self.label(inner, t(key), 10, T.MUTED, bold=True).pack(anchor=self.anchor, pady=(0 if first else 12, 5))

        caption("orientation", first=True)
        row = tk.Frame(inner, bg=T.PANEL)
        row.pack(fill="x")
        self.seg_orient = Segmented(row, [("vertical", t("o_vertical")), ("horizontal", t("o_horizontal"))],
                                    "vertical", self.on_orient, rtl=self.rtl, min_w=140,
                                    icons={"vertical": "portrait", "horizontal": "landscape"})
        self.seg_orient.pack(side=self.side)
        self.orient_note = self.label(row, "", 9, T.DIM)
        self.orient_note.pack(side=self.side, padx=14)
        caption("res_title")
        self.seg_quality = Segmented(inner, [("original", t("original"))], self.opts.out_quality, self.on_quality,
                                     rtl=self.rtl, min_w=74)
        self.seg_quality.pack(anchor=self.anchor)
        # only shown when the plan uses AI upscaling
        self.model_row = tk.Frame(inner, bg=T.PANEL)
        self.label(self.model_row, t("content_type"), 10, T.MUTED, bold=True).pack(anchor=self.anchor, pady=(12, 5))
        mrow = tk.Frame(self.model_row, bg=T.PANEL)
        mrow.pack(fill="x")
        self.seg_model = Segmented(mrow, [("real", t("ct_real")), ("anime", t("ct_anime"))],
                                   self.opts.upscale_model if self.opts.upscale_model != "off" else "real",
                                   self.on_model, rtl=self.rtl, min_w=120)
        self.seg_model.pack(side=self.side)
        self.model_note = self.label(mrow, "", 9, T.DIM)
        self.model_note.pack(side=self.side, padx=14)
        self.fps_caption = self.label(inner, t("fps_title"), 10, T.MUTED, bold=True)
        self.fps_caption.pack(anchor=self.anchor, pady=(12, 5))
        self.seg_fps = Segmented(inner, [("original", t("original"))], self.opts.out_fps, self.on_fps,
                                 rtl=self.rtl, min_w=74)
        self.seg_fps.pack(anchor=self.anchor)

        tk.Frame(inner, height=1, bg=T.BORDER).pack(fill="x", pady=(18, 4))
        self.sw_colour = self.switch_row(inner, "colour_switch", "colour_desc", self.opts.prep_color == "auto",
                                         self.on_colour)
        self.sw_trick = self.switch_row(inner, "trick_switch", "trick_desc", self.opts.tiktok_trick, self.on_trick)
        self.sw_sharpen = self.switch_row(inner, "sharpen_switch", "sharpen_desc", self.opts.sharpen,
                                          self.on_sharpen)
        tk.Frame(inner, height=1, bg=T.BORDER).pack(fill="x", pady=(4, 0))

        self.label(inner, t("plan_title"), 10, T.MUTED, bold=True).pack(anchor=self.anchor, pady=(12, 4))
        self.plan_box = tk.Frame(inner, bg=T.PANEL)
        self.plan_box.pack(fill="x")

        actions = tk.Frame(bottom, bg=T.PANEL)
        actions.pack(fill="x")
        Button(actions, t("advanced"), self.open_advanced, kind="ghost").pack(side=self.side)
        self.export_btn = Button(actions, t("export_btn"), self.start, kind="primary", width=170)
        self.export_btn.pack(side=self.far)
        self.preview_btn = Button(actions, t("preview_short"), self.preview, height=46)
        self.preview_btn.pack(side=self.far, padx=10)
        # shown once an export finished
        self.upload_btn = Button(actions, "UPLOAD TO TIKTOK", self.upload_to_tiktok, height=46)
        status = tk.Frame(bottom, bg=T.PANEL)
        status.pack(fill="x", pady=(12, 0))
        self.progress = ProgressLine(status)
        self.progress.pack(fill="x")
        srow = tk.Frame(status, bg=T.PANEL)
        srow.pack(fill="x", pady=(8, 0))
        self.status = self.label(srow, t("status_ready"), 10, T.MUTED)
        self.status.pack(side=self.side)
        details = self.label(srow, t("show_details"), 10, T.MUTED, cursor="hand2")
        details.configure(font=(T.FONT, 10, "underline"))
        details.pack(side=self.far)
        details.bind("<Button-1>", lambda e: self.show_log())
        self.cancel_link = self.label(srow, t("cancel"), 10, T.ACCENT, cursor="hand2")
        self.cancel_link.bind("<Button-1>", lambda e: self.cancel_flag.set())
        self.open_link = self.label(srow, t("open_output"), 10, T.FG, cursor="hand2")
        self.open_link.configure(font=(T.FONT, 10, "underline"))
        self.open_link.bind("<Button-1>", lambda e: open_path(self.last_output_dir))
        return page

    def switch_row(self, parent, title, desc, value, command):
        row = tk.Frame(parent, bg=T.PANEL)
        row.pack(fill="x", pady=3)
        sw = Switch(row, value, command)
        sw.pack(side=self.far)
        # title and description on one line keeps room for the plan below
        self.label(row, self.t(title), 11, bold=True).pack(side=self.side)
        self.label(row, self.t(desc), 9, T.MUTED).pack(side=self.side, padx=12)
        return sw

    # ---------------------------------------------------------- check page

    def build_check(self, body):
        t = self.t
        page = tk.Frame(body, bg=T.BG)
        card = tk.Frame(page, bg=T.PANEL)
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg=T.PANEL)
        inner.pack(fill="both", expand=True, padx=32, pady=26)
        self.label(inner, t("nav_check"), 15, bold=True).pack(anchor=self.anchor)
        self.label(inner, t("check_intro"), 10, T.MUTED, wraplength=900).pack(anchor=self.anchor, pady=(4, 16))
        row = tk.Frame(inner, bg=T.PANEL)
        row.pack(fill="x")
        self.check_btn = Button(row, t("check"), lambda: self.check(False), kind="primary", width=140)
        self.check_btn.pack(side=self.far, padx=self.pad(12, 0))
        self.v_url = tk.StringVar(value=getattr(self, "_url", ""))
        e = ttk.Entry(row, textvariable=self.v_url, font=(T.FONT, 11))
        e.pack(side=self.side, fill="x", expand=True, ipady=6)
        e.bind("<Return>", lambda ev: self.check(False))

        self.result_box = tk.Frame(inner, bg=T.PANEL)
        self.result_box.pack(fill="x")
        self.verdict = tk.Frame(self.result_box, bg=T.FIELD)
        self.verdict_dot = tk.Canvas(self.verdict, width=14, height=14, bg=T.FIELD, highlightthickness=0)
        self.verdict_dot.pack(side=self.side, padx=16, pady=14)
        self.verdict_text = tk.Label(self.verdict, text="", bg=T.FIELD, fg=T.FG, font=(T.FONT, 12, "bold"),
                                     justify=self.justify)
        self.verdict_text.pack(side=self.side, pady=14)
        cols = ("name", "res", "fps", "codec", "rate", "size")
        heads = {"name": t("col_stream"), "res": t("col_res"), "fps": "FPS", "codec": t("col_codec"),
                 "rate": t("col_rate"), "size": t("col_size")}
        order = tuple(reversed(cols)) if self.rtl else cols
        self.tree = ttk.Treeview(self.result_box, columns=order, show="headings", height=6, selectmode="none")
        for c in order:
            self.tree.heading(c, text=heads[c], anchor="e" if self.rtl else "w")
            self.tree.column(c, width=220 if c == "name" else 120, anchor="e" if self.rtl else "w")

        acts = tk.Frame(inner, bg=T.PANEL)
        acts.pack(side="bottom", fill="x", pady=(16, 0))
        self.download_btn = Button(acts, t("download"), lambda: self.check(True))
        self.download_btn.pack(side=self.side)
        Button(acts, t("open_folder"), lambda: open_path(self.last_download_dir or downloads_dir()),
               kind="ghost").pack(side=self.side, padx=8)
        self.check_progress = ProgressLine(acts)
        self.check_progress.pack(side=self.side, fill="x", expand=True, padx=8)
        self.check_details = self.label(inner, "", 9, T.MUTED, wraplength=900)
        self.check_details.pack(side="bottom", anchor=self.anchor, pady=(12, 0))
        if self.check_result:
            self.show_check_result(*self.check_result)
        return page

    # ------------------------------------------------------------ state

    def src(self):
        if not self.files:
            return None
        info = self.infos.get(self.files[self.current])
        return info[0] if info else None

    def out_orient(self, src=None):
        src = src or self.src()
        if self.opts.out_orientation in ("vertical", "horizontal"):
            return self.opts.out_orientation
        return src["orientation"] if src else "vertical"

    def refresh(self):
        """Update the export page from the current video and choices."""
        t, src = self.t, self.src()
        orient = self.out_orient(src)
        self.seg_orient.set(orient)
        if src and orient != src["orientation"]:
            self.orient_note.configure(text=t("orient_changed"))
        else:
            self.orient_note.configure(text=t("orient_auto") if src else "")
        q_orig = t("orig_of", v=quality_name(src["short"])) if src and src["short"] else t("original")
        f_orig = t("orig_of", v=f"{src['fps']:.0f}") if src and src["fps"] else t("original")
        self.seg_quality.set_options([("original", q_orig), ("1080", "1080p"),
                                      ("1440", "2K"), ("2160", "4K")])
        self.seg_fps.set_options([("original", f_orig), ("30", "30"), ("60", "60"), ("120", "120")])
        self.seg_quality.set(self.opts.out_quality)
        self.seg_fps.set(self.opts.out_fps)

        if not self.files:
            self.phone.show(None, "vertical", t("drop_here"))
            self.file_name.configure(text="")
            self.file_info.configure(text="")
        elif src is None:
            self.phone.show(None, orient, t("analyzing"))
            self.file_name.configure(text=os.path.basename(self.files[self.current]))
            self.file_info.configure(text="")
        else:
            frame = self.infos[self.files[self.current]][1]
            img = compose(frame, src["orientation"], orient, self.opts.fill_style,
                          PhoneView.SCREEN[orient]) if frame is not None else None
            self.phone.show(img, orient, t("analyzing"))
            self.file_name.configure(text=os.path.basename(src["path"]))
            parts = [f"{src['width']}×{src['height']}", f"{src['fps']:.0f} fps", fmt_duration(src["duration"])]
            if src["colour"]["kind"] != "sdr":
                parts.append("HDR")
            self.file_info.configure(text="   ·   ".join(parts))
        multi = len(self.files) > 1
        if multi:
            self.queue_nav.pack(pady=(10, 0), before=self.all_note)
        else:
            self.queue_nav.pack_forget()
        self.counter.configure(text=t("of", i=self.current + 1, n=len(self.files)) if self.files else "")
        self.all_note.configure(text=t("all_videos", n=len(self.files)) if multi else "")
        self.remove_btn.set_enabled(bool(self.files))
        self.inspect_btn.set_enabled(bool(self.files))
        self.render_plan(src)

    def render_plan(self, src):
        for w in self.plan_box.winfo_children():
            w.destroy()
        if not src:
            self.model_row.pack_forget()
            self.label(self.plan_box, self.t("plan_empty"), 10, T.DIM).pack(anchor=self.anchor)
            return
        run_opts, steps = make_plan(src, self.opts)
        if run_opts.prep_upscale != "off":
            self.seg_model.set(run_opts.prep_upscale)
            self.model_note.configure(text=self.t("ct_" + run_opts.prep_upscale + "_note"))
            self.model_row.pack(fill="x", before=self.fps_caption)
        else:
            self.model_row.pack_forget()
        for key, params in steps:
            params = dict(params)
            if "o" in params:
                params["o"] = self.t("o_" + params["o"])
            row = tk.Frame(self.plan_box, bg=T.PANEL)
            row.pack(fill="x", pady=1)
            dot = tk.Canvas(row, width=10, height=10, bg=T.PANEL, highlightthickness=0)
            warn = key.startswith("pl_warn")
            dot.create_oval(1, 1, 9, 9, fill=T.WARN if warn else (T.ACCENT if key in AI_STEPS else T.DIM),
                            outline="")
            dot.pack(side=self.side, padx=self.pad(0, 10))
            self.label(row, self.t(key, **params), 10, wraplength=560).pack(side=self.side)

    # ------------------------------------------------------------ events

    def on_orient(self, key):
        src = self.src()
        self.opts.out_orientation = "auto" if (src and key == src["orientation"]) else key
        self.refresh()

    def on_quality(self, key):
        self.opts.out_quality = key
        self.refresh()

    def on_model(self, key):
        self.opts.upscale_model = key
        self.refresh()

    def on_fps(self, key):
        self.opts.out_fps = key
        self.refresh()

    def on_colour(self, value):
        self.opts.prep_color = "auto" if value else "off"
        self.refresh()

    def on_sharpen(self, value):
        self.opts.sharpen = value
        self.refresh()

    def on_trick(self, value):
        self.opts.tiktok_trick = value
        self.refresh()

    def change_language(self, key):
        self.opts.language = key
        self._url = self.v_url.get()
        save_settings(self.opts)
        self.build()

    def step_video(self, delta):
        if self.files:
            self.current = (self.current + delta) % len(self.files)
            self.refresh()

    def _phone_click(self):
        if not self.files:
            self.browse()

    def add_files(self, paths):
        added = []
        for p in paths:
            p = os.path.abspath(p)
            if os.path.isfile(p) and p not in self.files:
                self.files.append(p)
                added.append(p)
        if added:
            self.current = self.files.index(added[0])
            for p in added:
                threading.Thread(target=self._analyze, args=(p,), daemon=True).start()
            self.refresh()
            self.set_busy(self.busy)

    def _analyze(self, path):
        try:
            src = analyze(path)
            self.emit("analyzed", (path, src, thumbnail(path, src)))
        except Exception as e:
            self.emit("log", self.t("cannot_inspect", name=os.path.basename(path), msg=e))

    def browse(self):
        self.add_files(filedialog.askopenfilenames(
            title=self.t("add_videos"), filetypes=[("Video", VIDEO_TYPES), ("*", "*.*")]))

    def remove_current(self):
        if self.files and not self.busy:
            self.infos.pop(self.files.pop(self.current), None)
            self.current = max(0, min(self.current, len(self.files) - 1))
            self.refresh()
            self.set_busy(self.busy)

    def inspect_current(self):
        if not self.files:
            return
        path = self.files[self.current]
        try:
            for line in inspect(path)[1]:
                self.log(line)
        except Exception as e:
            self.log(self.t("cannot_inspect", name=os.path.basename(path), msg=e))
        self.show_log()

    # --------------------------------------------------------- dialogs

    def dialog(self, title):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=T.PANEL)
        win.transient(self.root)
        T.dark_title_bar(win)
        return win

    def open_advanced(self):
        t, o = self.t, self.opts
        win = self.dialog(t("advanced"))
        win.resizable(False, False)
        frm = tk.Frame(win, bg=T.PANEL)
        frm.pack(fill="both", expand=True, padx=28, pady=24)
        lc, cc = (1, 0) if self.rtl else (0, 1)

        def row(r, key, widget, stretch=True):
            self.label(frm, t(key), 10, T.MUTED).grid(row=r, column=lc, sticky=self.anchor,
                                                     padx=self.pad(0, 18), pady=6)
            widget.grid(row=r, column=cc, sticky="ew" if stretch else self.anchor, pady=6)

        c_fill = Choice(frm, t, ("blur", "crop"), "fl_", o.fill_style, 36)
        row(0, "fill", c_fill.widget)
        c_frames = Choice(frm, t, ("ai", "motion", "blend"), "i_", o.frames_method, 36)
        row(1, "frames", c_frames.widget)
        c_up = Choice(frm, t, UPSCALE, "u_", o.upscale_model, 36)
        row(2, "upscale", c_up.widget)
        c_enh = Choice(frm, t, ENHANCE, "en_", o.prep_enhance, 36)
        row(3, "enhance", c_enh.widget)
        c_enc = Choice(frm, t, ENCODERS, "e_", o.prep_encoder, 36)
        row(4, "encoder", c_enc.widget)
        v_crf = tk.StringVar(value=str(o.prep_crf))
        row(5, "crf_label", ttk.Spinbox(frm, textvariable=v_crf, from_=0, to=35, width=6), stretch=False)
        trim = tk.Frame(frm, bg=T.PANEL)
        v_ts, v_te = tk.StringVar(value=fmt_time(o.trim_start)), tk.StringVar(value=fmt_time(o.trim_end))
        for w in (self.label(trim, t("trim_from"), 10, T.MUTED), ttk.Entry(trim, textvariable=v_ts, width=9),
                  self.label(trim, t("trim_to"), 10, T.MUTED), ttk.Entry(trim, textvariable=v_te, width=9)):
            w.pack(side=self.side, padx=self.pad(0, 6))
        row(6, "trim", trim, stretch=False)
        c_mode = Choice(frm, t, ("method", "slowmo"), "m_", o.fps_mode, 46)
        row(7, "trick_mode", c_mode.widget)
        sw_ghost = Switch(frm, o.ghost)
        row(8, "st3", sw_ghost, stretch=False)

        # motion blur, like f0e/blur
        tk.Frame(frm, height=1, bg=T.BORDER).grid(row=9, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        sw_blur = Switch(frm, o.motion_blur)
        row(10, "motion_blur", sw_blur, stretch=False)
        v_amount = tk.StringVar(value=f"{o.blur_amount:g}")
        row(11, "blur_amount", ttk.Spinbox(frm, textvariable=v_amount, from_=0.05, to=3, increment=0.05, width=6),
            stretch=False)
        v_interp = tk.StringVar(value=o.blur_interp)
        row(12, "blur_interp", ttk.Combobox(frm, textvariable=v_interp, width=10,
                                            values=("300", "480", "600", "960", "5x", "10x")), stretch=False)
        v_weight = tk.StringVar(value=o.blur_weighting)
        row(13, "blur_weighting", ttk.Combobox(frm, textvariable=v_weight, width=20,
                                               values=motionblur.WEIGHTINGS), stretch=False)
        grade = tk.Frame(frm, bg=T.PANEL)
        v_grade = [tk.StringVar(value=f"{x:g}") for x in o.grade()]
        for var in v_grade:
            ttk.Spinbox(grade, textvariable=var, from_=GRADE_MIN, to=GRADE_MAX, increment=0.05, width=5).pack(
                side=self.side, padx=self.pad(0, 6))
        row(14, "grade", grade, stretch=False)

        tk.Frame(frm, height=1, bg=T.BORDER).grid(row=15, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        out = tk.Frame(frm, bg=T.PANEL)
        v_out = tk.StringVar(value=o.out_dir or "")
        Button(out, t("browse"), lambda: v_out.set(filedialog.askdirectory(parent=win) or v_out.get())
               ).pack(side=self.far, padx=self.pad(8, 0))
        ttk.Entry(out, textvariable=v_out, width=30).pack(side=self.side, fill="x", expand=True)
        row(16, "output_title", out)
        self.label(frm, t("output_hint"), 9, T.DIM).grid(row=17, column=cc, sticky=self.anchor)

        def collect():
            ts, te = parse_time(v_ts.get()), parse_time(v_te.get())
            crf = int(v_crf.get())
            if ts and te and te <= ts:
                raise ValueError(t("invalid", name=t("trim")))
            amount = float(v_amount.get())
            sat, con, bri = (min(GRADE_MAX, max(GRADE_MIN, float(v.get()))) for v in v_grade)
            interp = v_interp.get().strip().lower()
            motionblur.plan(30, 60, interp, amount)  # validates "600" / "5x"
            folder = v_out.get().strip() or None
            if folder and not os.path.isdir(folder):
                raise ValueError(t("no_outdir"))
            return replace(self.opts, fill_style=c_fill.get(), frames_method=c_frames.get(),
                           upscale_model=c_up.get(), prep_enhance=c_enh.get(), prep_encoder=c_enc.get(),
                           prep_crf=crf, trim_start=ts, trim_end=te, fps_mode=c_mode.get(),
                           ghost=sw_ghost.get(), out_dir=folder, motion_blur=sw_blur.get(), blur_amount=amount,
                           blur_interp=interp, blur_weighting=v_weight.get().strip() or "equal",
                           saturation=sat, contrast=con, brightness=bri)

        def save():
            try:
                self.opts = collect()
            except Exception as e:
                messagebox.showerror(t("advanced"), str(e), parent=win)
                return
            save_settings(self.opts)
            win.destroy()
            self.refresh()

        def import_cfg():
            path = filedialog.askopenfilename(parent=win, title=t("import_cfg"),
                                              filetypes=[("blur config", "*.cfg"), ("*", "*.*")])
            if not path:
                return
            try:
                values, notes = motionblur.read_cfg(path)
            except Exception as e:
                messagebox.showerror(t("import_cfg"), t("cfg_failed", msg=e), parent=win)
                return
            self.opts = replace(self.opts, **values)
            save_settings(self.opts)
            win.destroy()
            self.refresh()
            messagebox.showinfo(t("import_cfg"), "\n".join([t("cfg_imported", name=os.path.basename(path))]
                                                          + [f"• {n}" for n in notes]))
            self.open_advanced()

        bar = tk.Frame(frm, bg=T.PANEL)
        bar.grid(row=18, column=0, columnspan=2, sticky="ew", pady=(20, 0))
        Button(bar, t("close"), save, kind="primary", width=140).pack(side=self.far)
        Button(bar, t("import_cfg"), import_cfg).pack(side=self.side)

        def reset():
            # the look that holds up best on TikTok: no extra colour, no blur, real-footage AI model
            self.opts = replace(self.opts, prep_enhance="off", saturation=1.0, contrast=1.0, brightness=1.0,
                                motion_blur=False, upscale_model="real", frames_method="ai")
            save_settings(self.opts)
            win.destroy()
            self.refresh()
            self.open_advanced()

        Button(bar, t("reset_recommended"), reset).pack(side=self.side, padx=self.pad(8, 0))
        win.grab_set()

    def show_log(self):
        if self.log_win is not None and self.log_win.winfo_exists():
            self.log_win.lift()
            return
        win = self.log_win = self.dialog(self.t("log_title"))
        win.geometry("820x460")
        frame = tk.Frame(win, bg=T.PANEL)
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        self.log_text = tk.Text(frame, wrap="word", state="disabled")
        T.style_tk(self.log_text, mono=True)
        sb = ttk.Scrollbar(frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side=self.far, fill="y")
        self.log_text.pack(side=self.side, fill="both", expand=True)
        self.log_text.tag_configure("rtl", justify="right", font=(T.FONT, 10))
        for line in self.log_lines:
            self._append(self.log_text, line)

    def _append(self, widget, msg):
        widget.configure(state="normal")
        arabic = any("؀" <= c <= "ۿ" for c in msg)
        widget.insert("end", msg + "\n", ("rtl",) if arabic else ())
        widget.see("end")
        widget.configure(state="disabled")

    def log(self, msg):
        self.log_lines.append(msg)
        if self.log_win is not None and self.log_win.winfo_exists():
            self._append(self.log_text, msg)

    # ------------------------------------------------------------ actions

    def set_busy(self, busy):
        self.busy = busy
        self.export_btn.set_enabled(not busy)
        self.preview_btn.set_enabled(not busy and bool(self.files))
        self.check_btn.set_enabled(not busy)
        self.download_btn.set_enabled(not busy)
        if busy:
            self.open_link.pack_forget()
            self.cancel_link.pack(side=self.far, padx=14)
        else:
            self.cancel_link.pack_forget()

    def spawn(self, target, *args):
        self.cancel_flag.clear()
        self.set_busy(True)
        threading.Thread(target=target, args=args, daemon=True).start()

    def emit(self, kind, data=None):
        self.events.put((kind, data))

    def _tools_ok(self):
        if not find_tool("ffmpeg"):
            messagebox.showerror(self.t("export_btn"), self.t("need_ffmpeg"))
            return False
        return True

    def start(self):
        if not self.files:
            self.browse()
            return
        if not self._tools_ok():
            return
        save_settings(self.opts)
        self.progress["value"] = 0
        self.spawn(self.work, list(self.files), replace(self.opts))

    def work(self, files, opts):
        ok, out, errors = 0, None, []
        for n, path in enumerate(files):
            if self.cancel_flag.is_set():
                break
            self.emit("status", self.t("status_working", n=n + 1, total=len(files)))
            self.emit("log", f"\n=== [{n + 1}/{len(files)}] {os.path.basename(path)}")
            try:
                info = self.infos.get(path)
                src = info[0] if info else analyze(path)
                run_opts, _ = make_plan(src, opts)
                if not run_opts.any_step():  # nothing to change: still produce a clean copy
                    run_opts = replace(run_opts, prepare=True)
                out = run(path, run_opts, log=lambda m: self.emit("log", m),
                          progress=lambda f, n=n: self.emit("progress", (n + f) / len(files)),
                          cancel=self.cancel_flag.is_set)
                self.emit("log", self.t("saved", path=out))
                ok += 1
            except Exception as e:
                self.emit("log", self.t("error", msg=e))
                errors.append(f"{os.path.basename(path)}:\n{e}")
        self.emit("done", (ok, len(files), out, errors))

    def preview(self):
        src = self.src()
        if not src or not self._tools_ok():
            return
        run_opts, _ = make_plan(src, self.opts)
        if not run_opts.prepare:
            messagebox.showinfo(self.t("preview_short"), self.t("pl_instant"))
            return
        self.progress["value"] = 0
        self.status.configure(text=self.t("rendering_preview", s=6), fg=T.MUTED)
        self.spawn(self.preview_work, src["path"], run_opts)

    def preview_work(self, path, opts):
        try:
            out = make_preview(path, opts, progress=lambda f: self.emit("progress", f),
                               cancel=self.cancel_flag.is_set, log=lambda m: self.emit("log", m))
            self.emit("preview_done", out)
        except Exception as e:
            self.emit("log", self.t("error", msg=e))
            self.emit("preview_done", None)

    def check(self, download):
        url = self.v_url.get().strip()
        if not url:
            return
        self.check_progress["value"] = 0
        self.verdict.pack_forget()
        self.tree.pack_forget()
        self.check_details.configure(text=self.t("checking"))
        self.spawn(self.check_work, url, download)

    def check_work(self, url, download):
        t = self.t
        try:
            info, session = linkcheck.check(url)
            best = info["best_fps"]
            lines = [f"@{info['author']}   {info['title']}",
                     t("via", src="TikTok" if info["source"] == "tiktok" else "tikwm.com")
                     + f"   ·   {info['duration']}s"
                     + (f"   ·   VQScore {info['vqscore']}" if info.get("vqscore") else "")]
            if download:
                folder = downloads_dir()
                name = f"tiktok_{info['url'].rstrip('/').split('/')[-1].split('?')[0]}.mp4"
                dest = os.path.join(folder, name)
                linkcheck.download(info, session, dest, progress=lambda f: self.emit("cprogress", f),
                                   cancel=self.cancel_flag.is_set)
                self.last_download_dir = folder
                result, _ = inspect(dest)
                v = result.get("video") or {}
                lines.append(t("saved_to", path=dest))
                if v:
                    lines.append(f"{v['width']}×{v['height']}   ·   {v['fps']:.2f} fps   ·   {v['codec']}")
                if not best and v.get("fps"):
                    best = round(v["fps"])
            self.emit("check_result", (info, best, "\n".join(lines)))
        except Exception as e:
            self.emit("check_result", (None, 0, t("error", msg=e)))

    def show_check_result(self, info, best, details):
        self.check_result = (info, best, details)
        self.check_details.configure(text=details)
        if not info:
            return
        verdict = linkcheck.verdict(best)
        text = self.t("v_" + verdict)
        if best:
            text = self.t("best_fps", fps=best) + "   ·   " + text
        color = {"smooth": T.GOOD, "normal": T.WARN}.get(verdict, T.MUTED)
        self.verdict_dot.delete("all")
        self.verdict_dot.create_oval(1, 1, 13, 13, fill=color, outline="")
        self.verdict_text.configure(text=text, fg=color)
        self.verdict.pack(fill="x", pady=(18, 0))
        self.tree.pack(fill="x", pady=(14, 0))
        self.tree.delete(*self.tree.get_children())
        for s in info["streams"]:
            vals = {"name": s["name"], "res": f"{s['width']}×{s['height']}" if s["width"] else "?",
                    "fps": s["fps"] or "?", "codec": s["codec"],
                    "rate": f"{s['mbps']:.2f} Mbps" if s["mbps"] else "",
                    "size": f"{s['size'] / 1e6:.1f} MB" if s["size"] else ""}
            self.tree.insert("", "end", values=[vals[c] for c in self.tree["columns"]])

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "drop":
                    self.add_files(data)
                elif kind == "analyzed":
                    path, src, frame = data
                    if path in self.files:
                        self.infos[path] = (src, frame)
                        if self.files[self.current] == path:
                            self.refresh()
                elif kind == "log":
                    self.log(data)
                elif kind == "status":
                    self.status.configure(text=data, fg=T.MUTED)
                elif kind == "progress":
                    self.progress["value"] = data
                elif kind == "cprogress":
                    self.check_progress["value"] = data
                elif kind == "check_result":
                    self.check_progress["value"] = 1.0
                    self.set_busy(False)
                    self.show_check_result(*data)
                elif kind == "preview_done":
                    self.set_busy(False)
                    self.status.configure(text=self.t("status_ready"), fg=T.MUTED)
                    if data:
                        self.progress["value"] = 1.0
                        open_path(data)
                elif kind == "done":
                    ok, total, out, errors = data
                    self.set_busy(False)
                    self.log("\n" + self.t("finished", ok=ok, total=total))
                    if ok == total and out:
                        self.progress["value"] = 1.0
                        self.last_output_dir = os.path.dirname(out)
                        saved_next_to_source = all(
                            os.path.dirname(os.path.abspath(f)) == self.last_output_dir for f in self.files)
                        text = (self.t("status_done") if saved_next_to_source and not self.opts.out_dir
                                else self.t("status_done_dir", path=self.last_output_dir))
                        self.status.configure(text=text, fg=T.GOOD)
                        self.open_link.pack(side=self.far, padx=14)
                        self.last_output_file = out
                        self.upload_btn.pack(side=self.far)
                    else:
                        self.status.configure(text=self.t("status_failed"), fg=T.WARN)
                    if errors and not self.cancel_flag.is_set():
                        messagebox.showerror(self.t("export_failed"), "\n\n".join(errors[:3]))
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def upload_to_tiktok(self):
        """Open TikTok Studio's upload page and show the exported file, selected, ready to drag in.

        A browser never lets another program fill a web page's file box, so the drag is the user's."""
        out = self.last_output_file
        if not out or not os.path.isfile(out):
            messagebox.showinfo("UPLOAD TO TIKTOK", self.t("upload_no_file"))
            return
        webbrowser.open(TIKTOK_UPLOAD_URL)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(out)])  # noqa: S603,S607
        self.status.configure(text=self.t("upload_hint"), fg=T.FG)

    def on_close(self):
        if self.busy:
            if not messagebox.askyesno(self.t("quit"), self.t("running_quit")):
                return
            self.cancel_flag.set()
        save_settings(self.opts)
        self.root.destroy()

    def mainloop(self):
        self.root.mainloop()


def run_gui(files=()):
    App(files).mainloop()
