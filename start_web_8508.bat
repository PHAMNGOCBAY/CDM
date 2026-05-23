@echo off
title TTHC HTML App (port 8508)
cd /d "G:\My Drive\AI-SUC TAI COC THEO DAT NEN"
set PY=C:\Users\bayng\AppData\Local\Programs\Python\Python312\python.exe
echo Khoi dong HTML App tren port 8508...
echo Truy cap: http://localhost:8508
echo.
"%PY%" -X utf8 -m uvicorn web.app8508:app --host 0.0.0.0 --port 8508 --reload
pause
