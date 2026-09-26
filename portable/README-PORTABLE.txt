==========================================================
  YouTube Heatmap Clipper - PAKET PORTABLE (Windows x64)
==========================================================

CARA PAKAI
----------
1. Ekstrak semua file (jangan cuma exe-nya) ke folder, misal:

       C:\YoutubeHeatmapClipper\

2. Double-click  YoutubeHeatmapClipper.exe

3. Browser otomatis terbuka ke http://127.0.0.1:5000
   Kalau port 5000 sudah dipakai, aplikasi otomatis pindah port dan
   alamat yang benar akan tertulis di jendela console.

4. File sementara dan hasil clip disimpan di folder  clips\  (di dalam paket ini)
   sehingga foldernya bisa langsung dipindah / di-backup.

5. Untuk menutup aplikasi: tutup jendela console, atau tekan Ctrl+C di
   jendela itu.


YANG SUDAH TERDAPAT DI DALAM PAKET
-----------------------------------
  Python runtime 3.11 + Flask        -> tidak perlu install Python
  ffmpeg + ffprobe                   -> tidak perlu install FFmpeg
  yt-dlp.exe                         -> tidak perlu install yt-dlp
  20+ font (Roboto, Montserrat, ...) -> untuk burn subtitle
  faster-whisper                     -> subtitle AI (model diunduh sekali
                                        saat pertama kali dipakai)


CATATAN PENTING
---------------
- Extractor Windows / antivirus boleh menandai file .exe di dalam paket
  ini (PyInstaller onefile-style bundling). Aplikasi ini open-source,
  source-nya bisa dicek langsung di GitHub.

- Model Whisper (besar: tiny ~75 MB, small ~466 MB) diunduh otomatis saat
  subtitle AI pertama kali dipakai, lalu disimpan di  models\  di dalam
  paket ini. Butuh koneksi internet untuk unduhan pertama saja.

- yt-dlp sering perlu di-update kalau YouTube mengubah stuff.
  Ganti saja file  _internal\bin\yt-dlp.exe  dengan versi terbaru dari
  https://github.com/yt-dlp/yt-dlp/releases/latest
  (tidak perlu reinstall aplikasi).

- Subtitles/ffmpeg butuh symlink? Tidak. Paket ini sudah termasuk
  cache model di dalam folder sendiri, jadi aman di flashdisk / OneDrive.


MODE CLI (opsional)
-------------------
Paket ini juga bisa dipakai lewat command prompt, tanpa browser:

    YoutubeHeatmapClipper.exe --url "https://www.youtube.com/watch?v=VIDEO_ID" ^
        --crop split_left --subtitle y --whisper-model small --ratio 9:16

    YoutubeHeatmapClipper.exe --check      (cek dependensi)
    YoutubeHeatmapClipper.exe --self-test  (cek kelengkapan paket)


MASALAH UMUM
------------
  "Port 5000 sudah dipakai"
      Tidak apa-apa, aplikasi otomatis cari port kosong. Baca alamat
      yang muncul di jendela console.

  Error "FFmpeg tidak ketemu"
      Paket ini tidak lengkap. Cek isi  _internal\bin\  (harus ada
      ffmpeg.exe, ffprobe.exe, yt-dlp.exe).

  Subtitle AI gagal / "WinError 1314"
      Jalankan exe sebagai Administrator sekali, atau pindahkan folder
      ke C:\ (bukan flashdisk/OneDrive), lalu ulangi.

  Antivirus mendeteksi file sebagai virus
      Lihat catatan di atas + build-info.txt di folder ini berisi versi
      persis dari tiap komponen yang dipakai.


INFO VERSI
----------
  build-info.txt  -> versi app, Python, PyInstaller, ffmpeg, yt-dlp
