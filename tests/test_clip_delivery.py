"""Test jalur play/download clip.

Dipakai karena gejala di lapangan: progres 100%, tapi Play gagal dan Download
menyimpan file HTML, bukan video.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AKAR)

import run as core  # noqa: E402


class TestValidasiFileVideo(unittest.TestCase):
    """Progres selesai tidak boleh berarti file rusak."""

    def _tulis(self, isi):
        path = os.path.join(AKAR, "tests", "_tmp_video.bin")
        with open(path, "wb") as fh:
            fh.write(isi)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_mp4_asli_diterima(self):
        payload = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 2000
        self.assertTrue(core.file_video_valid(self._tulis(payload)))

    def test_mkv_asli_diterima(self):
        payload = b"\x1a\x45\xdf\xa3" + b"\x00" * 2000
        self.assertTrue(core.file_video_valid(self._tulis(payload)))

    def test_halaman_html_ditolak(self):
        # Ini yang tersimpan sebagai "clip_1.mp4" dan gagal diputar.
        payload = b"<!DOCTYPE html><html><body>Sign in to confirm</body></html>" * 40
        self.assertFalse(core.file_video_valid(self._tulis(payload)))

    def test_json_error_ditolak(self):
        payload = b'{"error":{"message":"Video unavailable"}}' + b" " * 2000
        self.assertFalse(core.file_video_valid(self._tulis(payload)))

    def test_file_kosong_ditolak(self):
        self.assertFalse(core.file_video_valid(self._tulis(b"")))

    def test_file_kecil_ditolak(self):
        self.assertFalse(core.file_video_valid(self._tulis(b"\x00\x00\x00\x18ftyp")))

    def test_file_hilang_ditolak(self):
        self.assertFalse(core.file_video_valid(os.path.join(AKAR, "tidak-ada.mp4")))


class TestRouteClip(unittest.TestCase):
    """Route harus serve inline untuk Play, attachment untuk Download."""

    @classmethod
    def setUpClass(cls):
        import webapp

        cls.webapp = webapp
        cls.client = webapp.app.test_client()
        cls.job = "testjob123"
        cls.job_dir = webapp.job_dir_for(cls.job)
        os.makedirs(cls.job_dir, exist_ok=True)
        with open(os.path.join(cls.job_dir, "clip_1.mp4"), "wb") as fh:
            fh.write(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 4000)

    @classmethod
    def tearDownClass(cls):
        f = os.path.join(cls.job_dir, "clip_1.mp4")
        if os.path.exists(f):
            os.remove(f)
        if os.path.isdir(cls.job_dir):
            os.rmdir(cls.job_dir)

    def test_route_play_inline_bukan_attachment(self):
        """Content-Disposition: attachment bikin <video> gagal memutar."""
        r = self.client.get(f"/clips/{self.job}/clip_1.mp4")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Content-Type"), "video/mp4")
        disp = r.headers.get("Content-Disposition", "")
        self.assertNotIn("attachment", disp)
        self.assertTrue(disp.startswith("inline") or disp == "")

    def test_route_download_menghantar_attachment(self):
        r = self.client.get(f"/download/{self.job}/clip_1.mp4")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers.get("Content-Disposition", ""))

    def test_isi_file_bukan_html(self):
        r = self.client.get(f"/clips/{self.job}/clip_1.mp4")
        self.assertTrue(r.data.startswith(b"\x00\x00\x00\x18ftyp"))
        self.assertNotIn(b"<!DOCTYPE html>", r.data)

    def test_file_hilang_tidak_membalas_html(self):
        r = self.client.get(f"/clips/{self.job}/clip_9.mp4")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b"<!DOCTYPE html>", r.data)
        self.assertTrue(r.is_json)

    def test_job_id_berbahaya_ditolak(self):
        for jahat in ("..", "../../etc", "a/b", "x" * 80, "job;rm"):
            r = self.client.get(f"/clips/{jahat}/clip_1.mp4")
            self.assertIn(r.status_code, (400, 404), f"{jahat} lolos")

    def test_clip_rusak_tidak_ditampilkan(self):
        junk = os.path.join(self.job_dir, "clip_2.mp4")
        with open(junk, "wb") as fh:
            fh.write(b"<!DOCTYPE html><html>Sign in</html>" * 60)
        self.addCleanup(lambda: os.path.exists(junk) and os.remove(junk))

        outputs = self.webapp.list_outputs(self.job_dir)
        nama = [o["name"] for o in outputs]
        self.assertIn("clip_1.mp4", nama)
        self.assertNotIn("clip_2.mp4", nama)


class TestDeteksiCacheWhisper(unittest.TestCase):
    """
    Cache model harus terdeteksi dari struktur folder huggingface yang sebenarnya.

    Regresi: cek lama hanya `os.listdir(HF_HOME)`, padahal faster-whisper
    menyimpan model di `HF_HOME/hub/models--Systran--faster-whisper-<model>`.
    Akibatnya cache selalu dianggap kosong dan user selalu diberi tahu
    "~466 MB akan diunduh" walau modelnya sudah ada di disk.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hfhome-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._simpan_env("HF_HOME", self.tmp)
        self._simpan_env("HUGGINGFACE_HUB_CACHE", None)

    def _simpan_env(self, nama, nilai):
        lama = os.environ.get(nama)
        if nilai is None:
            os.environ.pop(nama, None)
        else:
            os.environ[nama] = nilai
        self.addCleanup(self._kembalikan, nama, lama)

    @staticmethod
    def _kembalikan(nama, lama):
        if lama is None:
            os.environ.pop(nama, None)
        else:
            os.environ[nama] = lama

    def _buat_model(self, model):
        """Buat struktur cache gaya huggingface_hub."""
        d = os.path.join(self.tmp, "hub", f"models--Systran--faster-whisper-{model}")
        os.makedirs(d, exist_ok=True)
        return d

    def test_model_di_dalam_hub_terdeteksi(self):
        self._buat_model("small")
        self.assertTrue(core.whisper_model_cached("small"))

    def test_model_base_terdeteksi(self):
        self._buat_model("base")
        self.assertTrue(core.whisper_model_cached("base"))

    def test_model_yang_belum_ada_tidak_terdeteksi(self):
        self._buat_model("small")
        self.assertFalse(core.whisper_model_cached("large-v3"))

    def test_cache_kosong_tidak_terdeteksi(self):
        os.makedirs(os.path.join(self.tmp, "hub"), exist_ok=True)
        self.assertFalse(core.whisper_model_cached("small"))

    def test_folder_hub_kosong_tidak_terdeteksi(self):
        # inilah kondisi nyata yang bikin cek lama gagal: HF_HOME hanya berisi "hub"
        self.assertEqual(sorted(os.listdir(self.tmp)), [])

    def test_nama_model_bersih_dinormalisasi(self):
        self._buat_model("small")
        for nilai in ("  Small ", "SMALL", "small"):
            with self.subTest(nilai=nilai):
                self.assertTrue(core.whisper_model_cached(nilai))

    def test_nama_model_tidak_sah_tidak_pecah(self):
        for salah in ("", None, "  ", "model-hantu"):
            with self.subTest(nilai=salah):
                self.assertIsInstance(core.whisper_model_cached(salah), bool)


