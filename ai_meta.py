"""
Pembuat metadata YouTube (judul, deskripsi, tag) memakai LLM lokal.

Endpoint speaks OpenAI-compatible chat completions, jadi yang bisa dipakai:
Ollama, LM Studio, llama.cpp server, KoboldCpp, LocalAI, atau router sendiri.
Tidak ada dependensi baru - semuanya stdlib urllib, supaya ukuran paket
portable tidak bertambah.

Prinsip: kalau LLM gagal, jawabannya harus jujur. Tidak pernah diam-diam
mengisi placeholder lalu berpura-pura sukses.
"""

import json
import re
import socket
import time
import urllib.error
import urllib.request


# Model lokal di CPU lambat. Batas bawah 120 detik supaya error cepat tetap
# terasa, tapi 900 detik memberi ruang untuk model 1-3B.
DEFAULT_TIMEOUT = 600.0
MIN_TIMEOUT = 30.0
MAX_TIMEOUT = 1800.0

# Batas input supaya prompt tidak meledakkan RAM mesin kecil.
MAX_CONTEXT_CHARS = 6000
MAX_DESC_CHARS = 4000
MAX_TAGS = 30
MAX_TITLE_LEN = 130
MAX_TRANSLIT_LEN = 480

# YouTube hanya menampilkan maksimal 15 hashtag di atas judul. Lebih dari itu
# tidak menambah jangkauan, cuma membuat deskripsi berantakan.
MAX_HASHTAGS = 15
MAX_HASHTAG_LEN = 60
_TONE_GUIDANCE = {
    "informative": "clear, factual, structured, and direct; explain the key point without hype",
    "casual": "friendly, relaxed, natural, and conversational; use simple everyday wording",
    "energetic": "lively, enthusiastic, punchy, and motivating; keep claims grounded in the video",
    "educational": "teacher-like, easy to follow, explanatory, and useful for a learner",
}

# Batas yang dipaksakan YouTube untuk deskripsi. MAX_DESC_CHARS sengaja lebih
# kecil supaya masih ada ruang untuk baris hashtag diBELAKANG deskripsi.
YOUTUBE_DESC_LIMIT = 5000

# Sisa penanda JSON yang tidak pernah perlu muncul di teks final: escape
# string dan karakter kontrol. Judul serta tag tidak butuh ini, dan user
# tidak boleh melihatnya. Kurung kurawal sengaja TIDAK dihapus karena
# deskripsi yang sah bisa memakainya.
_STRIP_JSON_NOISE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]|\\n|\\t|\\r|\\"')


# --------------------------------------------------------------------------
# Normalisasi endpoint
# --------------------------------------------------------------------------

