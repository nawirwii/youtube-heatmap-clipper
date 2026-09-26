"""Test jalur play/download clip.

Dipakai karena gejala di lapangan: progres 100%, tapi Play gagal dan Download
menyimpan file HTML, bukan video.
"""

import io
import os
import sys
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
