"""Installer for TikTok Quality Toolkit (built into a single Setup.exe).

Installs per-user (no admin): copies the app to
%LOCALAPPDATA%\\Programs\\TikTok Quality Toolkit, creates Start-menu and
optional desktop shortcuts, and registers an uninstaller in
"Apps & features".

Test flags: --silent --dir <folder> --no-shortcuts --no-register
"""

import argparse
import os
import shutil
import subprocess
import sys
import threading
import zipfile

APP = "TikTok Quality Toolkit"
EXE = APP + ".exe"
VERSION = "4.3.6"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TikTokQualityToolkit"
NO_WINDOW = 0x08000000


def resource(name):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), name)


def default_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", APP)


def ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, creationflags=NO_WINDOW)


def special_folder(name):
    r = ps(f"[Environment]::GetFolderPath('{name}')")
    return r.stdout.strip() or None


def make_shortcut(lnk, target, workdir):
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:TT_LNK); "
        "$s.TargetPath = $env:TT_TARGET; $s.WorkingDirectory = $env:TT_WORK; "
        "$s.IconLocation = $env:TT_TARGET + ',0'; $s.Save()"
    )
    env = dict(os.environ, TT_LNK=lnk, TT_TARGET=target, TT_WORK=workdir)
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                   env=env, capture_output=True, creationflags=NO_WINDOW, check=True)


