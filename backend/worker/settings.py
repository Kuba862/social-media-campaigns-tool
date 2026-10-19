"""Environment-backed settings for the worker."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    temporal_address: str
    temporal_namespace: str
    temporal_api_key: str


def load_settings() -> Settings:
    """Defaults match `temporal server start-dev`, so the worker runs locally with no .env."""
    return Settings(
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        temporal_api_key=os.environ.get("TEMPORAL_API_KEY", ""),
    )
