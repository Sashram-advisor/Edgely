"""auth_provider.py - Verifies Supabase Auth access tokens.

The frontend signs users in with Supabase Auth and sends the access token in
the Authorization header (Authorization: Bearer <token>). This module checks
that token and returns who the user is.

It does not touch the database. Finding or creating the matching row in the
users table (users.external_auth_id == AuthenticatedUser.auth_id) comes later
in dependencies.py / user_service.py, once the models exist.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import settings  # settings.supabase_url, settings.supabase_jwt_secret

logger = logging.getLogger(__name__)

# Supabase access tokens for signed-in users carry this audience value.
_AUDIENCE = "authenticated"

# Projects using Supabase's newer signing keys sign with one of these.
_ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")

# auto_error=False lets us return a clean 401 ourselves when the header is missing.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Who is calling, according to a verified token."""

    auth_id: str  # Supabase user id. Stored as users.external_auth_id
    email: str | None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _issuer() -> str:
    """The expected token issuer, built from the Supabase project URL."""
    if not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth is not configured. Set SUPABASE_URL in .env",
        )
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def _jwks_client() -> PyJWKClient:
    """Fetches Supabase's public signing keys. The client caches them."""
    return PyJWKClient(f"{_issuer()}/.well-known/jwks.json")


def verify_token(token: str) -> AuthenticatedUser:
    """Check a Supabase access token and return the user it belongs to.

    Raises HTTP 401 if the token is malformed, expired, or not from this project.
    """
    issuer = _issuer()
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")

        if algorithm == "HS256":
            # Older Supabase projects sign with a shared secret.
            if not settings.supabase_jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Auth is not configured. Set SUPABASE_JWT_SECRET in .env",
                )
            key = settings.supabase_jwt_secret
        elif algorithm in _ASYMMETRIC_ALGORITHMS:
            key = _jwks_client().get_signing_key_from_jwt(token).key
        else:
            raise _unauthorized()

        claims = jwt.decode(
            token,
            key,
            algorithms=[algorithm],  # only the one algorithm that matched its key source
            audience=_AUDIENCE,
            issuer=issuer,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        # Log the reason (never the token itself). The client only sees a generic 401.
        logger.warning("Token verification failed: %s", exc)
        raise _unauthorized() from exc

    return AuthenticatedUser(auth_id=claims["sub"], email=claims.get("email"))


def get_current_auth_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    """FastAPI dependency: the verified user for this request.

    Usage:
        @router.get("/users/me")
        def me(user: AuthenticatedUser = Depends(get_current_auth_user)):
            ...
    """
    if credentials is None:
        raise _unauthorized()
    return verify_token(credentials.credentials)