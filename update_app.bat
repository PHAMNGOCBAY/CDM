@echo off
title Cap nhat TTHC App len Streamlit Cloud
cd /d "G:\My Drive\AI-SUC TAI COC THEO DAT NEN"

echo === Dong bo code vao cdm-deploy ===
copy /Y "scripts\app_cdm.py" "cdm-deploy\scripts\app_cdm.py" >nul
copy /Y "scripts\app_cdm.py" "cdm-deploy\app_cdm.py" >nul
copy /Y "scripts\wall_internal_force.py" "cdm-deploy\scripts\wall_internal_force.py" >nul
copy /Y "scripts\sw_global_stability.py" "cdm-deploy\scripts\sw_global_stability.py" >nul
copy /Y "scripts\settlement_calc.py" "cdm-deploy\scripts\settlement_calc.py" >nul
copy /Y "scripts\cdm_zoning.py" "cdm-deploy\scripts\cdm_zoning.py" >nul
copy /Y "scripts\thuyvan_phuan_import.py" "cdm-deploy\scripts\thuyvan_phuan_import.py" >nul
copy /Y "data\TTHC.sqlite"   "cdm-deploy\data\TTHC.sqlite"   >nul
copy /Y "data\tccs41_params.json" "cdm-deploy\data\tccs41_params.json" >nul
REM Cac MD render runtime trong app_cdm.py
copy /Y "55-cdm-zoning-principles.md" "cdm-deploy\55-cdm-zoning-principles.md" >nul
REM KHONG copy requirements.txt: file cloud (cdm-deploy/requirements.txt) khac file local
echo   app_cdm + wall_force + sw_stability + settlement + cdm_zoning + thuyvan + TTHC.sqlite + tccs41.json + MD 55 da copy xong

echo.
echo === Push len GitHub (Streamlit Cloud tu redeploy) ===
cd cdm-deploy

git add app_cdm.py scripts\app_cdm.py scripts\wall_internal_force.py scripts\sw_global_stability.py scripts\settlement_calc.py scripts\cdm_zoning.py scripts\thuyvan_phuan_import.py data\TTHC.sqlite data\tccs41_params.json 55-cdm-zoning-principles.md requirements.txt

set /p MSG="Nhap mo ta thay doi (Enter de dung 'Update app'): "
if "%MSG%"=="" set MSG=Update app

git commit -m "%MSG%"
git push origin main

echo.
echo === Xong! Kiem tra tai https://phantichcocdm.streamlit.app ===
echo Streamlit Cloud redeploy trong khoang 30-60 giay.
echo.
pause
