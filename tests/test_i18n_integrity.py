"""
Test integritas i18n app.js.

Tujuan kelas test ini: menangkap perubahan yang secara sintaks SAH tapi
secara semantik salah. Contoh nyata yang pernah terjadi: penutup objek
`en: {` diletakkan di posisi yang terlalu awal, sehingga key baru justru menempel
ke objek I18N paling atas, bukan ke I18N.en. `node --check` tetap lolos
karena kodenya valid, tapi seluruh terjemahan bahasa Inggris untuk fitur
tersebut hilang tanpa_gejala error sama sekali.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "static" / "app.js"
INDEX_HTML = ROOT / "templates" / "index.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node tidak tersedia")


def literal_i18n(src):
    """Ambil literal objek I18N dengan hitungan brace yang sadar string."""
    start = src.index("const I18N =")
    obj = src.index("{", start)
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(obj, len(src)):
        ch = src[i]
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
                end = i
                break
    assert end > 0, "literal I18N tidak ditemukan atau tidak tertutup"
    return src[obj:end + 1]


@pytest.fixture(scope="module")
def i18n():
    js = (
        "const o = eval('(' + require('fs').readFileSync(0,'utf8') + ')');"
        "console.log(JSON.stringify({id: o.id, en: o.en, top: Object.keys(o)}));"
    )
    r = subprocess.run(["node", "-e", js], input=literal_i18n(APP_JS.read_text("utf-8")),
                       capture_output=True, text=True)
    assert r.returncode == 0, f"gagal parse I18N: {r.stderr[:400]}"
    return json.loads(r.stdout)


class TestI18nIntegrity:
    def test_sintaks_bersih(self):
        r = subprocess.run(["node", "--check", str(APP_JS)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[:400]

    def test_key_en_lengkap(self, i18n):
        hilang = sorted(set(i18n["id"]) - set(i18n["en"]))
        assert not hilang, f"key hilang di terjemahan Inggris: {hilang[:15]}"

    def test_key_id_lengkap(self, i18n):
        hilang = sorted(set(i18n["en"]) - set(i18n["id"]))
        assert not hilang, f"key hilang di terjemahan Indonesia: {hilang[:15]}"

    def test_tidak_ada_key_yang_melayang_di_atas(self, i18n):
        """Key harus milik id atau en, bukan I18N langsung.

        Ini regresi dari penutup objek yang diletakkan salah posisi.
        """
        nyasar = sorted(k for k in i18n["top"] if k not in ("id", "en"))
        assert not nyasar, f"key menempel di luar id/en: {nyasar[:15]}"

    def test_semua_nilai_string_terisi(self, i18n):
        kosong = [k for k, v in i18n["id"].items() if not isinstance(v, str) or not v.strip()]
        kosong_en = [k for k, v in i18n["en"].items() if not isinstance(v, str) or not v.strip()]
        assert not kosong, f"nilai ID kosong: {kosong[:10]}"
        assert not kosong_en, f"nilai EN kosong: {kosong_en[:10]}"

    def test_teks_inggris_tidak_ada_di_blok_id(self, i18n):
        """Blok Indonesia tidak boleh memakai kalimat Inggris penuh.

        Kutipan singkat bahasa Inggris di dalam kalimat Indonesia itu
        sah (misalnya nama fitur), jadi yang dicari adalah kalimat yang
        seluruhnya Inggris: tidak ada satu pun kata kerja Indonesia.
        """
        id_kata = re.compile(r"\b(yang|dan|untuk|dengan|adalah|buat|biar|supaya|kamu|"
                             r"lebih|kalau|kalau|akan|sudah|tidak|ini|itu|nya)\b", re.I)
        en_kata = re.compile(r"\b(the|and|with|from|your|this|that|will|can|for)\b", re.I)
        salah = []
        for k, v in i18n["id"].items():
            if len(v) < 40:
                continue
            if not en_kata.search(v):
                continue
            if not id_kata.search(v):
                salah.append((k, v))
        assert not salah, f"teks Inggris penuh di blok ID: {salah[:5]}"

    def test_placeholder_konsisten_antar_bahasa(self, i18n):
        """{nama} harus muncul di ID dan EN agar tidak ada teks menggantung."""
        pola = re.compile(r"\{(\w+)\}")
        beda = []
        for k, vid in i18n["id"].items():
            ven = i18n["en"].get(k, "")
            if set(pola.findall(vid)) != set(pola.findall(ven)):
                beda.append((k, sorted(pola.findall(vid)), sorted(pola.findall(ven))))
        assert not beda, f"placeholder tidak cocok: {beda[:8]}"


class TestHtmlI18n:
    @pytest.fixture(scope="class")
    def html(self):
        return INDEX_HTML.read_text("utf-8")

    @pytest.fixture(scope="class")
    def pakai_key(self, html):
        return set(re.findall(r'data-i18n(?:-placeholder)?="([^"]+)"', html))

    def test_semua_key_html_ada_di_kamus(self, i18n, pakai_key):
        hilang = sorted(pakai_key - set(i18n["id"]))
        assert not hilang, f"key dipakai di HTML tapi tidak ada di kamus: {hilang[:15]}"

    def test_tidak_ada_teks_inggris_hardcode(self, html):
        """Judul/label panel tidak boleh ditulis langsung di HTML."""
        panel = re.search(r'<div class="panelTitle" data-i18n="panel\.ai">(.*?)</div>', html)
        assert panel, "panel AI tidak ditemukan"
        assert panel.group(1).strip() == "AI Metadata", panel.group(1)

    def test_aset_pakai_cache_buster(self, html):
        """Tanpa ?v=, browser bisa memakai JS lama setelah aplikasi diperbarui."""
        assert re.search(r'src="/static/app\.js\?v=\{\{\s*asset_v\s*\}\}"', html), \
            "app.js tidak memakai cache-buster versi"
        assert re.search(r'href="/static/style\.css\?v=\{\{\s*asset_v\s*\}\}"', html), \
            "style.css tidak memakai cache-buster versi"

    def test_id_panel_ai_lengkap(self, pakai_key):
        wajib = {
            "panel.ai", "label.ai_base_url", "label.ai_model", "label.ai_tone",
            "label.ai_timeout", "label.ai_note", "label.ai_transcript",
            "label.ai_titles", "label.ai_description", "label.ai_tags",
            "btn.ai_test", "btn.ai_generate", "btn.copy", "btn.copy_all",
        }
        assert wajib <= pakai_key, f"kurang: {sorted(wajib - pakai_key)}"