def normalise_base_url(raw):
    """Bersihkan input base URL dari user.

    Terima 'localhost:11434', 'http://127.0.0.1:1234/v1/', dan Balearik apa
    adanya. Hasil selalu berakhiran '/v1' tanpa garis miring berlebih.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    text = re.sub(r"^https?://", "", text, flags=re.I)
    text = text.strip().strip("/")
    if not text:
        return ""
    # Buang path di belakang '/v1' supaya user tidak salah tempel '/v1/chat'.
    text = re.sub(r"/v\d+(/.*)?$", "", text, flags=re.I)
    return "http://" + text + "/v1"


def validate_base_url(url):
    """True kalau URL aman dan masuk akal untuk dipakai client lokal.

    Sengaja hanya menerima loopback + LAN. Model lokal tidak ada di internet,
    jadi menolak public host mencegah user mengetik base URL awan dan
    mengirim isi video ke sana tanpa sadar.
    """
    if not url:
        return False, "Base URL kosong"
    m = re.match(r"^http://([^/:]+|\[[0-9a-fA-F:]+\])(?::(\d{1,5}))?(/.*)?$", url)
    if not m:
        return False, "Format base URL tidak dikenali"
    host = m.group(1).strip("[]")
    port = m.group(2)
    if port and not (1 <= int(port) <= 65535):
        return False, "Port di luar rentang"
    if _is_public_host(host):
        return False, "Hanya alamat lokal atau LAN yang diizinkan (127.0.0.1, localhost, atau IP LAN)"
    return True, ""


def _is_public_host(host):
    """Deteksi host yang bukan loopback/LAN."""
    low = host.lower()
    if low in ("localhost", "localhost.localdomain", "::1", "0.0.0.0"):
        return False
    # Hostname tanpa titik = nama mesin di jaringan lokal (mis. 'mypc').
    if re.fullmatch(r"[a-z0-9-]+", low):
        return False
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
        parts = [int(p) for p in host.split(".")]
        if any(p > 255 for p in parts):
            return True
        if parts[0] == 10 or parts[0] == 127:
            return False
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return False
        if parts[0] == 192 and parts[1] == 168:
            return False
        if parts[0] == 169 and parts[1] == 254:
            return False
        return True  # IP publik
    # Nama host dengan titik dan bukan akhiran jaringan lokal = awan. Putuskan
    # dari bentuk namanya, BUKAN dari hasil DNS: kalau DNS gagal lalu host
    # dianggap lokal, server awan bisa lolos hanya karena tidak kebaca.
    if low.endswith((".local", ".localhost", ".lan", ".home", ".home.arpa", ".internal")):
        return False
    return True


def clamp_timeout(value):
    try:
        t = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT
    if t != t or t in (float("inf"), float("-inf")):  # NaN/inf
        return DEFAULT_TIMEOUT
    return max(MIN_TIMEOUT, min(MAX_TIMEOUT, t))


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

def build_prompt(context, options=None):
    """Susun pesan chat dari konteks video.

    Prompt ditulis dalam bahasa Inggris karena model kecil bilingual (Qwen,
    Llama, Gemma) jauh lebih patuh ke instruksi Inggris, tapi tetap minta output
    mengikuti bahasa yang diminta.
    """
    options = options or {}
    title = str(context.get("title") or "").strip()
    channel = str(context.get("channel") or "").strip()
    duration = context.get("duration_text") or ""
    desc = str(context.get("description") or "").strip()[:MAX_DESC_CHARS]
    transcript = str(context.get("transcript") or "").strip()[:MAX_CONTEXT_CHARS]
    segments = context.get("segments") or []
    user_note = str(options.get("note") or "").strip()[:MAX_CONTEXT_CHARS]
    lang = "Indonesian" if options.get("lang") == "id" else "English"
    n_titles = max(1, min(5, int(options.get("n_titles") or 3)))
    tone = str(options.get("tone") or "informative").strip().lower()[:40]
    tone_guidance = _TONE_GUIDANCE.get(tone, _TONE_GUIDANCE["informative"])
    include_hook = options.get("include_hook", True) is not False

    lines = [
        "You are a YouTube metadata writer. Read the video info and reply with "
        "ONE JSON object and nothing else. No markdown fence, no commentary.",
        "",
        f"Output language: {lang}.",
        f"Writing tone: {tone}. Style behavior: {tone_guidance}.",
        "STRICT SCRIPT RULE: write only in the requested language using Latin "
        "letters (A-Z), digits, normal spaces, and ordinary punctuation.",
        "NEVER output Chinese, Mandarin, Han/CJK characters, Japanese kana, "
        "Japanese kanji, Korean Hangul, or any other non-Latin script.",
        "If you cannot express a word safely in the requested language, use a "
        "simple Latin alternative or omit it. Do not translate into Chinese.",
        "",
        "Required JSON shape:",
        '{"titles": ["..."], "hook": "...", "description": "...", '
        '"tags": ["..."], "hashtags": ["#..."]}',
        "",
        "Rules:",
        f"- titles: exactly {n_titles} options, each under 100 characters, "
        "specific to the actual topic, no clickbait lies, no ALL CAPS spam.",
        "- description: 2-4 short paragraphs plus 3-5 short bullet points, "
        f"under {MAX_DESC_CHARS} characters, plain text only, in {lang}. "
        "Do NOT write any hashtag in the description; it is added separately.",
        "- hook: one relevant opening sentence based on the actual video topic; "
        "no fake claims, generic clickbait, or code. "
        + ("Include it." if include_hook else "Return an empty string."),
        "- Never put source code, programming syntax, HTML/XML, JSON, markdown "
        "fences, URLs, internal reasoning, or prompt notes in metadata. Return "
        "finished viewer-facing copy only.",
        f"- tags: between 8 and {MAX_TAGS} lowercase tags, no '#' character, "
        "no duplicates, mix broad and specific search terms.",
        f"- hashtags: between 3 and {MAX_HASHTAGS} items, each starting with '#', "
        f"no spaces inside, under {MAX_HASHTAG_LEN} characters, no duplicates. "
        "Pick the ones a viewer of this exact video would actually search for.",
        "- Do not invent facts that are not in the info below.",
        "- If the info is thin, write conservatively instead of guessing.",
        "",
        "Video info:",
        f"Title: {title or '(unknown)'}",
        f"Channel: {channel or '(unknown)'}",
        f"Length: {duration or '(unknown)'}",
    ]
    if desc:
        lines += ["", "Original description:", desc]
    if transcript:
        lines += [
            "",
            "Transcript excerpt (may be imperfect, prefer it over guessing):",
            transcript,
        ]
    if segments:
        seg_txt = ", ".join(
            f"{s.get('label') or '?'}" for s in segments[:12] if isinstance(s, dict)
        )
        lines += ["", "Clip chapters:", seg_txt]
    if user_note:
        lines += ["", "Extra instruction from the creator:", user_note]

    return [
        {"role": "system", "content": "You output only valid JSON. No markdown, no explanation."},
        {"role": "user", "content": "\n".join(lines)},
    ]


# --------------------------------------------------------------------------
# Panggil endpoint
# --------------------------------------------------------------------------

class AiError(RuntimeError):
    """Kegagalan yang layak ditampilkan ke user apa adanya."""


def _post_json(url, payload, timeout, api_key=None, headers=None):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", "Bearer " + str(api_key).strip())
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def list_models(base_url, timeout=20.0, api_key=None):
    """Ambil daftar model dari endpoint. Dipakai untuk mengisi dropdown."""
    base_url = normalise_base_url(base_url)
    ok, why = validate_base_url(base_url)
    if not ok:
        raise AiError(why)
    req = urllib.request.Request(base_url.rstrip("/") + "/models", method="GET")
    if api_key:
        req.add_header("Authorization", "Bearer " + str(api_key).strip())
    tmo = clamp_timeout(timeout)
    try:
        with urllib.request.urlopen(req, timeout=tmo or DEFAULT_TIMEOUT) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        raise AiError(friendly_http_error(e.code, _error_body(e), "", base_url)) from None
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        raise AiError(friendly_url_error(e, base_url, tmo)) from None
    except json.JSONDecodeError:
        raise AiError("Server AI membalas dengan JSON yang tidak bisa dibaca.") from None
    items = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        items = raw.get("models") if isinstance(raw, dict) else None
    names = []
    for it in items or []:
        if isinstance(it, dict):
            name = it.get("id") or it.get("name") or it.get("model")
            if name:
                names.append(str(name))
    return names


def generate(base_url, model, context, options=None, timeout=None, api_key=None,
             max_tokens=1600, temperature=0.7, log=None):
    """Panggil LLM dan kembalikan dict metadata ternormalisasi."""
    options = options or {}
    base_url = normalise_base_url(base_url)
    ok, why = validate_base_url(base_url)
    if not ok:
        raise AiError(why)
    model = str(model or "").strip()
    if not model:
        raise AiError("Nama model belum diisi")

    timeout = clamp_timeout(options.get("timeout", timeout))
    messages = build_prompt(context, options)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False,
    }
    if log:
        log(f"Generating metadata via {model} at {base_url} (timeout {int(timeout)}s)")

    started = time.time()
    try:
        raw = _post_json(base_url.rstrip("/") + "/chat/completions", payload,
                         timeout, api_key=api_key)
    except urllib.error.HTTPError as e:
        body = _error_body(e)
        raise AiError(friendly_http_error(e.code, body, model, base_url)) from None
    except urllib.error.URLError as e:
        raise AiError(friendly_url_error(e, base_url, timeout)) from None
    except socket.timeout:
        raise AiError(friendly_timeout_error(timeout, model)) from None
    except Exception as e:  # noqa: BLE001 - user harus tetap dapat pesan jelas
        raise AiError(f"Gagal menghubungi model: {type(e).__name__}: {e}") from None

    elapsed = time.time() - started
    text = _extract_text(raw)
    if not text.strip():
        raise AiError(
            f"Model '{model}' menjawab kosong. Coba model lain atau naikkan max token."
        )
    result = parse_metadata(text, options)
    if log:
        log(
            f"Metadata done in {elapsed:.1f}s "
            f"({len(result['titles'])} judul, {len(result['tags'])} tag, "
            f"{len(result['hashtags'])} hashtag)"
        )
    result["elapsed"] = round(elapsed, 1)
    return result


def _error_body(err):
    try:
        raw = err.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""
    m = re.search(r'"message"\s*:\s*"([^"]+)"', raw)
    return (m.group(1) if m else raw)[:300]


def friendly_http_error(code, body, model, base_url):
    low = (body or "").lower()
    if code == 404:
        return (
            f"Endpoint {base_url}/chat/completions tidak ada (404). "
            "Pastikan yang tersimpan memang server OpenAI-compatible, bukan web UI."
        )
    if code == 401 or code == 403:
        return f"Endpoint menolak kunci API ({code}). Kalau tidak butuh kunci, kosongkan saja."
    if code == 400 and ("model" in low):
        return f"Model '{model}' tidak dikenali oleh server. Cek daftar model di panel AI."
    if code in (500, 502, 503):
        return (
            f"Server error {code} dari model. Ini biasanya kehabisan RAM atau model gagal dimuat. "
            "Coba model yang lebih kecil."
        )
    return f"Server membalas {code}: {body or 'tanpa pesan'}"


def friendly_url_error(err, base_url, timeout):
    reason = getattr(err, "reason", None)
    text = str(reason or err)
    low = text.lower()
    if "refused" in low:
        return (
            f"Tidak ada server AI yang menjawab di {base_url}. "
            "Jalankan Ollama/LM Studio/llama.cpp dulu, lalu cek portnya."
        )
    if "timed out" in low or "timeout" in low:
        return friendly_timeout_error(timeout, "(model)")
    if "name or service not known" in low or "getaddrinfo" in low:
        return f"Nama host di {base_url} tidak bisa di-resolve."
    return f"Gagal menghubungi {base_url}: {text}"


def friendly_timeout_error(timeout, model):
    return (
        f"Model '{model}' tidak selesai dalam {int(timeout)} detik. "
        "Model lokal di CPU bisa sangat lambat - naikkan timeout, pakai model lebih "
        "kecil, atau pendekkan input (matikan transkrip kalau tidak perlu)."
    )


def _extract_text(raw):
    """Ambil konten teks dari respons OpenAI-compatible."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AiError(
            "Respons server bukan JSON yang valid. "
            f"Error: {e}. Awal respons: {raw[:200]}"
        ) from None
    if isinstance(data, dict):
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"]
            # Beberapa server lama pakai 'text'.
            if isinstance(choices[0], dict) and isinstance(choices[0].get("text"), str):
                return choices[0]["text"]
        # Ollama lama: {'response': '...'}
        if isinstance(data.get("response"), str):
            return data["response"]
        #LM Studio / llama.cpp sebagian: {'content': '...'}
        if isinstance(data.get("content"), str):
            return data["content"]
    raise AiError(
        "Respons server tidak punya isi yang bisa dibaca "
        f"(kunci: {sorted(data.keys()) if isinstance(data, dict) else type(data).__name__})."
    )


