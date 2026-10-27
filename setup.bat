@echo off
setlocal
python --version
if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer and try again.
    exit /b 1
)
python -c "import tkinter"
if errorlevel 1 (
    echo Tkinter is missing. Reinstall Python with Tcl/Tk support enabled.
    exit /b 1
)
python -c "import sounddevice, speech_recognition, pyttsx3, gtts"
if errorlevel 1 (
    echo Voice packages are missing. Run: python -m pip install -r requirements.txt
    exit /b 1
)
echo Setup checks passed. Set OPENAI_API_KEY if your API requires one, then run run.bat.
