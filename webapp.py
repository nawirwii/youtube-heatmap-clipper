import glob
import os
import json
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from types import SimpleNamespace

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

import ai_config
import ai_meta
import run as core
from portable_runtime import bootstrap, data_dir, resource_dir, ytdlp_cmd


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


def clips_dir():
    """
    Folder clip absolut, bukan relatif terhadap CWD.

    Route lama memakai string "clips", jadi kalau CWD tidak bisa ditulis
    (executable dijalankan dari folder sistem) clip gagal dibuat, dan kalau
    CWD berubah antara tulis dan baca, route membalas 404 -- yang tersimpan
    di browser sebagai "clip_1.mp4" berisi HTML.
    """
    return os.path.abspath(os.path.join(data_dir(), "clips"))


def job_dir_for(job_id):
    """
    Folder satu job, absolut dan tervalidasi.

    Sebelumnya route dan penulisan clip memakai string relatif "clips", jadi
    semuanya bergantung pada CWD. Paket portable menjalankan bootstrap() yang
    melakukan chdir ke DATA_DIR; kalau CWD tidak bisa ditulis, clip gagal
    dibuat, dan kalau CWD berubah antara tulis dan baca, route mengembalikan
    404 -- yang tersimpan di browser sebagai "clip_1.mp4" berisi HTML.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id or ""):
        abort(404)

    path = os.path.abspath(os.path.join(clips_dir(), job_id))
    root = os.path.abspath(clips_dir())
    if os.path.commonpath([root, path]) != root:
        abort(404)

    return path


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
    """
    Hanya file yang benar-benar video yang ditampilkan sebagai hasil.

    Kalau file rusak ikut masuk daftar, user menekan Play lalu mendapat
    "gagal memutar" tanpa petunjuk apa pun.
    """
    if not os.path.isdir(job_dir):
        return []

    items = []
    for name in os.listdir(job_dir):
        path = os.path.join(job_dir, name)
        if not (os.path.isfile(path) and name.lower().endswith(".mp4")):
            continue
        if not core.file_video_valid(path):
            print(f"  Lewati hasil rusak: {path}")
            continue
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
        source_height = safe_int(payload.get("source_height"), None) or (
            core.DEFAULT_SOURCE_HEIGHT
        )
        set_job(job_id, subtitle_enabled=subtitle)

        core.WHISPER_MODEL = whisper_model
        core.SUBTITLE_FONT = subtitle_font
        core.SUBTITLE_FONTS_DIR = subtitle_fontsdir
        core.SUBTITLE_LOCATION = subtitle_location
        core.PADDING = max(0, padding if padding is not None else 10)
        core.set_ratio_preset(ratio)

        job_dir = job_dir_for(job_id)
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

        # Unduh video-nya SEKALI per job, lalu semua clip dipotong dari file
        # yang sama. Selain jauh lebih cepat untuk max_clips besar, ini juga
        # menghindari satu unduhan per clip yang bisa gagal sendiri-sendiri.
        set_job(job_id, stage="download", stage_at=now_ms(), status_text="unduh video")
        started_download = time.time()
        add_log(
            job_id,
            f"Unduh video (maks {source_height}p). Ini tahap paling lama "
            "kalau koneksi sedang lambat.",
        )
        source_file = core.download_source(
            video_id, 0, total_duration, max_height=source_height
        )
        if not source_file:
            raise RuntimeError(
                "Gagal mengunduh video. YouTube bisa sedang membatasi akses dari "
                "koneksi ini -- coba lagi nanti atau ganti video."
            )
        unduh_detik = time.time() - started_download
        try:
            ukuran_mb = os.path.getsize(source_file) / 1024 / 1024
        except OSError:
            ukuran_mb = 0.0
        add_log(
            job_id,
            f"Video terunduh: {ukuran_mb:.1f} MB dalam {unduh_detik:.0f} detik.",
        )

        success = 0
        for idx, item in enumerate(targets, start=1):
            set_job(job_id, current=idx, status_text=f"clip {idx}/{len(targets)}")
            ok = core.proses_satu_clip(
                video_id, item, idx, total_duration, crop, subtitle,
                event_hook=event_hook, source_file=source_file,
            )
            if ok:
                success += 1
            set_job(job_id, done=idx, success=success, outputs=list_outputs(job_dir))

        if source_file and os.path.exists(source_file):
            try:
                os.remove(source_file)
            except OSError:
                pass

        outputs = list_outputs(job_dir)
        if targets and not outputs:
            # Semua clip gagal. Jangan lapor "done" karena itu bikin user
            # mengira file ada padahal tidak ada yang bisa diputar.
            set_job(
                job_id,
                status="error",
                finished_at=now_ms(),
                outputs=[],
                error=(
                    f"Tidak ada clip yang berhasil dibuat dari {len(targets)} "
                    "segmen. Coba lagi, atau ganti video."
                ),
            )
        else:
            set_job(
                job_id,
                status="done",
                finished_at=now_ms(),
                success=len(outputs),
                outputs=outputs,
            )
    except Exception as e:
        for sisa in ("source_*.mp4", "source_*.webm", "source_*.mkv", "temp_*.mkv",
                     "temp_cropped_*.mp4", "temp_*.srt"):
            for nama in glob.glob(os.path.join(clips_dir(), "*", sisa)):
                try:
                    os.remove(nama)
                except OSError:
                    pass
        set_job(job_id, status="error", error=str(e), finished_at=now_ms())


def asset_version():
    """Token cache-buster untuk app.js dan style.css.

    Tanpa ini, browser bisa tetap memakai JavaScript versi lama padahal
    aplikasinya sudah diperbarui. Gejalanya: UI masih menampilkan fitur
    yang sudah dihapus, atau tombol tidak merespons karena logika barunya
    tidak ikut termuat. File aset dibaca dari disk tiap request, jadi token
    cukup berupa ukuran dan waktu ubahnya.
    """
    try:
        stat = os.stat(os.path.join(RES_DIR, "static", "app.js"))
        return f"{int(stat.st_mtime)}-{stat.st_size}"
    except OSError:
        return "0"


@app.get("/")
def index():
    return render_template("index.html", asset_v=asset_version())

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
        # Deskripsi asli dipakai sebagai konteks topik saat generate metadata.
        # Dipotong karena deskripsi YouTube bisa ribuan karakter dan sebagian
        # besar berisi boilerplate/link yang tidak membantu LLM.
        "description": (item.get("description") or "")[:6000],
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


# --------------------------------------------------------------------------
# Metadata AI (judul, deskripsi, tag) lewat LLM lokal
# --------------------------------------------------------------------------

def format_duration_text(seconds):
    """'PT3M33S' -> '3:33'. Dipakai sebagai konteks panjang video."""
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_ai_context(payload):
    """Kumpulkan semua bahan yang bisa dibaca LLM dari state yang sudah ada.

    Sengaja memakai data yang sudah ada di memory, bukan memanggil yt-dlp lagi:
    satu request tambahan berarti satu langkah lebih dekat ke rate limit, dan metadata video
    sudah ada sejak preview.
    """
    url = (payload.get("url") or "").strip()
    preview = {}
    if url:
        with preview_lock:
            preview = preview_cache.get(url.strip()) or {}
    segments = payload.get("segments")
    if not isinstance(segments, list):
        segments = []
    return {
        "title": preview.get("title") or payload.get("title") or "",
        "channel": preview.get("uploader") or "",
        "duration_text": format_duration_text(preview.get("duration")),
        "description": preview.get("description") or "",
        "transcript": payload.get("transcript") or "",
        "segments": [s for s in segments if isinstance(s, dict)][:20],
    }


def _ai_settings(payload):
    """Ambil + bersihkan pengaturan AI dari request.

    Field yang tidak dikirim browser diisi dari config tersimpan, jadi user
    tidak perlu mengetik ulang model/url setiap kali aplikasi dibuka.
    """
    options = payload.get("options") or {}
    if not isinstance(options, dict):
        options = {}
    stored = ai_config.load()
    stored_options = {
        "tone": stored.get("tone"),
        "timeout": stored.get("timeout"),
        "n_titles": stored.get("n_titles"),
        "note": stored.get("note"),
        "hashtags_in_description": stored.get("hashtags_in_description", True),
    }
    merged = {k: v for k, v in stored_options.items() if v is not None}
    merged.update({k: v for k, v in options.items() if v is not None})

    # API key tidak pernah dikirim balik ke browser. Kalau kolomnya kosong di
    # browser, pakai yang tersimpan di server.
    api_key = (payload.get("api_key") or "").strip()
    if not api_key:
        api_key = ai_config.api_key()

    return {
        "base_url": (payload.get("base_url") or stored.get("base_url")),
        "model": (payload.get("model") or "").strip() or (stored.get("model") or ""),
        "api_key": api_key,
        "options": merged,
    }


@app.get("/api/ai/config")
def api_ai_config_get():
    """Kembalikan config AI tersimpan. API key tidak ikut di sini."""
    return jsonify({"ok": True, "config": ai_config.load()})


@app.post("/api/ai/config")
def api_ai_config_save():
    """Simpan config AI ke disk supaya tetap ada di sesi berikutnya."""
    payload = request.get_json(silent=True) or {}
    if payload.get("reset"):
        ai_config.clear()
        return jsonify({"ok": True, "config": ai_config.load(), "reset": True})
    saved = ai_config.save(payload)
    return jsonify({"ok": True, "config": saved})


@app.post("/api/ai/probe")
def api_ai_probe():
    """Cek apakah endpoint AI hidup dan modelnya benar-benar tersedia.

    Ini sengaja dipisah dari generate: user perlu tahu cepat apakah Ollama-nya
    jalan, tanpa menunggu satu generasi panjang.
    """
    payload = request.get_json(silent=True) or {}
    cfg = _ai_settings(payload)
    base_url = ai_meta.normalise_base_url(cfg["base_url"])
    ok, why = ai_meta.validate_base_url(base_url)
    if not ok:
        return jsonify({"ok": False, "error": why}), 400

    # Probe harusnya cepat dan gagal cepat juga. Timeout generous dipakai
    # hanya untuk generate, bukan untuk cek koneksi.
    probe_timeout = 8.0
    try:
        models = ai_meta.list_models(
            base_url, timeout=probe_timeout, api_key=cfg["api_key"] or None
        )
    except Exception as e:  # noqa: BLE001 - pesan asli sangat membantu user
        return jsonify({
            "ok": False,
            "error": ai_meta.friendly_url_error(e, base_url, probe_timeout),
            "base_url": base_url,
        }), 200

    chosen = cfg["model"]
    found = None
    if chosen:
        # Cocokkan longgar: beberapa server menulis "qwen2.5:3b-instruct"
        # sementara user mengetik "qwen2.5:3b".
        found = any(chosen == m or m.startswith(chosen) or chosen.startswith(m)
                     for m in models) if models else None
    return jsonify({
        "ok": True,
        "base_url": base_url,
        "models": models,
        "model_found": found,
        "count": len(models),
    })


@app.post("/api/ai/generate")
def api_ai_generate():
    """Buat judul, deskripsi, dan tag dari topik video.

    Dijalankan di thread supaya request tidak membekukan UI saat model lokal
    berpikir beberapa menit.
    """
    payload = request.get_json(silent=True) or {}
    cfg = _ai_settings(payload)
    base_url = ai_meta.normalise_base_url(cfg["base_url"])
    ok, why = ai_meta.validate_base_url(base_url)
    if not ok:
        return jsonify({"ok": False, "error": why}), 400
    if not cfg["model"]:
        return jsonify({"ok": False, "error": "Pilih model dulu di panel AI."}), 400

    context = build_ai_context(payload)
    if not context["title"] and not context["description"] and not context["transcript"]:
        return jsonify({
            "ok": False,
            "error": (
                "Belum ada info video untuk dianalisa. Tempel link YouTube dulu "
                "dan tunggu preview muncul."
            ),
        }), 400

    result = {}

    def worker():
        try:
            result["data"] = ai_meta.generate(
                base_url,
                cfg["model"],
                context,
                options=cfg["options"],
                api_key=cfg["api_key"] or None,
            )
        except Exception as e:  # noqa: BLE001
            result["error"] = str(e) if isinstance(e, ai_meta.AiError) else (
                f"Gagal membuat metadata: {type(e).__name__}: {e}"
            )

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    # Model lokal bisa sangat lambat; batas atas dibuat longgar karena user
    # yang tahu modelnya. UI menampilkan progres meanwhile.
    t.join(timeout=ai_meta.clamp_timeout(cfg["options"].get("timeout")))
    if t.is_alive():
        return jsonify({
            "ok": False,
            "error": (
                ai_meta.friendly_timeout_error(
                    ai_meta.clamp_timeout(cfg["options"].get("timeout")), cfg["model"]
                )
            ),
        }), 504
    if "error" in result:
        return jsonify({"ok": False, "error": result["error"]}), 502

    meta = result.get("data", {})
    # Guard bahasa: model kecil kadang menjawab dalam aksara yang tidak
    # diminta. Isi jawaban TIDAK ikut diubah - user berhak melihat apa yang
    # ditulis model - tapi status partial jadi true supaya UI menandai
    # hasilnya perlu diperiksa, bukan menambah warning yang diabaikan.
    audit = ai_meta.audit_language(meta, cfg["options"])
    meta["partial"] = audit["partial"]
    meta["language"] = {
        "ok": audit["ok"],
        "warnings": audit["warnings"],
        "message": ai_meta.format_language_warning(
            audit, "Indonesia" if cfg["options"].get("lang") == "id" else "Inggris"
        ),
    }
    return jsonify({"ok": True, "meta": meta})


@app.get("/clips/<job_id>/<path:filename>")
def serve_clip(job_id, filename):
    """
    Serve clip untuk diputar di <video>.

    PENTING: jangan pakai as_attachment=True di sini. Header
    Content-Disposition: attachment membuat browser memperlakukan respons
    sebagai unduhan, bukan media, sehingga <video> gagal memutar. Route
    download terpisah yang memakai as_attachment.
    """
    job_dir = job_dir_for(job_id)
    path = os.path.join(job_dir, filename)

    if not os.path.isfile(path):
        # Jangan balas halaman HTML: browser akan menyimpannya sebagai .mp4
        # dan user mengira itu videonya rusak.
        return jsonify({"ok": False, "error": "Clip tidak ditemukan."}), 404

    return send_from_directory(job_dir, filename, conditional=True)


@app.get("/download/<job_id>/<path:filename>")
def download_clip(job_id, filename):
    """Route yang memang untuk diunduh."""
    job_dir = job_dir_for(job_id)
    path = os.path.join(job_dir, filename)

    if not os.path.isfile(path):
        return jsonify({"ok": False, "error": "Clip tidak ditemukan."}), 404

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
