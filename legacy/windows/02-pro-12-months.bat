@echo off
chcp 65001 >nul
title Pro 12 months - step 1
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
echo ============================================
echo   Google AI Pro 5TB - 12-month offer (eligibility not guaranteed) (step 1)
echo   Confirm the sheet says: 12-month free trial
echo   DO NOT confirm if it shows 1 month or a price
echo ============================================
python ultra0.py --account "current@device" --no-add --force --plan pro12
echo.
pause