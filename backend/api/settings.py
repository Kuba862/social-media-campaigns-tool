"""Environment-backed settings for the API. Variable names follow guide section 10."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    panel_allowed_email_domain: str


def load_settings() -> Settings:
    return Settings(
        supabase_url=_require("SUPABASE_URL").rstrip("/"),
        supabase_service_role_key=_require("SUPABASE_SERVICE_ROLE_KEY"),
        panel_allowed_email_domain=_require("PANEL_ALLOWED_EMAIL_DOMAIN").lower(),
    )


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Missing environment variable {name}")
    return value
