"""
Server OpenAI-compatible palsu untuk menguji integrasi AI tanpa LLM sungguhan.

Ini BUKAN mock: ini HTTP server sungguhan yang menerima POST
/v1/chat/completions dan membalas seperti Ollama/LM Studio. Dipakai supaya
jalur jaringan, parsing header, dan decoding respons ikut teruji.

Jalankan:  python tools/fake_ai_server.py [port]
"""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _wrap(content):
    """Bungkus teks jadi respons OpenAI-compatible."""
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "model": "fake",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 300, "completion_tokens": 120},
    }


_BAIK = {
    "titles": [
        "FisiKA: Momentum Setelah Latihan",
        "Momentum dan Impuls: Penjelasan Sederhana",
        "Kenapa Momentum Penting dalam Olahraga",
    ],
    "description": (
        "Di video ini kita bahas momentum dan impuls dalam olahraga.\n\n"
        "Momentum menentukan seberapa sulit menghentikan benda yang bergerak, "
        "sedangkan impuls berkaitan dengan gaya dan waktu.\n\n"
        "- Konsep momentum\n"
        "- Hubungan dengan impuls\n"
        "- Contoh dalam olahraga\n\n"
        "Kalau masih bingung, tulis di komentar."
    ),
    "tags": [
        "momentum", "impuls", "fisika", "fisika sma", "momentumLinear",
        "gaya", "gerak", "belajar fisika", "tutorial fisika",
        "ilmupengetahuan", "videoshorts",
    ],
}


# Nama model menentukan cara server merespons, jadi tiap kasus ujinya
# bisa dipanggil lewat nama yang jelas.
MODES = {
    "good": {"content": json.dumps(_BAIK, ensure_ascii=False)},
    # Model kecil yang membungkus JSON dengan markdown fence.
    "fenced": {"content": '```json\n' + json.dumps(
        {"titles": ["Judul A", "Judul B"],
         "description": "Deskripsi\\n\\nparagraf dua",
         "tags": ["satu", "dua", "tiga"]}) + '\n```'},
    # Jawaban terpotong di tengah: harus diselamatkan jadi hasil parsial.
    "truncated": {"content": '```json\n{"titles": ["Judul utuh", "Judul kedua"], '
                             '"description": "Mulai adam'},
    # Model talkatif: penjelasan di luar JSON.
    "chatty": {"content": 'Tentu! Berikut hasilnya:\n\n' + json.dumps(
        {"titles": ["Satu", "Dua"], "description": "Isi", "tags": ["a", "b"]},
        ensure_ascii=False) + '\n\nSemoga membantu!'},
    # Judul & tag berantakan: duplikat, kapital, spasi, tanda pagar.
    "messy": {"content": json.dumps({
        "titles": ["1. Judul Bersih", "  JUDUL DUPLICAT  ", "judul bersih", "  3. Outro"],
        "description": "  Baris satu\n\n\n\n\n  Baris dua  ",
        "tags": ["#TagSatu", "tag satu", "TAG_DUA", "  tag_tiga  ", "12345", "  "],
    }, ensure_ascii=False)},
    "empty": {"content": "{}"},
    "refusal": {"content": "Maaf, saya tidak bisa membantu permintaan ini."},
    "server_error": {"status": 500, "raw": '{"error": {"message": "model out of memory"}}'},
    "not_found": {"status": 404, "raw": '{"error": {"message": "unknown endpoint"}}'},
    "bad_auth": {"status": 401, "raw": '{"error": {"message": "invalid api key"}}'},
    "slow": {"delay": 3, "content": json.dumps(
        {"titles": ["Lambat"], "description": "d", "tags": ["a"]})},
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if "--verbose" in sys.argv:
            sys.stderr.write("[fake-ai] " + (fmt % args) + "\n")

    def _send(self, code, payload, raw=False):
        body = payload.encode("utf-8") if raw else json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain" if raw else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send(200, {"data": [{"id": name} for name in MODES]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            self._send(400, {"error": "bad json"})
            return
        mode = MODES.get(req.get("model") or "good", MODES["good"])
        if mode.get("delay"):
            time.sleep(mode["delay"])
        status = mode.get("status", 200)
        if status != 200:
            self._send(status, mode.get("raw", "{}"), raw=True)
            return
        self._send(200, _wrap(mode["content"]))


def serve(port):
    """Jalankan server di background thread; kembalikan objeknya."""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 11555
    httpd = serve(port)
    print("fake OpenAI-compatible AI server di http://127.0.0.1:%d/v1" % port)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        httpd.shutdown()
