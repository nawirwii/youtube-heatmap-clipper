import os
import json
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from types import SimpleNamespace

from flask import Flask, jsonify, render_template, request, send_from_directory

import run as core
from portable_runtime import bootstrap, resource_dir, ytdlp_cmd


RES_DIR = resource_dir()
STATIC_DIR = os.path.join(RES_DIR, "static")
TEMPLATE_DIR = os.path.join(RES_DIR, "templates")
FONTS_DIR = os.path.join(RES_DIR, "fonts")

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)

jobs_lock = threading.Lock()
jobs = {}
preview_lock = threading.Lock()
preview_cache = {}


def now_ms():
    return int(time.time() * 1000)


def safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


def parse_time_to_seconds(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    parts = s.split(":")
    if len(parts) == 2:
        m, sec = parts
        return int(m) * 60 + int(float(sec))
    if len(parts) == 3:
        h, m, sec = parts
        return int(h) * 3600 + int(m) * 60 + int(float(sec))
    return None


def resolve_fonts_dir(value):
    """Path absolut folder font.

    Nilai relatif (mis. default UI = "fonts") selalu dibuka relatif ke folder
    aset aplikasi, bukan ke CWD — penting untuk paket portable yang bisa
    dijalankan dari folder mana pun.
    """
    if value:
        raw = str(value).strip()
        if raw:
            if not os.path.isabs(raw):
                candidate = os.path.join(RES_DIR, raw)
                if os.path.isdir(candidate):
                    return candidate
            return raw
    return FONTS_DIR if os.path.isdir(FONTS_DIR) else None


def set_job(job_id, **patch):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        job.update(patch)


def add_log(job_id, line):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        job["logs"].append(line)
        if len(job["logs"]) > 300:
            job["logs"] = job["logs"][-300:]


def list_outputs(job_dir):
    if not os.path.isdir(job_dir):
        return []
    items = []
    for name in os.listdir(job_dir):
        path = os.path.join(job_dir, name)
        if os.path.isfile(path) and name.lower().endswith(".mp4"):
            items.append({"name": name, "size": os.path.getsize(path)})
    items.sort(key=lambda x: x["name"])
    return items


def run_job(job_id, payload):
    started = now_ms()
    try:
        set_job(job_id, status="running", started_at=started)

        url = (payload.get("url") or "").strip()
        if not url:
            raise ValueError("URL kosong")

        crop = payload.get("crop") or "default"
        ratio = payload.get("ratio") or "9:16"
        subtitle = bool(payload.get("subtitle"))
        whisper_model = payload.get("whisper_model") or "small"
        subtitle_font = payload.get("subtitle_font") or "Arial"
        subtitle_location = payload.get("subtitle_location") or "bottom"
        subtitle_fontsdir = resolve_fonts_dir(payload.get("subtitle_fontsdir"))
        padding = safe_int(payload.get("padding"), 10)
        max_clips = safe_int(payload.get("max_clips"), 10)
        mode = payload.get("mode") or "heatmap"
        set_job(job_id, subtitle_enabled=subtitle)

        core.WHISPER_MODEL = whisper_model
        core.SUBTITLE_FONT = subtitle_font
        core.SUBTITLE_FONTS_DIR = subtitle_fontsdir
        core.SUBTITLE_LOCATION = subtitle_location
        core.PADDING = max(0, padding if padding is not None else 10)
        core.set_ratio_preset(ratio)

        job_dir = os.path.join("clips", job_id)
        os.makedirs(job_dir, exist_ok=True)
        core.OUTPUT_DIR = job_dir

        core.cek_dependensi._args = SimpleNamespace(no_update_ytdlp=True)
        ok = core.cek_dependensi(install_whisper=subtitle, fatal=False)
        if not ok:
            raise RuntimeError("FFmpeg tidak ketemu")

        video_id = core.extract_video_id(url)
        if not video_id:
            raise ValueError("URL YouTube invalid")

        total_duration = core.ambil_durasi(video_id)

        targets = []
        picked = payload.get("segments")
        if isinstance(picked, list) and len(picked) > 0:
            add_log(job_id, f"Pakai {len(picked)} segment yang dipilih...")
            for seg in picked:
                try:
                    start = float(seg.get("start"))
                    dur = float(seg.get("duration"))
                    score = float(seg.get("score", 1.0))
                except Exception:
                    continue
                if dur <= 0:
                    continue
                targets.append({"start": start, "duration": dur, "score": score})
            if not targets:
                raise ValueError("Segment pilihan invalid")
        elif mode == "custom":
            start_s = parse_time_to_seconds(payload.get("start"))
            end_s = parse_time_to_seconds(payload.get("end"))
            if start_s is None or end_s is None:
                raise ValueError("Start/End belum diisi")
            if end_s <= start_s:
                raise ValueError("End harus lebih besar dari Start")
            targets = [{"start": float(start_s), "duration": float(end_s - start_s), "score": 1.0}]
        else:
            add_log(job_id, "Scan heatmap...")
            hasil_scan = core.scan_heatmap(video_id)
            if not total_duration:
                total_duration = hasil_scan.get("duration") or 0
            targets = hasil_scan["segments"]
            if not targets:
                # Jangan berhenti di sini: kalau heatmap memang tidak ada, pakai
                # titik potong berjarak rata. Yang benar-benar fatal hanya kalau
                # YouTube tidak bisa diakses sama sekali.
                if hasil_scan["reason"] in ("network", "consent", "notfound"):
                    add_log(job_id, f"Heatmap gagal dibaca: {hasil_scan['detail']}")
                    raise RuntimeError(hasil_scan["detail"])
                add_log(job_id, f"Heatmap tidak tersedia: {hasil_scan['detail']}")
                targets = core.fallback_segments(
                    total_duration, count=max(1, max_clips or 5)
                )
                add_log(
                    job_id,
                    f"Fallback: {len(targets)} segment berjarak rata dari "
                    f"{total_duration}s video.",
                )
            targets = targets[: max(1, max_clips or 10)]

        if total_duration <= 0:
            raise ValueError(
                "Durasi video tidak terbaca. Cek link-nya, lalu coba lagi."
            )

        set_job(job_id, total=len(targets), done=0, status_text="processing")

        def event_hook(kind, data):
            if kind != "stage" or not isinstance(data, dict):
                return
            stage = data.get("stage") or ""
            clip_index = safe_int(data.get("clip_index"), 0) or 0
            set_job(job_id, stage=stage, stage_at=now_ms(), stage_clip=clip_index)

        success = 0
        for idx, item in enumerate(targets, start=1):
            set_job(job_id, current=idx, status_text=f"clip {idx}/{len(targets)}")
            ok = core.proses_satu_clip(video_id, item, idx, total_duration, crop, subtitle, event_hook=event_hook)
            if ok:
                success += 1
            set_job(job_id, done=idx, success=success, outputs=list_outputs(job_dir))

        set_job(job_id, status="done", finished_at=now_ms(), outputs=list_outputs(job_dir))
    except Exception as e:
        set_job(job_id, status="error", error=str(e), finished_at=now_ms())


@app.get("/")
def index():
    return render_template("index.html")

@app.get("/assets/fonts/<path:filename>")
def serve_font(filename):
    return send_from_directory(FONTS_DIR, filename, as_attachment=False)


def get_preview(url):
    key = url.strip()
    if not key:
        raise ValueError("URL kosong")

    with preview_lock:
        cached = preview_cache.get(key)
        if cached:
            return cached

    cmd = [
        *ytdlp_cmd(),
        "--skip-download",
        "-J",
        key,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout or "Gagal ambil metadata").strip())

    raw = json.loads(res.stdout)
    item = raw["entries"][0] if isinstance(raw, dict) and "entries" in raw and raw.get("entries") else raw

    preview = {
        "title": item.get("title"),
        "thumbnail": item.get("thumbnail"),
        "uploader": item.get("uploader"),
        "duration": item.get("duration"),
        "webpage_url": item.get("webpage_url") or key,
        "id": item.get("id"),
    }

    with preview_lock:
        preview_cache[key] = preview
        if len(preview_cache) > 200:
            preview_cache.clear()

    return preview


