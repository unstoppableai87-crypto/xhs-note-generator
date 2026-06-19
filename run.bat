@echo off
cd /d "%~dp0"

if not exist .env (
    echo No .env found - copying .env.example to .env
    copy .env.example .env >nul
    echo Please edit .env and add your GEMINI_API_KEY, then run this again.
    notepad .env
    exit /b
)

if not exist .venv (
    echo First-time setup: creating a private Python environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
streamlit run app.py
pause
