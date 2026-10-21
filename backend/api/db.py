"""The API's database handle: the shared PostgREST client configured from Settings."""

import httpx

from api.settings import Settings
from storage.postgrest import PostgrestClient, Row

__all__ = ["Database", "Row"]


class Database(PostgrestClient):
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(
            http,
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
        )
