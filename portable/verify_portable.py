#!/usr/bin/env python3
"""Verifikasi isi paket portable SEBELUM zip / sebelum release.

Build yang hijau tidak membuktikan paketnya lengkap. Script ini membuka zip
(hasil akhir yang benar-benar dikirim ke user) dan mengecek nama file yang
benar-benar ada di dalamnya, lalu keluar non-zero kalau ada yang kurang.

Usage:
    python portable/verify_portable.py dist/YoutubeHeatmapClipper_v2.0.47_x64_portable.zip
    python portable/verify_portable.py <zip> --expect-whisper
    python portable/verify_portable.py <zip> --list
"""

import argparse
import os
import sys
import zipfile

# Nama-nama ini = kontrak runtime aplikasi. Kalau salah satu hilang, aplikasi
# bisa "berjalan" tapi gagal saat dipakai user.
REQUIRED = [
    "YoutubeHeatmapClipper.exe",
    "_internal/VERSION",
    "_internal/templates/index.html",
    "_internal/static/app.js",
    "_internal/static/style.css",
    "_internal/bin/ffmpeg.exe",
    "_internal/bin/ffprobe.exe",
    "_internal/bin/yt-dlp.exe",
]

REQUIRED_FONTS = [
    "_internal/fonts/Roboto/static/Roboto-Regular.ttf",
]

REQUIRED_PYTHON = [
    "_internal/python311.dll",
]

# Kalau flashdisk / OneDrive tidak punya symlink, beberapa model whisper gagal
# di-cache; bukan berarti paket rusak, jadi hanya dicek sebagai info.
WHISPER_MARKERS = [
    "_internal/faster_whisper/__init__.py",
    "_internal/ctranslate2/__init__.py",
    "_internal/tokenizers/__init__.py",
]


def human(n):
    return "%.1f MiB" % (n / 1024 / 1024)


def main():
    ap = argparse.ArgumentParser(description="Verifikasi paket portable Windows")
    ap.add_argument("zip_path")
    ap.add_argument("--expect-whisper", action="store_true",
                    help="wajib ada modul faster-whisper di dalam paket")
    ap.add_argument("--platform", choices=["windows", "any"], default="windows",
                    help="windows = punglikan .exe/DLL (default). any = relaxed, "
                         "untuk dry-run paket non-Windows")
    ap.add_argument("--list", action="store_true", help="tampilkan daftar isi lalu keluar")
    args = ap.parse_args()

    if not os.path.isfile(args.zip_path):
        print("FAIL  zip tidak ditemukan: %s" % args.zip_path)
        return 2

    required = list(REQUIRED) + list(REQUIRED_FONTS)
    if args.platform != "windows":
        required = [
            r for r in required
            if not r.endswith(".exe") and not r.endswith(".dll")
        ] + ["_internal/bin/ffmpeg", "_internal/bin/ffprobe", "_internal/bin/yt-dlp"]

    size = os.path.getsize(args.zip_path)
    try:
        zf = zipfile.ZipFile(args.zip_path)
    except zipfile.BadZipFile as exc:
        print("FAIL  file bukan zip yang valid / korup: %s" % exc)
        return 2
    with zf:
        names = [n.replace("\\", "/") for n in zf.namelist()]
        bad = zf.testzip()
        if bad is not None:
            print("FAIL  zip korup di entri: %s" % bad)
            return 2

        if args.list:
            for n in sorted(names)[:200]:
                print("  %s" % n)
            print("... total %d entri" % len(names))
            return 0

        if args.expect_whisper:
            required += WHISPER_MARKERS
        if args.platform == "windows":
            # Versi Python bisa berbeda mengikuti runner; yang wajib ada DLL-nya.
            has_py_dll = any(n.endswith(".dll") and "python3" in n for n in names)
            if not has_py_dll:
                required += REQUIRED_PYTHON

        missing = []
        for want in required:
            if not any(n == want or n.endswith("/" + want) for n in names):
                missing.append(want)

        font_count = sum(1 for n in names if n.lower().endswith((".ttf", ".otf")))
        exe_count = sum(1 for n in names if n.lower().endswith(".exe"))

    print("zip    : %s" % os.path.basename(args.zip_path))
    print("ukuran : %d bytes (%s)" % (size, human(size)))
    print("entri  : %d  |  .exe=%d  |  font=%d" % (len(names), exe_count, font_count))

    if missing:
        print("FAIL  %d file wajib tidak ada di dalam paket:" % len(missing))
        for m in missing:
            print("   - %s" % m)
        return 1

    if font_count < 5:
        print("FAIL  jumlah font di paket terlalu sedikit (%d). Cek langkah copy fonts di build." % font_count)
        return 1

    print("PASS  semua %d file wajib ada." % len(required))
    return 0


if __name__ == "__main__":
    sys.exit(main())
