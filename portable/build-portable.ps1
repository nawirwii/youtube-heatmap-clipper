<#
.SYNOPSIS
    Build paket portable Windows (onedir) lalu zip + verifikasi isinya.

.DESCRIPTION
    Tahapan:
      1. install dependency build (requirements + pyinstaller [+ faster-whisper])
      2. tarik ffmpeg/ffprobe/yt-dlp ke bin/ (lewat fetch-deps.ps1)
      3. PyInstaller onedir  -> build-portable/dist/YoutubeHeatmapClipper
      4. stage  -> build-portable/stage/YoutubeHeatmapClipper_v<VER>_x64
      5. exe --self-test di folder hasil stage  (gate: paket harus benar-benar jalan)
      6. zip    -> build-portable/YoutubeHeatmapClipper_v<VER>_x64_portable.zip
      7. verify_portable.py membaca NAMA FILE di dalam zip

    Tahap 5 dan 7 bukan formalitas: tanpa keduanya, "build hijau" pernah
    menghasilkan paket yang launching-nya tapi tidak punya ffmpeg/yt-dlp.

.EXAMPLE
    pwsh portable/build-portable.ps1 -Version 2.0.47
    pwsh portable/build-portable.ps1 -Version 2.0.47 -NoWhisper
#>
[CmdletBinding()]
param(
    [string]$Version = "",
    [switch]$NoWhisper,
    [switch]$SkipDeps,
    [switch]$SkipSelfTest
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$root = Split-Path -Parent $PSScriptRoot
$work = Join-Path $root "build-portable"
$distDir = Join-Path $root "dist"
$stageRoot = Join-Path $work "stage"
$appName = "YoutubeHeatmapClipper"

Set-Location $root

if (-not $Version) {
    $Version = (Get-Content (Join-Path $root "VERSION") -Raw).Trim()
}
if (-not $Version) { throw "Version kosong dan file VERSION tidak terbaca." }
$Version = $Version.TrimStart("v")

$stageName = "${appName}_v${Version}_x64"
$zipPath = Join-Path $work "${appName}_v${Version}_x64_portable.zip"

function Step($msg) { Write-Host ""; Write-Host "==> $msg" }
function Info($msg) { Write-Host "    $msg" }

Step "Paket $appName v$Version (whisper: $(-not $NoWhisper))"
Info "python : $(& python --version 2>&1)"

# ---------------------------------------------------------------- dependencies
if (-not $SkipDeps) {
    Step "Install dependency build"
    & python -m pip install --upgrade pip --quiet
    & python -m pip install -r requirements.txt --quiet
    & python -m pip install "pyinstaller>=6.6,<7" --quiet
    if ($NoWhisper) {
        Info "subtitle AI: dilewati (-NoWhisper)"
    } else {
        & python -m pip install faster-whisper --quiet
    }
    if ($LASTEXITCODE -ne 0) { throw "pip install gagal (exit $LASTEXITCODE)." }
}

# ---------------------------------------------------------------- external bins
if (-not $SkipDeps) {
    Step "Tarik tool eksternal (ffmpeg, ffprobe, yt-dlp)"
    & pwsh -NoProfile -File (Join-Path $PSScriptRoot "fetch-deps.ps1")
    if ($LASTEXITCODE -ne 0) { throw "fetch-deps.ps1 gagal (exit $LASTEXITCODE)." }
} else {
    Step "Lewati tarik tool eksternal (-SkipDeps)"
    foreach ($t in @("ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe")) {
        $p = Join-Path $root "bin\$t"
        if (-not (Test-Path $p)) { Info "PERINGATAN: $t tidak ada di bin/" }
    }
}

# ---------------------------------------------------------------- pyinstaller
Step "PyInstaller onedir"
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
& python -m PyInstaller --noconfirm --clean `
    --distpath $distDir `
    --workpath (Join-Path $work "pyi") `
    (Join-Path $PSScriptRoot "yhc.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller gagal (exit $LASTEXITCODE)." }

$built = Join-Path $distDir $appName
if (-not (Test-Path (Join-Path $built "$appName.exe"))) {
    throw "Output PyInstaller tidak lengkap: $built\$appName.exe tidak ada."
}

# ---------------------------------------------------------------- stage
Step "Stage paket"
if (Test-Path $stageRoot) { Remove-Item -Recurse -Force $stageRoot }
$stage = Join-Path $stageRoot $stageName
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item -Recurse (Join-Path $built "*") $stage
Copy-Item (Join-Path $PSScriptRoot "README-PORTABLE.txt") $stage -Force

# build-info.txt: versi persis yang dipakai, supaya bisa ditelusuri saat bug report.
$ffmpegVer = (& (Join-Path $built "_internal\bin\ffmpeg.exe") -hide_banner -version 2>&1 | Select-Object -First 1)
$ytDlpVer = (& (Join-Path $built "_internal\bin\yt-dlp.exe") --version 2>&1 | Select-Object -First 1)
@(
    "app      : $appName v$Version",
    "built    : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')",
    "python   : $(& python --version 2>&1)",
    "pyinstaller: $(& python -m PyInstaller --version 2>&1)",
    "ffmpeg   : $ffmpegVer",
    "yt-dlp   : $ytDlpVer",
    "whisper  : $(-not $NoWhisper)"
) | Set-Content -Path (Join-Path $stage "build-info.txt") -Encoding UTF8
Info "build-info.txt ditulis"

# ---------------------------------------------------------------- self test
if (-not $SkipSelfTest) {
    Step "Self-test exe hasil build (gate)"
    $exe = Join-Path $stage "$appName.exe"
    $testArgs = @("--self-test")
    if (-not $NoWhisper) { $testArgs += "--require-whisper" }
    & $exe @testArgs
    if ($LASTEXITCODE -ne 0) { throw "Self-test GAGAL (exit $LASTEXITCODE) - paket yang dihasilkan tidak sah." }
    Info "self-test lulus"
} else {
    Info "self-test dilewati (-SkipSelfTest)"
}

# ---------------------------------------------------------------- zip
Step "Zip paket"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $stage, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)
$zipItem = Get-Item $zipPath
$sha = (Get-FileHash $zipPath -Algorithm SHA256).Hash
Info ("zip    : {0}" -f $zipItem.Name)
Info ("ukuran : {0:N0} bytes ({1:N1} MiB)" -f $zipItem.Length, ($zipItem.Length / 1MB))
Info ("sha256 : {0}" -f $sha)

# ---------------------------------------------------------------- verify zip
Step "Verifikasi isi zip"
$verifyArgs = @((Join-Path $PSScriptRoot "verify_portable.py"), $zipPath)
if (-not $NoWhisper) { $verifyArgs += "--expect-whisper" }
& python @verifyArgs
if ($LASTEXITCODE -ne 0) { throw "verifikasi zip GAGAL (exit $LASTEXITCODE)" }

# Format standar sha256sum: "<hash>  <nama file>" dengan akhiran LF.
# Set-Content di Windows menulis CRLF, itu bikin `sha256sum -c` gagal di Linux/WSL.
$shaLine = "{0}  {1}`n" -f $sha.ToLowerInvariant(), $zipItem.Name
[System.IO.File]::WriteAllText("$zipPath.sha256", $shaLine, (New-Object System.Text.UTF8Encoding $false))
Info "checksum ditulis: $(Split-Path -Leaf $zipPath).sha256"

Step "Selesai"
Info "paket  : $zipPath"
Info "stage  : $stage"
