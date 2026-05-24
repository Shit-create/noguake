# 启动 Web 应用（PowerShell，避免 bat 乱码）
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Py = Join-Path $Root "venv\Scripts\python.exe"
$Port = 8765

if (-not (Test-Path $Py)) {
    Write-Host "[ERROR] 请先运行 安装依赖.bat" -ForegroundColor Red
    pause
    exit 1
}

Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host "启动中: http://127.0.0.1:$Port" -ForegroundColor Green
Start-Process "http://127.0.0.1:$Port"
& $Py -m uvicorn app.main:app --host 127.0.0.1 --port $Port