# --------------------------------------------------------------------------
# Parsing + normalisasi hasil
# --------------------------------------------------------------------------

def strip_fences(text):
    """Buang fence markdown tanpa memilih fence kode yang salah."""
    s = (text or "").strip()
    fences = list(re.finditer(r"```(?:json|JSON)?\s*(.+?)\s*```", s, re.S))
    for fence in fences:
        candidate = fence.group(1).strip()
        if candidate.startswith("{") or candidate.startswith("["):
            return candidate
    return re.sub(r"```(?:json|JSON)?\s*|\s*```", "", s, flags=re.I)


def _balanced_object(text, start):
    """Ambil satu objek JSON dimulai di index tertentu, menghitung
    kurung kurawal dan mengabaikan yang di dalam string."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1], i + 1
    return None, start


def parse_metadata(text, options=None):
    """Ubah teks LLM jadi dict metadata yang rapi.

    Model kecil sering menambah markdown fence, mengulang kunci, atau memotong
    string di tengah. Semua itu dicoba diselamatkan selama masih ada isi
    yang bisa dipakai - hasil parsial lebih baik daripada seluruh hasil hilang.
    """
    options = options or {}
    body = strip_fences(text)
    data = None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = _salvage_object(body)

    if not isinstance(data, dict):
        raise AiError(
            "Tidak bisa membaca JSON dari jawaban model. "
            f"Awal jawaban: {body[:250]}"
        )

    # Kebijakan aplikasi: karakter Han/CJK, kana, dan hangul tidak boleh
    # pernah sampai ke hasil yang ditampilkan. Bersihkan sebelum normalisasi
    # tag/hashtag agar fallback hashtag juga tidak menghidupkan ulang kata
    # Mandarin yang sudah dibuang.
    had_forbidden_script = _contains_forbidden_scripts(data)
    data = _remove_forbidden_scripts(data)

    titles = _clean_titles(data.get("titles") or data.get("title"))
    hook = _clean_hook(data.get("hook") or data.get("opening"))
    description = _clean_desc(data.get("description") or data.get("desc"))
    tags = _clean_tags(data.get("tags") or data.get("keywords"))
    hashtags = _clean_hashtags(data.get("hashtags") or data.get("hashtag"), tags)

    if not titles and not description and not tags:
        raise AiError(
            "Model menjawab JSON tapi isinya kosong. "
            "Coba model lain atau perbaiki instruksi tambahan."
        )

    if options.get("hashtags_in_description", True):
        description = append_hashtags(description, hashtags)

    # Parsial berarti ada bagian yang benar-benar kosong, bukan cuma jawaban
    # yang perlu dibongkar dari fence atau kalimat tambahan. Model yang
    # talkatif tapi lengkap tetap dihitung utuh.
    return {
        "titles": titles,
        "hook": hook,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "partial": bool(had_forbidden_script) or not (titles and description and tags),
    }


def _salvage_object(text):
    """Ambil objek JSON pertama yang bisa dibaca, abaikan sisanya.

    Menangani kasus umum: fence belum ditutup, teks terpotong, atau ada
    kalimat penjelasan sebelum/sesudah JSON.
    """
    idx = text.find("{")
    while idx != -1:
        chunk, _ = _balanced_object(text, idx)
        if chunk:
            try:
                obj = json.loads(chunk)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                # Kunci tidak menutup dengan rapi - coba repairing.
                repaired = _repair(chunk)
                if isinstance(repaired, dict):
                    return repaired
        idx = text.find("{", idx + 1)
    # Semua efforts gagal: ambil setiap kunci secara terpisah. Ini menyelamatkan
    # jawaban yang terpotong di tengah - judul dan tag biasanya sudah keluar
    # sebelum model kehabisan token.
    return _salvage_fields(text)


def _salvage_fields(text):
    """Bangun dict dari setiap kunci yang masih bisa dibaca satu per satu.

    Dipakai kalau JSON tidak pernah bisa ditutup. Lebih baik dapat judul +
    tag tanpa deskripsi daripada kehilangan semuanya.
    """
    out = {}
    for key in ("titles", "title", "description", "desc", "tags", "keywords"):
        value = _read_field(text, key)
        if value is not None:
            out[key] = value
    return out or None


def _read_field(text, key):
    """Baca satu nilai kunci JSON dari teks yang mungkin rusak.

    Kalau nilainya string, ambil sampai kutipan penutup. Kalau array, ambil
    tiap elemen dan buang yang rusak.
    """
    m = re.search(r'"%s"\s*:\s*' % re.escape(key), text)
    if not m:
        return None
    rest = text[m.end():].lstrip()

    if rest.startswith('"'):
        # String yang tidak pernah ditutup (jawaban terpotong) tetap berguna.
        m2 = re.match(r'"((?:[^"\\]|\\.)*)', rest)
        if not m2:
            return None
        raw = m2.group(1)
        # Kutip yang tidak di-escape di dalam teks model.
        raw = re.sub(r'(?<!\\)"', ' ', raw)
        return _unescape(raw)
    if rest.startswith("["):
        end = rest.find("]")
        inner = rest[1:end] if end != -1 else rest[1:]
        items = []
        for part in re.findall(r'"((?:[^"\\]|\\.)*)"', inner):
            val = _unescape(re.sub(r'(?<!\\)"', ' ', part)).strip()
            if val:
                items.append(val)
        if items:
            return items
        # Array dari elemen non-string, mis. ["a", 3, "b"].
        cleaned = []
        for chunk in _split_array(inner):
            try:
                val = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(val, str) and val.strip():
                cleaned.append(val.strip())
        return cleaned or None
    if rest.startswith("{"):
        return None  # objek bersarang: diabaikan, tidak dibutuhkan
    m3 = re.match(r'[^,}\]\n]+', rest)
    if not m3:
        return None
    try:
        return json.loads(m3.group(0).strip())
    except json.JSONDecodeError:
        return None


def _split_array(inner):
    """Pecah isi array jadi potongan per elemen, dengan aman terhadap string."""
    parts, buf, in_str, esc, depth = [], [], False, False, 0
    for ch in inner:
        if in_str:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _unescape(text):
    """Buka escape JSON sebijak mungkin tanpa error pada string rusak."""
    try:
        return json.loads('"' + text + '"')
    except json.JSONDecodeError:
        return (
            text.replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
            .replace("\\\\", "\\")
        )


def _repair(chunk):
    """Tutup kurung kurawal dan array yang menggantung, lalu coba lagi."""
    fixed = chunk.rstrip()
    for suffix in ('",', '"', ",", ":"):
        if fixed.endswith(suffix):
            fixed = fixed[: -len(suffix)] + suffix.rstrip(",")
            break
    if fixed.count('"') % 2:
        fixed += '"'
    if fixed.count("{") > fixed.count("}"):
        fixed += "}" * (fixed.count("{") - fixed.count("}"))
    if fixed.count("[") > fixed.count("]"):
        fixed += "]" * (fixed.count("[") - fixed.count("]"))
    try:
        obj = json.loads(fixed)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _clean_titles(value):
    """Rapikan daftar judul: buang pembungkus, potong yang kelewat panjang."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            continue
        t = re.sub(r"^\s*[\"'\-\*\d\.\)\s]+", "", item)
        t = t.strip().strip('"\'').strip("*_` ").strip()
        t = re.sub(r"\\[nrt]", " ", t)
        t = re.sub(r"\s+", " ", t)
        if len(t) > MAX_TITLE_LEN:
            t = t[: MAX_TITLE_LEN - 1].rstrip() + "\u2026"
        if not t:
            continue
        if _looks_like_non_copy(t):
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _clean_hook(value):
    """Satu kalimat pembuka relevan; buang code, URL, dan markup."""
    if not isinstance(value, str):
        return ""
    hook = _clean_desc(value).replace("\n", " ").strip()
    if _CODE_LINE.search(hook) or _URL.search(hook):
        return ""
    return hook[:240].strip()


