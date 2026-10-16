"""Build the release: portable app folder + single-file installer.

    python build_tools/build.py [output folder]

Needs PyInstaller and Pillow, plus ffmpeg/, rife/ and esrgan/ folders in the project.
Output goes to ../Release (next to the project folder) unless a folder is given;
the work folder lives in %TEMP% (Windows "Controlled folder access" can block
build tools from writing inside Documents).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = "TikTok Quality Toolkit"
WORK = os.path.join(tempfile.gettempdir(), "tt_toolkit_build")
RELEASE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "Release")


def pyinstaller(*args):
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--log-level", "WARN",
                    "--workpath", os.path.join(WORK, "build"), "--specpath", WORK, *args], check=True)


def main():
    for need in ("ffmpeg/ffmpeg.exe", "ffmpeg/ffprobe.exe", "rife/rife-ncnn-vulkan.exe",
                 "esrgan/realesrgan-ncnn-vulkan.exe"):
        if not os.path.isfile(os.path.join(HERE, need)):
            sys.exit(f"missing {need}")
    if not os.path.isfile(os.path.join(HERE, "icon.ico")):
        subprocess.run([sys.executable, os.path.join(HERE, "build_tools", "make_icon.py")], check=True)
    shutil.rmtree(WORK, ignore_errors=True)
    icon_ico, icon_png = os.path.join(HERE, "icon.ico"), os.path.join(HERE, "icon.png")

    # 1. the app, as a folder (fast start, ffmpeg/rife sit next to the exe)
    dist = os.path.join(WORK, "dist")
    pyinstaller("--windowed", "--onedir", "--name", APP, "--icon", icon_ico,
                "--add-data", f"{icon_png};.", "--distpath", dist, os.path.join(HERE, "tiktok_toolkit.py"))
    app_dir = os.path.join(dist, APP)
    for folder in ("ffmpeg", "rife", "esrgan"):
        shutil.copytree(os.path.join(HERE, folder), os.path.join(app_dir, folder))
    for doc in ("README.md", os.path.join("..", "USER_GUIDE.html")):
        src = os.path.join(HERE, doc)
        if os.path.isfile(src):
            shutil.copy2(src, app_dir)

    # 2. payload for the installer
    payload = os.path.join(WORK, "payload.zip")
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dp, _, files in os.walk(app_dir):
            for n in files:
                full = os.path.join(dp, n)
                z.write(full, os.path.relpath(full, app_dir))

    # 3. the installer
    os.makedirs(RELEASE, exist_ok=True)
    pyinstaller("--windowed", "--onefile", "--name", f"{APP} Setup", "--icon", icon_ico,
                "--add-data", f"{payload};.", "--add-data", f"{icon_png};.", "--distpath", RELEASE,
                os.path.join(HERE, "build_tools", "setup_app.py"))

    # 4. portable copy
    portable = os.path.join(RELEASE, f"{APP} (portable)")
    shutil.rmtree(portable, ignore_errors=True)
    shutil.copytree(app_dir, portable)
    shutil.rmtree(WORK, ignore_errors=True)
    for name in sorted(os.listdir(RELEASE)):
        p = os.path.join(RELEASE, name)
        size = os.path.getsize(p) if os.path.isfile(p) else sum(
            os.path.getsize(os.path.join(dp, n)) for dp, _, fs in os.walk(p) for n in fs)
        print(f"{size / 1e6:8.1f} MB  {name}")


if __name__ == "__main__":
    main()