@app.post("/api/preview")
def api_preview():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    try:
        preview = get_preview(url)
        return jsonify({"ok": True, "preview": preview})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/scan")
def api_scan():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    video_id = core.extract_video_id(url)
    if not video_id:
        return jsonify({"ok": False, "error": "URL YouTube invalid"}), 400

    core.cek_dependensi._args = SimpleNamespace(no_update_ytdlp=True)
    ok = core.cek_dependensi(install_whisper=False, fatal=False)
    if not ok:
        return jsonify({"ok": False, "error": "FFmpeg tidak ketemu"}), 400

    max_clips = safe_int(data.get("max_clips"), 0)

    hasil = core.scan_heatmap(video_id)

    # Durasi dari HTML yang sudah kita ambil bersifat instan dan tidak kena
    # rate limit. yt-dlp hanya dipakai kalau angka itu tidak ada.
    total = hasil.get("duration") or core.ambil_durasi(video_id)

    segments = hasil["segments"]
    source = "heatmap"
    reason = hasil["reason"]
    detail = hasil["detail"]

    if not segments:
        # Gagal jaringan/consent tidak bisa ditutup dengan tebakan: user harus
        # tahu itu masalah akses, bukan emang videonya tidak panas.
        if reason in ("network", "consent", "notfound"):
            return jsonify({
                "ok": False,
                "video_id": video_id,
                "error": detail,
                "reason": reason,
            }), 502

        segments = core.fallback_segments(total, count=max(1, int(max_clips or 5)))
        source = "fallback"
        if not segments:
            return jsonify({
                "ok": False,
                "video_id": video_id,
                "error": (
                    "Tidak ada data heatmap dan durasi videonya tidak terbaca, "
                    "jadi tidak ada titik potong yang bisa dihitung."
                ),
                "reason": reason,
            }), 422

    return jsonify({
        "ok": True,
        "video_id": video_id,
        "duration": total,
        "segments": segments,
        "source": source,
        "reason": reason,
        "detail": detail,
        "markers": hasil["markers"],
    })


