@echo off
title TTHC Web App (FastAPI)
cd /d "G:\My Drive\AI-SUC TAI COC THEO DAT NEN"

set PY=C:\Users\bayng\AppData\Local\Programs\Python\Python312\python.exe

echo Dung Streamlit neu dang chay...
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

echo Khoi dong FastAPI tren port 8503...
"%PY%" -X utf8 -m uvicorn web.main:app --host 0.0.0.0 --port 8503 --reload

pause
