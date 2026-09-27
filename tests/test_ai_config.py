"""
Test penyimpanan konfigurasi AI (offline, tanpa jaringan).

Fokus: config benar-benar bertahan di disk, dan API key tidak pernah bocor
ke browser.

Jalankan:  .venv/bin/python -m pytest tests/ -q
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ai_config  # noqa: E402


@pytest.fixture(autouse=True)
def config_di_tmp(tmp_path, monkeypatch):
    """Arahkan config ke folder sementara supaya repo tidak tergarap."""
    monkeypatch.setattr(ai_config, "data_dir", lambda: str(tmp_path))
    return tmp_path


class TestSimpanDanBaca:
    def test_kosong_Kalau_belum_pernah_disimpan(self):
        assert ai_config.load()["has_api_key"] is False
        assert ai_config.api_key() == ""

    def test_roundtrip_semua_field(self):
        ai_config.save({
            "base_url": "http://localhost:11434/v1",
            "model": "qwen2.5:3b",
            "tone": "santai",
            "timeout": 900,
            "note": "fokus ke topik fisika",
            "transcript": "isi transkrip",
        })
        cfg = ai_config.load()
        assert cfg["base_url"] == "http://localhost:11434/v1"
        assert cfg["model"] == "qwen2.5:3b"
        assert cfg["tone"] == "santai"
        assert cfg["timeout"] == 900
        assert cfg["note"] == "fokus ke topik fisika"
        assert cfg["transcript"] == "isi transkrip"

    def test_field_tidak_dikenal_diabaikan(self):
        ai_config.save({"model": "a", "field_ngawur": "nilai", "__init__": "x"})
        assert "field_ngawur" not in ai_config.load()
        assert "__init__" not in ai_config.load()

    def test_simpan_parsial_tidak_menghapus_yang_lama(self):
        ai_config.save({"model": "qwen2.5:3b", "base_url": "http://x/v1"})
        ai_config.save({"model": "llama3.2:3b"})
        cfg = ai_config.load()
        assert cfg["model"] == "llama3.2:3b"
        assert cfg["base_url"] == "http://x/v1"

    def test_file_benar_benar_ada_di_disk(self, config_di_tmp):
        ai_config.save({"model": "qwen2.5:3b"})
        path = config_di_tmp / ai_config.CONFIG_NAME
        assert path.is_file()
        assert json.loads(path.read_text(encoding="utf-8"))["model"] == "qwen2.5:3b"


class TestApiKey:
    def test_api_key_tidak_pernah_dikembalikan(self):
        ai_config.save({"model": "a", "api_key": "rahasia-super"})
        cfg = ai_config.load()
        assert cfg["has_api_key"] is True
        # Nilai aslinya tidak boleh ada di respons mana pun.
        assert "rahasia-super" not in json.dumps(cfg)
        assert "api_key" not in cfg

    def test_api_key_tersimpan_dan_bisa_dibaca_server(self):
        ai_config.save({"api_key": "kunciku"})
        assert ai_config.api_key() == "kunciku"

    def test_kosong_tidak_menimpa_key_lama(self):
        ai_config.save({"api_key": "lama"})
        ai_config.save({"api_key": "", "model": "b"})
        assert ai_config.api_key() == "lama"

    def test_bisa_dihapus(self):
        ai_config.save({"api_key": "lama"})
        ai_config.save({"clear_api_key": True})
        assert ai_config.api_key() == ""
        assert ai_config.load()["has_api_key"] is False

    def test_panjang_api_key_dibatasi(self):
        ai_config.save({"api_key": "x" * 5000})
        assert len(ai_config.api_key()) <= 5000


class TestBatasNilai:
    def test_timeout_dijepit(self):
        ai_config.save({"timeout": 999999})
        assert ai_config.load()["timeout"] == 1800
        ai_config.save({"timeout": 1})
        assert ai_config.load()["timeout"] == 30

    def test_timeout_bukan_angka_diabaikan(self):
        ai_config.save({"timeout": "cepat"})
        assert "timeout" not in ai_config.load()

    def test_n_titles_dijepit(self):
        ai_config.save({"n_titles": 99})
        assert ai_config.load()["n_titles"] == 5

    def test_field_teks_dipotong(self):
        ai_config.save({"note": "a" * 5000})
        assert len(ai_config.load()["note"]) == 500

    def test_hashtag_toggle_default_aktif(self):
        assert ai_config.load().get("hashtags_in_description", True) is True
        ai_config.save({"hashtags_in_description": False})
        assert ai_config.load()["hashtags_in_description"] is False


class TestKetahanan:
    def test_file_rusak_tidak_menggagalkan_aplikasi(self):
        ai_config.save({"model": "a"})
        Path(ai_config.config_path()).write_text("{bukan json sama sekali", encoding="utf-8")
        # Tidak boleh melempar: settings hilang boleh, app gagal start tidak.
        assert ai_config.load()["has_api_key"] is False
        assert ai_config.api_key() == ""

    def test_file_berisi_json_bukan_object(self):
        ai_config.save({"model": "a"})
        Path(ai_config.config_path()).write_text("[1, 2, 3]", encoding="utf-8")
        assert ai_config.load()["has_api_key"] is False

    def test_simpan_berulang_tidak_ada_file_sisa(self, config_di_tmp):
        for i in range(5):
            ai_config.save({"model": f"m{i}"})
        assert list(config_di_tmp.glob("*.tmp")) == []

    def test_hapus_kosong_tidak_error(self):
        ai_config.clear()
        assert ai_config.load()["has_api_key"] is False
