# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""Sign-in, sign-out, and the profile summary for the delivered storefront. The token
never appears in a response: the browser keeps only the session id, and the host looks
the credential up by it."""

from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from demo_common.sessions import SESSION_HEADER, UnknownSessionError
from demo_common.storefront import StorefrontHost, StorefrontRecord

from .delivered_auth import AuthUnavailable, SignInFailed
from .delivered_backend import DeliveredStorefront

GUEST_NAME = "Guest"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False


class SessionSummary(BaseModel):
    session_id: str
    user_id: str
    signed_in: bool
    name: str
    tier: str | None = None
    country: str | None = None


def summary_of(record: StorefrontRecord, backend: DeliveredStorefront) -> SessionSummary:
    credential = backend.credentials.get(record.session_id)
    if credential is None:
        return SessionSummary(
            session_id=record.session_id, user_id=record.user_id, signed_in=False, name=GUEST_NAME
        )
    profile = credential.profile
    return SessionSummary(
        session_id=record.session_id,
        user_id=record.user_id,
        signed_in=True,
        name=profile.display_name,
        tier=profile.member_tier,
        country=profile.country,
    )


def register_session_routes(
    app: FastAPI, host: StorefrontHost, backend: DeliveredStorefront
) -> None:
    CurrentSession = host.CurrentSession

    @app.post("/api/session/login")
    async def login(
        request: LoginRequest,
        session_id: Annotated[str | None, Header(alias=SESSION_HEADER)] = None,
    ) -> SessionSummary:
        try:
            result, profile = await backend.sign_in(
                request.email, request.password, request.remember_me
            )
        except SignInFailed:
            raise HTTPException(status_code=401, detail="invalid_credentials") from None
        except AuthUnavailable:
            raise HTTPException(status_code=502, detail="auth_unavailable") from None
        record = _existing_record(host, session_id)
        user_id = f"dk:{profile.customer_id}"
        if record is None:
            record = host.sessions.start(user_id)
        else:
            record.user_id = user_id
            host.sessions.save(record)
        backend.attach(record.session_id, result, profile)
        return summary_of(record, backend)

    @app.post("/api/session/logout")
    async def logout(record: CurrentSession) -> SessionSummary:
        if backend.sign_out(record.session_id):
            record.pending_app_events.append(
                "Customer signed out; the session continues as a guest."
            )
            host.sessions.save(record)
        return summary_of(record, backend)

    @app.get("/api/session/me")
    async def me(record: CurrentSession) -> SessionSummary:
        return summary_of(record, backend)


def _existing_record(host: StorefrontHost, session_id: str | None) -> StorefrontRecord | None:
    if not session_id:
        return None
    try:
        return host.sessions.require(session_id)
    except UnknownSessionError:
        return None
