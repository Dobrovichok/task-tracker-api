from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.config import get_auth_settings
from app.database import DbSession
from app.models import User
from app.schemas import AccessToken


ALGORITHM = "HS256"
ISSUER = "task-tracker"
AUDIENCE = "task-tracker-api"
password_hasher = PasswordHash.recommended()
dummy_password_hash = password_hasher.hash(token_urlsafe(32))
bearer = HTTPBearer(auto_error=False, bearerFormat="JWT")


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def issue_access_token(user: User) -> AccessToken:
    settings = get_auth_settings()
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    token = jwt.encode(
        {"sub": str(user.id), "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + lifetime},
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )
    return AccessToken(access_token=token, expires_in=int(lifetime.total_seconds()))


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise unauthorized("Bearer token required")

    settings = get_auth_settings()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["sub", "iss", "aud", "iat", "exp"]},
        )
        user_id = UUID(claims["sub"])
    except (InvalidTokenError, ValueError):
        raise unauthorized("Invalid or expired token") from None

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized("Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
