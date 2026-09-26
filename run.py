import os
import re
import json
import sys
import subprocess
import requests
import shutil
from urllib.parse import urlparse, parse_qs
import argparse
import warnings
from portable_runtime import IS_FROZEN, tool, ytdlp_cmd
warnings.filterwarnings("ignore")

OUTPUT_DIR = "clips"      # Directory where generated clips will be saved
MAX_DURATION = 60         # Maximum duration (in seconds) for each clip
MIN_SCORE = 0.40          # Minimum heatmap intensity score to be considered viral
MAX_CLIPS = 10            # Maximum number of clips to generate per video
MAX_WORKERS = 1           # Number of parallel workers (reserved for future concurrency)
PADDING = 10              # Extra seconds added before and after each detected segment
TOP_HEIGHT = 960          # Height for top section (center content) in split mode
BOTTOM_HEIGHT = 320       # Height for bottom section (facecam) in split mode
USE_SUBTITLE = True       # Enable auto subtitle using Faster-Whisper (4-5x faster)
WHISPER_MODEL = "small"    # Whisper model size: tiny, base, small, medium, large
SUBTITLE_FONT = "Arial"
SUBTITLE_FONTS_DIR = None
SUBTITLE_LOCATION = "bottom"
OUTPUT_RATIO = "9:16"
OUT_WIDTH = 720
OUT_HEIGHT = 1280


def set_ratio_preset(preset):
    global OUTPUT_RATIO, OUT_WIDTH, OUT_HEIGHT
    OUTPUT_RATIO = preset
    if preset == "9:16":
        OUT_WIDTH, OUT_HEIGHT = 720, 1280
        return
    if preset == "1:1":
        OUT_WIDTH, OUT_HEIGHT = 720, 720
        return
    if preset == "16:9":
        OUT_WIDTH, OUT_HEIGHT = 1280, 720
        return
    if preset == "original":
        OUT_WIDTH, OUT_HEIGHT = None, None
        return
    raise ValueError("Invalid ratio preset")

def ffmpeg_bin():
    """Path ffmpeg: pakai yang bundled di bin/ kalau ada, else PATH."""
    return tool("ffmpeg")


def ffmpeg_tersedia():
    candidate = ffmpeg_bin()
    if os.path.isabs(candidate) and os.path.isfile(candidate):
        return True
    return bool(shutil.which("ffmpeg"))


def coba_masukkan_ffmpeg_ke_path():
    if ffmpeg_tersedia():
        return True

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return False

    winget_packages = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
    gyan_root = os.path.join(winget_packages, "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe")
    if not os.path.isdir(gyan_root):
        return False

    found_bin_dir = None
    for root, dirs, files in os.walk(gyan_root):
        if "ffmpeg.exe" in files and os.path.basename(root).lower() == "bin":
            found_bin_dir = root
            break

    if not found_bin_dir:
        return False

    os.environ["PATH"] = f"{found_bin_dir};{os.environ.get('PATH', '')}"
    return ffmpeg_tersedia()


def parse_args():
    parser = argparse.ArgumentParser(prog="yt-heatmap-clipper")
    parser.add_argument("--url", help="YouTube URL (watch/shorts/youtu.be)")
    parser.add_argument(
        "--crop",
        choices=["default", "split_left", "split_right"],
        help="Crop mode",
    )
    parser.add_argument(
        "--subtitle",
        choices=["y", "n"],
        help="Enable auto subtitle (y/n)",
    )
    parser.add_argument("--whisper-model", dest="whisper_model", help="Faster-Whisper model")
    parser.add_argument("--subtitle-font", dest="subtitle_font", help="Subtitle font name (e.g., Poppins)")
    parser.add_argument("--subtitle-fontsdir", dest="subtitle_fontsdir", help="Folder containing .ttf/.otf fonts")
    parser.add_argument(
        "--subtitle-location",
        dest="subtitle_location",
        choices=["center", "bottom"],
        help="Subtitle placement: center or bottom",
    )
    parser.add_argument("--ratio", choices=["9:16", "1:1", "16:9", "original"], help="Output ratio preset")
    parser.add_argument("--check", action="store_true", help="Check dependencies then exit")
    parser.add_argument("--no-update-ytdlp", action="store_true", help="Skip auto-update yt-dlp")
    return parser.parse_args()


