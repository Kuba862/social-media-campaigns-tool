"""Who is calling? Supabase auth checks the token, we check the domain"""

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.settings import Settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str


async def verify_token(
    client: httpx.AsyncClient, settings: Settings, token: str
) -> AuthUser | None:
    """Ask Supabase Auth who owns this token. None means: not a valid token."""
    try:
        response = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {token}",
            },
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "auth service unavailable"
        ) from exc
    if response.status_code != 200:
        return None
    data = response.json()
    return AuthUser(id=str(data["id"]), email=str(data.get("email") or "").lower())


async def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    settings: Settings = request.app.state.settings
    user = await verify_token(request.app.state.http, settings, credentials.credentials)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    if user.email.rsplit("@", 1)[-1] != settings.panel_allowed_email_domain:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "e-mail domain not allowed")
    return user


CurrentUser = Annotated[AuthUser, Depends(current_user)]
