import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from assistant_app.api_client import AssistantAPIError, AssistantClient
from assistant_app.settings import Settings


class FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class AssistantClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = AssistantClient(
            Settings(
                api_key="test-key",
                base_url="https://example.test/v1",
                model="test-model",
            )
        )

    @patch("assistant_app.api_client.urlopen")
    def test_posts_chat_messages_and_returns_answer(self, urlopen: Mock) -> None:
        urlopen.return_value = FakeResponse(
            {"choices": [{"message": {"content": " Hello there. "}}]}
        )
        messages = [{"role": "user", "content": "Hello"}]

        answer = self.client.complete(messages)

        self.assertEqual(answer, "Hello there.")
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url, "https://example.test/v1/chat/completions"
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(
            json.loads(request.data),
            {"model": "test-model", "messages": messages},
        )

    @patch("assistant_app.api_client.urlopen")
    def test_http_error_is_reported(self, urlopen: Mock) -> None:
        error_body = io.BytesIO(b'{"error":{"message":"invalid key"}}')
        urlopen.side_effect = HTTPError(
            "https://example.test/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            error_body,
        )

        with self.assertRaisesRegex(AssistantAPIError, "HTTP 401: invalid key"):
            self.client.complete([{"role": "user", "content": "Hello"}])

    @patch("assistant_app.api_client.urlopen")
    def test_unexpected_api_response_is_reported(self, urlopen: Mock) -> None:
        urlopen.return_value = FakeResponse({"choices": []})

        with self.assertRaisesRegex(AssistantAPIError, "no answer"):
            self.client.complete([{"role": "user", "content": "Hello"}])

    @patch("assistant_app.api_client.urlopen")
    def test_api_key_is_omitted_when_not_configured(self, urlopen: Mock) -> None:
        urlopen.return_value = FakeResponse(
            {"choices": [{"message": {"content": "Local answer"}}]}
        )
        client = AssistantClient(
            Settings(
                api_key="",
                base_url="http://localhost:1234",
                model="local-model",
            )
        )

        self.assertEqual(
            client.complete([{"role": "user", "content": "Hello"}]),
            "Local answer",
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://localhost:1234/v1/chat/completions",
        )
        self.assertIsNone(request.get_header("Authorization"))

    @patch("assistant_app.api_client.urlopen")
    def test_invalid_json_is_reported(self, urlopen: Mock) -> None:
        response = FakeResponse({})
        response.read = lambda: b"not-json"
        urlopen.return_value = response

        with self.assertRaisesRegex(AssistantAPIError, "invalid JSON"):
            self.client.complete([{"role": "user", "content": "Hello"}])


if __name__ == "__main__":
    unittest.main()
