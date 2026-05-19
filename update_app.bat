@echo off
title Cap nhat TTHC App len Streamlit Cloud
cd /d "G:\My Drive\AI-SUC TAI COC THEO DAT NEN"

echo === Dong bo code vao cdm-deploy ===
copy /Y "scripts\app_cdm.py" "cdm-deploy\scripts\app_cdm.py" >nul
copy /Y "scripts\app_cdm.py" "cdm-deploy\app_cdm.py" >nul
copy /Y "data\TTHC.sqlite"   "cdm-deploy\data\TTHC.sqlite"   >nul
echo   app_cdm.py + TTHC.sqlite da copy xong

echo.
echo === Push len GitHub (Streamlit Cloud tu redeploy) ===
cd cdm-deploy

git add app_cdm.py scripts\app_cdm.py data\TTHC.sqlite

set /p MSG="Nhap mo ta thay doi (Enter de dung 'Update app'): "
if "%MSG%"=="" set MSG=Update app

git commit -m "%MSG%"
git push origin main

echo.
echo === Xong! Kiem tra tai https://phantichcocdm.streamlit.app ===
echo Streamlit Cloud redeploy trong khoang 30-60 giay.
echo.
pause
