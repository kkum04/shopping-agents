# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The sign-in routes and the sign-in gate on the cart, through the app (L2): the host is
assembled the way ``main.py`` does it, with both gateways on ``MockTransport`` and no
startup warm-up, so nothing reaches the network. The sign-in success shape is the
customer frontend's assumption; the failure shapes were probed on staging (2026-09-11).
"""

import asyncio
import logging

import httpx
import pytest
from anthropic import AsyncAnthropic
from fastapi.testclient import TestClient

from commerce_common.memory import InMemoryMemoryStore
from delivered.api.agent_config import build_shopping_config
from delivered.api.delivered_auth import CredentialStore, DeliveredAuthClient, TokenExpired
from delivered.api.delivered_backend import DATA_DIR, DeliveredClient, DeliveredStorefront
from delivered.api.delivered_executor import DeliveredToolExecutor
from delivered.api.session_routes import register_session_routes
from delivered.api.tests.test_delivered_auth import ACCESS, PASSWORD, REFRESH, FakeAuthGateway
from delivered.api.tests.test_delivered_backend import FakeGateway
from demo_common import REPO_ROOT, CartAddRequest, MemorySeeder, build_storefront_host
from demo_common.sessions import SESSION_HEADER
from shopping_agent_runtime import ShoppingAgent

SECRETS = (ACCESS, REFRESH, PASSWORD)


class Harness:
    def __init__(self) -> None:
        self.auth_gateway = FakeAuthGateway()
        self.catalog_gateway = FakeGateway()
        auth = DeliveredAuthClient(
            "https://auth.test",
            "https://customer.test/api/customer",
            transport=httpx.MockTransport(self.auth_gateway.handler),
        )
        catalog = DeliveredClient(
            "https://gateway.test/v1", transport=httpx.MockTransport(self.catalog_gateway.handler)
        )
        self.backend = DeliveredStorefront(catalog, auth=auth, credentials=CredentialStore())
        agent = ShoppingAgent(
            backend=self.backend,
            skills_dir=REPO_ROOT / "shopping-agent" / "skills",
            config=build_shopping_config(),
            memory_store=InMemoryMemoryStore(),
            client=AsyncAnthropic(api_key="test-key"),
            executor_class=DeliveredToolExecutor,
        )
        self.host = build_storefront_host(
            title="delivered test API",
            example_root=DATA_DIR.parent,
            backend=self.backend,
            agent=agent,
            memory_seeder=MemorySeeder(DATA_DIR / "memory-seed.json"),
        )
        register_session_routes(self.host.app, self.host, self.backend)
        host = self.host

        @host.app.post("/api/cart/add")
        async def cart_add(request: CartAddRequest, record: host.CurrentSession) -> dict:
            return await host.direct_add(record, request, note="Customer tapped add on {title}.")


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.fixture
def client(harness: Harness):
    with TestClient(harness.host.app, base_url="http://localhost") as client:
        yield client


def start_guest(client: TestClient) -> str:
    return client.post("/api/session").json()["session_id"]


def headers(session_id: str) -> dict[str, str]:
    return {SESSION_HEADER: session_id}


LOGIN = {"email": "ken@example.test", "password": PASSWORD}


def assert_no_secrets(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text


# -- T006: routes -----------------------------------------------------------------


def test_login_without_a_session_starts_a_signed_in_session(client, harness):
    response = client.post("/api/session/login", json=LOGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["signed_in"] is True
    assert body["name"] == "Ken Park" and body["tier"] == "GOLD" and body["country"] == "US"
    assert body["user_id"] == "dk:77"
    assert harness.backend.credentials.get(body["session_id"]) is not None
    assert_no_secrets(response.text)


def test_login_with_a_session_attaches_to_the_same_session(client, harness):
    session_id = start_guest(client)
    record = harness.host.sessions.require(session_id)
    record.messages.append({"role": "user", "content": "줄넘기 찾아줘"})
    harness.host.sessions.save(record)

    response = client.post("/api/session/login", json=LOGIN, headers=headers(session_id))
    body = response.json()
    assert body["session_id"] == session_id
    assert body["user_id"] == "dk:77"
    record = harness.host.sessions.require(session_id)
    assert record.user_id == "dk:77"
    assert record.messages[0]["content"] == "줄넘기 찾아줘"
    assert_no_secrets(response.text)


def test_login_with_an_unknown_session_id_starts_a_new_session(client, harness):
    response = client.post("/api/session/login", json=LOGIN, headers=headers("no-such-session"))
    assert response.status_code == 200
    assert response.json()["session_id"] != "no-such-session"


def test_wrong_credentials_answer_401_and_keep_the_session_a_guest(client, harness):
    harness.auth_gateway.sign_in_status = 404
    session_id = start_guest(client)
    response = client.post("/api/session/login", json=LOGIN, headers=headers(session_id))
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_credentials"
    assert harness.backend.credentials.get(session_id) is None
    assert harness.host.sessions.require(session_id).user_id == "demo-user"


@pytest.mark.parametrize("failure", ["gateway", "profile"])
def test_a_failing_gateway_or_profile_answers_502_without_a_token(client, harness, failure):
    if failure == "gateway":
        harness.auth_gateway.sign_in_status = 503
    else:
        harness.auth_gateway.me_status = 503
    response = client.post("/api/session/login", json=LOGIN)
    assert response.status_code == 502
    assert response.json()["detail"] == "auth_unavailable"
    assert len(harness.backend.credentials) == 0


def test_me_reports_guest_then_signed_in_then_guest_after_logout(client, harness):
    session_id = start_guest(client)
    assert client.get("/api/session/me", headers=headers(session_id)).json() == {
        "session_id": session_id,
        "user_id": "demo-user",
        "signed_in": False,
        "name": "Guest",
        "tier": None,
        "country": None,
    }
    client.post("/api/session/login", json=LOGIN, headers=headers(session_id))
    me = client.get("/api/session/me", headers=headers(session_id)).json()
    assert me["signed_in"] is True and me["name"] == "Ken Park"

    out = client.post("/api/session/logout", headers=headers(session_id))
    assert out.status_code == 200
    assert out.json()["session_id"] == session_id
    assert out.json()["signed_in"] is False and out.json()["name"] == "Guest"
    assert harness.backend.credentials.get(session_id) is None
    record = harness.host.sessions.require(session_id)
    assert any("signed out" in event for event in record.pending_app_events)


def test_login_requires_a_body(client):
    assert client.post("/api/session/login", json={"email": "x@y.z"}).status_code == 422


def test_no_secret_reaches_the_info_log(client, harness, caplog):
    caplog.set_level(logging.INFO)
    session_id = start_guest(client)
    client.post("/api/session/login", json=LOGIN, headers=headers(session_id))
    client.get("/api/session/me", headers=headers(session_id))
    harness.auth_gateway.expired_paths.add("/api/customer/v3/cart")
    session = session_context(harness, session_id)
    with pytest.raises(TokenExpired):
        asyncio.run(harness.backend.customer_call(session, "GET", "/v3/cart", feature="장바구니"))
    assert_no_secrets(caplog.text)


# -- T009 (route side): the sign-in gate through the button route ------------------


def test_a_guest_add_to_cart_button_gets_the_sign_in_guidance(client, harness):
    session_id = start_guest(client)
    asyncio.run(harness.backend.search_products(session_context(harness, session_id), "bts"))
    record = harness.host.sessions.require(session_id)
    record.state.remember_products([harness.backend.product("smart_store:10791906854")])
    harness.host.sessions.save(record)

    response = client.post(
        "/api/cart/add",
        json={"product_id": "smart_store:10791906854", "quantity": 1},
        headers=headers(session_id),
    )
    assert response.status_code == 400
    assert "로그인이 필요합니다" in response.json()["detail"]
    assert (client.get("/api/cart", headers=headers(session_id)).json().get("cart") or {}).get(
        "items", []
    ) == []


def session_context(harness: Harness, session_id: str):
    return harness.host.context(harness.host.sessions.require(session_id))
