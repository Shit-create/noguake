# 打包发布：PyInstaller + 可选 Inno Setup
param(
    [switch]$SkipPyInstaller,
    [switch]$InnoOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$VenvPython = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = "python"
}

if (-not $InnoOnly) {
    Write-Host "==> Icon and version_info ..."
    & $VenvPython (Join-Path $Root "scripts\make_icon.py")
    & $VenvPython (Join-Path $Root "scripts\make_version_info.py")

    Write-Host "==> Installing PyInstaller ..."
    & $VenvPython -m pip install -q pyinstaller

    Write-Host "==> PyInstaller build (5-15 min, large size) ..."
    & $VenvPython -m PyInstaller --noconfirm --clean noguake.spec
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$DistApp = Join-Path $Root "dist\Noguake"
if (-not (Test-Path (Join-Path $DistApp "Noguake.exe"))) {
    Write-Host "[ERROR] dist\Noguake\Noguake.exe not found" -ForegroundColor Red
    exit 1
}

$exeKb = [math]::Round((Get-Item (Join-Path $DistApp "Noguake.exe")).Length / 1KB)
$totalBytes = (Get-ChildItem $DistApp -Recurse -File | Measure-Object -Property Length -Sum).Sum
$totalMb = [math]::Round($totalBytes / 1MB, 1)
$fileCount = (Get-ChildItem $DistApp -Recurse -File).Count
Write-Host "==> dist\Noguake: Noguake.exe = ${exeKb} KB (launcher only)"
Write-Host "    Full folder = ${totalMb} MB, $fileCount files (includes _internal\ torch etc.)"
if ($totalMb -lt 200) {
    Write-Host "[WARN] Package seems too small; dependencies may be missing." -ForegroundColor Yellow
}

$ReleaseDir = Join-Path $Root "release\NoguakeSetup"
if (Test-Path $ReleaseDir) { Remove-Item $ReleaseDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Copy-Item -Path $DistApp -Destination (Join-Path $ReleaseDir "app") -Recurse
Copy-Item -Path (Join-Path $Root "installer\install.ps1") -Destination $ReleaseDir
Copy-Item -Path (Join-Path $Root "installer\使用说明.txt") -Destination $ReleaseDir -ErrorAction SilentlyContinue

Write-Host "==> Portable package: release\NoguakeSetup"
Write-Host "    Users: unzip and run install.ps1 for desktop shortcut."

function Find-InnoIscc {
    # Optional: set INNO_SETUP_DIR to your install folder, e.g. D:\Program Files (x86)\Inno Setup 6
    if ($env:INNO_SETUP_DIR) {
        $custom = Join-Path $env:INNO_SETUP_DIR "ISCC.exe"
        if (Test-Path $custom) { return $custom }
    }
    $localCfg = Join-Path $Root "installer\inno_setup_path.txt"
    if (Test-Path $localCfg) {
        $dir = (Get-Content $localCfg -Raw).Trim()
        if ($dir) {
            $custom = Join-Path $dir "ISCC.exe"
            if (Test-Path $custom) { return $custom }
        }
    }
    $candidates = [System.Collections.Generic.List[string]]::new()
    foreach ($base in @(
        ${env:ProgramFiles(x86)},
        $env:ProgramFiles,
        "D:\Program Files (x86)",
        "D:\Program Files",
        "C:\Program Files (x86)",
        "C:\Program Files"
    )) {
        if ($base) {
            $candidates.Add((Join-Path $base "Inno Setup 6\ISCC.exe"))
        }
    }
    foreach ($drive in (Get-PSDrive -PSProvider FileSystem).Root) {
        $candidates.Add((Join-Path $drive "Program Files (x86)\Inno Setup 6\ISCC.exe"))
        $candidates.Add((Join-Path $drive "Program Files\Inno Setup 6\ISCC.exe"))
    }
    foreach ($path in ($candidates | Select-Object -Unique)) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

$Iscc = Find-InnoIscc

if ($Iscc) {
    Write-Host "==> Inno Setup compile ($Iscc) ..."
    & $Iscc (Join-Path $Root "installer\noguake.iss")
    if ($LASTEXITCODE -eq 0) {
        Write-Host "==> Created: installer\Output\NoguakeSetup.exe" -ForegroundColor Green
    }
} else {
    Write-Host "(Inno Setup 6 not found; skipped Setup.exe.)"
    Write-Host "  Install Inno Setup, or create installer\inno_setup_path.txt with one line:"
    Write-Host "  D:\Program Files (x86)\Inno Setup 6"
}

Write-Host "Done."