def _clean_desc(value):
    if not isinstance(value, str):
        return ""
    d = value.replace("\r\n", "\n").replace("\r", "\n")
    d = re.sub(r"```.*?```", "", d, flags=re.S)
    # kembalikan newline yang masih ter-escape jadi baris baru SEBELUM
    # whitespace dirapikan. Kalau dibalik, "\n" jadi spasi dan paragraf hilang.
    d = d.replace("\\n", "\n").replace("\\t", " ").replace("\\r", "")
    d = _STRIP_JSON_NOISE.sub(" ", d)
    cleaned = []
    for line in d.split("\n"):
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if _CODE_LINE.search(stripped) or _URL.search(stripped):
            continue
        if _JSON_LINE.match(stripped) and (":" in stripped or stripped in ("{", "}")):
            continue
        cleaned.append(line)
    d = "\n".join(cleaned)
    d = re.sub(r"[ \t]+", " ", d)
    d = re.sub(r" ?\n ?", "\n", d)
    d = re.sub(r"\n{3,}", "\n\n", d).strip()
    if len(d) > MAX_DESC_CHARS:
        cut = d[:MAX_DESC_CHARS]
        d = cut.rsplit("\n", 1)[0].strip() or cut.strip()
    return d


def _clean_tags(value):
    """Normalisasi tag: lowercase, tanpa '#', unik, dan batas panjang per tag."""
    if value is None:
        return []
    if isinstance(value, str):
        value = re.split(r"[,\n]", value)
    if not isinstance(value, list):
        return []
    out = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            continue
        t = item.strip().lower().lstrip("#")
        t = re.sub(r"\\[nrt]", " ", t)
        t = re.sub(r"\s+", " ", t).strip(" .,:;|")
        if not t or len(t) > MAX_TRANSLIT_LEN:
            continue
        if _looks_like_non_copy(t):
            continue
        # Buang tag yang cuma noise (###, ---, dll). Aksara non-Latin
        # SENGAJA TIDAK dibuang di sini: tag Mandarin dari model adalah bukti
        # jawaban salah bahasa, dan kalau dibuang di sini, guard bahasa tidak
        # pernah melihatnya. Guard yang melapor, bukan filter senyap.
        if not re.search(r"[a-z0-9]", t) and not _OFF_SCRIPT.search(t):
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= MAX_TAGS:
            break
    return out


