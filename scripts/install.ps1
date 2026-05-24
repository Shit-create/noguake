# UTF-8 install script - avoids CMD encoding bugs
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "========================================"
Write-Host " Campus RAG - Install dependencies"
Write-Host "========================================"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python not found. Install Python 3.10+ from python.org" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Creating venv..."
    python -m venv venv
}

$py = Join-Path (Get-Location) "venv\Scripts\python.exe"
& $py -m pip install -U pip
& $py -m pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] pip install failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host " Done"
Write-Host "========================================"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Install Ollama from ollama.com"
Write-Host "  2. Run: ollama pull qwen2.5:3b"
Write-Host "  3. Put PDF/PPT/DOCX into data\ folder"
Write-Host "  4. Double-click build_index bat (build knowledge base)"
Write-Host "  5. Double-click start ask bat"
Write-Host ""
