# 将 release 目录中的 app 安装到本机，并创建桌面/开始菜单快捷方式
# 用法：在「NoguakeSetup」文件夹内右键「使用 PowerShell 运行」或：
#   powershell -ExecutionPolicy Bypass -File install.ps1
param(
    [string]$SourceDir = "",
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"
$AppName = "不挂科神器"
$ExeName = "Noguake.exe"

if (-not $SourceDir) {
    $SourceDir = Join-Path $PSScriptRoot "app"
}
if (-not $InstallDir) {
    $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\Noguake"
}

if (-not (Test-Path (Join-Path $SourceDir $ExeName))) {
    Write-Host "[错误] 未找到 $ExeName，请先运行「制作安装包.bat」生成 app 目录。" -ForegroundColor Red
    exit 1
}

Write-Host "正在安装到: $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path (Join-Path $SourceDir "*") -Destination $InstallDir -Recurse -Force

$TargetExe = Join-Path $InstallDir $ExeName
$Wsh = New-Object -ComObject WScript.Shell

$Desktop = [Environment]::GetFolderPath("Desktop")
$DesktopLnk = Join-Path $Desktop "$AppName.lnk"
$sc = $Wsh.CreateShortcut($DesktopLnk)
$sc.TargetPath = $TargetExe
$sc.WorkingDirectory = $InstallDir
$sc.Description = $AppName
$sc.Save()
Write-Host "已创建桌面快捷方式: $DesktopLnk"

$StartMenu = [Environment]::GetFolderPath("Programs")
$StartFolder = Join-Path $StartMenu $AppName
New-Item -ItemType Directory -Force -Path $StartFolder | Out-Null
$StartLnk = Join-Path $StartFolder "$AppName.lnk"
$sc2 = $Wsh.CreateShortcut($StartLnk)
$sc2.TargetPath = $TargetExe
$sc2.WorkingDirectory = $InstallDir
$sc2.Description = $AppName
$sc2.Save()
Write-Host "已创建开始菜单快捷方式: $StartLnk"

Write-Host ""
Write-Host "安装完成。双击桌面「$AppName」即可使用。" -ForegroundColor Green
Write-Host "题库数据保存在: $(Join-Path $env:LOCALAPPDATA 'Noguake\libraries')"
