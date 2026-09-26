"""
Test untuk scan heatmap.

Semua test ini OFFLINE: fixture HTML disimpan di tests/fixtures/ supaya
hasilnya deterministik dan tidak bergantung koneksi internet.

Cara jalan:  python -m pytest tests/ -q
atau tanpa pytest:  python tests/test_heatmap_scan.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run as core  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def baca_fixture(nama):
    with open(os.path.join(FIXTURES, nama), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------- parser inti

def test_cari_markers_dari_html_nyata():
    """Fixture YouTube asli harus ketemu dan JSON-nya valid."""
    html = baca_fixture("watch_with_heatmap.html")
    blok = core._cari_array_markers(html)
    assert blok is not None, "markers tidak ketemu di fixture"
    data = json.loads(blok)
    assert isinstance(data, list)
    assert len(data) == 100
    assert "startMillis" in data[0]
    assert "intensityScoreNormalized" in data[0]


def test_parser_tidak_rapuh_terhadap_key_tetangga():
    """
    Regression test untuk bug utama.

    Regex lama demanding 'markersMetadata' langsung setelah array. Kalau
    YouTube mengganti key tetangga, hasilnya kosong. Parser baru harus tetap
    berhasil.
    """
    html = baca_fixture("watch_with_heatmap.html")
    blok_lama = re.search(
        r'"markers":\s*(\[.*?\])\s*,\s*"?markersMetadata"?', html, re.DOTALL
    )
    assert blok_lama, "fixture harus masih cocok dengan regex lama (kontrol)"

    # Buang markersMetadata, ganti dengan key lain - kondisi yang dulu bikin gagal
    html_tanpa_tetangga = html.replace(
        ',"markersMetadata":[{"key":"HEATMAP","label":"Most replayed"}]', ""
    )
    assert not re.search(
        r'"markers":\s*(\[.*?\])\s*,\s*"?markersMetadata"?',
        html_tanpa_tetangga, re.DOTALL
    ), "regex lama harus gagal di sini - kalau tidak, test ini tidak membuktikan apa-apa"

    blok_baru = core._cari_array_markers(html_tanpa_tetangga)
    assert blok_baru is not None, "parser baru gagal menemukan markers"
    assert len(json.loads(blok_baru)) == 100, "parser baru harus baca 100 marker"


def test_parser_handling_string_dengan_kurung():
    """Kurung di dalam string tidak boleh mengacaukan hitungan depth."""
    html = '{"markers":[{"startMillis":"0","durationMillis":"2000",' \
           '"intensityScoreNormalized":1,"label":"a]b[c"}],"next":1}'
    blok = core._cari_array_markers(html)
    assert blok is not None
    assert json.loads(blok)[0]["label"] == "a]b[c"


def test_parser_tidak_ada_markers():
    assert core._cari_array_markers(baca_fixture("watch_without_heatmap.html")) is None
    assert core._cari_array_markers("") is None
    assert core._cari_array_markers('{"markers": "bukan array"') is None


# ------------------------------------------------------------- gabung marker

def test_marker_kontigu_bergabung_jadi_satu_momen():
    markers = [
        {"startMillis": "0", "durationMillis": "2000", "intensityScoreNormalized": 0.9},
        {"startMillis": "2000", "durationMillis": "2000", "intensityScoreNormalized": 0.8},
        {"startMillis": "4000", "durationMillis": "2000", "intensityScoreNormalized": 0.7},
    ]
    hasil = core.gabung_marker(markers, threshold=0.40)
    assert len(hasil) == 1, "tiga marker bersebelahan harus jadi satu momen"
    assert hasil[0]["start"] == 0.0
    assert abs(hasil[0]["duration"] - 6.0) < 0.01
    assert abs(hasil[0]["score"] - 0.9) < 0.01


def test_marker_terpisah_jadi_beberapa_momen():
    markers = [
        {"startMillis": "0", "durationMillis": "2000", "intensityScoreNormalized": 0.9},
        {"startMillis": "60000", "durationMillis": "2000", "intensityScoreNormalized": 0.6},
    ]
    hasil = core.gabung_marker(markers, threshold=0.40)
    assert len(hasil) == 2
    assert hasil[0]["score"] == 0.9, "harus urut dari skor tertinggi"


def test_marker_rusak_di_skip():
    markers = [
        "bukan dict",
        {"tidak": "ada startMillis"},
        {"startMillis": "abc", "durationMillis": "2000", "intensityScoreNormalized": 1},
        {"startMillis": "0", "durationMillis": "2000", "intensityScoreNormalized": 1},
    ]
    hasil = core.gabung_marker(markers, threshold=0.40)
    assert len(hasil) == 1 and hasil[0]["start"] == 0.0


def test_marker_bawah_ambang_dibuang():
    markers = [
        {"startMillis": "0", "durationMillis": "2000", "intensityScoreNormalized": 0.1},
    ]
    assert core.gabung_marker(markers, threshold=0.40) == []


def test_heat_marker_renderer_masih_didukung():
    """Format lama heatMarkerRenderer tidak boleh ikut mati."""
    markers = [
        {"heatMarkerRenderer": {
            "startMillis": "1000", "durationMillis": "2000",
            "intensityScoreNormalized": 0.95
        }},
    ]
    hasil = core.gabung_marker(markers, threshold=0.40)
    assert len(hasil) == 1 and hasil[0]["start"] == 1.0


# ------------------------------------------------------------------- status

def test_scan_heatmap_berhasil_dari_fixture():
    """Simulasikan respons nyata supaya jalur indoors tidak perlu internet."""
    html = baca_fixture("watch_with_heatmap.html")
    asli = core._ambil_html_watch
    core._ambil_html_watch = lambda vid, timeout=20: (html, None)
    try:
        hasil = core.scan_heatmap("dummy")
    finally:
        core._ambil_html_watch = asli

    assert hasil["ok"] is True
    assert hasil["source"] == "heatmap"
    assert hasil["markers"] == 100
    assert len(hasil["segments"]) >= 1
    # 100 keranjjang 2 detik harus jadi jauh lebih sedikit momen
    assert len(hasil["segments"]) < 100


def test_scan_heatmap_melapor_alasan_bukan_kosong_diam_diam():
    """Ini inti bug yang dilaporkan: hasil kosong harus punya penjelasan."""
    html = baca_fixture("watch_without_heatmap.html")
    asli = core._ambil_html_watch
    core._ambil_html_watch = lambda vid, timeout=20: (html, None)
    try:
        hasil = core.scan_heatmap("dummy")
    finally:
        core._ambil_html_watch = asli

    assert hasil["ok"] is False
    assert hasil["source"] == "none"
    assert hasil["reason"] == "no_heatmap"
    assert hasil["segments"] == []
    assert hasil["detail"], "wajib ada penjelasan untuk user"


def test_scan_heatmap_deteksi_consent():
    asli = core._ambil_html_watch
    core._ambil_html_watch = lambda vid, timeout=20: ("<html>Sign in to confirm</html>", "consent")
    try:
        hasil = core.scan_heatmap("dummy")
    finally:
        core._ambil_html_watch = asli
    assert hasil["reason"] == "consent"


def test_scan_heatmap_deteksi_network():
    asli = core._ambil_html_watch
    core._ambil_html_watch = lambda vid, timeout=20: (None, "network")
    try:
        hasil = core.scan_heatmap("dummy")
    finally:
        core._ambil_html_watch = asli
    assert hasil["reason"] == "network"


def test_ambil_most_replayed_tetap_kembalikan_list():
    """Backward compatibility: fungsi lama harus tetap mengembalikan list."""
    html = baca_fixture("watch_with_heatmap.html")
    asli = core._ambil_html_watch
    core._ambil_html_watch = lambda vid, timeout=20: (html, None)
    try:
        hasil = core.ambil_most_replayed("dummy")
    finally:
        core._ambil_html_watch = asli
    assert isinstance(hasil, list) and len(hasil) > 0
    assert set(hasil[0].keys()) == {"start", "duration", "score"}


# ------------------------------------------------------------------ fallback

def test_fallback_segments_tidak_kosong():
    """Video tanpa heatmap harus tetap bisa dipotong."""
    seg = core.fallback_segments(213, count=3)
    assert len(seg) == 3
    for s in seg:
        assert s["start"] >= 0
        assert s["duration"] > 0
        assert s["score"] == 0.0


def test_fallback_segments_dalam_batas_durasi():
    durasi = 213
    for s in core.fallback_segments(durasi, count=5):
        assert s["start"] + s["duration"] <= durasi + 0.01, "potongan melebihi durasi video"


def test_fallback_segments_tidak_tumpang_tindih():
    seg = sorted(core.fallback_segments(300, count=5), key=lambda x: x["start"])
    for a, b in zip(seg, seg[1:]):
        assert b["start"] >= a["start"] + a["duration"] - 0.01, "segmen tumpang tindih"


def test_fallback_segments_video_pendek():
    """Video 30 detik: satu potongan penuh, bukan nol potongan."""
    seg = core.fallback_segments(30, count=5)
    assert len(seg) == 1
    assert seg[0]["duration"] <= 30


def test_fallback_segments_durasi_tidak_valid():
    assert core.fallback_segments(0) == []
    assert core.fallback_segments(None) == []
    assert core.fallback_segments(-5) == []


# --------------------------------------------- deteksi video tidak tersedia

def test_teks_video_unavailable_tidak_bohong():
    """
    Regression test untuk bug yang saya buat sendiri.

    Cek lama memakai '"Video unavailable" in html'. String itu bagian dari
    tabel terjemahan YouTube yang muncul di SETIAP halaman -- termasuk video
    sehat. Akibatnya setiap video dilaporkan tidak ditemukan.
    """
    html = baca_fixture("watch_with_heatmap.html")
    assert "Video unavailable" in html, "fixture harus memuat string jebakan"
    assert "playabilityStatus" in html

    # Yang benar adalah playabilityStatus
    assert core._status_playability(html) == "OK"
    assert core._status_playability(html) not in core.PLAYABILITY_GAGAL


def test_playability_error_terdeteksi():
    html = baca_fixture("watch_unavailable.html")
    assert core._status_playability(html) == "ERROR"
    assert core._status_playability(html) in core.PLAYABILITY_GAGAL


def test_video_tidak_tersedia_ditandai_benar():
    html = baca_fixture("watch_unavailable.html")
    asli = core._ambil_html_watch
    core._ambil_html_watch = lambda vid, timeout=20: (html, None)
    try:
        status = core._status_playability(html)
    finally:
        core._ambil_html_watch = asli
    assert status == "ERROR"


def test_playability_status_kosong():
    assert core._status_playability("") == ""
    assert core._status_playability("<html>halo</html>") == ""


# ------------------------------------------------------------------- durasi

def test_durasi_dari_html():
    html = baca_fixture("watch_with_heatmap.html")
    assert core.durasi_dari_html(html) == 252


def test_durasi_dari_html_tidak_ada_atau_rusak():
    assert core.durasi_dari_html("") == 0
    assert core.durasi_dari_html("<html>tiada apa-apa</html>") == 0
    assert core.durasi_dari_html('"lengthSeconds":"abc"') == 0
    assert core.durasi_dari_html('"lengthSeconds":""') == 0


def test_scan_heatmap_membawa_durasi():
    html = baca_fixture("watch_with_heatmap.html")
    asli = core._ambil_html_watch
    core._ambil_html_watch = lambda vid, timeout=20: (html, None)
    try:
        hasil = core.scan_heatmap("dummy")
    finally:
        core._ambil_html_watch = asli
    assert hasil["duration"] == 252


def test_get_duration_tidak_lagi_tebak_3600():
    """
    Default lama 3600 membuat clip dipotong di titik yang tidak ada.
    Sekarang harus mengembalikan nilai fallback yang daresi.
    """
    asli = core.subprocess.run
    core.subprocess.run = lambda *a, **k: type(
        "R", (), {"stdout": "", "stderr": "ERROR: whatever", "returncode": 1}
    )()
    try:
        assert core.get_duration("dummy") == 0
        assert core.get_duration("dummy", fallback=99) == 99
    finally:
        core.subprocess.run = asli


def test_get_duration_menerima_desimal_dan_menit():
    asli = core.subprocess.run
    for keluar, harap in [("252.0\n", 252), ("4:12\n", 252), ("1:02:03\n", 3723)]:
        core.subprocess.run = lambda *a, **k: type(
            "R", (), {"stdout": keluar, "stderr": "", "returncode": 0}
        )()
        try:
            assert core.get_duration("dummy") == harap, f"{keluar!r} -> {harap}"
        finally:
            core.subprocess.run = asli


# ------------------------------------------------------------------ runner

if __name__ == "__main__":
    gagal = 0
    total = 0
    for nama, fn in sorted(list(globals().items())):
        if not nama.startswith("test_") or not callable(fn):
            continue
        total += 1
        try:
            fn()
            print(f"  LULUS  {nama}")
        except AssertionError as e:
            gagal += 1
            print(f"  GAGAL  {nama}: {e}")
        except Exception as e:  # noqa: BLE001
            gagal += 1
            print(f"  ERROR  {nama}: {type(e).__name__}: {e}")
    print(f"\n{total - gagal}/{total} lulus")
    sys.exit(1 if gagal else 0)
