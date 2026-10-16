"""Hand-drawn controls for the main window: segmented picker, switch,
buttons, nav tabs and the phone preview. Plain Tk canvases so they look
the same on every Windows version."""

import tkinter as tk
import tkinter.font as tkfont

from . import theme as T

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except ImportError:  # pragma: no cover - Pillow is bundled
    Image = None


def _rounded(c, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


class Segmented(tk.Canvas):
    """Segmented control: one choice out of a few, all visible."""

    def __init__(self, parent, options, value, command=None, bg=T.PANEL, rtl=False, height=38, min_w=64,
                 icons=None):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.font = tkfont.Font(family=T.FONT, size=10)
        self.font_sel = tkfont.Font(family=T.FONT, size=10, weight="bold")
        self.command, self.rtl, self.h, self.min_w = command, rtl, height, min_w
        self.icons = icons or {}
        self.value, self.hover = value, None
        self.set_options(options)
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))

    def set_options(self, options):
        self.options = list(options)
        self.widths = {k: max(self.min_w, self.font_sel.measure(label) + 32 + (22 if k in self.icons else 0))
                       for k, label in self.options}
        self.configure(width=sum(self.widths.values()) + 8)
        self.draw()

    def _spans(self):
        x, out = 4, []
        for key, label in self._order():
            out.append((key, label, x, x + self.widths[key]))
            x += self.widths[key]
        return out

    def _order(self):
        return list(reversed(self.options)) if self.rtl else self.options

    def draw(self):
        self.delete("all")
        w = sum(self.widths.values()) + 8
        _rounded(self, 1, 1, w - 1, self.h - 1, 12, fill=T.FIELD, outline=T.BORDER)
        for key, label, x1, x2 in self._spans():
            if key == self.value:
                _rounded(self, x1, 4, x2, self.h - 4, 9, fill=T.SEL_BG, outline=T.SEL_BG)
                color, font = T.SEL_FG, self.font_sel
            else:
                color, font = (T.FG if key == self.hover else T.MUTED), self.font
            cx, cy = (x1 + x2) / 2, self.h / 2
            icon = self.icons.get(key)
            if icon:
                tw = font.measure(label)
                ix = cx - (tw + 22) / 2 + 7
                iw, ih = (8, 13) if icon == "portrait" else (14, 8)
                self.create_rectangle(ix - iw / 2, cy - ih / 2, ix + iw / 2, cy + ih / 2, outline=color, width=2)
                cx += 11
            self.create_text(cx, cy, text=label, fill=color, font=font)

    def _key_at(self, x):
        for key, _, x1, x2 in self._spans():
            if x1 <= x < x2:
                return key
        return None

    def _click(self, e):
        key = self._key_at(e.x)
        if key is not None and key != self.value:
            self.value = key
            self.draw()
            if self.command:
                self.command(key)

    def _motion(self, e):
        self._set_hover(self._key_at(e.x))

    def _set_hover(self, key):
        if key != self.hover:
            self.hover = key
            self.draw()

    def get(self):
        return self.value

    def set(self, key):
        self.value = key
        self.draw()


class Switch(tk.Canvas):
    def __init__(self, parent, value, command=None, bg=T.PANEL):
        super().__init__(parent, width=46, height=26, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.value, self.command = bool(value), command
        self.bind("<Button-1>", self.toggle)
        self.draw()

    def draw(self):
        self.delete("all")
        on = self.value
        _rounded(self, 1, 2, 45, 24, 11, fill=T.ACCENT if on else T.BORDER, outline=T.ACCENT if on else T.BORDER)
        x = 33 if on else 13
        self.create_oval(x - 9, 4, x + 9, 22, fill="#ffffff" if on else T.MUTED, outline="")

    def toggle(self, _e=None):
        self.set(not self.value)
        if self.command:
            self.command(self.value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)
        self.draw()


class Button(tk.Canvas):
    """Rounded button. kind: primary | secondary | ghost."""

    STYLES = {
        "primary": (T.ACCENT, T.ACCENT_HI, "#ffffff", ("bold", 11)),
        "secondary": (T.PANEL2, T.BORDER, T.FG, ("normal", 10)),
        "ghost": (None, T.PANEL2, T.MUTED, ("normal", 10)),
    }

    def __init__(self, parent, text, command, kind="secondary", bg=T.PANEL, height=None, width=None):
        self.kind = kind
        weight, size = self.STYLES[kind][3]
        self.font = tkfont.Font(family=T.FONT, size=size, weight=weight)
        self.h = height or (46 if kind == "primary" else 36)
        self.w = width or self.font.measure(text) + (56 if kind == "primary" else 32)
        super().__init__(parent, width=self.w, height=self.h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.text, self.command, self.enabled, self.hover = text, command, True, False
        self.bind("<Button-1>", lambda e: self.enabled and self.command and self.command())
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.draw()

    def _hover(self, h):
        self.hover = h
        self.draw()

    def draw(self):
        self.delete("all")
        base, hi, fg, _ = self.STYLES[self.kind]
        if not self.enabled:
            fill, fg = (T.DISABLED if self.kind == "primary" else (T.PANEL2 if base else None)), T.DIM
        else:
            fill = hi if self.hover else base
        if fill:
            _rounded(self, 1, 1, self.w - 1, self.h - 1, 10, fill=fill, outline=fill)
        self.create_text(self.w / 2, self.h / 2, text=self.text, fill=fg, font=self.font)
        self.configure(cursor="hand2" if self.enabled else "arrow")

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.draw()


class ProgressLine(tk.Canvas):
    """Thin progress line; supports widget["value"] = fraction like ttk.Progressbar."""

    def __init__(self, parent, bg=T.PANEL, height=4):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0)
        self.value = 0.0
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), int(self["height"])
        self.create_rectangle(0, 0, w, h, fill=T.FIELD, outline="")
        if self.value > 0:
            self.create_rectangle(0, 0, max(2, w * min(1.0, self.value)), h, fill=T.ACCENT, outline="")

    def __setitem__(self, key, value):
        if key == "value":
            self.value = float(value)
            self.draw()
        else:
            super().__setitem__(key, value)


