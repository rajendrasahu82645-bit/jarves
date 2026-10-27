import os
from dataclasses import dataclass
from urllib.parse import urlparse


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout: float = 60.0

    @classmethod
    def from_environment(cls) -> "Settings":
        base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
        model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL).strip()
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()

        parsed_url = urlparse(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("OPENAI_BASE_URL must be a valid http:// or https:// URL.")
        if not model:
            raise ValueError("OPENAI_MODEL cannot be empty.")

        return cls(api_key=api_key, base_url=base_url, model=model)