def _clean_hashtags(value, fallback_tags=None):
    """Normalisasi hashtag: selalu diawali '#', tanpa spasi, unik, maksimal 15.

    Kalau model tidak mengirim hashtags sama sekali, turunkan dari tag yang
    ada. Lebih baik hashtag turunan daripada kolom kosong: hashtag adalah
    bagian dari metadata yang benar-benar terpakai user saat mengunggah.
    """
    # Bedakan "turunkan dari tag" dari " hashtag dari model": untuk tag,
    # frasa ber-spasi tidak dipecah jadi beberapa hashtag, karena
    # "belajar fisika" adalah satu istilah, bukan "#belajar #fisika".
    turunan = value is None and fallback_tags is not None
    if value is None:
        value = fallback_tags
    if isinstance(value, str):
        value = re.split(r"[,\n]", value)
    if not isinstance(value, list):
        return []
    if turunan:
        value = [str(t).strip().split(" ", 1)[0] for t in value]

    out = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            continue
        # Satu item bisa memuat beberapa hashtag sekaligus, misal
        # 'Hashtags: #a #b'. Pisahkan dulu supaya keduanya tidak hilang.
        for bagian in item.split():
            t = bagian.strip().strip("\"'`").strip()
            t = re.sub(r"\\[nrt]", " ", t)
            t = t.lstrip("#").strip()
            t = re.sub(r"^[\\-\\*\\d\\.\\)\\s]+", "", t)
            # Buang label seperti "hashtag:" atau "kata kunci:" yang kadang
            # ditulis model sebelum daftar hashtag.
            t = re.sub(
                r"^(?:hashtags?|hash|kata\s*kunci|keywords?)\s*[:\-]\s*$", "", t,
                flags=re.I,
            )
            t = t.strip(" .,:;|#*_")
            if not t or len(t) > MAX_HASHTAG_LEN:
                continue
            if _looks_like_non_copy(t):
                continue
            # Sama seperti tag: aksara non-Latin dibiarkan lewat supaya
            # guard bahasa bisa melaporkannya.
            if not re.search(r"[a-z0-9]", t.lower()) and not _OFF_SCRIPT.search(t):
                continue
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append("#" + t)
            if len(out) >= MAX_HASHTAGS:
                return out
    return out


