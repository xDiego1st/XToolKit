@echo off
chcp 65001 >nul
title Env check
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
echo ============================================
echo   Checking emulator / frida / billing module
echo ============================================
python ultra0.py --check
echo.
pause