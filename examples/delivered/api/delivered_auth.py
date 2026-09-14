# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""delivered sign-in and customer API access for the delivered example. The auth gateway
issues the tokens; ``CredentialStore`` keeps them beside the session, keyed by session
id, outside the session's state document; ``DeliveredAuthClient`` is the one place that
puts a token on a request. Nothing here logs a token, a password, or a response body.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_AUTH_BASE_URL = "https://gw-staging.delivered.co.kr"
DEFAULT_CUSTOMER_BASE_URL = "https://gw-staging.delivered.co.kr/dk-delivered/api/customer"
SIGN_IN_PATH = "/auth/sign-in/dk-service/customer"
ME_PATH = "/v2/me"
EXPIRED_TOKEN_MESSAGE = "Expired Token"
REDACTED = "<redacted>"


class DeliveredApiError(Exception):
    """A delivered call that did not complete: transport failure, 5xx, or a body that is
    not JSON. The message names the method, path, and status only."""


class SignInFailed(Exception):
    """The gateway rejected the credentials (401 or 404)."""


class AuthUnavailable(Exception):
    """The gateway or the profile call could not complete, so no session was signed in."""


class SignInRequired(Exception):
    """A guest session asked for something that needs a delivered account. The message
    names the feature only."""


class TokenExpired(Exception):
    """The customer API reported the session's token as expired; the session continues
    as a guest."""


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: str
    display_name: str
    country: str | None = None
    member_tier: str | None = None
    email: str | None = None

    @classmethod
    def from_me(cls, payload: dict[str, Any], fallback_name: str | None = None) -> CustomerProfile:
        """``/v2/me`` answers ``{"result": true, "data": {...}}`` on the gateway (probed
        on staging, 2026-09-14); a flat object is accepted too. A profile without a name
        falls back to ``fallback_name`` (the sign-in response's userName)."""
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        first = str(data.get("firstName") or "").strip()
        last = str(data.get("lastName") or "").strip()
        display = (
            " ".join(part for part in (first, last) if part)
            or (fallback_name or "").strip()
            or "delivered customer"
        )
        payload = data
        return cls(
            customer_id=str(payload.get("customerId") or ""),
            display_name=display,
            country=payload.get("country") or None,
            member_tier=payload.get("memberTier") or None,
            email=payload.get("customerEmail") or None,
        )


@dataclass(repr=False)
class SignInResult:
    access_token: str
    refresh_token: str | None
    user_id: str
    user_name: str | None = None

    def __repr__(self) -> str:
        return f"SignInResult(user_id={self.user_id!r}, tokens={REDACTED})"


@dataclass(repr=False)
class SessionCredential:
    access_token: str
    refresh_token: str | None
    customer_id: str
    profile: CustomerProfile
    signed_in_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"SessionCredential(customer_id={self.customer_id!r}, tokens={REDACTED})"


class CredentialStore:
    """Per-process map from session id to the credential the host holds for it."""

    def __init__(self) -> None:
        self._by_session: dict[str, SessionCredential] = {}

    def get(self, session_id: str) -> SessionCredential | None:
        return self._by_session.get(session_id)

    def put(self, session_id: str, credential: SessionCredential) -> None:
        self._by_session[session_id] = credential

    def drop(self, session_id: str) -> bool:
        return self._by_session.pop(session_id, None) is not None

    def __len__(self) -> int:
        return len(self._by_session)


class DeliveredAuthClient:
    """The sign-in call on the auth gateway and Bearer calls on the customer API."""

    def __init__(
        self,
        auth_base_url: str | None = None,
        customer_base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        self.auth_base_url = (
            auth_base_url or os.environ.get("DELIVERED_AUTH_URL") or DEFAULT_AUTH_BASE_URL
        ).rstrip("/")
        self.customer_base_url = (
            customer_base_url
            or os.environ.get("DELIVERED_CUSTOMER_API_URL")
            or DEFAULT_CUSTOMER_BASE_URL
        ).rstrip("/")
        self._client = httpx.AsyncClient(
            transport=transport, timeout=timeout_s, headers={"Accept": "application/json"}
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def sign_in(self, email: str, password: str, remember_me: bool = False) -> SignInResult:
        url = f"{self.auth_base_url}{SIGN_IN_PATH}"
        body = {
            "email": email,
            "password": password,
            "ipAddress": "",
            "country": "",
            "isRememberMe": remember_me,
        }
        try:
            response = await self._client.post(
                url, json=body, params={"isRememberMe": str(remember_me).lower()}
            )
        except httpx.HTTPError as error:
            raise AuthUnavailable(f"POST {SIGN_IN_PATH}: {type(error).__name__}") from error
        logger.info("delivered sign-in status=%s", response.status_code)
        if response.status_code in (401, 404):
            raise SignInFailed(f"POST {SIGN_IN_PATH}: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise AuthUnavailable(f"POST {SIGN_IN_PATH}: HTTP {response.status_code}")
        payload = _json_object(response)
        token = payload.get("accessToken") if payload else None
        if not payload or not isinstance(token, str) or not token:
            raise AuthUnavailable(f"POST {SIGN_IN_PATH}: no access token in response")
        return SignInResult(
            access_token=token,
            refresh_token=payload.get("refreshToken") or None,
            user_id=str(payload.get("userId") or payload.get("id") or ""),
            user_name=payload.get("userName") or None,
        )

    async def get_me(self, access_token: str) -> dict[str, Any]:
        return await self.customer_request("GET", ME_PATH, access_token)

    async def customer_request(
        self, method: str, path: str, access_token: str, **kwargs: Any
    ) -> dict[str, Any]:
        url = f"{self.customer_base_url}{path}"
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {access_token}"
        try:
            response = await self._client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as error:
            raise DeliveredApiError(f"{method} {path}: {type(error).__name__}") from error
        logger.info("delivered customer api %s %s status=%s", method, path, response.status_code)
        payload = _json_object(response)
        if payload is not None and payload.get("message") == EXPIRED_TOKEN_MESSAGE:
            raise TokenExpired(f"{method} {path}: token expired")
        if response.status_code >= 500 or payload is None:
            raise DeliveredApiError(f"{method} {path}: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise DeliveredApiError(f"{method} {path}: HTTP {response.status_code}")
        return payload


def _json_object(response: httpx.Response) -> dict[str, Any] | None:
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None
