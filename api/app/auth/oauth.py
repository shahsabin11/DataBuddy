"""Google and Microsoft OAuth (OIDC) helpers."""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWK

from app.auth.claims import IdentityClaims
from app.config import Settings, get_settings
from app.logging import get_logger
from app.models.enums import OAuthProvider

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

MS_AUTH = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
MS_TOKEN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
MS_JWKS = "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"

logger = get_logger(__name__)


class OAuthError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def new_state() -> str:
    return secrets.token_urlsafe(32)


def _signing_key_from_jwks(jwks_url: str, id_token: str) -> Any:
    """
    Fetch JWKS with httpx (uses certifi) instead of PyJWKClient/urllib.

    macOS Python installs often lack system CAs, so urllib SSL verify fails
    while httpx still works — that was breaking Google ID token verification.
    """
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(jwks_url)
            resp.raise_for_status()
            jwks = resp.json()
    except Exception as exc:
        raise OAuthError(
            "jwks_fetch_failed",
            "Could not fetch identity provider signing keys.",
        ) from exc

    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    for key_data in jwks.get("keys", []):
        if kid is None or key_data.get("kid") == kid:
            return PyJWK.from_dict(key_data).key
    raise OAuthError("jwks_key_missing", "No matching signing key for ID token.")


def google_authorize_url(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH}?{urlencode(params)}"


def microsoft_authorize_url(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    tenant = settings.microsoft_tenant_id or "common"
    params = {
        "client_id": settings.microsoft_client_id,
        "redirect_uri": settings.microsoft_redirect_uri,
        "response_type": "code",
        "response_mode": "query",
        "scope": "openid email profile offline_access",
        "state": state,
        "prompt": "select_account",
    }
    return f"{MS_AUTH.format(tenant=tenant)}?{urlencode(params)}"


def exchange_google_code(code: str, settings: Settings | None = None) -> IdentityClaims:
    settings = settings or get_settings()
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        body = resp.json()
    id_token = body.get("id_token")
    if not id_token:
        raise OAuthError("no_id_token", "Google did not return an ID token.")
    return verify_google_id_token(id_token, settings=settings)


def exchange_microsoft_code(code: str, settings: Settings | None = None) -> IdentityClaims:
    settings = settings or get_settings()
    tenant = settings.microsoft_tenant_id or "common"
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            MS_TOKEN.format(tenant=tenant),
            data={
                "code": code,
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "redirect_uri": settings.microsoft_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        body = resp.json()
    id_token = body.get("id_token")
    if not id_token:
        raise OAuthError("no_id_token", "Microsoft did not return an ID token.")
    return verify_microsoft_id_token(id_token, settings=settings)


def verify_google_id_token(id_token: str, settings: Settings | None = None) -> IdentityClaims:
    settings = settings or get_settings()
    key = _signing_key_from_jwks(GOOGLE_JWKS, id_token)
    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=list(GOOGLE_ISSUERS),
            options={"require": ["sub", "email"]},
        )
    except jwt.PyJWTError as exc:
        raise OAuthError("invalid_id_token", "Google ID token failed verification.") from exc
    return _google_claims(claims)


def verify_microsoft_id_token(
    id_token: str, settings: Settings | None = None
) -> IdentityClaims:
    settings = settings or get_settings()
    # Decode unverified to learn tid, then verify against that tenant's JWKS.
    unverified = jwt.decode(id_token, options={"verify_signature": False})
    tid = unverified.get("tid")
    if not tid:
        raise OAuthError("missing_tid", "Microsoft token missing tenant id.")
    key = _signing_key_from_jwks(MS_JWKS.format(tenant=tid), id_token)
    issuer = f"https://login.microsoftonline.com/{tid}/v2.0"
    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.microsoft_client_id,
            issuer=issuer,
            options={"require": ["sub"]},
        )
    except jwt.PyJWTError as exc:
        raise OAuthError(
            "invalid_id_token", "Microsoft ID token failed verification."
        ) from exc
    return _microsoft_claims(claims)


def _google_claims(claims: dict[str, Any]) -> IdentityClaims:
    email = (claims.get("email") or "").strip().lower()
    verified = bool(claims.get("email_verified"))
    return IdentityClaims(
        provider=OAuthProvider.GOOGLE.value,
        subject=str(claims["sub"]),
        email=email,
        email_verified=verified,
        name=claims.get("name"),
        entra_tenant_id=None,
    )


def _microsoft_claims(claims: dict[str, Any]) -> IdentityClaims:
    email = (
        claims.get("email")
        or claims.get("preferred_username")
        or ""
    )
    email = str(email).strip().lower()
    # Microsoft consumer + work accounts: treat presence of email as verified
    # by the IdP unless xms_edov explicitly says otherwise.
    edov = claims.get("xms_edov")
    if edov is False or edov == "0":
        verified = False
    else:
        verified = bool(email)
    return IdentityClaims(
        provider=OAuthProvider.MICROSOFT.value,
        subject=str(claims.get("oid") or claims["sub"]),
        email=email,
        email_verified=verified,
        name=claims.get("name"),
        entra_tenant_id=str(claims.get("tid")) if claims.get("tid") else None,
    )
