"""FastAPI dependencies for service-session authentication."""

from typing import cast

from fastapi import Cookie, HTTPException, Request, status

from meta_api.repositories.auth import AuthRepository


def repository(request: Request) -> AuthRepository:
    return cast(AuthRepository, request.app.state.auth_repository)


async def authenticated_session(
    request: Request,
    authorization: str | None = None,
    meta_session: str | None = Cookie(default=None),
) -> str:
    """Accept the opaque service session cookie or a bearer session credential."""
    credential = meta_session
    header = request.headers.get("Authorization")
    if header and header.lower().startswith("bearer "):
        credential = header[7:].strip()
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session = await repository(request).get_session(credential)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credential