def escape_subtitles_filter_path(path):
    abs_path = os.path.abspath(path)
    return abs_path.replace("\\", "/").replace(":", "\\:")


def escape_subtitles_filter_dir(path):
    abs_path = os.path.abspath(path)
    return abs_path.replace("\\", "/").replace(":", "\\:")

def build_subtitle_force_style():
    alignment = "2" if SUBTITLE_LOCATION == "bottom" else "5"
    margin_v = "40" if SUBTITLE_LOCATION == "bottom" else "0"
    return (
        f"FontName={SUBTITLE_FONT},FontSize=12,Bold=1,"
        f"PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
        f"BorderStyle=1,Outline=2,Shadow=1,"
        f"Alignment={alignment},MarginV={margin_v}"
    )


def build_cover_scale_crop_vf(out_w, out_h):
    ar_expr = f"{out_w}/{out_h}"
    scale = f"scale='if(gte(iw/ih,{ar_expr}),-2,{out_w})':'if(gte(iw/ih,{ar_expr}),{out_h},-2)'"
    crop = f"crop={out_w}:{out_h}:(iw-{out_w})/2:(ih-{out_h})/2"
    return f"{scale},{crop}"


def build_cover_scale_vf(out_w, out_h):
    ar_expr = f"{out_w}/{out_h}"
    scale = f"scale='if(gte(iw/ih,{ar_expr}),-2,{out_w})':'if(gte(iw/ih,{ar_expr}),{out_h},-2)'"
    return scale


def get_split_heights(out_h):
    if not out_h:
        return None, None
    bottom = min(BOTTOM_HEIGHT, max(1, out_h - 1))
    top = max(1, out_h - bottom)
    return top, bottom
def extract_video_id(url):
    """
    Extract the YouTube video ID from a given URL.
    Supports standard YouTube URLs, shortened URLs, and Shorts URLs.
    """
    parsed = urlparse(url)

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path[1:]

    if parsed.hostname in ("youtube.com", "www.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/")[2]

    return None


def get_model_size(model):
    """
    Get the approximate size of a Whisper model.
    """
    sizes = {
        "tiny": "75 MB",
        "base": "142 MB",
        "small": "466 MB",
        "medium": "1.5 GB",
        "large-v1": "2.9 GB",
        "large-v2": "2.9 GB",
        "large-v3": "2.9 GB"
    }
    return sizes.get(model, "unknown size")