class NavTabs(tk.Frame):
    """Text tabs with an underline for the active page."""

    def __init__(self, parent, items, value, command, bg=T.BG, rtl=False):
        super().__init__(parent, bg=bg)
        self.labels, self.value, self.command = {}, value, command
        for key, text in (reversed(items) if rtl else items):
            cell = tk.Frame(self, bg=bg)
            cell.pack(side="left", padx=(0, 26))
            lab = tk.Label(cell, text=text, bg=bg, font=(T.FONT, 11, "bold"), cursor="hand2", pady=4)
            lab.pack()
            bar = tk.Frame(cell, height=3, bg=bg)
            bar.pack(fill="x")
            lab.bind("<Button-1>", lambda e, k=key: self.select(k))
            self.labels[key] = (lab, bar)
        self.select(value, notify=False)

    def select(self, key, notify=True):
        self.value = key
        for k, (lab, bar) in self.labels.items():
            lab.configure(fg=T.FG if k == key else T.MUTED)
            bar.configure(bg=T.ACCENT if k == key else self["bg"])
        if notify:
            self.command(key)


class PhoneView(tk.Canvas):
    """Phone mock-up that turns with the output orientation and shows the frame."""

    SCREEN = {"vertical": (198, 352), "horizontal": (352, 198)}

    def __init__(self, parent, size=(420, 420), bg=T.PANEL, on_click=None):
        super().__init__(parent, width=size[0], height=size[1], bg=bg, highlightthickness=0, bd=0)
        self.size, self.bg = size, bg
        self._photo = None
        if on_click:
            self.bind("<Button-1>", lambda e: on_click())
        self.show(None, "vertical", "")

    def show(self, image, orient, empty_text):
        """image: PIL image already composed to the screen aspect, or None."""
        self.delete("all")
        sw, sh = self.SCREEN[orient]
        bezel = 11
        cx, cy = self.size[0] / 2, self.size[1] / 2
        x1, y1 = cx - sw / 2 - bezel, cy - sh / 2 - bezel
        x2, y2 = cx + sw / 2 + bezel, cy + sh / 2 + bezel
        # side buttons
        if orient == "vertical":
            self.create_rectangle(x2, y1 + 70, x2 + 3, y1 + 120, fill=T.BORDER, outline="")
            self.create_rectangle(x1 - 3, y1 + 60, x1, y1 + 90, fill=T.BORDER, outline="")
        else:
            self.create_rectangle(x1 + 70, y1 - 3, x1 + 120, y1, fill=T.BORDER, outline="")
            self.create_rectangle(x1 + 60, y2, x1 + 90, y2 + 3, fill=T.BORDER, outline="")
        _rounded(self, x1, y1, x2, y2, 34, fill=T.PHONE, outline=T.BORDER, width=2)
        sx1, sy1 = cx - sw / 2, cy - sh / 2
        if image is not None and Image is not None:
            img = image.resize((sw, sh), Image.LANCZOS).convert("RGB")
            mask = Image.new("L", (sw, sh), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw - 1, sh - 1), radius=24, fill=255)
            canvas = Image.new("RGB", (sw, sh), T.PHONE)
            canvas.paste(img, (0, 0), mask)
            self._photo = ImageTk.PhotoImage(canvas)
            self.create_image(sx1, sy1, image=self._photo, anchor="nw")
        else:
            _rounded(self, sx1, sy1, sx1 + sw, sy1 + sh, 24, fill=T.FIELD, outline=T.FIELD)
            self.create_text(cx, cy, text=empty_text, fill=T.MUTED, font=(T.FONT, 11), justify="center",
                             width=sw - 30)
            self.configure(cursor="hand2")
        # camera punch-hole
        if orient == "vertical":
            self.create_oval(cx - 5, sy1 + 9, cx + 5, sy1 + 19, fill="#000000", outline=T.BORDER)
        else:
            self.create_oval(sx1 + 9, cy - 5, sx1 + 19, cy + 5, fill="#000000", outline=T.BORDER)


def compose(frame, src_orient, out_orient, fill, screen):
    """Return how the frame will look in the output (PIL image of `screen` size)."""
    sw, sh = screen
    fw, fh = frame.size
    if src_orient != out_orient:
        if fill == "crop":
            s = max(sw / fw, sh / fh)
            img = frame.resize((max(1, int(fw * s)), max(1, int(fh * s))), Image.LANCZOS)
            left, top = (img.width - sw) // 2, (img.height - sh) // 2
            return img.crop((left, top, left + sw, top + sh))
        s = max(sw / fw, sh / fh)
        bg = frame.resize((max(1, int(fw * s)), max(1, int(fh * s))), Image.LANCZOS)
        left, top = (bg.width - sw) // 2, (bg.height - sh) // 2
        bg = bg.crop((left, top, left + sw, top + sh)).filter(ImageFilter.GaussianBlur(14))
        bg = Image.blend(bg, Image.new("RGB", bg.size, (0, 0, 0)), 0.25)
    else:
        bg = Image.new("RGB", (sw, sh), (0, 0, 0))
    s = min(sw / fw, sh / fh)
    fg = frame.resize((max(1, int(fw * s)), max(1, int(fh * s))), Image.LANCZOS)
    bg.paste(fg, ((sw - fg.width) // 2, (sh - fg.height) // 2))
    return bg
