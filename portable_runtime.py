"""Runtime bootstrap agar aplikasi jalan baik dari source maupun dari paket
portable Windows (PyInstaller).

Dua root direktori yang dipisah secara sengaja:

- RES_DIR  : root aset read-only (templates, static, fonts, bin).
             source  -> folder repo
             frozen  -> sys._MEIPASS (folder _internal di dalam paket)
- DATA_DIR : root writable (clips, temp, cache model).
             kalau folder aplikasi writable -> dipakai langsung, supaya
             paketnya benar-benar portabel (bawa folder ke mana-mana).
             kalau tidak (mis. diekstrak ke C:\\Program Files) -> fallback
             ke %LOCALAPPDATA%\\YoutubeHeatmapClipper.

Semua tool eksternal (ffmpeg, ffprobe, yt-dlp) diambil lewat `tool()` sehingga
tidak bergantung pada PATH milik user.
"""

import os
import sys

APP_NAME = "YoutubeHeatmapClipper"
IS_FROZEN = bool(getattr(sys, "frozen", False))


def resource_dir():
    """Root aset read-only."""
    if IS_FROZEN:
        return os.path.abspath(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


def app_dir():
    """Folder tempat executable / script berada."""
    if IS_FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write-probe")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


def data_dir():
    """Root writable untuk output & cache."""
    preferred = app_dir()
    if _writable(preferred):
        return preferred
    fallback = os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME
    )
    try:
        os.makedirs(fallback, exist_ok=True)
    except Exception:
        fallback = os.path.abspath(os.getcwd())
    return fallback


def bin_dir():
    return os.path.join(resource_dir(), "bin")


def tool(name):
    """Path absolut tool bundled, fallback ke pencarian PATH.

    `name` boleh 'ffmpeg', 'ffmpeg.exe', 'yt-dlp', 'yt-dlp.exe'.
    """
    if not name:
        return name
    base, ext = os.path.splitext(name)
    suffixes = [ext] if ext else [".exe", ""]
    for suffix in suffixes:
        candidate = os.path.join(bin_dir(), base + suffix)
        if os.path.isfile(candidate):
            return candidate
    return name


def ytdlp_cmd():
    """Prefix command untuk memanggil yt-dlp.

    Paket portable shipping `yt-dlp.exe` di bin/ karena
    `sys.executable -m yt_dlp` tidak mungkin jalan ketika sys.executable
    adalah aplikasi itu sendiri.
    """
    exe = tool("yt-dlp")
    if os.path.isabs(exe):
        return [exe]
    if IS_FROZEN:
        raise RuntimeError(
            "yt-dlp tidak ditemukan di bin/ — paket portable tidak lengkap."
        )
    return [sys.executable, "-m", "yt_dlp"]


def bootstrap():
    """chdir ke DATA_DIR, expose bin/ lewat PATH, set cache model.

    Return directory data yang aktif.
    """
    target = data_dir()
    try:
        os.chdir(target)
    except Exception:
        target = os.path.abspath(os.getcwd())

    bundled_bin = bin_dir()
    if os.path.isdir(bundled_bin):
        current = os.environ.get("PATH", "")
        if bundled_bin.lower() not in current.lower():
            os.environ["PATH"] = bundled_bin + os.pathsep + current

    # Model Whisper ikut disimpan di dalam folder portable supaya aplikasi
    # tetap jalan offline setelah model terunduh sekali.
    if "HF_HOME" not in os.environ:
        os.environ["HF_HOME"] = os.path.join(target, "models", "hf")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    return target
