$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 (64-bit) from python.org and run setup again.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt --timeout 120
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' scripts/download_models.py
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
Write-Host 'CBlur is ready. Double-click Launch CBlur.cmd.'
