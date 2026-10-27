#!/bin/sh
set -eu

PYTHON="${PYTHON:-python3}"
"$PYTHON" -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10 or newer is required'"
"$PYTHON" -c "import tkinter"
"$PYTHON" -c "import sounddevice, speech_recognition, pyttsx3, gtts" || {
    printf '%s\n' "Voice packages are missing. Run: $PYTHON -m pip install -r requirements.txt" >&2
    exit 1
}
printf '%s\n' "Setup checks passed. Set OPENAI_API_KEY if your API requires one, then run: $PYTHON main.py"