def hashtag_line(hashtags):
    """Gabungkan hashtag jadi satu baris siap tempel, atau string kosong."""
    if not hashtags:
        return ""
    return " ".join(h for h in hashtags if isinstance(h, str) and h.strip())


def append_hashtags(description, hashtags):
    """Tempel baris hashtag di akhir deskripsi, tetap di bawah batas YouTube.

    YouTube menghitung hashtag sebagai bagian dari deskripsi, jadi batas
    5000 karakter dihitung setelah digabung. Kalau tidak muat, deskripsi yang
    dipotong - bukan hashtag yang dibuang, karena hashtag justru bagian yang
    paling wanted user.
    """
    line = hashtag_line(hashtags)
    desc = (description or "").strip()
    if not line:
        return desc
    if line in desc:
        return desc

    block = f"{desc}\n\n{line}" if desc else line
    if len(block) <= YOUTUBE_DESC_LIMIT:
        return block

    room = YOUTUBE_DESC_LIMIT - len(line) - 2
    if room <= 0:
        return line[:YOUTUBE_DESC_LIMIT]
    cut = desc[:room]
    # Potong di batas paragraf kalau ada, supaya kalimat tidak terpotong
    # tepat di tengah kata.
    nl = cut.rfind("\n")
    if nl > room // 2:
        cut = cut[:nl]
    return f"{cut.rstrip()}\n\n{line}"


