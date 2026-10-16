"""Dark ttk theme (built on 'clam') + dark Windows title bar."""

import sys
import tkinter as tk
from tkinter import ttk

BG = "#0f0f13"        # window
PANEL = "#17171d"     # surfaces
PANEL2 = "#22222a"    # secondary buttons, hover
FIELD = "#1d1d24"     # inputs / segmented track
BORDER = "#2d2d37"
FG = "#f1f1f4"
MUTED = "#9d9dab"
DIM = "#5f5f6d"
ACCENT = "#fe2c55"    # single brand accent, used sparingly
ACCENT_HI = "#ff4a6e"
DISABLED = "#3a2730"
SEL_BG = "#f1f1f4"    # selected segment
SEL_FG = "#111116"
PHONE = "#060608"
CYAN = MUTED          # section captions stay neutral
GOOD = "#3ddc84"
WARN = "#ffb547"
FONT = "Segoe UI"


def apply(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    root.configure(bg=BG)
    s.configure(".", background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=BORDER,
                lightcolor=PANEL, darkcolor=PANEL, troughcolor=FIELD, focuscolor=PANEL,
                selectbackground=ACCENT, selectforeground="#ffffff", insertcolor=FG,
                font=(FONT, 10))
    s.configure("TFrame", background=BG)
    s.configure("Card.TFrame", background=PANEL)
    s.configure("TLabel", background=BG, foreground=FG)
    s.configure("Card.TLabel", background=PANEL, foreground=FG)
    s.configure("Muted.Card.TLabel", background=PANEL, foreground=MUTED, font=(FONT, 9))
    s.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(FONT, 9))
    s.configure("Title.TLabel", background=BG, foreground=FG, font=(FONT, 17, "bold"))
    s.configure("CardTitle.Card.TLabel", background=PANEL, foreground=FG, font=(FONT, 11, "bold"))
    s.configure("Section.Card.TLabel", background=PANEL, foreground=CYAN, font=(FONT, 9, "bold"))
    s.configure("Summary.Card.TLabel", background=PANEL, foreground=CYAN, font=(FONT, 10, "bold"))
    s.configure("Good.TLabel", background=BG, foreground=GOOD, font=(FONT, 13, "bold"))
    s.configure("Warn.TLabel", background=BG, foreground=WARN, font=(FONT, 13, "bold"))
    s.configure("Plain.TLabel", background=BG, foreground=FG, font=(FONT, 13, "bold"))

    s.configure("TButton", background=PANEL2, foreground=FG, bordercolor=BORDER, lightcolor=PANEL2,
                darkcolor=PANEL2, padding=(12, 6), relief="flat", focusthickness=0)
    s.map("TButton", background=[("disabled", PANEL), ("pressed", BORDER), ("active", "#31313f")],
          foreground=[("disabled", DIM)])
    s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", lightcolor=ACCENT, darkcolor=ACCENT,
                bordercolor=ACCENT, font=(FONT, 11, "bold"), padding=(26, 9))
    s.map("Accent.TButton", background=[("disabled", "#4a2535"), ("pressed", "#e0306c"), ("active", ACCENT_HI)],
          foreground=[("disabled", "#9a7080")], bordercolor=[("disabled", "#4a2535")])

    for name, bg in (("TCheckbutton", BG), ("Card.TCheckbutton", PANEL)):
        s.configure(name, background=bg, foreground=FG, indicatorbackground=FIELD, indicatorforeground="#ffffff",
                    indicatormargin=(0, 0, 8, 0), indicatorsize=16, padding=2, focusthickness=0)
        s.map(name, background=[("active", bg)],
              indicatorbackground=[("selected", ACCENT), ("disabled", PANEL2)],
              foreground=[("disabled", DIM)])
    s.configure("Toggle.Card.TCheckbutton", font=(FONT, 11, "bold"))

    common = dict(fieldbackground=FIELD, background=PANEL2, foreground=FG, arrowcolor=FG,
                  bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD, padding=(6, 4))
    s.configure("TCombobox", **common)
    s.map("TCombobox", fieldbackground=[("readonly", FIELD), ("disabled", PANEL)],
          foreground=[("disabled", DIM), ("readonly", FG)], arrowcolor=[("disabled", DIM)],
          selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", FG)],
          bordercolor=[("focus", ACCENT)])
    s.configure("TEntry", fieldbackground=FIELD, foreground=FG, bordercolor=BORDER, lightcolor=FIELD,
                darkcolor=FIELD, padding=(6, 4))
    s.map("TEntry", fieldbackground=[("disabled", PANEL)], foreground=[("disabled", DIM)],
          bordercolor=[("focus", ACCENT)])
    s.configure("TSpinbox", **common)
    s.map("TSpinbox", fieldbackground=[("disabled", PANEL)], foreground=[("disabled", DIM)],
          arrowcolor=[("disabled", DIM)], bordercolor=[("focus", ACCENT)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))

    s.configure("TNotebook", background=BG, bordercolor=BG, tabmargins=(0, 4, 0, 0))
    s.configure("TNotebook.Tab", background=BG, foreground=MUTED, bordercolor=BG, lightcolor=BG,
                padding=(18, 8), font=(FONT, 10, "bold"))
    s.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", FG)],
          lightcolor=[("selected", PANEL)], bordercolor=[("selected", PANEL)])
    s.configure("Inner.TNotebook", background=PANEL, bordercolor=PANEL)
    s.configure("Inner.TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(14, 6), bordercolor=PANEL,
                lightcolor=PANEL)
    s.map("Inner.TNotebook.Tab", background=[("selected", PANEL2)], foreground=[("selected", FG)],
          lightcolor=[("selected", PANEL2)], bordercolor=[("selected", PANEL2)])

    s.configure("Accent.Horizontal.TProgressbar", troughcolor=FIELD, background=ACCENT, bordercolor=FIELD,
                lightcolor=ACCENT, darkcolor=ACCENT, thickness=6)
    s.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=PANEL, bordercolor=PANEL,
                arrowcolor=MUTED, lightcolor=PANEL2, darkcolor=PANEL2)
    s.map("Vertical.TScrollbar", background=[("active", BORDER)])
    s.configure("TSeparator", background=BORDER)
    s.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=FG, bordercolor=BORDER,
                lightcolor=FIELD, darkcolor=FIELD, rowheight=28, font=(FONT, 10))
    s.map("Treeview", background=[("selected", PANEL2)], foreground=[("selected", FG)])
    s.configure("Treeview.Heading", background=PANEL, foreground=MUTED, bordercolor=BORDER, lightcolor=PANEL,
                darkcolor=PANEL, relief="flat", font=(FONT, 9, "bold"), padding=(8, 6))
    s.map("Treeview.Heading", background=[("active", PANEL2)])
    setup_checkbuttons(root)


