"""Environment-backed settings for the API. Variable names follow guide section 10."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    panel_allowed_email_domain: str
    meta_graph_version: str
    meta_waba_id: str
    meta_phone_number_id: str
    meta_system_user_token: str  # empty: Meta calls answer 503, drafts still work
    meta_app_secret: str
    meta_webhook_verify_token: str


def load_settings() -> Settings:
    return Settings(
        supabase_url=_require("SUPABASE_URL").rstrip("/"),
        supabase_service_role_key=_require("SUPABASE_SERVICE_ROLE_KEY"),
        panel_allowed_email_domain=_require("PANEL_ALLOWED_EMAIL_DOMAIN").lower(),
        meta_graph_version=os.environ.get("META_GRAPH_VERSION", "v24.0"),
        meta_waba_id=os.environ.get("META_WABA_ID", "local-waba"),
        meta_phone_number_id=os.environ.get("META_PHONE_NUMBER_ID", "local-phone"),
        meta_system_user_token=os.environ.get("META_SYSTEM_USER_TOKEN", ""),
        meta_app_secret=os.environ.get("META_APP_SECRET", ""),
        meta_webhook_verify_token=os.environ.get("META_WEBHOOK_VERIFY_TOKEN", ""),
    )


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Missing environment variable {name}")
    return value
