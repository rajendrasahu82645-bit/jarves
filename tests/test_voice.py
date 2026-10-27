import array
import os
import queue
import unittest
from unittest.mock import Mock, patch

from assistant_app.voice import (
    VoiceError,
    _rms,
    _speak_with_google,
    start_voice_task,
)


class VoiceTests(unittest.TestCase):
    def test_rms_is_zero_for_silence(self) -> None:
        self.assertEqual(_rms(array.array("h", [0, 0, 0]).tobytes()), 0)

    def test_rms_detects_audio_level(self) -> None:
        self.assertEqual(_rms(array.array("h", [300, -300]).tobytes()), 300)

    def test_voice_task_returns_success_to_response_queue(self) -> None:
        responses: queue.Queue[tuple[str, str, int, str]] = queue.Queue()

        start_voice_task(lambda: "नमस्ते", responses, "voice", 7)

        self.assertEqual(responses.get(timeout=2), ("voice", "नमस्ते", 7, ""))

    def test_voice_task_reports_expected_voice_errors(self) -> None:
        responses: queue.Queue[tuple[str, str, int, str]] = queue.Queue()

        def fail() -> str:
            raise VoiceError("Microphone unavailable")

        start_voice_task(fail, responses, "voice", 3)

        self.assertEqual(
            responses.get(timeout=2),
            ("voice_error", "Microphone unavailable", 3, ""),
        )

    @patch("assistant_app.voice._play_mp3")
    @patch("gtts.gTTS")
    def test_google_speech_synthesizes_hindi_and_plays_audio(
        self, gtts: Mock, play_mp3: Mock
    ) -> None:
        audio_paths: list[str] = []

        def remember_path(path: str) -> None:
            audio_paths.append(path)

        gtts.return_value.save.side_effect = remember_path

        _speak_with_google("नमस्ते", None)

        gtts.assert_called_once_with(text="नमस्ते", lang="hi", timeout=(5, 20))
        play_mp3.assert_called_once()
        self.assertEqual(len(audio_paths), 1)
        self.assertFalse(os.path.exists(audio_paths[0]))


if __name__ == "__main__":
    unittest.main()
