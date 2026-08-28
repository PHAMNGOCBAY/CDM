@echo off
title AI Geology Chatbot
echo Dang khoi dong Chatbot AI...
echo ---------------------------------
call .venv\Scripts\activate
streamlit run web\chat_app.py
pause