# --------------------------------------------------------------------------
# Ringkasan untuk UI
# --------------------------------------------------------------------------

def character_count(text):
    return len(text or "")


# --------------------------------------------------------------------------
# Deteksi bahasa nyasar
# --------------------------------------------------------------------------
# Model kecil (1-3B) kadang menjawab dalam bahasa yang salah, paling sering
# Mandarin: tokenizer model-nya kuat ke arah sana, dan konteks Indonesia
# yang tipis tidak cukup menahannya. Hasilnya tidak bisa dipakai user, tapi
# tampilannya terlihat "sukses" - itu yang bikin bug ini lama tidak ketahuan.
#
# Sifat guard ini: DETEKSI, bukan diam-diam membuang. Isi yang sudah jadi
# milik user tidak dihapus tanpa izin; yang berubah cuma penanda partial jadi
# true supaya UI memberi tahu jawabannya meragukan, dan UI menampilkan
# daftar temuannya supaya user bisa langsung melihat karakter yang tidak wajar.

# CJK unified ideograph + kana + hangul. Fullwidth punctuation sengaja tidak
# masuk: itu bentuk ASCII yang sering muncul di teks Latin, bukan penanda
# bahasa lain.
_OFF_SCRIPT = re.compile(
    r"[\u3005\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\u3040-\u30ff\uac00-\ud7af]"
)
_FORBIDDEN_WORDS = re.compile(
    r"\b(?:mandarin|chinese|china|cina|tiongkok)\b", flags=re.IGNORECASE
)
# Karakter kontrol dibuang; newline/tab tetap dipertahankan untuk deskripsi.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CODE_LINE = re.compile(
    r"^\s*(?:[#@$]?import\b|from\s+\S+\s+import\b|def\s+\w+\s*\(|"
    r"class\s+\w+\s*[:(]|(?:const|let|var)\s+\w+\s*=|return\b|"
    r"<\/?[a-z][^>]*>|[{}]\s*$|```|(?:SELECT|INSERT|UPDATE|DELETE)\s+.+)", flags=re.I
)
_JSON_LINE = re.compile(r"^\s*[\[\]{\"]?(?:\"?\w+\"?\s*:|[\[\]{\}])")
_URL = re.compile(r"https?://\S+|www\.\S+", flags=re.I)


def _looks_like_non_copy(text):
    """True untuk potongan code/markup/URL, bukan kata metadata."""
    value = str(text or "").strip()
    return bool(_CODE_LINE.search(value) or _URL.search(value) or re.search(
    r"[<>]|=>|\b(?:function|print|console|script|html|body)\b", value,
        flags=re.I,
    ))


def _remove_forbidden_scripts(value):
    """Hapus aksara non-Latin dari struktur JSON metadata secara rekursif.

    Ini adalah kebijakan output aplikasi: user meminta tidak pernah ada kata
    atau huruf Mandarin/Cina/Tiongkok. Teks tidak dibuat kosong total; kalau
    sebuah string hanya berisi aksara terlarang, string itu menjadi kosong dan
    normalisasi berikutnya menandainya sebagai field kosong.
    """
    if isinstance(value, str):
        value = _FORBIDDEN_WORDS.sub("", value)
        value = _OFF_SCRIPT.sub("", value)
        return _CONTROL_CHARS.sub("", value)
    if isinstance(value, list):
        return [_remove_forbidden_scripts(item) for item in value]
    if isinstance(value, dict):
        return {key: _remove_forbidden_scripts(item) for key, item in value.items()}
    return value


