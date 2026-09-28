"""
Test integrasi AI metadata (offline, tanpa LLM sungguhan).

Server yang dipakai adalah tools/fake_ai_server.py: HTTP server sungguhan
yang berbalas seperti Ollama/LM Studio. Jadi jalur jaringan, header, dan
decoding respons ikut teruji, bukan cuma fungsi murni.

Jalankan:  .venv/bin/python -m pytest tests/ -q
"""

import json
import socket
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import ai_meta  # noqa: E402
import fake_ai_server  # noqa: E402


@pytest.fixture(scope="module")
def ai_server():
    """Server OpenAI-compatible palsu, hidup selama modul ini diuji."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = fake_ai_server.serve(port)
    yield f"http://127.0.0.1:{port}/v1"
    httpd.shutdown()


CTX = {
    "title": "FisiKA: Momentum",
    "channel": "Kanal Belajar",
    "duration_text": "3:33",
    "description": "Video tentang momentum dan impuls",
    "transcript": "kita bahas momentum hari ini",
    "segments": [{"label": "1:00 - 1:30"}],
}


def gen(base, model, ctx=None, options=None):
    return ai_meta.generate(base, model, ctx or CTX, options or {"timeout": 60})


# --------------------------------------------------------------- normalisasi

class TestNormaliseBaseUrl:
    @pytest.mark.parametrize("raw,expect", [
        ("localhost:11434", "http://localhost:11434/v1"),
        ("127.0.0.1:1234", "http://127.0.0.1:1234/v1"),
        ("http://localhost:11434", "http://localhost:11434/v1"),
        ("http://localhost:11434/v1", "http://localhost:11434/v1"),
        ("http://localhost:11434/v1/", "http://localhost:11434/v1"),
        ("192.168.0.6:8000", "http://192.168.0.6:8000/v1"),
        ("http://mypc", "http://mypc/v1"),
        ("", ""),
    ])
    def test_variasi(self, raw, expect):
        assert ai_meta.normalise_base_url(raw) == expect

    def test_tanpa_skema_https_ditolak_kosong(self):
        # Satu-satunya skema yang boleh adalah http:// untuk alamat lokal.
        assert ai_meta.normalise_base_url("https://localhost:1234").startswith("http://")


class TestValidateBaseUrl:
    @pytest.mark.parametrize("url,allow", [
        ("http://localhost:11434/v1", True),
        ("http://127.0.0.1:1234/v1", True),
        ("http://192.168.0.6:8000/v1", True),
        ("http://10.0.0.5:11434/v1", True),
        ("http://172.16.3.4:8000/v1", True),
        ("http://mypc:8080/v1", True),
        ("http://nas.lan:11434/v1", True),
        ("http://box.local:1234/v1", True),
        ("", False),
        ("http://8.8.8.8/v1", False),
        ("http://api.openai.com/v1", False),
        ("http://1.2.3.4:99999/v1", False),
        ("bukan-url", False),
    ])
    def test_lokal_dan_lan_aja(self, url, allow):
        ok, why = ai_meta.validate_base_url(url)
        assert ok is allow, f"{url} -> {ok} ({why})"

    def test_host_awan_ditolak_walau_dns_gagal(self):
        # Kalau keputusan pakai hasil DNS, host yang tidak kebaca akan
        # dianggap lokal dan lolos. Bustakan itu.
        ok, _ = ai_meta.validate_base_url("http://host-tidak-ada-xyz-12345.com/v1")
        assert ok is False

    def test_pesan_kosong_jelas(self):
        _, why = ai_meta.validate_base_url("")
        assert "kosong" in why.lower()


class TestClampTimeout:
    @pytest.mark.parametrize("raw,expect", [
        (None, ai_meta.DEFAULT_TIMEOUT),
        ("abc", ai_meta.DEFAULT_TIMEOUT),
        (5, ai_meta.MIN_TIMEOUT),        # di bawah minimum, dinaikkan
        (99999, ai_meta.MAX_TIMEOUT),    # di atas maksimum, diturunkan
        (300, 300.0),
    ])
    def test_nilai_kabur_dijaga(self, raw, expect):
        got = ai_meta.clamp_timeout(raw)
        assert got == expect
        assert ai_meta.MIN_TIMEOUT <= got <= ai_meta.MAX_TIMEOUT

    def test_nan_dan_inf_kena_default(self):
        for v in (float("nan"), float("inf"), float("-inf")):
            assert ai_meta.clamp_timeout(v) == ai_meta.DEFAULT_TIMEOUT

    def test_minimum_cukup_untuk_model_lambat_di_cpu(self):
        # Model lokal 1B di CPU lambat bisa lebih dari 30 detik.
        assert ai_meta.MIN_TIMEOUT >= 30.0


# ------------------------------------------------------------------ parsing

class TestParseMetadata:
    def test_json_sempurna(self):
        r = ai_meta.parse_metadata(json.dumps({
            "titles": ["A", "B"], "description": "D", "tags": ["x", "y"],
        }))
        assert r["titles"] == ["A", "B"] and r["tags"] == ["x", "y"]
        assert r["partial"] is False

    def test_fence_markdown(self):
        r = ai_meta.parse_metadata('```json\n{"titles": ["A"], "description": "D", "tags": ["x"]}\n```')
        # Deskripsi sudah termasuk baris hashtag; fence tetap dibuang.
        assert r["titles"] == ["A"]
        assert r["description"] == "D\n\n#x"
        assert "```" not in r["description"]

    def test_fence_tanpa_json_label(self):
        r = ai_meta.parse_metadata('```\n{"titles": ["A"], "description": "D", "tags": ["x"]}\n```')
        assert r["titles"] == ["A"]

    def test_ada_kalimat_sebelum_dan_sesudah(self):
        r = ai_meta.parse_metadata(
            'Tentu! Berikut hasilnya:\n\n'
            '{"titles": ["Satu"], "description": "D", "tags": ["a"]}\n\nSemoga membantu!'
        )
        assert r["titles"] == ["Satu"] and r["partial"] is False

    def test_json_terpotong_diselamatkan(self):
        # Model kehabisan token di tengah. Judul sudah utuh, deskripsi belum.
        r = ai_meta.parse_metadata('{"titles": ["Judul utuh", "Judul kedua"], "description": "Mulai adam')
        assert r["titles"] == ["Judul utuh", "Judul kedua"]
        assert r["partial"] is True

    def test_terpotong_tidak_bikin_artefak(self):
        r = ai_meta.parse_metadata('{"titles": ["A"], "description": "Mulai "\\n}')
        assert "\\n" not in r["description"]

    def test_kutip_tidak_ter_escape_diusahakan(self):
        r = ai_meta.parse_metadata(
            '{"titles": ["A"], "description": "Dia bilang \\"halo\\" tadi", "tags": ["x"]}')
        assert '"halo"' in r["description"]

    def test_lima_bidang_kosong_ditolak(self):
        with pytest.raises(ai_meta.AiError):
            ai_meta.parse_metadata("{}")

    def test_tanpa_json_ditolak_jelas(self):
        with pytest.raises(ai_meta.AiError):
            ai_meta.parse_metadata("Maaf, saya tidak bisa membantu.")

    def test_teks_bukan_json_apa_pun_ditolak(self):
        for teks in ("", "   ", "halo dunia", "<html>error</html>", "[1,2,3]"):
            with pytest.raises(ai_meta.AiError):
                ai_meta.parse_metadata(teks)

    def test_model_null_ditolak(self):
        with pytest.raises(ai_meta.AiError):
            ai_meta.parse_metadata("null")


class TestCleanTitles:
    def test_bungkus_dan_nomor_dibuang(self):
        got = ai_meta._clean_titles(['1. Judul', '"Judul"', "  - Judul  ", "* Judul*"])
        assert got == ["Judul"], got

    def test_duplikat_hanya_satu(self):
        got = ai_meta._clean_titles(["Sama", "sama", "SAMA"])
        assert got == ["Sama"]

    def test_kosong_dibuang(self):
        assert ai_meta._clean_titles(["", "   ", '"', "1."]) == []

    def test_terlalu_panjang_dipotong(self):
        got = ai_meta._clean_titles(["x" * 500])
        assert len(got[0]) <= ai_meta.MAX_TITLE_LEN

    def test_escape_dijadi_spasi(self):
        assert ai_meta._clean_titles(["Satu\\nDua"]) == ["Satu Dua"]

    def test_bukan_daftar_dan_null(self):
        assert ai_meta._clean_titles(None) == []
        assert ai_meta._clean_titles(12345) == []
        assert ai_meta._clean_titles({"a": 1}) == []

    def test_string_tunggal_diterima(self):
        assert ai_meta._clean_titles("Judul Tunggal") == ["Judul Tunggal"]


class TestCleanTags:
    def test_hash_kapital_dan_spasi_dinormalisasi(self):
        got = ai_meta._clean_tags(["#TagSatu", "TAG_DUA", "  tag tiga  "])
        assert got == ["tagsatu", "tag_dua", "tag tiga"]

    def test_duplikat_hanya_satu(self):
        assert ai_meta._clean_tags(["fisika", "FISIKA", "Fisika"]) == ["fisika"]

    def test_koma_jadi_pemisah(self):
        assert ai_meta._clean_tags("satu, dua, tiga") == ["satu", "dua", "tiga"]

    def test_tanpa_huruf_dibuang(self):
        # "12345" tetap sah karena punya karakter alnum; yang dibuang hanya
        # tanda baca murni yang tidak berguna sebagai tag.
        assert ai_meta._clean_tags(["!!!", "  ", "", "---", "***"]) == []

    def test_angka_tetap_disimpan(self):
        assert ai_meta._clean_tags(["12345"]) == ["12345"]

    def test_batas_jumlah_tag(self):
        got = ai_meta._clean_tags([f"tag{i}" for i in range(200)])
        assert len(got) <= ai_meta.MAX_TAGS

    def test_batas_panjang_per_tag(self):
        assert ai_meta._clean_tags(["y" * 9999]) == []

    def test_null_dan_bukan_daftar(self):
        assert ai_meta._clean_tags(None) == []
        assert ai_meta._clean_tags(7) == []


class TestCleanDesc:
    def test_paragraf_asli_dipertain(self):
        got = ai_meta._clean_desc("Baris satu\n\n\n\n\n  Baris dua  ")
        assert got == "Baris satu\n\nBaris dua"

    def test_escape_newline_dijadi_baris_baru(self):
        # Urutan salah akan mengubah \n jadi spasi dan menghilangkan paragraf.
        assert ai_meta._clean_desc("Satu\\n\\nDua") == "Satu\n\nDua"

    def test_escape_tab_jadi_spasi(self):
        assert ai_meta._clean_desc("A\\tB") == "A B"

    def test_karakter_kontrol_dibuang(self):
        assert "\x07" not in ai_meta._clean_desc("Halo\x07 dunia")

    def test_escape_quote_tidak_bocor(self):
        assert "\\n" not in ai_meta._clean_desc('Selesai \\" di sini')

    def test_teks_sah_tidak_dirusak(self):
        # CJK dan kurung kurawal adalah isi yang sah, bukan noise.
        # Huruf non-Latin dari konten user HARUS utuh. Pembersihan teks
        # hanya boleh membuang escape string dan karakter kontrol, bukan
        # huruf. Bahasa Mandarin/Jepang di sini adalah data uji yang
        # disengaja, bukan sisa-salinan tak sengaja.
        assert ai_meta._clean_desc("Belajar 中文 hari ini") == "Belajar 中文 hari ini"
        assert ai_meta._clean_desc("Fungsi f(x) = {1}") == "Fungsi f(x) = {1}"
        assert ai_meta._clean_desc("- koma\n- impus") == "- koma\n- impus"

    def test_batas_panjang_dan_potong_di_baris(self):
        got = ai_meta._clean_desc("kata " * 5000)
        assert len(got) <= ai_meta.MAX_DESC_CHARS

    def test_bukan_string(self):
        assert ai_meta._clean_desc(None) == ""
        assert ai_meta._clean_desc(123) == ""


# -------------------------------------------------------------- prompt

class TestBuildPrompt:
    def test_mengandung_konteks_video(self):
        p = ai_meta.build_prompt(CTX, {"lang": "id", "tone": "casual"})
        teks = " ".join(m["content"] for m in p)
        assert "FisiKA: Momentum" in teks
        assert "Kanal Belajar" in teks
        assert "momentum" in teks

    def test_bahasa_menentukan_instruksi(self):
        id_ = ai_meta.build_prompt(CTX, {"lang": "id"})
        en = ai_meta.build_prompt(CTX, {"lang": "en"})
        assert id_ != en

    def test_minta_json(self):
        p = ai_meta.build_prompt(CTX, {"lang": "id"})
        teks = " ".join(m["content"] for m in p)
        assert "JSON" in teks

    def test_peran_sistem_selalu_ada(self):
        p = ai_meta.build_prompt(CTX, {"lang": "id"})
        assert p[0]["role"] == "system"

    def test_konteks_kosong_tidak_membuat_prompt_rusak(self):
        p = ai_meta.build_prompt({}, {"lang": "id"})
        assert p and all(m.get("content") for m in p)

    def test_input_dipotong_biar_prompt_tidak_membengkak(self):
        ctx = dict(CTX, transcript="kata " * 50000, description="d " * 20000)
        p = ai_meta.build_prompt(ctx, {"lang": "id"})
        teks = " ".join(m["content"] for m in p)
        assert len(teks) < 20000, f"prompt terlalu besar: {len(teks)}"

    def test_catatan_tambahan_dimasukkan(self):
        p = ai_meta.build_prompt(CTX, {"lang": "id", "note": "fokus untuk pemula"})
        assert "fokus untuk pemula" in " ".join(m["content"] for m in p)


# ------------------------------------------------------- HTTP ke server AI

class TestListModels:
    def test_daftar_model(self, ai_server):
        model = ai_meta.list_models(ai_server, timeout=10)
        assert "good" in model and len(model) > 5

    def test_server_mati_ditolak(self):
        with pytest.raises(ai_meta.AiError):
            ai_meta.list_models("http://127.0.0.1:9/v1", timeout=5)


class TestGenerateHTTP:
    def test_jalur_lengkap(self, ai_server):
        r = gen(ai_server, "good")
        assert len(r["titles"]) == 3
        assert len(r["tags"]) >= 8
        assert len(r["description"]) > 100
        assert r["partial"] is False

    def test_fence_dibaca(self, ai_server):
        r = gen(ai_server, "fenced")
        assert r["titles"] == ["Judul A", "Judul B"]
        assert r["tags"] == ["satu", "dua", "tiga"]
        assert "\n" in r["description"]

    def test_terpotong_jadi_parsial_tetap_dilaporkan(self, ai_server):
        r = gen(ai_server, "truncated")
        assert r["titles"] == ["Judul utuh", "Judul kedua"]
        assert r["partial"] is True

    def test_talkatif_tidak_mengganggu(self, ai_server):
        r = gen(ai_server, "chatty")
        assert r["titles"] == ["Satu", "Dua"]
        # Kalimat pembuka "Tentu! Berikut hasilnya:" tidak ikut terbawa,
        # dan hashtag tetap menempel di akhir deskripsi.
        assert r["description"].startswith("Isi")
        assert "Tentu" not in r["description"]
        assert r["description"].endswith(ai_meta.hashtag_line(r["hashtags"]))
        assert r["partial"] is False

    def test_kotor_dibersihkan(self, ai_server):
        r = gen(ai_server, "messy")
        assert r["titles"] == ["Judul Bersih", "JUDUL DUPLICAT", "Outro"]
        assert "tagsatu" in r["tags"] and "TAG_DUA" not in r["tags"]
        assert "\n\n\n" not in r["description"]

    def test_kosong_ditolak(self, ai_server):
        with pytest.raises(ai_meta.AiError):
            gen(ai_server, "empty")

    def test_ditolak_model_ditolak(self, ai_server):
        with pytest.raises(ai_meta.AiError):
            gen(ai_server, "refusal")

    def test_error_server_diterjemahkan(self, ai_server):
        with pytest.raises(ai_meta.AiError) as e:
            gen(ai_server, "server_error")
        assert "500" in str(e.value)

    def test_404_diterjemahkan(self, ai_server):
        with pytest.raises(ai_meta.AiError) as e:
            gen(ai_server, "not_found")
        assert "404" in str(e.value)

    def test_401_diterjemahkan(self, ai_server):
        with pytest.raises(ai_meta.AiError) as e:
            gen(ai_server, "bad_auth")
        assert "401" in str(e.value) or "kunci" in str(e.value).lower()

    def test_api_key_dikirim(self, ai_server):
        r = ai_meta.generate(ai_server, "good", CTX, {"timeout": 30}, api_key="secret-test")
        assert r["titles"]

    def test_timeout_dihormati(self, ai_server):
        # Server 'slow' menunda 3 detik; timeout dipaksa pendek via patch.
        asli = ai_meta.MIN_TIMEOUT
        ai_meta.MIN_TIMEOUT = 0.5
        try:
            with pytest.raises(ai_meta.AiError) as e:
                gen(ai_server, "slow", options={"timeout": 1})
            assert "1 detik" in str(e.value)
        finally:
            ai_meta.MIN_TIMEOUT = asli

    def test_server_mati_pesan_jelas(self):
        with pytest.raises(ai_meta.AiError) as e:
            gen("http://127.0.0.1:9/v1", "good", options={"timeout": 30})
        assert "Tidak ada server AI" in str(e.value)


class TestFriendlyUrlError:
    def test_masing_masing_punya_pesan(self, ai_server):
        for model, wajib in [("server_error", "500"), ("not_found", "404"), ("bad_auth", "kunci")]:
            with pytest.raises(ai_meta.AiError) as e:
                gen(ai_server, model)
            assert wajib in str(e.value), f"{model}: {e.value}"

    def test_refusal_tidak_disembunyikan(self, ai_server):
        with pytest.raises(ai_meta.AiError) as e:
            gen(ai_server, "refusal")
        assert "tidak bisa membaca" in str(e.value).lower()

# ------------------------------------------------------------------ hashtag

class TestHashtag:
    """Hashtag harus selalu ada karena itu bagian metadata yang dipakai."""

    def test_dari_model_dipakai_apa_adanya(self, ai_server):
        out = gen(ai_server, "hashtag")
        assert out["hashtags"][:3] == ["#Fisika", "#Momentum", "#BelajarFisika"]

    def test_kosong_dibuang(self, ai_server):
        out = gen(ai_server, "hashtag")
        assert "" not in out["hashtags"]
        assert all(h.startswith("#") for h in out["hashtags"])

    def test_model_lupa_hashtag_turunkan_dari_tag(self, ai_server):
        out = gen(ai_server, "no_hashtag")
        assert out["hashtags"], "hashtag tidak boleh kosong walau model tidak kirim"
        assert all(h.startswith("#") for h in out["hashtags"])
        # Turunan harus berasal dari tag yang ada, bukan mengarang. Tag
        # ber-spasi dipotong jadi kata pertama karena hashtag YouTube
        # tidak boleh mengandung spasi.
        kata_pertama = {t.lower().split(" ", 1)[0] for t in out["tags"]}
        for h in out["hashtags"]:
            assert h.lstrip("#").lower() in kata_pertama

    def test_tertempel_di_akhir_deskripsi(self, ai_server):
        out = gen(ai_server, "hashtag")
        baris = ai_meta.hashtag_line(out["hashtags"])
        assert out["description"].rstrip().endswith(baris)

    def test_bisa_dimatikan(self, ai_server):
        out = gen(ai_server, "hashtag", options={"timeout": 60, "hashtags_in_description": False})
        baris = ai_meta.hashtag_line(out["hashtags"])
        assert baris and baris not in out["description"]
        # Hashtag tetap ada sebagai field, cuma tidak menempel di deskripsi.
        assert out["hashtags"]

    def test_batas_15(self):
        banyak = [f"#tag{i}" for i in range(40)]
        assert len(ai_meta._clean_hashtags(banyak)) == 15

    def test_tanpa_tanda_pOUNDtetap_dibalik(self):
        assert ai_meta._clean_hashtags(["fisika", "#momentum"]) == ["#fisika", "#momentum"]

    def test_spasi_di_dalam_dipisah(self):
        # Hashtag YouTube tidak boleh berisi spasi, jadi satu item ber-spasi
        # dipecah jadi dua hashtag, bukan dipotong diam-diam.
        assert ai_meta._clean_hashtags(["#belajar fisika"]) == ["#belajar", "#fisika"]

    def test_turunan_dari_tag_tidak_diperparuh(self):
        # "belajar fisika" adalah satu istilah, bukan dua hashtag.
        out = ai_meta._clean_hashtags(None, ["belajar fisika", "momentum"])
        assert out == ["#belajar", "#momentum"]

    def test_koma_dipisah(self):
        assert ai_meta._clean_hashtags("#a, #b") == ["#a", "#b"]

    def test_duplikat_diabaikan_case_insensitive(self):
        assert ai_meta._clean_hashtags(["#Fisika", "#fisika", "#FISIKA"]) == ["#Fisika"]

    def test_kosong_total_tidak_melempar(self):
        assert ai_meta._clean_hashtags(["", "  ", "###"]) == []

    def test_bukan_list_tidak_melempar(self):
        assert ai_meta._clean_hashtags(123) == []
        assert ai_meta._clean_hashtags(None) == []

    def test_label_berantakan_dibersihkan(self):
        assert ai_meta._clean_hashtags(['"hashtag: #musik"']) == ["#musik"]


class TestAppendHashtags:
    def test_deskripsi_kosong_jadi_hashtag_saja(self):
        assert ai_meta.append_hashtags("", ["#a"]) == "#a"

    def test_tidak_menggandakan(self):
        assert ai_meta.append_hashtags("Halo #a", ["#a"]) == "Halo #a"

    def test_tidak_menggandakan_sudah_ada_di_akhir(self):
        desc = "Halo\n\n#a #b"
        assert ai_meta.append_hashtags(desc, ["#a", "#b"]) == desc

    def test_tetap_di_batas_youtube(self):
        panjang = "x" * 4900
        out = ai_meta.append_hashtags(panjang, ["#a", "#b"])
        assert len(out) <= ai_meta.YOUTUBE_DESC_LIMIT
        assert out.rstrip().endswith("#a #b")

    def test_hashtag_bukan_yang_dibuang(self):
        """Kalau tidak muat, deskripsi yang dipotong - hashtag tetap utuh."""
        out = ai_meta.append_hashtags("y" * 4900, ["#kijekpanjangsekali"])
        assert "#kijekpanjangsekali" in out
        assert len(out) <= ai_meta.YOUTUBE_DESC_LIMIT

    def test_tanpa_hashtag_tidak_berubah(self):
        assert ai_meta.append_hashtags("Halo", []) == "Halo"
        assert ai_meta.append_hashtags("Halo", None) == "Halo"

    def test_limit_batas_terekal_kecil(self):
        asli = ai_meta.YOUTUBE_DESC_LIMIT
        ai_meta.YOUTUBE_DESC_LIMIT = 20
        try:
            out = ai_meta.append_hashtags("x" * 50, ["#a"])
            assert len(out) <= 20
            assert "#a" in out
        finally:
            ai_meta.YOUTUBE_DESC_LIMIT = asli


# --------------------------------------------------------------------------
# Guard bahasa: model kecil kadang menjawab dengan aksara lain
# --------------------------------------------------------------------------

class TestDeteksiAksaraLain:
    def test_mandarin_terdeteksi(self):
        d = ai_meta.detect_off_script("Belajar 中文 hari ini momentum")
        assert d is not None
        assert d["script"] == "CJK/Han"
        assert "中" in d["sample"]

    def test_hangul_terdeteksi_sebagai_korea(self):
        d = ai_meta.detect_off_script("운동량 설명 momentum laws")
        assert d is not None
        assert d["script"] == "Korea"

    def test_kana_terdeteksi_sebagai_jepang(self):
        d = ai_meta.detect_off_script("運動量の説明 momentum laws")
        assert d is not None
        assert d["script"] == "Jepang"

    def test_teks_latin_bersih_aman(self):
        assert ai_meta.detect_off_script("Belajar Impuls dan Momentum") is None

    def test_emoji_bukan_salah_bahasa(self):
        assert ai_meta.detect_off_script("Belajar Momentum \U0001f525 hari ini") is None

    def test_aksara_tidak_dibuang_dari_tag(self):
        # Tag Mandarin harus TETAP ada supaya guard bisa melapor. Kalau
        # dibuang di parser, penyimpannya hilang tanpa jejak.
        tags = ai_meta._clean_tags(["momentum", "物理", "fisika"])
        assert "物理" in tags
        assert "momentum" in tags

    def test_hashtag_aksara_asing_tetap_ada(self):
        h = ai_meta._clean_hashtags(["#物理", "#Momentum"])
        assert any("物" in x for x in h)


class TestAuditBahasa:
    def _meta(self):
        return {
            "titles": ["\u7269\u7406 Momentum explained", "Momentum explained"],
            "description": "Pembahasan.\n\n- 第一定律",
            "tags": ["momentum", "物理"],
            "hashtags": ["#物理"],
            "partial": False,
        }

    def test_mendeteksi_per_field(self):
        a = ai_meta.audit_language(self._meta())
        assert a["ok"] is False
        assert a["partial"] is True
        fields = {w["field"] for w in a["warnings"]}
        assert {"titles", "description", "tags", "hashtags"} <= fields

    def test_isi_hasil_tidak_diubah(self):
        m = self._meta()
        before = dict(m)
        ai_meta.audit_language(m)
        assert m["titles"] == before["titles"]
        assert m["description"] == before["description"]
        assert m["tags"] == before["tags"]

    def test_hasil_bersih_ok(self):
        m = {
            "titles": ["Belajar Momentum", "Impuls dalam Fisika"],
            "description": "Pembahasan lengkap.",
            "tags": ["momentum", "fisika"],
            "hashtags": ["#Fisika"],
            "partial": False,
        }
        a = ai_meta.audit_language(m)
        assert a["ok"] is True
        assert a["partial"] is False

    def test_allow_cjk_mematikan_guard(self):
        a = ai_meta.audit_language(self._meta(), {"allow_cjk": True})
        assert a["ok"] is True

    def test_pesan_warning_bisa_dibaca(self):
        msg = ai_meta.format_language_warning(ai_meta.audit_language(self._meta()))
        assert msg
        assert "CJK" in msg or "Korea" in msg or "Jepang" in msg
        assert ai_meta.format_language_warning({"ok": True}) == ""


class TestLatinOnlyOutput:
    def test_aksara_asing_dihapus_dari_semua_field(self):
        r = ai_meta.parse_metadata(json.dumps({
            "titles": ["Fisika 物理 Momentum"],
            "description": "Belajar 第一定律 hari ini",
            "tags": ["fisika", "物理"],
            "hashtags": ["#物理", "#fisika"],
        }, ensure_ascii=False))
        text = json.dumps(r, ensure_ascii=False)
        assert not ai_meta._OFF_SCRIPT.search(text)
        assert r["partial"] is True
        assert r["titles"] == ["Fisika Momentum"]
        assert r["tags"] == ["fisika"]
        assert r["hashtags"] == ["#fisika"]

    def test_prompt_memerintahkan_latin_only(self):
        prompt = ai_meta.build_prompt({"title": "Momentum"}, {"lang": "id"})
        body = prompt[1]["content"]
        assert "only in the requested language using Latin" in body
        assert "NEVER output Chinese" in body
        assert "Japanese kanji" in body
        assert "Korean Hangul" in body