def cek_dependensi(install_whisper=False, fatal=True):
    """
    Ensure required dependencies are available.
    Automatically updates yt-dlp and checks FFmpeg availability.
    """
    global WHISPER_MODEL
    args = getattr(cek_dependensi, "_args", None)
    skip_update = bool(getattr(args, "no_update_ytdlp", False)) if args else False

    if not skip_update and not IS_FROZEN:
        # Paket portable tidak punya pip; yt-dlp-nya adalah bin/yt-dlp.exe
        # dan bisa di-upgrade user dengan menukar file itu.
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    if install_whisper:
        # Check if faster-whisper package is installed
        try:
            import faster_whisper
            print(f"✅ Faster-Whisper package installed.")
            
            # Check if selected model is cached
            cache_dir = os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
            model_name = f"faster-whisper-{WHISPER_MODEL}"
            
            model_cached = False
            if os.path.exists(cache_dir):
                try:
                    cached_items = os.listdir(cache_dir)
                    model_cached = any(model_name in item.lower() for item in cached_items)
                except Exception:
                    pass
            
            if model_cached:
                print(f"✅ Model '{WHISPER_MODEL}' already cached and ready.\n")
            else:
                print(f"⚠️  Model '{WHISPER_MODEL}' not found in cache.")
                print(f"   📥 Will auto-download ~{get_model_size(WHISPER_MODEL)} on first transcribe.")
                print(f"   ⏱️  Download happens only once, then cached for future use.\n")
                
        except ImportError:
            if IS_FROZEN:
                print("⚠️  Faster-Whisper tidak ada di paket portable ini.")
                print("    Paket ini dibuat tanpa fitur subtitle AI.")
                print("    Jalankan tanpa subtitle, atau rebuild paket dengan subtitle.")
                if fatal:
                    sys.exit(1)
                return False
            print("📦 Installing Faster-Whisper package...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"✅ Faster-Whisper package installed successfully.")
            print(f"⚠️  Model '{WHISPER_MODEL}' (~{get_model_size(WHISPER_MODEL)}) will be downloaded on first use.\n")

    coba_masukkan_ffmpeg_ke_path()
    if not ffmpeg_tersedia():
        print("FFmpeg not found. Please install FFmpeg and ensure it is in PATH.")
        if fatal:
            sys.exit(1)
        return False
    return True


WATCH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


PLAYABILITY_GAGAL = (
    "ERROR",
    "UNPLAYABLE",
    "LOGIN_REQUIRED",
    "AGE_VERIFICATION_REQUIRED",
    "AGE_CHECK_REQUIRED",
    "CONTENT_CHECK_REQUIRED",
    "AGE_RESTRICTED",
)


def _status_playability(html):
    """Baca playabilityStatus.status dari HTML halaman tontonan."""
    m = re.search(r'"playabilityStatus":\{"status":"([A-Z_]+)"', html or "")
    return m.group(1) if m else ""


def durasi_dari_html(html):
    """
    Ambil durasi video dari videoDetails.lengthSeconds.

    Number ini selalu ada kalau video bisa diputar, dan nilainya sama dengan
    yang dikembalikan yt-dlp -- tapi kita sudah memegang HTML-nya, jadi tidak
    perlu request kedua (dan tidak kena rate limit YouTube).
    """
    m = re.search(r'"lengthSeconds":"(\d+)"', html or "")
    if not m:
        return 0
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return 0


def _ambil_html_watch(video_id, timeout=20):
    """
    Ambil HTML halaman tontonan.
    Return (html, error) dengan error: None | 'network' | 'consent' | 'notfound'.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": WATCH_UA,
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        res = requests.get(url, headers=headers, timeout=timeout)
    except Exception:
        return None, "network"

    html = res.text or ""

    if res.status_code == 404:
        return html, "notfound"

    status = _status_playability(html)

    # Penting: jangan searching teks "Video unavailable" di HTML. String itu
    # bagian dari tabel terjemahan YouTube yang ada di SETIAP halaman, termasuk
    # video yang sehat. Satu-satunya sinyal yang bisa dipercaya adalah
    # playabilityStatus.
    if status in PLAYABILITY_GAGAL:
        return html, "notfound"

    # Halaman interstitial persetujuan / verifikasi bot tidak pernah memuat
    # data player, jadi mustahil ada heatmap di dalamnya.
    if "consent.youtube.com" in html or "Sign in to confirm" in html:
        return html, "consent"
    if "ytInitialPlayerResponse" not in html:
        return html, "consent"

    return html, None


def _cari_array_markers(html):
    """
    Ekstrak array "markers" dari HTML dengan pemindaian kurung seimbang.

    Regex lama ('"markers":[...],"markersMetadata"') rapuh: begitu YouTube
    mengganti nama key tetangga, match gagal dan hasilnya kosong tanpa alasan.
    Versi ini tidak peduli key apa yang mengikuti array.
    """
    awal = html.find('"markers"')
    if awal < 0:
        return None

    # Lompat ke tanda '[' pertama sesudah "markers"
    i = html.find("[", awal)
    if i < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for j in range(i, min(len(html), i + 400000)):
        c = html[j]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return html[i:j + 1]

    return None


def _marker_ke_segment(marker, threshold):
    """Konversi satu marker heatmap jadi dict segment, atau None."""
    if not isinstance(marker, dict):
        return None
    if "heatMarkerRenderer" in marker and isinstance(marker["heatMarkerRenderer"], dict):
        marker = marker["heatMarkerRenderer"]

    try:
        score = float(marker.get("intensityScoreNormalized", 0))
        start = float(marker["startMillis"]) / 1000
        dur = float(marker.get("durationMillis", 0)) / 1000
    except (KeyError, TypeError, ValueError):
        return None

    if score < threshold:
        return None
    if dur <= 0:
        dur = 2.0

    return {
        "start": start,
        "duration": min(dur, MAX_DURATION),
        "score": score,
    }


def gabung_marker(markers, threshold=MIN_SCORE, min_gap=0.0):
    """
    Gabungkan marker yang bersebelahan jadi momen utuh.

    YouTube memecah heatmap jadi ~100 keranjjang 2 detik. Kalau tiap keranjjang
    dipotong sendiri, hasilnya 10 clip yang isinya nyaris sama. Menggabungkan
    rentang yang skor tinggi-nya nyambung jadi momen yang benar-benar terpisah.
    """
    terfilter = [
        m for m in (_marker_ke_segment(x, threshold) for x in markers) if m
    ]
    terfilter.sort(key=lambda x: x["start"])
    if not terfilter:
        return []

    hasil = []
    berjalan = dict(terfilter[0])
    for m in terfilter[1:]:
        # Sentuh / nyambung dengan momen sebelumnya?
        if m["start"] <= berjalan["start"] + berjalan["duration"] + min_gap:
            ujung = m["start"] + m["duration"]
            if ujung > berjalan["start"] + berjalan["duration"]:
                berjalan["duration"] = min(
                    ujung - berjalan["start"], MAX_DURATION
                )
            berjalan["score"] = max(berjalan["score"], m["score"])
        else:
            hasil.append(berjalan)
            berjalan = dict(m)
    hasil.append(berjalan)

    hasil.sort(key=lambda x: x["score"], reverse=True)
    return hasil


def scan_heatmap(video_id, timeout=20):
    """
    Ambil data 'Most Replayed' plus alasan kalau gagal.

    Return dict:
      ok        -> bool
      source    -> 'heatmap' | 'fallback'
      reason    -> kode singkat untuk ditampilkan ke user
      detail    -> penjelasan human-readable
      segments  -> list segment
      markers   -> jumlah marker mentah yang dibaca YouTube (0 = tidak ada)
    """
    html, error = _ambil_html_watch(video_id, timeout=timeout)
    durasi = durasi_dari_html(html or "")

    if error == "network":
        return {
            "ok": False, "source": "none", "reason": "network",
            "detail": "Tidak bisa menghubungi YouTube. Cek koneksi internet.",
            "segments": [], "markers": 0, "duration": durasi,
        }
    if error == "consent":
        return {
            "ok": False, "source": "none", "reason": "consent",
            "detail": (
                "YouTube meminta verifikasi sebelum menampilkan halaman "
                "(consent/bot check). Buka link videonya di browser, "
                "selesai verifikasinya, lalu scan ulang."
            ),
            "segments": [], "markers": 0, "duration": durasi,
        }
    if error == "notfound":
        return {
            "ok": False, "source": "none", "reason": "notfound",
            "detail": "Video tidak ditemukan atau tidak bisa diakses.",
            "segments": [], "markers": 0, "duration": durasi,
        }

    blok = _cari_array_markers(html or "")
    if not blok:
        return {
            "ok": False, "source": "none", "reason": "no_heatmap",
            "detail": (
                "YouTube tidak menyediakan data Most Replayed untuk video ini "
                "(biasanya video pendek, baru diunggah, atau viewersnya masih sedikit)."
            ),
            "segments": [], "markers": 0, "duration": durasi,
        }

    try:
        markers = json.loads(blok)
    except Exception:
        return {
            "ok": False, "source": "none", "reason": "parse",
            "detail": "Data heatmap tidak bisa dibaca (format YouTube berubah).",
            "segments": [], "markers": 0, "duration": durasi,
        }

    if not isinstance(markers, list):
        markers = []

    segments = gabung_marker(markers)

    if not segments:
        return {
            "ok": False, "source": "none", "reason": "below_threshold",
            "detail": (
                f"Heatmap terbaca ({len(markers)} titik) tapi tidak ada satu "
                f"pun yang melewati ambang MIN_SCORE {MIN_SCORE}."
            ),
            "segments": [], "markers": len(markers), "duration": durasi,
        }

    return {
        "ok": True, "source": "heatmap", "reason": "",
        "detail": "",
        "segments": segments, "markers": len(markers), "duration": durasi,
    }


def ambil_most_replayed(video_id, timeout=20):
    """
    Backward compatible: kembalikan list segment saja.
    """
    return scan_heatmap(video_id, timeout=timeout)["segments"]


def fallback_segments(total_duration, count=5):
    """
    Susun segment berjarak merata untuk video tanpa data heatmap.

    Dipakai supaya tool tetap menghasilkan clip, bukan keluar kosong.
    Semua segment diberi score 0.0 supaya UI bisa menandai asal-usulnya.
    """
    durasi = float(total_duration or 0)
    if durasi <= 0:
        return []

    # Jeda antar potongan supaya tidak saling tumpang tindih.
    jeda = 5.0
    # Setiap potongan harus dapat minimal 30 detik (termasuk jeda), kalau tidak
    # video pendek berubah jadi potongan yang tumpang tindih.
    n = max(1, min(int(count), int(durasi // 30)))

    if n == 1:
        return [{"start": 0.0, "duration": round(durasi, 2), "score": 0.0}]

    slot = durasi / n
    panjang = min(MAX_DURATION, slot - jeda)

    hasil = []
    for i in range(n):
        start = i * slot
        hasil.append({
            "start": round(start, 2),
            "duration": round(min(panjang, durasi - start), 2),
            "score": 0.0,
        })
    return hasil


def get_duration(video_id, fallback=0):
    """
    Retrieve the total duration of a video in seconds.

    Default lama adalah 3600, yang diam-diam menghasilkan titik potong salah
    setiap kali yt-dlp gagal (kena rate limit, tanpa JS runtime, video privat).
    Sekarang mengembalikan `fallback` (default 0) supaya pemanggil bisa
    bereaksi, bukan memotong clip 60 menit dari video 20 detik.
    """
    cmd = [
        *ytdlp_cmd(),
        "--get-duration",
        f"https://youtu.be/{video_id}"
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        out = (res.stdout or "").strip()

        # yt-dlp kadang menulis durasi dengan desimal ("252.0") atau menambah
        # baris lain ke stdout, jadi ambil baris terakhir yang terbaca durasi.
        for baris in reversed(out.splitlines()):
            baris = baris.strip()
            if not baris or baris.startswith("ERROR") or baris.startswith("WARNING"):
                continue
            try:
                return int(float(baris))
            except ValueError:
                time_parts = baris.split(":")
                if len(time_parts) in (2, 3):
                    try:
                        detik = [int(float(x)) for x in time_parts]
                    except ValueError:
                        continue
                    if len(detik) == 2:
                        return detik[0] * 60 + detik[1]
                    return detik[0] * 3600 + detik[1] * 60 + detik[2]
    except Exception:
        pass

    return fallback


def ambil_durasi(video_id):
    """
    Durasi video, andalkan sumber paling murah dulu.

    yt-dlp lebih akurat untuk Shorts/live, tapi sering kena rate limit kalau
    dipanggil terus-menerus. Karena itu HTML dipakai sebagai cadangan, dan
    angka lengthSeconds di sana selalu ada untuk video yang bisa diputar.
    """
    dur = get_duration(video_id)
    if dur > 0:
        return dur

    html, _err = _ambil_html_watch(video_id)
    return durasi_dari_html(html or "")


def generate_subtitle(video_file, subtitle_file, event_hook=None):
    """
    Generate subtitle file using Faster-Whisper for the given video.
    Returns True if successful, False otherwise.
    """
    from faster_whisper import WhisperModel

    def load_and_transcribe():
        if callable(event_hook):
            try:
                event_hook("stage", {"stage": "subtitle_model_load"})
            except Exception:
                pass
        print(f"  Loading Faster-Whisper model '{WHISPER_MODEL}'...")
        print(f"  (If this is first time, downloading ~{get_model_size(WHISPER_MODEL)}...)")
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        print("  ✅ Model loaded. Transcribing audio (4-5x faster than standard Whisper)...")
        if callable(event_hook):
            try:
                event_hook("stage", {"stage": "subtitle_transcribe"})
            except Exception:
                pass
        segments, info = model.transcribe(video_file, language="id")
        return segments

    try:
        segments = load_and_transcribe()
    except Exception as e:
        msg = str(e)
        if os.name == "nt" and "WinError 1314" in msg:
            print(f"  Failed to generate subtitle: {msg}")
            print("  Windows kamu kelihatan tidak mengizinkan symlink (HuggingFace cache).")
            print("  Retrying sekali lagi (biasanya langsung beres setelah fallback cache aktif)...")
            try:
                segments = load_and_transcribe()
            except Exception as e2:
                print(f"  Failed to generate subtitle: {str(e2)}")
                return False
        else:
            print(f"  Failed to generate subtitle: {msg}")
            return False

    if callable(event_hook):
        try:
            event_hook("stage", {"stage": "subtitle_write"})
        except Exception:
            pass
    print("  Generating subtitle file...")
    with open(subtitle_file, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments, start=1):
            start_time = format_timestamp(segment.start)
            end_time = format_timestamp(segment.end)
            text = segment.text.strip()

            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")

    return True


def format_timestamp(seconds):
    """
    Convert seconds to SRT timestamp format (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def proses_satu_clip(video_id, item, index, total_duration, crop_mode="default", use_subtitle=False, event_hook=None):
    """
    Download, crop, and export a single vertical clip
    based on a heatmap segment.
    
    Args:
        crop_mode: "default", "split_left", or "split_right"
        use_subtitle: whether to generate and burn subtitle
    """
    start_original = item["start"]
    end_original = item["start"] + item["duration"]

    start = max(0, start_original - PADDING)
    end = min(end_original + PADDING, total_duration)

    if end - start < 3:
        return False

    temp_file = f"temp_{index}.mkv"
    cropped_file = f"temp_cropped_{index}.mp4"
    subtitle_file = f"temp_{index}.srt"
    output_file = os.path.join(OUTPUT_DIR, f"clip_{index}.mp4")

    print(
        f"[Clip {index}] Processing segment "
        f"({int(start)}s - {int(end)}s, padding {PADDING}s)"
    )
    if callable(event_hook):
        try:
            event_hook("stage", {"stage": "download", "clip_index": index})
        except Exception:
            pass

    cmd_download = [
        *ytdlp_cmd(),
        "--force-ipv4",
        "--quiet", "--no-warnings",
        "--downloader", "ffmpeg",
        "--downloader-args",
        f"ffmpeg_i:-ss {start} -to {end} -hide_banner -loglevel error",
        "--merge-output-format", "mkv",
        "-f",
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "-o", temp_file,
        f"https://youtu.be/{video_id}"
    ]
    cmd_download_fallback = [
        *ytdlp_cmd(),
        "--force-ipv4",
        "--quiet", "--no-warnings",
        "--downloader", "ffmpeg",
        "--downloader-args",
        f"ffmpeg_i:-ss {start} -to {end} -hide_banner -loglevel error",
        "--merge-output-format", "mkv",
        "-f", "bv*+ba/b",
        "-o", temp_file,
        f"https://youtu.be/{video_id}"
    ]

    try:
        try:
            subprocess.run(
                cmd_download,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            if "Requested format is not available" in stderr:
                subprocess.run(
                    cmd_download_fallback,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                raise

        if not os.path.exists(temp_file):
            print("Failed to download video segment.")
            return False

        out_w, out_h = OUT_WIDTH, OUT_HEIGHT
        if crop_mode == "default":
            if OUTPUT_RATIO == "original":
                cmd_crop = [
                    ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", temp_file,
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "aac", "-b:a", "128k",
                    cropped_file
                ]
            else:
                vf = build_cover_scale_crop_vf(out_w, out_h)
                cmd_crop = [
                    ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", temp_file,
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "aac", "-b:a", "128k",
                    cropped_file
                ]
        elif crop_mode == "split_left":
            if OUTPUT_RATIO == "original" or not out_w or not out_h or out_h < out_w:
                vf = build_cover_scale_crop_vf(out_w or 720, out_h or 1280) if OUTPUT_RATIO != "original" else None
                cmd_crop = [
                    ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", temp_file,
                    *([] if not vf else ["-vf", vf]),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "aac", "-b:a", "128k",
                    cropped_file
                ]
            else:
                top_h, bottom_h = get_split_heights(out_h)
                scaled = build_cover_scale_vf(out_w, out_h)
                vf = (
                    f"{scaled}[scaled];"
                    f"[scaled]split=2[s1][s2];"
                    f"[s1]crop={out_w}:{top_h}:(iw-{out_w})/2:(ih-{out_h})/2[top];"
                    f"[s2]crop={out_w}:{bottom_h}:0:ih-{bottom_h}[bottom];"
                    f"[top][bottom]vstack[out]"
                )
                cmd_crop = [
                    ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", temp_file,
                    "-filter_complex", vf,
                    "-map", "[out]", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "aac", "-b:a", "128k",
                    cropped_file
                ]
        elif crop_mode == "split_right":
            if OUTPUT_RATIO == "original" or not out_w or not out_h or out_h < out_w:
                vf = build_cover_scale_crop_vf(out_w or 720, out_h or 1280) if OUTPUT_RATIO != "original" else None
                cmd_crop = [
                    ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", temp_file,
                    *([] if not vf else ["-vf", vf]),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "aac", "-b:a", "128k",
                    cropped_file
                ]
            else:
                top_h, bottom_h = get_split_heights(out_h)
                scaled = build_cover_scale_vf(out_w, out_h)
                vf = (
                    f"{scaled}[scaled];"
                    f"[scaled]split=2[s1][s2];"
                    f"[s1]crop={out_w}:{top_h}:(iw-{out_w})/2:(ih-{out_h})/2[top];"
                    f"[s2]crop={out_w}:{bottom_h}:iw-{out_w}:ih-{bottom_h}[bottom];"
                    f"[top][bottom]vstack[out]"
                )
                cmd_crop = [
                    ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", temp_file,
                    "-filter_complex", vf,
                    "-map", "[out]", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "aac", "-b:a", "128k",
                    cropped_file
                ]

        if callable(event_hook):
            try:
                event_hook("stage", {"stage": "crop", "clip_index": index})
            except Exception:
                pass
        print("  Cropping video...")
        result = subprocess.run(
            cmd_crop,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        os.remove(temp_file)

        # Generate and burn subtitle if enabled
        if use_subtitle:
            if callable(event_hook):
                try:
                    event_hook("stage", {"stage": "subtitle", "clip_index": index})
                except Exception:
                    pass
            print("  Generating subtitle...")
            if generate_subtitle(cropped_file, subtitle_file, event_hook=event_hook):
                if callable(event_hook):
                    try:
                        event_hook("stage", {"stage": "burn_subtitle", "clip_index": index})
                    except Exception:
                        pass
                print("  Burning subtitle to video...")
                # Get absolute path for subtitle file
                subtitle_path = escape_subtitles_filter_path(subtitle_file)
                fonts_dir = SUBTITLE_FONTS_DIR
                fontsdir_arg = ""
                if fonts_dir and os.path.isdir(fonts_dir):
                    fontsdir_arg = f":fontsdir='{escape_subtitles_filter_dir(fonts_dir)}'"
                
                force_style = build_subtitle_force_style()
                cmd_subtitle = [
                    ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", cropped_file,
                    "-vf", f"subtitles='{subtitle_path}'{fontsdir_arg}:force_style='{force_style}'",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "copy",
                    output_file
                ]
                
                result = subprocess.run(
                    cmd_subtitle,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                os.remove(cropped_file)
                os.remove(subtitle_file)
            else:
                # If subtitle generation failed, use cropped file as output
                print("  Subtitle generation failed, continuing without subtitle...")
                if callable(event_hook):
                    try:
                        event_hook("stage", {"stage": "finalize", "clip_index": index})
                    except Exception:
                        pass
                os.rename(cropped_file, output_file)
        else:
            # No subtitle, rename cropped file to output
            if callable(event_hook):
                try:
                    event_hook("stage", {"stage": "finalize", "clip_index": index})
                except Exception:
                    pass
            os.rename(cropped_file, output_file)

        print("Clip successfully generated.")
        if callable(event_hook):
            try:
                event_hook("stage", {"stage": "done_clip", "clip_index": index})
            except Exception:
                pass
        return True

    except subprocess.CalledProcessError as e:
        # Cleanup temp files
        for f in [temp_file, cropped_file, subtitle_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        print(f"Failed to generate this clip.")
        print(f"Error details: {e.stderr if e.stderr else e.stdout}")
        return False
    except Exception as e:
        # Cleanup temp files
        for f in [temp_file, cropped_file, subtitle_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        print(f"Failed to generate this clip.")
        print(f"Error: {str(e)}")
        return False


def main():
    """
    Main entry point of the application.
    """
    args = parse_args()
    cek_dependensi._args = args

    if args.whisper_model:
        global WHISPER_MODEL
        WHISPER_MODEL = args.whisper_model
    if args.subtitle_font:
        global SUBTITLE_FONT
        SUBTITLE_FONT = args.subtitle_font
    if args.subtitle_fontsdir:
        global SUBTITLE_FONTS_DIR
        SUBTITLE_FONTS_DIR = args.subtitle_fontsdir
    if args.subtitle_location:
        global SUBTITLE_LOCATION
        SUBTITLE_LOCATION = args.subtitle_location
    if args.ratio:
        set_ratio_preset(args.ratio)

    if args.check:
        cek_dependensi(install_whisper=False)
        print("✅ Basic dependencies OK.")
        return

    coba_masukkan_ffmpeg_ke_path()
    if not ffmpeg_tersedia():
        print("FFmpeg not found. Please install FFmpeg and ensure it is in PATH.")
        return

    crop_mode = args.crop
    crop_desc = None
    if crop_mode:
        crop_desc = {
            "default": "Default center crop",
            "split_left": "Split crop (bottom-left facecam)",
            "split_right": "Split crop (bottom-right facecam)",
        }[crop_mode]

    subtitle_choice = args.subtitle
    if subtitle_choice:
        use_subtitle = subtitle_choice == "y"
    else:
        use_subtitle = None

    link = args.url

    if crop_mode is None or use_subtitle is None or not link:
        print("\n=== Crop Mode ===")
        print("1. Default (center crop)")
        print("2. Split 1 (top: center, bottom: bottom-left (facecam))")
        print("3. Split 2 (top: center, bottom: bottom-right ((facecam))")

        while crop_mode is None:
            choice = input("\nSelect crop mode (1-3): ").strip()
            if choice == "1":
                crop_mode = "default"
                crop_desc = "Default center crop"
                break
            if choice == "2":
                crop_mode = "split_left"
                crop_desc = "Split crop (bottom-left facecam)"
                break
            if choice == "3":
                crop_mode = "split_right"
                crop_desc = "Split crop (bottom-right facecam)"
                break
            print("Invalid choice. Please enter 1, 2, or 3.")

        print(f"Selected: {crop_desc}")

        print("\n=== Auto Subtitle ===")
        print(f"Available model: {WHISPER_MODEL} (~{get_model_size(WHISPER_MODEL)})")
        while use_subtitle is None:
            subtitle_choice = input("Add auto subtitle using Faster-Whisper? (y/n): ").strip().lower()
            if subtitle_choice in ["y", "yes"]:
                use_subtitle = True
            elif subtitle_choice in ["n", "no"]:
                use_subtitle = False
            else:
                print("Invalid choice. Please enter y or n.")

        if use_subtitle:
            print(f"✅ Subtitle enabled (Model: {WHISPER_MODEL}, Bahasa Indonesia)")
        else:
            print("❌ Subtitle disabled")

        print()

        cek_dependensi(install_whisper=use_subtitle)

        if not link:
            link = input("Link YT: ").strip()
    else:
        cek_dependensi(install_whisper=use_subtitle)

    video_id = extract_video_id(link)

    if not video_id:
        print("Invalid YouTube link.")
        return

    print("Reading YouTube heatmap data...")
    hasil = scan_heatmap(video_id)
    heatmap_data = hasil["segments"]
    total_duration = get_duration(video_id)

    if heatmap_data:
        print(
            f"Found {len(heatmap_data)} high-engagement moment(s) "
            f"from {hasil['markers']} heatmap marker(s)."
        )
    else:
        # Tidak berhenti di sini: video pendek/baru tidak punya Most Replayed,
        # tapi user tetap harusnya bisa dapat clip dari video itu.
        if hasil["reason"] in ("network", "consent", "notfound"):
            print(f"Heatmap gagal dibaca: {hasil['detail']}")
            return
        print(f"Heatmap tidak tersedia: {hasil['detail']}")
        heatmap_data = fallback_segments(total_duration, count=MAX_CLIPS)
        if not heatmap_data:
            print("Tidak bisa menentukan durasi video, tidak ada clip yang bisa dibuat.")
            return
        print(
            f"Fallback: {len(heatmap_data)} equally spaced segment(s) "
            f"dari {total_duration}s video."
        )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(
        f"Processing clips with {PADDING}s pre-padding "
        f"and {PADDING}s post-padding."
    )
    print(f"Using crop mode: {crop_desc}")

    success_count = 0

    for item in heatmap_data:
        if success_count >= MAX_CLIPS:
            break

        if proses_satu_clip(
            video_id,
            item,
            success_count + 1,
            total_duration,
            crop_mode,
            use_subtitle
        ):
            success_count += 1

    print(
        f"Finished processing. "
        f"{success_count} clip(s) successfully saved to '{OUTPUT_DIR}'."
    )


if __name__ == "__main__":
    main()
