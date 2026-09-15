$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.txt --timeout 120
if ($LASTEXITCODE -ne 0) { throw 'Build dependencies failed.' }
& '.\.venv\Scripts\python.exe' scripts/download_models.py
if ($LASTEXITCODE -ne 0) { throw 'Models missing.' }
& '.\.venv\Scripts\python.exe' -m PyInstaller CBlur.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
& '.\.venv\Scripts\python.exe' scripts/package_docs.py
if ($LASTEXITCODE -ne 0) { throw 'Packaging documentation failed.' }
Write-Host 'Portable application: dist\CBlur\CBlur.exe. Keep the entire CBlur folder together.'
