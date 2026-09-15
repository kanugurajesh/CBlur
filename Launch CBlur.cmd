@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run setup.ps1 first. See README.md for setup instructions.
  pause
  exit /b 1
)
start "CBlur" ".venv\Scripts\pythonw.exe" "main.py"
