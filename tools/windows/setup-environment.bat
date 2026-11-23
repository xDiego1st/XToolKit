@echo off
chcp 65001 >nul
title One-click environment setup
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8

echo ============================================================
echo   Google Ultra / Pro one-click setup
echo   - check Python
echo   - install frida 16.5.9
echo   - find or download adb
echo   - connect MuMu and self-check
echo ============================================================
echo.
pause

python setup_env.py

echo.
echo ------------------------------------------------------------
echo   Setup finished. Next: run-all.ps1 -ListOnly (no checkout)
echo ------------------------------------------------------------
pause