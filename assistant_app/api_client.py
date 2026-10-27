import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from assistant_app.settings import Settings


class AssistantAPIError(Exception):
    """Raised when the configured AI service cannot return a usable response."""


class AssistantClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def complete(self, messages: list[dict[str, str]]) -> str:
        url = self._completion_url()
        headers = {"Content-Type": "application/json"}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"

        payload = json.dumps(
            {"model": self._settings.model, "messages": messages}
        ).encode("utf-8")
        request = Request(url, data=payload, headers=headers, method="POST")

        try:
            with urlopen(request, timeout=self._settings.timeout) as response:
                body = response.read().decode("utf-8")
        except UnicodeDecodeError as error:
            raise AssistantAPIError(
                "The AI service response was not valid UTF-8."
            ) from error
        except HTTPError as error:
            with error:
                detail = error.read().decode("utf-8", errors="replace").strip()
            try:
                error_result: Any = json.loads(detail)
            except json.JSONDecodeError:
                error_result = detail
            message = self._error_message(error_result) or error.reason
            raise AssistantAPIError(
                f"The AI service returned HTTP {error.code}: {message}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise AssistantAPIError(f"Could not connect to the AI service: {error}") from error

        try:
            result: Any = json.loads(body)
        except json.JSONDecodeError as error:
            raise AssistantAPIError("The AI service returned invalid JSON.") from error

        if not isinstance(result, dict):
            raise AssistantAPIError("The AI service returned an unexpected response.")
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            detail = result.get("error")
            message = self._error_message(detail)
            raise AssistantAPIError(message or "The AI service returned no answer.")

        choice_message = choices[0].get("message")
        if not isinstance(choice_message, dict):
            raise AssistantAPIError("The AI service response did not contain a message.")
        content = choice_message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AssistantAPIError("The AI service returned an empty answer.")
        return content.strip()

    def _completion_url(self) -> str:
        base_url = self._settings.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    @staticmethod
    def _error_message(value: Any) -> str:
        if isinstance(value, dict):
            message = value.get("message")
            if isinstance(message, str):
                return message
            nested_error = value.get("error")
            if isinstance(nested_error, dict):
                nested_message = nested_error.get("message")
                if isinstance(nested_message, str):
                    return nested_message
        if isinstance(value, str):
            return value
        return ""