@app.post("/api/clip")
def api_clip():
    payload = request.get_json(silent=True) or {}
    job_id = uuid.uuid4().hex[:12]
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "created_at": now_ms(),
            "started_at": None,
            "finished_at": None,
            "error": None,
            "total": 0,
            "done": 0,
            "success": 0,
            "current": 0,
            "status_text": "",
            "stage": "",
            "stage_at": None,
            "stage_clip": 0,
            "subtitle_enabled": False,
            "outputs": [],
            "logs": [],
        }

    t = threading.Thread(target=run_job, args=(job_id, payload), daemon=True)
    t.start()
    return jsonify({"ok": True, "job_id": job_id})


@app.get("/api/job/<job_id>")
def api_job(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify({"ok": False, "error": "Job not found"}), 404
        return jsonify({"ok": True, "job": job})


@app.get("/clips/<job_id>/<path:filename>")
def serve_clip(job_id, filename):
    job_dir = os.path.join("clips", job_id)
    return send_from_directory(job_dir, filename, as_attachment=True)


def find_free_port(host, preferred, attempts=20):
    """Port pertama yang bebas, mulai dari `preferred`."""
    for offset in range(attempts):
        candidate = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, candidate))
                return candidate
            except OSError:
                continue
    return preferred


def _open_browser_when_ready(url, timeout=20.0):
    deadline = time.time() + timeout
    host = url.split("//", 1)[1].split("/", 1)[0].split(":")[0]
    port = int(url.rsplit(":", 1)[1].split("/", 1)[0])
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.5)
            if probe.connect_ex((host, port)) == 0:
                webbrowser.open(url)
                return
        time.sleep(0.2)


def serve(host="127.0.0.1", port=5000, open_browser=True, debug=False):
    """Jalankan web app di thread utama (dipakai launcher + `python webapp.py`)."""
    data_dir = bootstrap()
    port = find_free_port(host, port)
    url = f"http://{host}:{port}"

    print("=" * 58)
    print("  YouTube Heatmap Clipper")
    print("=" * 58)
    print(f"  Aplikasi   : {url}")
    print(f"  Folder data: {data_dir}")
    print(f"  Output     : {os.path.join(data_dir, 'clips')}")
    print("-" * 58)
    print("  Jangan tutup jendela ini selama app dipakai.")
    print("  Untuk berhenti: tekan Ctrl+C atau tutup jendela ini.")
    print("=" * 58)

    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready, args=(url,), daemon=True
        ).start()

    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(prog="webapp.py", add_help=False)
    _parser.add_argument("--port", type=int, default=5000)
    _parser.add_argument("--no-browser", action="store_true")
    _parser.add_argument("--debug", action="store_true")
    _opts, _ = _parser.parse_known_args()

    serve(
        port=_opts.port,
        open_browser=not _opts.no_browser,
        debug=_opts.debug,
    )