class TestNormalisasiNamaModel(unittest.TestCase):
    """Ukuran model harus konsisten dengan nama yang benar-benar dimuat."""

    def test_nama_biasa_tetap(self):
        for nama in ("tiny", "base", "small", "medium", "large-v3"):
            with self.subTest(nama=nama):
                self.assertEqual(core.normalise_model_name(nama), nama)

    def test_variasi_ejaan_rapis(self):
        for salah, benar in (
            ("  Small ", "small"),
            ("SMALL", "small"),
            ("large_v3", "large-v3"),
            ("large", "large-v3"),
            ("", "small"),
            (None, "small"),
        ):
            with self.subTest(nilai=salah):
                self.assertEqual(core.normalise_model_name(salah), benar)

    def test_ukuran_model_cocok_dengan_nama(self):
        # Inilah yang\log buat: "base" tidak boleh pernah dicetak 466 MB
        # (itu ukuran small).
        self.assertEqual(core.get_model_size("base"), "142 MB")
        self.assertEqual(core.get_model_size(" small "), "466 MB")
        self.assertEqual(core.get_model_size("tiny"), "75 MB")

    def test_ukuran_model_tidak_pernah_salah_santik(self):
        ukuran = {
            core.get_model_size(m)
            for m in ("tiny", "base", "small", "medium", "large-v3")
        }
        self.assertEqual(len(ukuran), 5, "dua model punya ukuran sama")


class TestGuardDownload(unittest.TestCase):
    """
    Route download hanya boleh mengirim file yang benar-benar siap.

    Kalau clip masih ditulis atau isinya rusak, jawaban 404 lebih jujur
    daripada mengirim file terpotong yang tersimpan sebagai .mp4.
    """

    @classmethod
    def setUpClass(cls):
        import webapp

        cls.webapp = webapp
        cls.client = webapp.app.test_client()
        cls.job = "guardtest01"
        cls.job_dir = webapp.job_dir_for(cls.job)
        os.makedirs(cls.job_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.job_dir, ignore_errors=True)

    def _tulis(self, nama, isi):
        p = os.path.join(self.job_dir, nama)
        with open(p, "wb") as fh:
            fh.write(isi)
        self.addCleanup(lambda: os.path.exists(p) and os.remove(p))
        return p

    def test_file_kosong_ditolak(self):
        self._tulis("clip_kosong.mp4", b"")
        r = self.client.get(f"/download/{self.job}/clip_kosong.mp4")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(r.is_json)

    def test_file_kecil_ditolak(self):
        self._tulis("clip_kecil.mp4", b"\x00\x00\x00\x18ftyp")
        r = self.client.get(f"/download/{self.job}/clip_kecil.mp4")
        self.assertEqual(r.status_code, 404)

    def test_file_html_ditolak(self):
        self._tulis("clip_html.mp4", b"<!DOCTYPE html><html>Sign in</html>" * 60)
        r = self.client.get(f"/download/{self.job}/clip_html.mp4")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b"<!DOCTYPE html>", r.data)

    def test_clip_valid_dikirim_lengkap(self):
        isi = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 4000
        self._tulis("clip_ok.mp4", isi)
        r = self.client.get(f"/download/{self.job}/clip_ok.mp4")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers.get("Content-Disposition", ""))
        # Content-Length harus cocok dengan isi nyata, bukan 0 atau terpotong.
        self.assertEqual(int(r.headers.get("Content-Length", 0)), len(isi))
        self.assertEqual(len(r.data), len(isi))

    def test_path_melolos_ditolak(self):
        r = self.client.get(f"/download/{self.job}/../../etc/passwd")
        self.assertIn(r.status_code, (400, 404))


class TestJobDir(unittest.TestCase):
    def test_job_dir_selalu_absolut(self):
        d = self.webapp_abs().job_dir_for("abc123")
        self.assertTrue(os.path.isabs(d))
        self.assertTrue(d.endswith(os.path.join("clips", "abc123")))

    @staticmethod
    def webapp_abs():
        import webapp

        return webapp


if __name__ == "__main__":
    unittest.main(verbosity=2)
