import array
import ctypes
import math
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable


SAMPLE_RATE = 16_000
BLOCK_SIZE = 1_024
SILENCE_SECONDS = 1.2
MAX_PHRASE_SECONDS = 20
START_TIMEOUT_SECONDS = 8


class VoiceError(Exception):
    """Raised when speech cannot be captured, recognized, or spoken."""


def _rms(audio: bytes) -> float:
    samples = array.array("h")
    samples.frombytes(audio)
    if not samples:
        return 0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def listen_hindi(cancel_event: threading.Event | None = None) -> str:
    try:
        import sounddevice as sd
        import speech_recognition as sr
    except ImportError as error:
        raise VoiceError(
            "Voice input needs its optional packages. Run: python -m pip install -r requirements.txt"
        ) from error

    audio_blocks: queue.Queue[bytes] = queue.Queue()
    callback_errors: list[str] = []

    def receive_audio(indata: Any, _frames: int, _time_info: Any, status: Any) -> None:
        if status:
            callback_errors.append(str(status))
        audio_blocks.put(indata.tobytes())

    frames: list[bytes] = []
    phrase_started_at: float | None = None
    last_speech_at: float | None = None
    deadline = time.monotonic() + START_TIMEOUT_SECONDS + MAX_PHRASE_SECONDS
    speech_threshold = 300

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=1,
            dtype="int16",
            callback=receive_audio,
        ):
            while time.monotonic() < deadline:
                if cancel_event is not None and cancel_event.is_set():
                    raise VoiceError("Voice chat stopped.")
                try:
                    block = audio_blocks.get(timeout=0.25)
                except queue.Empty:
                    continue
                if callback_errors:
                    raise VoiceError(f"Microphone input error: {callback_errors[0]}")

                now = time.monotonic()
                if _rms(block) >= speech_threshold:
                    phrase_started_at = phrase_started_at or now
                    last_speech_at = now
                if phrase_started_at is not None:
                    frames.append(block)
                    if (
                        last_speech_at is not None
                        and now - last_speech_at >= SILENCE_SECONDS
                    ):
                        break
                    if now - phrase_started_at >= MAX_PHRASE_SECONDS:
                        break
            else:
                raise VoiceError("No speech detected. Check your microphone and try again.")
    except VoiceError:
        raise
    except (OSError, RuntimeError, sd.PortAudioError) as error:
        raise VoiceError(f"Could not use the microphone: {error}") from error

    if not frames:
        raise VoiceError("No speech detected. Check your microphone and try again.")

    audio = sr.AudioData(b"".join(frames), SAMPLE_RATE, 2)
    try:
        text = sr.Recognizer().recognize_google(audio, language="hi-IN")
    except sr.UnknownValueError as error:
        raise VoiceError("I couldn't understand that. Please try speaking again.") from error
    except sr.RequestError as error:
        raise VoiceError(f"Online Hindi speech recognition failed: {error}") from error
    if not text.strip():
        raise VoiceError("I couldn't recognize any words. Please try again.")
    return text.strip()


def speak_hindi(
    text: str,
    cancel_event: threading.Event | None = None,
    backend: str = "google",
) -> None:
    if backend == "windows":
        _speak_with_windows(text)
    elif backend == "google":
        _speak_with_google(text, cancel_event)
    else:
        raise VoiceError("JARVIS_TTS must be set to 'google' or 'windows'.")


def _speak_with_windows(text: str) -> None:
    try:
        import pyttsx3
    except ImportError as error:
        raise VoiceError(
            "Windows speech output needs pyttsx3. Run: python -m pip install -r requirements.txt"
        ) from error

    engine = None
    try:
        engine = pyttsx3.init()
        hindi_voices = [
            voice
            for voice in engine.getProperty("voices")
            if "hi-in" in str(voice.id).lower()
            or "hindi" in str(voice.name).lower()
            or "hi-in" in str(voice.name).lower()
            or "0439" in str(getattr(voice, "languages", "")).lower()
        ]
        if not hindi_voices:
            raise VoiceError(
                "A Hindi speech voice is not installed. Add a Hindi text-to-speech "
                "voice in Windows Settings > Time & language > Speech."
            )
        engine.setProperty("voice", hindi_voices[0].id)
        engine.say(text)
        engine.runAndWait()
    except VoiceError:
        raise
    except (OSError, RuntimeError) as error:
        raise VoiceError(f"Could not play the spoken reply: {error}") from error
    finally:
        if engine is not None:
            engine.stop()


def _speak_with_google(
    text: str,
    cancel_event: threading.Event | None,
) -> None:
    try:
        from gtts import gTTS
        from gtts.tts import gTTSError
    except ImportError as error:
        raise VoiceError(
            "Google voice output needs its optional packages. "
            "Run: python -m pip install -r requirements.txt"
        ) from error

    audio_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
            audio_path = audio_file.name
        gTTS(text=text, lang="hi", timeout=(5, 20)).save(audio_path)
        if cancel_event is not None and cancel_event.is_set():
            return
        _play_mp3(audio_path, cancel_event)
    except (gTTSError, OSError, TimeoutError, subprocess.SubprocessError) as error:
        raise VoiceError(f"Could not generate or play the Hindi reply: {error}") from error
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


def _play_mp3(audio_path: str, cancel_event: threading.Event | None) -> None:
    if os.name == "nt":
        _play_mp3_windows(audio_path, cancel_event)
        return

    player = "afplay" if sys.platform == "darwin" else "ffplay"
    executable = shutil.which(player)
    if executable is None:
        raise VoiceError(f"Install {player} to play Google voice replies on this system.")
    command = [executable, audio_path] if player == "afplay" else [
        executable,
        "-nodisp",
        "-autoexit",
        "-loglevel",
        "error",
        audio_path,
    ]
    with subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                process.terminate()
                process.wait()
                return
            time.sleep(0.1)
        if process.returncode:
            detail = process.stderr.read().strip() if process.stderr else ""
            raise VoiceError(detail or f"{player} could not play the reply.")


def _play_mp3_windows(
    audio_path: str,
    cancel_event: threading.Event | None,
) -> None:
    winmm = ctypes.WinDLL("winmm")
    send_command = winmm.mciSendStringW
    error_message = winmm.mciGetErrorStringW
    send_command.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint,
        ctypes.c_void_p,
    ]
    send_command.restype = ctypes.c_uint
    error_message.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
    error_message.restype = ctypes.c_int
    response = ctypes.create_unicode_buffer(256)

    def command(value: str) -> str:
        result = send_command(value, response, len(response), None)
        if result:
            message = ctypes.create_unicode_buffer(256)
            error_message(result, message, len(message))
            raise VoiceError(f"Windows could not play the Hindi reply: {message.value}")
        return response.value

    alias = "jarvis_reply"
    command(f'open "{audio_path}" type mpegvideo alias {alias}')
    try:
        command(f"play {alias}")
        while command(f"status {alias} mode") == "playing":
            if cancel_event is not None and cancel_event.is_set():
                command(f"stop {alias}")
                return
            time.sleep(0.1)
    finally:
        command(f"close {alias}")


def start_voice_task(
    target: Callable[..., str | None],
    responses: queue.Queue[tuple[str, str, int, str]],
    kind: str,
    session_id: int,
    *args: Any,
    task_text: str = "",
) -> None:
    def run() -> None:
        try:
            result = target(*args)
        except VoiceError as error:
            responses.put((f"{kind}_error", str(error), session_id, task_text))
        else:
            responses.put(
                (kind, result if isinstance(result, str) else "", session_id, task_text)
            )

    threading.Thread(target=run, daemon=True).start()
