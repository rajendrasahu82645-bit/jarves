import os
import unittest
from unittest.mock import patch

from assistant_app.settings import DEFAULT_BASE_URL, DEFAULT_MODEL, Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_are_used_when_environment_is_empty(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_environment()

        self.assertEqual(settings.base_url, DEFAULT_BASE_URL)
        self.assertEqual(settings.model, DEFAULT_MODEL)
        self.assertEqual(settings.api_key, "")

    def test_custom_values_are_read_and_base_url_is_normalized(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "http://localhost:1234/v1/",
                "OPENAI_MODEL": "test-model",
            },
            clear=True,
        ):
            settings = Settings.from_environment()

        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.base_url, "http://localhost:1234/v1")
        self.assertEqual(settings.model, "test-model")

    def test_invalid_base_url_is_rejected(self) -> None:
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "not a URL"}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_BASE_URL"):
                Settings.from_environment()

    def test_empty_model_is_rejected(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MODEL": "  "}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_MODEL"):
                Settings.from_environment()


if __name__ == "__main__":
    unittest.main()