def style_tk(widget, mono=False):
    """Colour a classic tk widget (Listbox / Text) to match."""
    widget.configure(bg=FIELD, fg=FG, selectbackground=ACCENT, selectforeground="#ffffff",
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                     bd=0, relief="flat", font=("Consolas", 9) if mono else (FONT, 10))
    if isinstance(widget, tk.Text):
        widget.configure(insertbackground=FG, padx=8, pady=6)


def dark_title_bar(root):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        value = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass


# ------------------------------------------------------------- check boxes

_IMAGES = []


def _indicator_images(size=18):
    from PIL import Image, ImageDraw, ImageTk
    scale = 4  # draw large, downsample for smooth edges
    big = size * scale

    def make(fill, border, tick):
        im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((2, 2, big - 3, big - 3), radius=big // 4, fill=fill, outline=border, width=scale * 2)
        if tick:
            d.line([(big * 0.26, big * 0.52), (big * 0.43, big * 0.70), (big * 0.75, big * 0.32)],
                   fill=tick, width=int(scale * 2.6), joint="curve")
        return ImageTk.PhotoImage(im.resize((size, size), Image.LANCZOS))

    imgs = {
        "off": make(FIELD, BORDER, None),
        "on": make(ACCENT, ACCENT, "#ffffff"),
        "off_dis": make(PANEL, PANEL2, None),
        "on_dis": make("#4a2535", "#4a2535", "#9a7080"),
    }
    _IMAGES.append(imgs)  # keep references alive
    return imgs


def setup_checkbuttons(root):
    """Custom tick-box indicator; 'Rtl…' styles put the box on the right."""
    s = ttk.Style(root)
    imgs = _indicator_images()
    for name, pad in (("tt.indicatorL", (0, 0, 9, 0)), ("tt.indicatorR", (9, 0, 0, 0))):
        s.element_create(name, "image", imgs["off"],
                         ("disabled", "selected", imgs["on_dis"]), ("disabled", imgs["off_dis"]),
                         ("selected", imgs["on"]), sticky="", padding=pad)
    for rtl in (False, True):
        side = "right" if rtl else "left"
        layout = [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("tt.indicatorR" if rtl else "tt.indicatorL", {"side": side, "sticky": ""}),
            ("Checkbutton.focus", {"side": side, "sticky": "nswe", "children": [
                ("Checkbutton.label", {"sticky": "nswe"})]})]})]
        for name, bg, bold in (("TCheckbutton", BG, False), ("Card.TCheckbutton", PANEL, False),
                               ("Toggle.Card.TCheckbutton", PANEL, True)):
            style = ("Rtl" + name) if rtl else name
            s.layout(style, layout)
            s.configure(style, background=bg, foreground=FG, padding=(2, 3),
                        font=(FONT, 11, "bold") if bold else (FONT, 10))
            s.map(style, background=[("active", bg)], foreground=[("disabled", DIM)])


def cb(style, rtl):
    return ("Rtl" + style) if rtl else style
