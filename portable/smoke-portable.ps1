<#
.SYNOPSIS
    Smoke test paket portable: nyalakan exe-nya, pastikan UI benar-benar
    tersaji dari aset di dalam paket, lalu matikan lagi.

.DESCRIPTION
    Self-test hanya membuktikan file ada dan tool jalan. Smoke test ini
    membuktikan aplikasi frozen benar-benar bisa serve halaman + aset, yaitu
    hal yang pertama dikeluhkan user ("kok putih kosong / 404 font").

    Tidak memanggil YouTube: runner CI bisa diblokir / lambat, dan itu bukan
    bagian dari kontrak "aplikasi bisa jalan".

.EXAMPLE
    pwsh portable/smoke-portable.ps1 -StageDir "build-portable\stage\YoutubeHeatmapClipper_v2.0.47_x64"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$StageDir,
    [int]$StartupTimeoutSec = 90
)

$ErrorActionPreference = "Stop"

$exe = Join-Path $StageDir "YoutubeHeatmapClipper.exe"
if (-not (Test-Path $exe)) { throw "Exe tidak ditemukan: $exe" }

Write-Host "==> Menyalakan $exe (port 5099, tanpa browser)"
$proc = Start-Process -FilePath $exe -ArgumentList @("--port", "5099", "--no-browser") -PassThru
$base = "http://127.0.0.1:5099"

function Stop-App {
    if ($proc -and -not $proc.HasExited) {
        Write-Host "==> Mematikan proses"
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}
trap { Stop-App; Write-Error "Smoke test gagal: $_"; exit 1 }

try {
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSec)
    $up = $false
    while ((Get-Date) -lt $deadline) {
        if ($proc.HasExited) { throw "Proses exit duluan dengan kode $($proc.ExitCode)" }
        try {
            $r = Invoke-WebRequest -Uri $base -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { $up = $true; break }
        } catch { Start-Sleep -Milliseconds 700 }
    }
    if (-not $up) { throw "Server tidak hidup dalam $StartupTimeoutSec detik." }
    Write-Host "    server hidup, HTTP 200"

    if ($r.Content -notmatch "YouTube Heatmap Clipper") {
        throw "HTML root tidak memuat judul aplikasi."
    }
    Write-Host "    [OK] /  -> HTML aplikasi"

    $js = Invoke-WebRequest -Uri "$base/static/app.js" -UseBasicParsing -TimeoutSec 15
    if ($js.StatusCode -ne 200 -or $js.Content.Length -lt 1000) {
        throw "static/app.js gagal dilayani (len=$($js.Content.Length))."
    }
    Write-Host ("    [OK] /static/app.js ({0:N0} bytes)" -f $js.RawContentLength)

    $fontUrl = "$base/assets/fonts/Roboto/static/Roboto-Regular.ttf"
    $font = Invoke-WebRequest -Uri $fontUrl -UseBasicParsing -TimeoutSec 20
    if ($font.StatusCode -ne 200 -or $font.RawContentLength -lt 1000) {
        throw "font gagal dilayani (len=$($font.RawContentLength))."
    }
    Write-Host ("    [OK] /assets/fonts/.../Roboto-Regular.ttf ({0:N0} bytes)" -f $font.RawContentLength)

    # 404 = Flask yang hidup tapi route-nya hilang, bukan "halaman kosong".
    try {
        Invoke-WebRequest -Uri "$base/clip/000/nope.mp4" -UseBasicParsing -TimeoutSec 10 | Out-Null
        Write-Host "    [!!] route /clip/<id>/<file> untuk file hilang seharusnya 404"
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 404) {
            Write-Host "    [OK] route 404 ditangani benar"
        } else {
            throw "Error tidak terduga saat cek 404: $_"
        }
    }

    Write-Host "==> Smoke test LULUS"
}
finally {
    Stop-App
}
