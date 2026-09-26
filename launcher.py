"""Entry point untuk paket portable Windows (PyInstaller).

Perilakunya:

    YoutubeHeatmapClipper.exe                 -> web app + browser otomatis
    YoutubeHeatmapClipper.exe --port 5050     -> ganti port
    YoutubeHeatmapClipper.exe --no-browser    -> tanpa membuka browser
    YoutubeHeatmapClipper.exe --url <link> ... -> mode CLI (fitur run.py)
    YoutubeHeatmapClipper.exe --self-test     -> cek paket, lalu keluar

`--self-test` dipakai CI: paket yang lolos build tapi isinya kurang (ffmpeg /
yt-dlp / whisper tidak ikut terbawa) akan gagal di gate ini, bukan complaints
dari user.
"""

import os
import subprocess
import sys

import portable_runtime as prt

APP_TITLE = "YouTube Heatmap Clipper"
VERSION_FILE = "VERSION"


def read_version():
    path = os.path.join(prt.resource_dir(), VERSION_FILE)
    for candidate in (path, os.path.join(prt.app_dir(), VERSION_FILE)):
        try:
            with open(candidate, "r", encoding="utf-8") as handle:
                value = handle.read().strip()
                if value:
                    return value
        except Exception:
            continue
    return "dev"


def _run(cmd, timeout=90):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output.strip()
    except Exception as exc:
        return -1, str(exc)


def self_test(require_whisper=False):
    """Cek isi paket. Return (exit_code, lines)."""
    lines = []
    failures = []

    def check(name, ok, detail=""):
        mark = "OK  " if ok else "FAIL"
        lines.append(f"[{mark}] {name}{(' - ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    lines.append(f"{APP_TITLE} v{read_version()}")
    lines.append(f"mode      : {'frozen' if prt.IS_FROZEN else 'source'}")
    lines.append(f"resource  : {prt.resource_dir()}")
    lines.append(f"app dir   : {prt.app_dir()}")

    data_dir = prt.bootstrap()
    lines.append(f"data dir  : {data_dir}")
    check("data dir writable", os.access(data_dir, os.W_OK))

    for rel in ("templates/index.html", "static/app.js", "static/style.css"):
        check(f"asset {rel}", os.path.isfile(os.path.join(prt.resource_dir(), rel)))

    fonts_dir = os.path.join(prt.resource_dir(), "fonts")
    font_count = 0
    if os.path.isdir(fonts_dir):
        for _root, _dirs, files in os.walk(fonts_dir):
            font_count += sum(1 for f in files if f.lower().endswith((".ttf", ".otf")))
    check("fonts bundled", font_count > 0, f"{font_count} file font")

    ffmpeg = prt.tool("ffmpeg")
    code, out = _run([ffmpeg, "-version"])
    first_line = out.splitlines()[0] if out else ""
    check("ffmpeg jalan", code == 0 and "ffmpeg version" in out, first_line)

    ffprobe = prt.tool("ffprobe")
    code, _out = _run([ffprobe, "-version"])
    check("ffprobe jalan", code == 0)

    try:
        ytdlp = prt.ytdlp_cmd()
    except RuntimeError as exc:
        ytdlp = None
        check("yt-dlp tersedia", False, str(exc))
    if ytdlp:
        code, out = _run([*ytdlp, "--version"])
        check("yt-dlp jalan", code == 0, out)

    try:
        import webapp  # noqa: F401  (import saja, jangan serve)

        check("webapp import", True)
    except Exception as exc:
        check("webapp import", False, str(exc))

    try:
        import faster_whisper

        check("faster-whisper import", True, getattr(faster_whisper, "__version__", ""))
        whisper_required = True
    except Exception as exc:
        whisper_required = require_whisper
        check(
            "faster-whisper import",
            not require_whisper,
            f"{exc}" if require_whisper else "tidak ada (subtitle AI nonaktif)",
        )

    check("clip directory", True, os.path.join(data_dir, "clips"))

    lines.append("")
    if failures:
        lines.append(f"GAGAL: {len(failures)} cek tidak lulus -> {', '.join(failures)}")
    else:
        extra = "" if whisper_required else " (tanpa subtitle AI)"
        lines.append(f"SEMUA CEK LULUS{extra}")
    return (1 if failures else 0), lines


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--self-test" in argv:
        require_whisper = "--require-whisper" in argv
        code, lines = self_test(require_whisper=require_whisper)
        print("\n".join(lines))
        return code

    if "--version" in argv:
        print(f"{APP_TITLE} v{read_version()}")
        return 0

    prt.bootstrap()

    # Mode CLI: teruskan seluruh argumen ke run.py (menu interaktifnya tetap
    # bekerja seperti sebelumnya).
    if "--url" in argv or "--check" in argv:
        import run as core

        print(f"{APP_TITLE} v{read_version()} - mode CLI")
        sys.argv = [sys.argv[0]] + argv
        core.main()
        return 0

    import argparse

    parser = argparse.ArgumentParser(prog="YoutubeHeatmapClipper", add_help=False)
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--help", "-h", action="store_true")
    opts, _unknown = parser.parse_known_args(argv)

    if opts.help:
        parser.print_help()
        return 0

    import webapp

    webapp.serve(
        host=opts.host,
        port=opts.port,
        open_browser=not opts.no_browser,
        debug=opts.debug,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n dihentikan user.")
        sys.exit(0)