def install(folder, desktop=True, shortcuts=True, register=True, progress=None):
    payload = resource("payload.zip")
    if not os.path.isfile(payload):
        raise RuntimeError("payload.zip missing from the installer.")
    folder = os.path.abspath(folder)
    exe = os.path.join(folder, EXE)
    if os.path.isdir(folder) and os.listdir(folder):
        # Only ever clear a folder that holds a previous install of this app.
        if not os.path.isfile(exe):
            raise RuntimeError(f"The folder is not empty and is not a {APP} install:\n{folder}\n"
                               "Choose an empty or new folder.")
        for name in os.listdir(folder):
            p = os.path.join(folder, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    os.makedirs(folder, exist_ok=True)
    with zipfile.ZipFile(payload) as z:
        items = z.infolist()
        total = sum(i.file_size for i in items) or 1
        done = 0
        for i in items:
            z.extract(i, folder)
            done += i.file_size
            if progress:
                progress(done / total * 0.95)

    links = []
    if shortcuts:
        programs = special_folder("Programs")
        if programs:
            links.append(os.path.join(programs, APP + ".lnk"))
        if desktop:
            desk = special_folder("Desktop")
            if desk:
                links.append(os.path.join(desk, APP + ".lnk"))
        for lnk in links:
            make_shortcut(lnk, exe, folder)

    uninstall = os.path.join(folder, "uninstall.cmd")
    with open(uninstall, "w", encoding="mbcs" if sys.platform == "win32" else "utf-8") as f:
        f.write("@echo off\r\n")
        f.write(f'taskkill /im "{EXE}" /f >nul 2>&1\r\n')
        for lnk in links:
            f.write(f'del /f /q "{lnk}" >nul 2>&1\r\n')
        if register:
            f.write(f'reg delete "HKCU\\{REG_KEY}" /f >nul 2>&1\r\n')
        f.write('"%SystemRoot%\\System32\\PING.EXE" -n 2 127.0.0.1 >nul\r\n')  # ~1 s pause, works without a console
        f.write('cd /d "%TEMP%"\r\n')
        # "(goto)" ends this script first, so it can delete its own folder
        f.write(f'(goto) 2>nul & rmdir /s /q "{folder}"\r\n')

    if register and sys.platform == "win32":
        import winreg
        size_kb = sum(os.path.getsize(os.path.join(dp, n)) for dp, _, fs in os.walk(folder) for n in fs) // 1024
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            for name, value in (("DisplayName", APP), ("DisplayVersion", VERSION),
                                ("Publisher", APP), ("DisplayIcon", exe), ("InstallLocation", folder),
                                ("UninstallString", f'cmd /c "{uninstall}"')):
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
            for name, value in (("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", size_kb)):
                winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)
    if progress:
        progress(1.0)
    return exe


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(f"{APP} {VERSION} Setup")
    root.resizable(False, False)
    try:
        root.iconphoto(True, tk.PhotoImage(file=resource("icon.png")))
    except Exception:
        pass
    frm = ttk.Frame(root, padding=18)
    frm.pack(fill="both")
    ttk.Label(frm, text=APP, font=("Segoe UI", 16, "bold")).pack(anchor="w")
    ttk.Label(frm, text="Install the toolkit (FFmpeg + RIFE + Real-ESRGAN AI included)\n"
                        "‫تثبيت الأداة (يشمل FFmpeg و RIFE و Real-ESRGAN للذكاء الاصطناعي)‬",
              justify="left").pack(anchor="w", pady=(2, 12))
    ttk.Label(frm, text="Install folder / مجلد التثبيت").pack(anchor="w")
    row = ttk.Frame(frm)
    row.pack(fill="x", pady=4)
    folder = tk.StringVar(value=default_dir())
    ttk.Entry(row, textvariable=folder, width=58).pack(side="left", fill="x", expand=True)
    ttk.Button(row, text="…", width=3,
               command=lambda: folder.set(os.path.join(filedialog.askdirectory() or os.path.dirname(folder.get()), APP))
               ).pack(side="left", padx=4)
    desktop = tk.BooleanVar(value=True)
    launch = tk.BooleanVar(value=True)
    ttk.Checkbutton(frm, text="Desktop shortcut / اختصار على سطح المكتب", variable=desktop).pack(anchor="w", pady=2)
    ttk.Checkbutton(frm, text="Start the app when done / تشغيل الأداة بعد التثبيت", variable=launch).pack(anchor="w", pady=2)
    bar = ttk.Progressbar(frm, maximum=1.0, length=440)
    bar.pack(fill="x", pady=(12, 6))
    status = ttk.Label(frm, text="")
    status.pack(anchor="w")
    btn = ttk.Button(frm, text="Install / تثبيت")
    btn.pack(anchor="e", pady=(8, 0))
    state = {}

    def work():
        try:
            state["exe"] = install(folder.get(), desktop.get(), progress=lambda f: state.__setitem__("p", f))
        except Exception as e:
            state["err"] = e
        state["done"] = True

    def poll():
        bar["value"] = state.get("p", 0)
        if not state.get("done"):
            root.after(100, poll)
            return
        if "err" in state:
            btn.configure(state="normal")
            messagebox.showerror("Setup", f"Installation failed:\n{state['err']}")
            return
        status.configure(text="Installed. / تم التثبيت.")
        if launch.get():
            subprocess.Popen([state["exe"]], cwd=folder.get())
        messagebox.showinfo("Setup", "Installed successfully.\nتم التثبيت بنجاح.")
        root.destroy()

    def start():
        btn.configure(state="disabled")
        status.configure(text="Installing… / جارٍ التثبيت…")
        threading.Thread(target=work, daemon=True).start()
        root.after(100, poll)

    btn.configure(command=start)
    root.mainloop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--silent", action="store_true")
    ap.add_argument("--dir", default=default_dir())
    ap.add_argument("--no-shortcuts", action="store_true")
    ap.add_argument("--no-register", action="store_true")
    args = ap.parse_args()
    if args.silent:
        # windowed build: an uncaught error would open a dialog, so report and exit instead
        try:
            exe = install(args.dir, shortcuts=not args.no_shortcuts, register=not args.no_register)
        except Exception as e:
            if sys.stderr:
                print(f"install failed: {e}", file=sys.stderr)
            sys.exit(1)
        if sys.stdout:
            print("installed", exe)
    else:
        gui()


if __name__ == "__main__":
    main()
