# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The delivered sign-in client, the credential store, and the backend's use of them.
``FakeAuthGateway`` plays the auth gateway and the customer API over ``MockTransport``;
nothing here reaches the network. Failure shapes follow the staging gateway as probed
on 2026-09-11 (404 ``NOT_FOUND_USER`` for unknown credentials, 401 without a token); the
success shapes follow the customer frontend's types and are still assumptions.
"""

from __future__ import annotations

import json

import httpx
import pytest

from delivered.api.delivered_auth import (
    AuthUnavailable,
    CredentialStore,
    CustomerProfile,
    DeliveredApiError,
    DeliveredAuthClient,
    SessionCredential,
    SignInFailed,
    SignInResult,
    TokenExpired,
)

ACCESS = "access-token-SECRET-1"
REFRESH = "refresh-token-SECRET-2"
PASSWORD = "hunter2-SECRET"
ME = {
    "customerId": 77,
    "customerEmail": "ken@example.test",
    "firstName": "Ken",
    "lastName": "Park",
    "country": "US",
    "memberTier": "GOLD",
}


class FakeAuthGateway:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.sign_in_status = 200
        self.me_status = 200
        self.me_body: dict | None = None
        self.expired_paths: set[str] = set()
        self.raise_transport = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.raise_transport:
            raise httpx.ConnectError("boom", request=request)
        path = request.url.path
        if path.endswith("/auth/sign-in/dk-service/customer"):
            if self.sign_in_status == 404:
                return httpx.Response(
                    404, json={"httpStatus": "NOT_FOUND", "message": "NOT_FOUND_USER"}
                )
            if self.sign_in_status != 200:
                return httpx.Response(self.sign_in_status, text="<html>gateway error</html>")
            return httpx.Response(
                200,
                json={
                    "id": 77,
                    "role": "CUSTOMER",
                    "service": "dk-service",
                    "userId": 77,
                    "userName": "Ken Park",
                    "accessToken": ACCESS,
                    "refreshToken": REFRESH,
                    "refreshTokenExpiredAt": "2026-10-11T00:00:00",
                },
            )
        if path in self.expired_paths:
            return httpx.Response(
                401, json={"httpStatus": "UNAUTHORIZED", "message": "Expired Token"}
            )
        if path.endswith("/v2/me"):
            if request.headers.get("Authorization") != f"Bearer {ACCESS}":
                return httpx.Response(
                    401,
                    json={"httpStatus": "UNAUTHORIZED", "message": "Authorization Key not found"},
                )
            if self.me_status != 200:
                return httpx.Response(self.me_status, json={"message": "boom"})
            return httpx.Response(
                200, json={"result": True, "data": self.me_body or ME, "message": None}
            )
        if path.endswith("/v3/cart"):
            return httpx.Response(200, json={"result": True, "data": {"orders": []}})
        return httpx.Response(404, json={"message": "no route"})


@pytest.fixture
def gateway() -> FakeAuthGateway:
    return FakeAuthGateway()


@pytest.fixture
def auth(gateway: FakeAuthGateway) -> DeliveredAuthClient:
    return DeliveredAuthClient(
        "https://auth.test",
        "https://customer.test/api/customer",
        transport=httpx.MockTransport(gateway.handler),
    )


# -- T002: sign-in client ----------------------------------------------------------


async def test_sign_in_returns_tokens_and_sends_the_frontends_body(auth, gateway):
    result = await auth.sign_in("ken@example.test", PASSWORD, remember_me=True)
    assert result.access_token == ACCESS
    assert result.refresh_token == REFRESH
    assert result.user_id == "77"
    request = gateway.calls[0]
    assert request.url.path == "/auth/sign-in/dk-service/customer"
    assert request.url.params["isRememberMe"] == "true"
    body = json.loads(request.content)
    assert body == {
        "email": "ken@example.test",
        "password": PASSWORD,
        "ipAddress": "",
        "country": "",
        "isRememberMe": True,
    }


@pytest.mark.parametrize("status", [401, 404])
async def test_wrong_credentials_are_a_sign_in_failure(auth, gateway, status):
    gateway.sign_in_status = status
    with pytest.raises(SignInFailed) as raised:
        await auth.sign_in("ken@example.test", PASSWORD)
    assert PASSWORD not in str(raised.value)
    assert "example.test" not in str(raised.value)


@pytest.mark.parametrize("status", [500, 502, 503])
async def test_a_gateway_failure_is_unavailable_not_a_sign_in_failure(auth, gateway, status):
    gateway.sign_in_status = status
    with pytest.raises(AuthUnavailable):
        await auth.sign_in("ken@example.test", PASSWORD)


async def test_a_transport_error_is_unavailable(auth, gateway):
    gateway.raise_transport = True
    with pytest.raises(AuthUnavailable):
        await auth.sign_in("ken@example.test", PASSWORD)


async def test_a_200_without_a_token_is_unavailable(gateway):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"userId": 1})

    auth = DeliveredAuthClient(
        "https://auth.test", "https://c.test", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(AuthUnavailable):
        await auth.sign_in("a@b.c", "x")


async def test_get_me_sends_the_bearer_header(auth, gateway):
    me = await auth.get_me(ACCESS)
    assert me["data"]["firstName"] == "Ken"
    assert gateway.calls[-1].headers["Authorization"] == f"Bearer {ACCESS}"
    assert gateway.calls[-1].url.path == "/api/customer/v2/me"


@pytest.mark.parametrize("status", [200, 401])
async def test_an_expired_token_message_raises_regardless_of_status(gateway, status):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "Expired Token"})

    auth = DeliveredAuthClient(
        "https://auth.test", "https://c.test", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(TokenExpired):
        await auth.customer_request("GET", "/v3/cart", ACCESS)


async def test_a_customer_api_5xx_is_a_delivered_api_error(auth, gateway):
    gateway.me_status = 503
    with pytest.raises(DeliveredApiError) as raised:
        await auth.get_me(ACCESS)
    assert ACCESS not in str(raised.value)


def test_the_profile_reads_the_enveloped_and_the_flat_shape():
    enveloped = CustomerProfile.from_me({"result": True, "data": ME})
    flat = CustomerProfile.from_me(ME)
    assert enveloped == flat
    assert enveloped.customer_id == "77" and enveloped.member_tier == "GOLD"
    nameless = CustomerProfile.from_me(
        {"result": True, "data": {**ME, "firstName": None, "lastName": None}},
        fallback_name="A0020",
    )
    assert nameless.display_name == "A0020"
    assert CustomerProfile.from_me({"data": {}}).display_name == "delivered customer"


def test_credentials_do_not_leak_through_repr():
    profile = CustomerProfile.from_me(ME)
    credential = SessionCredential(ACCESS, REFRESH, "77", profile)
    assert ACCESS not in repr(credential) and REFRESH not in repr(credential)
    assert "77" in repr(credential)
    assert ACCESS not in repr(SignInResult(ACCESS, REFRESH, "77"))
    assert profile.display_name == "Ken Park"
    assert profile.member_tier == "GOLD" and profile.country == "US"


def test_credential_store_put_get_drop():
    store = CredentialStore()
    credential = SessionCredential(ACCESS, None, "77", CustomerProfile.from_me(ME))
    assert store.get("s-1") is None
    store.put("s-1", credential)
    assert store.get("s-1") is credential and len(store) == 1
    assert store.drop("s-1") is True
    assert store.drop("s-1") is False
    assert store.get("s-1") is None


# -- T004 / T009: the backend over the credential store ------------------------------

from delivered.api.delivered_auth import SignInRequired  # noqa: E402
from delivered.api.delivered_backend import DeliveredClient, DeliveredStorefront  # noqa: E402
from delivered.api.tests.test_delivered_backend import FakeGateway  # noqa: E402
from shopping_agent import ShoppingSessionContext  # noqa: E402


def session(session_id: str = "s-1") -> ShoppingSessionContext:
    return ShoppingSessionContext(session_id=session_id, user_id="demo-user")


@pytest.fixture
def backend(auth: DeliveredAuthClient) -> DeliveredStorefront:
    catalog = DeliveredClient(
        "https://gateway.test/v1", transport=httpx.MockTransport(FakeGateway().handler)
    )
    return DeliveredStorefront(catalog, auth=auth, credentials=CredentialStore())


def signed_in(backend: DeliveredStorefront, session_id: str = "s-1") -> SessionCredential:
    credential = SessionCredential(ACCESS, REFRESH, "77", CustomerProfile.from_me(ME))
    backend.credentials.put(session_id, credential)
    return credential


async def test_preferences_and_account_context_follow_the_credential(backend):
    guest = await backend.get_preferences(session())
    assert guest.display_name == "Guest" and guest.loyalty_tier is None
    guest_context = await backend.get_account_context(session())
    assert guest_context["signed_in"] is False and "sign in" in guest_context["note"]

    signed_in(backend)
    prefs = await backend.get_preferences(session())
    assert prefs.display_name == "Ken Park"
    assert prefs.loyalty_tier == "GOLD" and prefs.default_location == "US"
    context = await backend.get_account_context(session())
    assert context == {"signed_in": True, "member_tier": "GOLD", "country": "US"}
    assert ACCESS not in str(prefs) and ACCESS not in str(context)


async def test_sign_in_reads_the_profile_and_attach_stores_the_credential(backend, gateway):
    result, profile = await backend.sign_in("ken@example.test", PASSWORD)
    assert profile.display_name == "Ken Park" and profile.customer_id == "77"
    assert backend.credential_of(session()) is None
    backend.attach("s-1", result, profile)
    assert backend.credential_of(session()).customer_id == "77"
    assert backend.sign_out("s-1") is True
    assert backend.credential_of(session()) is None


async def test_sign_in_fails_as_unavailable_when_the_profile_call_fails(backend, gateway):
    gateway.me_status = 503
    with pytest.raises(AuthUnavailable):
        await backend.sign_in("ken@example.test", PASSWORD)
    assert len(backend.credentials) == 0


async def test_customer_call_sends_bearer_and_drops_an_expired_credential(backend, gateway):
    signed_in(backend)
    body = await backend.customer_call(session(), "GET", "/v3/cart", feature="장바구니")
    assert body["result"] is True
    assert gateway.calls[-1].headers["Authorization"] == f"Bearer {ACCESS}"

    gateway.expired_paths.add("/api/customer/v3/cart")
    with pytest.raises(TokenExpired):
        await backend.customer_call(session(), "GET", "/v3/cart", feature="장바구니")
    assert backend.credential_of(session()) is None
    with pytest.raises(SignInRequired):
        await backend.customer_call(session(), "GET", "/v3/cart", feature="장바구니")


async def test_a_guest_cannot_write_the_cart_and_sees_an_empty_one(backend):
    await backend.search_products(session(), "bts")
    for call in (
        backend.add_to_cart(session(), "smart_store:10791906854", 1),
        backend.update_cart_item(session(), "smart_store:10791906854", 2),
        backend.remove_from_cart(session(), "smart_store:10791906854"),
    ):
        with pytest.raises(SignInRequired) as raised:
            await call
        assert "장바구니" in str(raised.value)
    assert (await backend.get_cart(session())).items == []

    signed_in(backend)
    cart = await backend.add_to_cart(session(), "smart_store:10791906854", 1)
    assert cart.items[0].quantity == 1 and cart.currency == "KRW"
    backend.reset_session("s-1")
    assert backend.credential_of(session()) is None


async def test_the_executor_turns_sign_in_errors_into_guidance():
    from delivered.api.delivered_executor import DeliveredToolExecutor

    executor = object.__new__(DeliveredToolExecutor)
    from shopping_agent.fencing import STOREFRONT_FENCE

    executor.fence = STOREFRONT_FENCE
    outcome = executor.domain_error(SignInRequired("장바구니"))
    assert outcome is not None and outcome.is_error
    assert "로그인이 필요합니다" in outcome.result_text and "장바구니" in outcome.result_text
    expired = executor.domain_error(TokenExpired("GET /v3/cart: token expired"))
    assert expired is not None and "다시 로그인" in expired.result_text
    assert ACCESS not in expired.result_text
