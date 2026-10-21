"""Environment-backed settings for the API. Variable names follow guide section 10."""

import os
from dataclasses import dataclass

from core.sending import parse_allowlist


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
    wa_send_mode: str  # "test" or "live"; the PoC never sets live
    wa_allowed_test_recipients: frozenset[str]
    temporal_address: str
    temporal_namespace: str
    temporal_api_key: str  # empty for the local dev server


def load_settings() -> Settings:
    send_mode = os.environ.get("WA_SEND_MODE", "test")
    if send_mode not in ("test", "live"):
        raise RuntimeError("WA_SEND_MODE must be test or live")

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
        wa_send_mode=send_mode,
        wa_allowed_test_recipients=parse_allowlist(
            os.environ.get("WA_ALLOWED_TEST_RECIPIENTS", "")
        ),
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        temporal_api_key=os.environ.get("TEMPORAL_API_KEY", ""),
    )


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Missing environment variable {name}")
    return value
