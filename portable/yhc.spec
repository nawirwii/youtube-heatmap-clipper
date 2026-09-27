# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec untuk paket portable Windows.

Layout hasil build (onedir):

    YoutubeHeatmapClipper.exe
    _internal/
        templates/  static/  fonts/  bin/{ffmpeg,ffprobe,yt-dlp}.exe
        VERSION  python313.dll  ... (runtime PyInstaller)

`portable_runtime.resource_dir()` mengembalikan folder `_internal`, jadi aset
dibaca dari sana — bukan dari CWD — sehingga exe bisa dijalankan dari folder
mana pun.
"""

import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
BIN_DIR = os.path.join(ROOT, "bin")
ICON = os.path.join(ROOT, "portable", "assets", "app.ico")

APP_NAME = "YoutubeHeatmapClipper"
# Whitelist: hanya file ini yang boleh ikut ke bin/. Kalau folder bin/ berisi
# sisa file lokal, jangan dib blindly-copy.
EXTERNAL_TOOLS = ("ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe")

datas = [
    (os.path.join(ROOT, "templates"), "templates"),
    (os.path.join(ROOT, "static"), "static"),
    (os.path.join(ROOT, "fonts"), "fonts"),
    (os.path.join(ROOT, "VERSION"), "."),
    (os.path.join(ROOT, "README.md"), "."),
    (os.path.join(ROOT, "LICENSE"), "."),
]

binaries = []
missing_tools = []
for name in EXTERNAL_TOOLS:
    candidate = os.path.join(BIN_DIR, name)
    if os.path.isfile(candidate):
        binaries.append((candidate, "bin"))
    else:
        missing_tools.append(name)

# faster-whisper & friends: hanya dikumpulkan kalau benar-benar terpasang,
# supaya spec tetap jalan untuk build tanpa subtitle AI.
WHISPER_PACKAGES = (
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "av",
    "onnxruntime",
    "huggingface_hub",
)

hiddenimports = [
    "run",
    "webapp",
    "ai_meta",
    "ai_config",
    "portable_runtime",
    "werkzeug.middleware.proxy_fix",
]

for package in WHISPER_PACKAGES:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [os.path.join(ROOT, "launcher.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "notebook",
        "pytest",
        "setuptools",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    icon=ICON if os.path.isfile(ICON) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if missing_tools:
    print("[spec] PERINGATAN: tool ini tidak ada di bin/: %s" % ", ".join(missing_tools))
    print("[spec] Jalankan portable/fetch-deps.ps1 sebelum build.")
