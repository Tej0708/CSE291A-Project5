from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model_name: str
    log_dir: str = "logs"
    request_timeout_s: float = 60.0
    min_request_interval_s: float = 1.0
    max_completion_tokens: int = 1024

    def __post_init__(self):
        if self.request_timeout_s <= 0 or self.min_request_interval_s < 0:
            raise ValueError('Request timeout must be positive and pacing must be nonnegative')
        if self.max_completion_tokens < 1:
            raise ValueError('Completion-token limit must be positive')


def load_settings() -> Settings:
    """Load runtime settings from .env / environment variables."""
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("TRITONAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY (or TRITONAI_API_KEY). "
            "Add it to .env or export it in your shell."
        )

    base_url = os.getenv("OPENAI_BASE_URL") or "https://tritonai-api.ucsd.edu/v1"
    model_name = os.getenv("MODEL_NAME", "api-glm-5.3-flash")
    log_dir = os.getenv("LOG_DIR", "logs")

    return Settings(
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        log_dir=log_dir,
        request_timeout_s=float(os.getenv("REQUEST_TIMEOUT_S", "60")),
        min_request_interval_s=float(os.getenv("MIN_REQUEST_INTERVAL_S", "1")),
        max_completion_tokens=int(os.getenv("MAX_COMPLETION_TOKENS", "1024")),
    )
