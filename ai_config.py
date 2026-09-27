"""
Penyimpanan konfigurasi AI di sisi server.

Kenapa tidak localStorage saja? LocalStorage terikat origin, sedangkan aplikasi
portable memakai `find_free_port()`: kalau port 5000 sedang dipakai, aplikasi
pindah ke 5001 dan browser kehilangan semua pengaturan AI. Ditambah, user bisa
membuka jendela private atau membersihkan data browser. Karena server hanya
bind ke 127.0.0.1, config di file lokal tetap aman.

API key tidak pernah dikembalikan ke browser. Frontend hanya perlu tahu
"ada key tersimpan atau tidak"; kalau user mengetik key baru, key itu yang
dipakai, kalau tidak, key lama di server yang dipakai.
"""
import json
import os
import threading

from portable_runtime import data_dir

CONFIG_NAME = "ai_config.json"
_lock = threading.Lock()

# Batas per field supaya file config tidak bisa membengkak dari inputanehas.
_LIMITS = {
    "base_url": 400,
    "model": 120,
    "tone": 60,
    "note": 500,
    "transcript": 6000,
}
_INT_LIMITS = {
    "timeout": (30, 1800),
    "n_titles": (1, 5),
}

# Field yang boleh disimpan. `api_key` sengaja terpisah: nilainya tidak
# pernah dikirim balik ke browser.
_FIELDS = ("base_url", "model", "tone", "note", "transcript", "api_key")


def config_path():
    return os.path.join(data_dir(), CONFIG_NAME)


def _read():
    path = config_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        # File rusak tidak boleh membuat aplikasi gagal start. Kehilangan
        # pengaturan boleh terjadi; aplikasi tidak bisa dibuka tidak boleh.
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(data):
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    # os.replace atomik: kalau aplikasi ditutup saat menulis, file lama tetap
    # utuh dan tidak ada config setengah jadi.
    os.replace(tmp, path)
    return path


def _sanitise(payload):
    """Bersihkan input config. Field di luar daftar diabaikan."""
    if not isinstance(payload, dict):
        return {}
    out = {}
    for key in _FIELDS:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        text = str(value)
        limit = _LIMITS.get(key)
        if limit:
            text = text[:limit]
        out[key] = text
    for key, (lo, hi) in _INT_LIMITS.items():
        if key not in payload:
            continue
        raw = payload.get(key)
        if raw is None or isinstance(raw, bool):
            continue
        try:
            num = int(float(raw))
        except (TypeError, ValueError):
            continue
        out[key] = max(lo, min(hi, num))
    # Opsi boolean: hanya True yang dianggap aktif.
    if "hashtags_in_description" in payload:
        out["hashtags_in_description"] = bool(payload.get("hashtags_in_description"))
    return out


def load():
    """Kembalikan config untuk dikirim ke browser (tanpa API key)."""
    data = _read()
    safe = {}
    for key, value in data.items():
        if key == "api_key":
            continue
        safe[key] = value
    safe["has_api_key"] = bool(data.get("api_key"))
    safe["api_key_saved"] = bool(data.get("api_key"))
    return safe


def api_key():
    return str(_read().get("api_key") or "")


def save(payload):
    """Gabungkan config baru ke config lama dan tulis ke disk."""
    clean = _sanitise(payload)
    with _lock:
        current = _read()

        if clean.get("api_key"):
            current["api_key"] = clean["api_key"]
        if payload.get("clear_api_key"):
            current.pop("api_key", None)

        for key in _FIELDS:
            if key in clean and key != "api_key":
                current[key] = clean[key]
        for key in _INT_LIMITS:
            if key in clean:
                current[key] = clean[key]
        if "hashtags_in_description" in clean:
            current["hashtags_in_description"] = clean["hashtags_in_description"]

        _write(current)
    return load()


def clear():
    """Hapus semua config AI."""
    with _lock:
        try:
            os.remove(config_path())
        except FileNotFoundError:
            pass
        except OSError:
            return False
    return True
