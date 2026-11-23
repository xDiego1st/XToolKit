@echo off
chcp 65001 >nul
title Pro +6 months - step 3
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
echo ============================================
echo   Google AI Pro 5TB - claimed six-month extension (step 3)
echo   Verify the actual renewal date; 24 months is not guaranteed
echo ============================================
python ultra0.py --account "current@device" --no-add --force --stack --plan pro6b
echo.
pause