def _contains_forbidden_scripts(value):
    """True jika struktur hasil model mengandung aksara yang harus dibuang."""
    if isinstance(value, str):
        return bool(_OFF_SCRIPT.search(value))
    if isinstance(value, list):
        return any(_contains_forbidden_scripts(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_forbidden_scripts(item) for item in value.values())
    return False


# --------------------------------------------------------------------------
# Deteksi bahasa nyasar
_HANGUL = re.compile(r"[\uac00-\ud7af]")
_KANA = re.compile(r"[\u3040-\u30ff]")
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def detect_off_script(text, threshold=0.02, min_chars=8):
    """Deteksi karakter dari aksara non-Latin yang kemungkinan tidak disengaja.

    Mengembalikan dict berisi rasio, jumlah, contoh, dan nama bahasa. Kalau
    teksnya pendek, rasio kecil itu normal (misal satu kata Mandarin di judul
    pendek), jadi ambang rasio dan jumlah karakter minimum ikut dihitung.
    """
    s = str(text or "")
    if not s:
        return None
    found = _OFF_SCRIPT.findall(s)
    if not found:
        return None
    # Emoji itu bawaan zaman sekarang, bukan tanda salah bahasa: buang dulu
    # supaya emoji tidak dihitung sebagai karakter CJK.
    for ch in s:
        if _OFF_SCRIPT.fullmatch(ch) and ord(ch) > 0x1F000:
            found = [c for c in found if c != ch]
    if not found:
        return None
    # Rasio dihitung terhadap huruf+angka, bukan panjang mentah: spasi dan
    # tanda baca bukan sinyal bahasa.
    core = re.sub(r"[^0-9A-Za-z\u3005\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", "", s)
    if not core:
        return None
    ratio = len(found) / len(core)
    if ratio < threshold and len(core) < min_chars:
        return None
    sample = "".join(dict.fromkeys(found))[:12]
    gabung = "".join(found)
    if _HANGUL.search(gabung):
        nama = "Korea"
    elif _KANA.search(gabung):
        nama = "Jepang"
    else:
        # Han tanpa kana dan tanpa hangul. Namai sebagai script, bukan bahasa
        # spesifik: Mandarin, CJK, dan Vietnam memakai Aksara Han yang sama,
        # jadi tidak bisa dibedakan dari teks saja.
        nama = "CJK/Han"
    return {
        "ratio": round(ratio, 4),
        "count": len(found),
        "sample": sample,
        "script": nama,
    }


def audit_language(meta, options=None):
    """Periksa hasil metadata untuk aksara yang tidak diminta.

    Mengembalikan dict berisi 'ok', 'warnings' (list of dict per field), dan
    'partial'. Sengaja TIDAK mengubah isi metadata: user berhak melihat apa
    yang sebenarnya ditulis model, dan user bisa membetulkan sendiri.
    """
    options = options or {}
    want_cjk = bool(options.get("allow_cjk"))
    if want_cjk:
        return {"ok": True, "warnings": [], "partial": False}
    fields = ("titles", "description", "tags", "hashtags")
    warnings = []
    for name in fields:
        val = meta.get(name)
        if isinstance(val, list):
            gabung = " ".join(str(v) for v in val)
        else:
            gabung = str(val or "")
        det = detect_off_script(gabung)
        if det:
            warnings.append({"field": name, **det})
    return {
        "ok": not warnings,
        "warnings": warnings,
        "partial": bool(warnings) or bool(meta.get("partial")),
    }


def format_language_warning(audit, lang="Indonesian"):
    """Kalimat singkat yang bisa langsung ditampilkan di UI."""
    if audit.get("ok"):
        return ""
    parts = []
    for w in audit.get("warnings", []):
        parts.append(
            f"{w['field']}: karakter {w['script']} ({w['sample']})"
        )
    return (
        "Hasil metadata mengandung karakter di luar bahasa yang diminta: "
        + "; ".join(parts)
        + ". Model lokal biasanya perlu waktu lebih lama untuk menghasilkan output "
        f"{lang} yang konsisten - coba model yang lebih besar, turunkan "
        "suhu, atau tambahkan instruksi bahasa di kolom catatan."
    )


def youtube_limits():
    """Batas yang dipaksakan YouTube, dipakai untuk explanation di UI."""
    return {
        "title": 100,
        "description": YOUTUBE_DESC_LIMIT,
        "tag_max_len": MAX_TRANSLIT_LEN,
        "tags_total": 500,
        "hashtags": MAX_HASHTAGS,
    }
