@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run setup.ps1 first.
  pause
  exit /b 1
)
start "CBlur Demo" ".venv\Scripts\pythonw.exe" "main.py" --demo
