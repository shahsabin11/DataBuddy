"""Normalized identity claims from Google / Microsoft ID tokens."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IdentityClaims:
    provider: str  # google | microsoft
    subject: str
    email: str
    email_verified: bool
    name: str | None = None
    # Microsoft Entra tenant id (tid). None for Google.
    entra_tenant_id: str | None = None


def email_domain(email: str) -> str:
    """Exact domain used for institution_domains lookup (lowercase)."""
    return email.rsplit("@", 1)[-1].strip().lower()
