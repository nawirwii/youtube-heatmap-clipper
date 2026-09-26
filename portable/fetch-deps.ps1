<#
.SYNOPSIS
    Download tool eksternal (ffmpeg, ffprobe, yt-dlp) ke folder bin/.

.DESCRIPTION
    Binari tool TIDAK di-commit ke repo (ffmpeg ~80MB, yt-dlp ~13MB).
    Script ini menariknya dari URL yang stabil, lalu memverifikasi hasilnya.
    Dijalankan otomatis oleh build-portable.ps1, dan bisa dipanggil manual.

.EXAMPLE
    pwsh portable/fetch-deps.ps1
    pwsh portable/fetch-deps.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$root = Split-Path -Parent $PSScriptRoot
$bin = Join-Path $root "bin"
$tmp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }

# URL "latest" -> selalu ada, tidak perlu pin versi di sini.
# BtbN GPL build memuat libx264 + libass (dibutuhkan untuk burn subtitle).
$ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$ytdlpUrl = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

New-Item -ItemType Directory -Force -Path $bin | Out-Null
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

function Test-Have([string]$name) {
    if ($Force) { return $false }
    $path = Join-Path $bin $name
    return (Test-Path $path) -and ((Get-Item $path).Length -gt 0)
}

function Get-Tool($name, [string]$url) {
    if (Test-Have $name) {
        Write-Host "  [skip] $name sudah ada"
        return
    }
    $dest = Join-Path $bin $name
    Write-Host "  [get ] $name <- $url"
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
    if (-not (Test-Path $dest) -or (Get-Item $dest).Length -lt 1024) {
        throw "Download $name gagal / file terlalu kecil."
    }
    Write-Host ("         {0:N0} bytes" -f (Get-Item $dest).Length)
}

Write-Host "==> Menarik tool eksternal ke $bin"

# --- ffmpeg + ffprobe dari satu zip ---
$needFfmpeg = (-not (Test-Have "ffmpeg.exe")) -or (-not (Test-Have "ffprobe.exe"))
if ($needFfmpeg) {
    $zip = Join-Path $tmp "ffmpeg-win64-gpl.zip"
    $extract = Join-Path $tmp "ffmpeg-extract"
    Write-Host "  [get ] ffmpeg-master-latest-win64-gpl.zip"
    Invoke-WebRequest -Uri $ffmpegUrl -OutFile $zip -UseBasicParsing
    if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
    Expand-Archive -Path $zip -DestinationPath $extract -Force
    foreach ($tool in @("ffmpeg.exe", "ffprobe.exe")) {
        $found = Get-ChildItem -Path $extract -Recurse -Filter $tool -File | Select-Object -First 1
        if (-not $found) { throw "$tool tidak ada di dalam zip ffmpeg." }
        Copy-Item $found.FullName (Join-Path $bin $tool) -Force
        Write-Host ("         {0} {1:N0} bytes" -f $tool, (Get-Item (Join-Path $bin $tool)).Length)
    }
    Remove-Item -Force $zip
    Remove-Item -Recurse -Force $extract
} else {
    Write-Host "  [skip] ffmpeg.exe + ffprobe.exe sudah ada"
}

# --- yt-dlp.exe ---
Get-Tool "yt-dlp.exe" $ytdlpUrl

# --- verifikasi: jalankan toolnya, jangan hanya cek file ada ---
Write-Host "==> Verifikasi tool"
$problems = @()
try {
    $ver = (& (Join-Path $bin "ffmpeg.exe") -hide_banner -version 2>&1 | Select-Object -First 1)
    Write-Host "  ffmpeg : $ver"
    if (-not $ver) { $problems += "ffmpeg.exe tidak bisa dijalankan" }
} catch { $problems += "ffmpeg.exe error: $_" }
try {
    $ver = (& (Join-Path $bin "ffprobe.exe") -hide_banner -version 2>&1 | Select-Object -First 1)
    Write-Host "  ffprobe: $ver"
    if (-not $ver) { $problems += "ffprobe.exe tidak bisa dijalankan" }
} catch { $problems += "ffprobe.exe error: $_" }
try {
    $ver = (& (Join-Path $bin "yt-dlp.exe") --version 2>&1 | Select-Object -First 1)
    Write-Host "  yt-dlp : $ver"
    if (-not $ver) { $problems += "yt-dlp.exe tidak bisa dijalankan" }
} catch { $problems += "yt-dlp.exe error: $_" }

if ($problems.Count -gt 0) {
    throw "Tool eksternal tidak lengkap:`n  - $($problems -join "`n  - ")"
}

Write-Host "==> Selesai. Isi bin/:"
Get-ChildItem $bin | ForEach-Object { Write-Host ("  {0,-14} {1,15:N0} bytes" -f $_.Name, $_.Length) }
