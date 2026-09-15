# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The delivered backend over recorded guest API responses; nothing here reaches the
network. ``fixtures/`` holds trimmed copies of real responses."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest

from delivered.api.delivered_backend import (
    SUPPORTED_SHOP_TYPES,
    DeliveredApiError,
    DeliveredClient,
    DeliveredStorefront,
    detail_to_product_details,
    interleave_by_market,
    list_response_to_products,
    product_id_of,
    query_variants,
    search_response_to_products,
    split_product_id,
)
from shopping_agent import Cart, SearchFilters, ShoppingSessionContext, Unavailable

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def session() -> ShoppingSessionContext:
    return ShoppingSessionContext(session_id="s-1", user_id="demo-user")


class FakeGateway:
    """The three routes over the fixtures, with the quirks the real gateway has."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.search_status = 200
        self.list_status = 200
        self.detail_status = 200
        self.options_status = 200
        self.sold_out_option_ids: set[int] = set()
        # Without ``shop_types`` the real search accepts known keywords only (뉴진스 yes,
        # 뉴진스 굿즈 no); with the supported types listed it answers any keyword, and it
        # rejects a list that names an unsupported type.
        self.supported_queries = {"bts"}
        self.honor_shop_types = True
        self.empty_for: set[str] = set()  # accepted queries that come back with no products

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        path = request.url.path
        if path.endswith("/search-products"):
            body = json.loads(request.content)
            if body["size"] < 20:
                return httpx.Response(404, json={"code": "SP-001", "result": False})
            shop_types = body.get("shop_types")
            if shop_types is not None and not set(shop_types) <= set(SUPPORTED_SHOP_TYPES):
                return httpx.Response(
                    400,
                    json={
                        "code": "400",
                        "result": False,
                        "message": "The specified shop type is not supported.",
                    },
                )
            explicit = bool(shop_types) and self.honor_shop_types
            if body["query"] in self.empty_for:
                return httpx.Response(200, json={"result": True, "data": {"products": []}})
            if not explicit and body["query"] not in self.supported_queries:
                return httpx.Response(400, json={"code": "NOT_SUPPORT_MARKETS", "result": False})
            if self.search_status != 200:
                return httpx.Response(self.search_status, json={"result": False})
            return httpx.Response(200, json=fixture("search-products.json"))
        if path.endswith("/buy-request/stores/smartstore"):
            if self.list_status != 200:
                return httpx.Response(self.list_status, json={"result": False})
            return httpx.Response(200, json=fixture("smartstore-list.json"))
        if path.endswith("/option-groups") or path.endswith("/options"):
            if self.options_status != 200:
                return httpx.Response(self.options_status, json={"result": False})
            pid = path.rsplit("/", 2)[1]
            name = (
                "smartstore-option-groups.json"
                if path.endswith("/option-groups")
                else "smartstore-options.json"
            )
            recorded = fixture(name).get(pid)
            if recorded and path.endswith("/options") and self.sold_out_option_ids:
                recorded = {
                    **recorded,
                    "data": [
                        {**row, "stockQuantity": 0}
                        if row["optionId"] in self.sold_out_option_ids
                        else row
                        for row in recorded["data"]
                    ],
                }
            return httpx.Response(
                200, json=recorded or {"result": True, "data": [], "message": None}
            )
        if "/buy-request/stores/smartstore/" in path:
            if self.detail_status != 200:
                return httpx.Response(self.detail_status, json={"result": False})
            pid = path.rsplit("/", 1)[1]
            if (FIXTURES / f"smartstore-detail-{pid}.json").exists():
                return httpx.Response(200, json=fixture(f"smartstore-detail-{pid}.json"))
            return httpx.Response(200, json=fixture("smartstore-detail.json"))
        return httpx.Response(404, json={"result": False})


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def backend(gateway: FakeGateway) -> DeliveredStorefront:
    client = DeliveredClient(
        "https://gateway.test/v1", transport=httpx.MockTransport(gateway.handler)
    )
    return DeliveredStorefront(client)


# -- Mapping ------------------------------------------------------------------


def test_ids_are_namespaced_by_market():
    assert product_id_of("SMART_STORE", "10791906854") == "smart_store:10791906854"
    assert split_product_id("bunjang:429925416") == ("BUNJANG", "429925416")


def test_search_records_carry_krw_prices_market_and_a_usable_image():
    records = search_response_to_products(fixture("search-products.json"))
    assert len(records) == 6
    first = records[0]
    assert first.product_id.startswith("bunjang:")
    assert first.currency == "KRW"
    assert first.price == 39500
    assert first.attributes["market"] == "번개장터"
    assert first.attributes["condition"] == "새상품"
    assert first.attributes["domestic_shipping_krw"] == "4,500"
    assert "{cnt}" not in (first.image_url or "")
    assert first.in_stock is True


def test_list_records_use_the_discounted_price_and_flag_the_discount():
    records = list_response_to_products(fixture("smartstore-list.json"))
    first = records[0]
    assert first.product_id == "smart_store:10791906854"
    assert first.price == 4000
    assert first.attributes["list_price_krw"] == "6,000"
    assert "할인" in first.labels
    assert first.short_description == "jump rope string collection wire pvc thread"
    assert first.specs["판매 페이지"].startswith("https://smartstore.naver.com/")


def test_detail_adds_stock_shipping_and_export_facts():
    detail = detail_to_product_details(fixture("smartstore-detail.json"))
    assert detail is not None
    assert detail.specs["재고 수량"] == "28918"
    assert detail.specs["국내 배송비"] == "3,126원"
    assert detail.specs["해외 배송"] == "가능 (delivered 해외배송)"
    assert detail.attributes["international_shipping"] == "가능 (delivered 해외배송)"


def test_a_sellers_export_flag_does_not_change_shipping():
    payload = fixture("smartstore-detail.json")
    payload["data"]["isProhibitedExport"] = True
    payload["data"]["prohibitedExportReason"] = "배터리 포함"
    detail = detail_to_product_details(payload)
    assert detail is not None
    assert detail.specs["해외 배송"] == "가능 (delivered 해외배송)"
    assert "해외 배송 불가" not in detail.labels


def test_a_failed_envelope_maps_to_nothing():
    assert search_response_to_products({"result": False, "code": "NOT_SUPPORT_MARKETS"}) == []
    assert list_response_to_products({"result": False}) == []
    assert detail_to_product_details({"result": False}) is None


# -- Backend --------------------------------------------------------------------


def test_interleave_shows_every_market_on_the_first_page():
    records = search_response_to_products(fixture("search-products.json")) + (
        list_response_to_products(fixture("smartstore-list.json"))
    )
    ordered = interleave_by_market(records)
    assert [r.category for r in ordered[:3]] == ["bunjang", "poca_market", "smart_store"]
    assert [r.product_id for r in ordered if r.category == "bunjang"] == [
        r.product_id for r in records if r.category == "bunjang"
    ]
    assert len(ordered) == len(records)


async def test_search_merges_both_sources_across_markets(backend, gateway):
    results = await backend.search_products(session(), "bts", limit=12)
    assert gateway.calls[:2] == [
        "POST /v1/search-products",
        "GET /v1/buy-request/stores/smartstore",
    ]
    assert results[0].product_id.startswith("bunjang:")
    assert {r.category for r in results[:3]} == {"bunjang", "poca_market", "smart_store"}
    assert len(results) == 8
    assert all(r.currency == "KRW" for r in results)


@pytest.mark.parametrize("keyword", ["줄넘기", "화장품", "나이키", "삼성 이어폰", "jump rope"])
async def test_a_generic_keyword_searches_every_market_with_shop_types(backend, gateway, keyword):
    seen: list[dict] = []
    original = gateway.handler

    def capture(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search-products"):
            seen.append(json.loads(request.content))
        return original(request)

    backend.client._client._transport = httpx.MockTransport(capture)
    results = await backend.search_products(session(), keyword, limit=12)
    assert len(seen) == 1  # the explicit call succeeded; no word-by-word retry
    assert seen[0]["shop_types"] == list(SUPPORTED_SHOP_TYPES)
    assert seen[0]["size"] == 40  # slots 21+ are where Bunjang listings arrive
    assert "OTHER" not in seen[0]["shop_types"]
    assert len(SUPPORTED_SHOP_TYPES) == 16
    assert {r.category for r in results} >= {"bunjang", "poca_market", "smart_store"}


def test_query_variants_try_each_word_longest_first():
    assert query_variants("뉴진스 굿즈 추천") == ["뉴진스", "굿즈", "추천"]
    assert query_variants("bts 앨범 포토카드 (한정판)") == ["포토카드", "bts", "한정판"]
    assert query_variants("줄넘기") == []


async def test_a_rejected_query_retries_its_words_before_the_smart_store_only_answer(
    backend, gateway
):
    gateway.honor_shop_types = False  # a gateway that still judges the keyword
    results = await backend.search_products(session(), "bts 앨범 포토카드", limit=12)
    searches = [c for c in gateway.calls if c.endswith("/search-products")]
    assert len(searches) == 3  # full query, 포토카드, then bts matched
    assert results[0].product_id.startswith("bunjang:")


async def test_an_empty_accepted_answer_also_retries_word_by_word(backend, gateway):
    gateway.empty_for = {"bts 앨범"}
    results = await backend.search_products(session(), "bts 앨범", limit=12)
    searches = [c for c in gateway.calls if c.endswith("/search-products")]
    assert len(searches) == 2  # "bts 앨범" came back empty, then "bts" (longest word) matched
    assert results[0].product_id.startswith("bunjang:")


async def test_a_shop_types_list_naming_an_unsupported_type_is_refused(gateway):
    client = DeliveredClient(
        "https://gateway.test/v1", transport=httpx.MockTransport(gateway.handler)
    )
    request = client._client.build_request(
        "POST", "/search-products", json={"query": "bts", "size": 20, "shop_types": ["OTHER"]}
    )
    response = gateway.handler(request)
    assert response.status_code == 400
    assert "not supported" in response.json()["message"]


async def test_a_4xx_from_the_multi_market_search_is_a_miss_not_an_error(backend, gateway):
    gateway.honor_shop_types = False
    results = await backend.search_products(session(), "줄넘기")
    assert [r.product_id for r in results] == ["smart_store:10791906854", "smart_store:10529071942"]


async def test_both_sources_down_raises(backend, gateway):
    gateway.search_status = 503
    gateway.list_status = 503
    with pytest.raises(DeliveredApiError):
        await backend.search_products(session(), "bts")


async def test_filters_and_sort_apply_to_the_merged_page(backend):
    filters = SearchFilters(max_price=10000, sort="price_asc")
    results = await backend.search_products(session(), "bts", filters=filters)
    assert [r.price for r in results] == sorted(r.price for r in results)
    assert all(r.price <= 10000 for r in results)
    only_used = await backend.search_products(
        session(), "bts", filters=SearchFilters(attributes={"condition": "중고"})
    )
    assert all(r.attributes["condition"] == "중고" for r in only_used)


async def test_a_category_narrows_to_a_market_or_is_ignored(backend):
    everything = await backend.search_products(session(), "bts", limit=12)
    ignored = await backend.search_products(
        session(), "bts", filters=SearchFilters(category="음반"), limit=12
    )
    assert [r.product_id for r in ignored] == [r.product_id for r in everything]
    only = await backend.search_products(
        session(), "bts", filters=SearchFilters(category="번개장터"), limit=12
    )
    assert only and all(r.category == "bunjang" for r in only)


async def test_details_resolve_from_the_detail_route_or_the_seen_cache(backend, gateway):
    await backend.search_products(session(), "bts")
    smart = await backend.get_product_details(session(), "smart_store:10791906854")
    assert smart is not None and smart.specs["재고 수량"] == "28918"
    bunjang = await backend.get_product_details(session(), "bunjang:429925416")
    assert bunjang is not None and bunjang.attributes["market"] == "번개장터"
    assert await backend.get_product_details(session(), "bunjang:0") is None
    assert backend.product("bunjang:429925416") is not None


async def test_warm_up_fills_the_home_listing(backend, gateway):
    await backend.warm_up(pages=1)
    assert set(backend.products) == {"smart_store:10791906854", "smart_store:10529071942"}
    gateway.list_status = 503
    fresh = DeliveredStorefront(backend.client)
    await fresh.warm_up(pages=1)
    assert fresh.products == {}


CART_ACCESS = "access-token-SECRET-1"


def sign_in_session(backend: DeliveredStorefront, session_id: str = "s-1") -> None:
    from delivered.api.delivered_auth import CustomerProfile, SessionCredential

    profile = CustomerProfile(customer_id="77", display_name="Ken Park")
    backend.credentials.put(session_id, SessionCredential(CART_ACCESS, None, "77", profile))


async def test_cart_is_in_won_and_refuses_sold_out_lines(cart_backend, gateway):
    sign_in_session(cart_backend)
    await cart_backend.search_products(session(), "bts")
    cart = await cart_backend.add_to_cart(session(), "smart_store:10791906854", 2)
    assert cart.currency == "KRW"
    assert cart.items[0].quantity == 2
    sold_out = cart_backend.product("bunjang:429925416").model_copy(update={"in_stock": False})
    cart_backend._seen[sold_out.product_id] = sold_out
    with pytest.raises(Unavailable):
        await cart_backend.add_to_cart(session(), sold_out.product_id, 1)
    with pytest.raises(KeyError):
        await cart_backend.add_to_cart(session(), "bunjang:0", 1)


async def test_switched_off_systems_answer_empty(backend):
    assert await backend.get_orders(session()) == []
    assert await backend.get_order(session(), "o-1") is None
    assert await backend.search_policies(session(), "환불") == []
    assert await backend.get_fulfillment_options(session(), ["smart_store:1"]) == []
    profile = await backend.get_preferences(session())
    assert profile.user_id == "demo-user"


# ---------------------------------------------------------------------------
# delivered cart (RBD-8277): buy requests attached to the customer's cart
# ---------------------------------------------------------------------------

from delivered.api.delivered_auth import (  # noqa: E402
    CredentialStore,
    DeliveredAuthClient,
    SignInRequired,
)
from delivered.api.delivered_cart import CartRejected, unit_price_of  # noqa: E402


class FakeCustomerGateway:
    """The customer API's cart routes with delivered's two-step model: a buy request is
    created per market route, then attached; ``v3/cart`` lists what is attached."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.next_id = 500
        self.requests: dict[int, dict] = {}
        self.attached: list[int] = []
        self.errors: dict[str, tuple[int, dict]] = {}
        self.detail_status = 200

    def preload(
        self,
        market: str,
        pid: str,
        title: str,
        quantity: int = 1,
        options: list[dict] | None = None,
    ) -> int:
        buy_request_id = self._create(
            market, pid, title, quantity, product_url=f"https://web.test/{pid}", options=options
        )
        self.attached.append(buy_request_id)
        return buy_request_id

    def _create(
        self,
        market: str,
        pid: str,
        title: str,
        quantity: int,
        product_url: str,
        options: list[dict] | None = None,
    ) -> int:
        self.next_id += 1
        self.requests[self.next_id] = {
            "market": market,
            "pid": pid,
            "title": title,
            "quantity": quantity,
            "options": options or [],
            "product_url": product_url,
        }
        return self.next_id

    def paths(self) -> list[str]:
        return [
            f"{r.method} {r.url.path}{('?' + r.url.query.decode()) if r.url.query else ''}"
            for r in self.calls
        ]

    def bodies(self, path_end: str) -> list[dict]:
        return [
            json.loads(r.content) for r in self.calls if r.url.path.endswith(path_end) and r.content
        ]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        path = request.url.path
        if request.headers.get("Authorization") != f"Bearer {CART_ACCESS}":
            return httpx.Response(
                401, json={"httpStatus": "UNAUTHORIZED", "message": "Authorization Key not found"}
            )
        for suffix, (status, body) in self.errors.items():
            if path.endswith(suffix):
                return httpx.Response(status, json=body)
        if path.endswith("/v1/buy-request/rpa-store"):
            body = json.loads(request.content)
            new_id = self._create(
                body["market_sub_type"],
                body["pid"],
                f"{body['market_sub_type']} {body['pid']}",
                body["quantity"],
                product_url="",
            )
            return httpx.Response(200, json={"result": True, "data": new_id, "message": None})
        if path.endswith("/v2/buy-request/bunjang"):
            body = json.loads(request.content)
            new_id = self._create(
                "BUNJANG",
                str(body["pid"]),
                body["item_description"],
                body["quantity"],
                body["product_url"],
            )
            return httpx.Response(
                200, content=str(new_id).encode(), headers={"Content-Type": "application/json"}
            )
        if path.endswith("/v2/buy-request/shop"):
            body = json.loads(request.content)
            new_id = self._create(
                "DK_SHOP",
                body["pid"],
                body["item_description"],
                body["quantity"],
                body["product_url"],
            )
            return httpx.Response(200, json={"data": new_id})
        if path.endswith("/v2/cart/add-carts"):
            ids = [int(x) for x in request.url.params["buyRequestIds"].split(",")]
            for buy_request_id in ids:
                if buy_request_id in self.attached:
                    return httpx.Response(
                        400,
                        json={
                            "code": "CART-004",
                            "result": False,
                            "message": "The item already exists in the cart.",
                        },
                    )
                if buy_request_id not in self.requests:
                    return httpx.Response(
                        400,
                        json={
                            "code": "CART-003",
                            "result": False,
                            "message": "Failed to add to the cart.",
                        },
                    )
                self.attached.append(buy_request_id)
            return httpx.Response(200, json={"result": True, "data": None, "message": None})
        if request.method == "DELETE" and path.endswith("/v2/cart"):
            ids = [int(x) for x in request.url.params["buyRequestIds"].split(",")]
            missing = [i for i in ids if i not in self.attached]
            if missing:
                return httpx.Response(
                    400,
                    json={"code": "CART-001", "result": False, "message": "No cart data exists."},
                )
            self.attached = [i for i in self.attached if i not in ids]
            return httpx.Response(200, json={"result": True, "data": {}, "message": None})
        if path.endswith("/v3/cart"):
            groups: dict[str, list[dict]] = {}
            for buy_request_id in self.attached:
                record = self.requests[buy_request_id]
                groups.setdefault(record["market"], []).append(
                    {
                        "id": 900000 + buy_request_id,
                        "cart_id": buy_request_id,
                        "quantity": record["quantity"],
                        "product_title": record["title"],
                        "product_url": record["product_url"],
                        "thumbnail_image_url": f"https://img.test/{record['pid']}.jpg",
                        "total_price": [],
                        "prices": [{"fee_type": "UNIT_PRICE", "cost_krw": 12000, "cost_usd": 8.8}],
                        "options": record["options"],
                        "is_expired": False,
                        "is_selling": True,
                        "market_info": {
                            "type": "OTHER",
                            "sub_type": record["market"],
                            "name": record["market"],
                        },
                    }
                )
            orders = [
                {
                    "market_sub_type": market,
                    "market_name": market,
                    "is_bundled": False,
                    "items": items,
                }
                for market, items in groups.items()
            ]
            return httpx.Response(
                200, json={"result": True, "data": {"orders": orders}, "message": None}
            )
        if "/v2/cart/" in path:
            buy_request_id = int(path.rsplit("/", 1)[1])
            if self.detail_status != 200 or buy_request_id not in self.requests:
                return httpx.Response(
                    self.detail_status if self.detail_status != 200 else 400,
                    json={"code": "CART-001", "result": False, "message": "No cart data exists."},
                )
            record = self.requests[buy_request_id]
            return httpx.Response(
                200,
                json={
                    "result": True,
                    "data": {
                        "id": buy_request_id,
                        "product_id": record["pid"],
                        "product_url": record["product_url"],
                        "quantity": record["quantity"],
                        "options": [
                            {
                                "type": "Option",
                                "key": "Option",
                                "value": row.get("value_ko") or row.get("value"),
                            }
                            for row in record["options"]
                        ],
                        "market": {
                            "type": "OTHER",
                            "sub_type": record["market"],
                            "name": record["market"],
                        },
                    },
                },
            )
        return httpx.Response(404, json={"result": False})


@pytest.fixture
def customer() -> FakeCustomerGateway:
    return FakeCustomerGateway()


@pytest.fixture
def cart_backend(gateway: FakeGateway, customer: FakeCustomerGateway) -> DeliveredStorefront:
    client = DeliveredClient(
        "https://gateway.test/v1", transport=httpx.MockTransport(gateway.handler)
    )
    auth = DeliveredAuthClient(
        "https://auth.test",
        "https://customer.test/api/customer",
        transport=httpx.MockTransport(customer.handler),
    )
    return DeliveredStorefront(client, auth=auth, credentials=CredentialStore())


async def seen(backend: DeliveredStorefront, *queries: str) -> None:
    for query in queries:
        await backend.search_products(session(), query)


# -- T004: add_to_cart happy paths ----------------------------------------------


async def test_add_to_cart_creates_a_buy_request_on_the_markets_route_then_attaches_it(
    cart_backend, customer
):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    cart = await cart_backend.add_to_cart(session(), "smart_store:10791906854", 2)
    assert customer.paths()[:3] == [
        "POST /api/customer/v1/buy-request/rpa-store",
        "POST /api/customer/v2/cart/add-carts?buyRequestIds=501&entryType=0",
        "GET /api/customer/v3/cart",
    ]
    body = customer.bodies("/rpa-store")[0]
    assert (
        body["pid"] == "10791906854"
        and body["market_sub_type"] == "SMART_STORE"
        and body["quantity"] == 2
    )
    assert body["market_type"] == "SHOP" and body["options"] == []
    assert [item.product_id for item in cart.items] == ["smart_store:10791906854"]
    assert cart.items[0].quantity == 2 and cart.currency == "KRW"
    assert cart.items[0].price == unit_price_of(
        {"quantity": 2, "prices": [{"fee_type": "UNIT_PRICE", "cost_krw": 12000}]}
    )


async def test_bunjang_and_dk_shop_products_take_their_own_routes(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    await cart_backend.add_to_cart(session(), "bunjang:429925416", 1)
    assert "POST /api/customer/v2/buy-request/bunjang" in customer.paths()
    body = customer.bodies("/bunjang")[0]
    assert body["pid"] == 429925416 and body["market_sub_type"] == "BUNJANG" and body["product_url"]
    assert body["bid_confirm_type"] == "REJECTED"
    cart = await cart_backend.get_cart(session())
    assert "bunjang:429925416" in [item.product_id for item in cart.items]


async def test_adding_a_line_the_cart_already_holds_recreates_it_with_the_sum(
    cart_backend, customer
):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    await cart_backend.add_to_cart(session(), "smart_store:10791906854", 2)
    customer.calls.clear()
    cart = await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    assert customer.paths()[:4] == [
        "GET /api/customer/v3/cart",
        "DELETE /api/customer/v2/cart?buyRequestIds=501",
        "POST /api/customer/v1/buy-request/rpa-store",
        "POST /api/customer/v2/cart/add-carts?buyRequestIds=502&entryType=0",
    ]
    assert customer.bodies("/rpa-store")[0]["quantity"] == 3
    assert cart.items[0].quantity == 3


# -- T005: add_to_cart failures and non-sends ------------------------------------


async def test_a_guest_add_never_reaches_delivered(cart_backend, customer):
    await seen(cart_backend, "bts")
    with pytest.raises(SignInRequired):
        await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    assert customer.calls == []


async def test_an_unsupported_market_is_refused_before_any_call(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    cart_backend._seen["other:1"] = cart_backend.product("smart_store:10791906854").model_copy(
        update={"product_id": "other:1"}
    )
    with pytest.raises(CartRejected) as rejected:
        await cart_backend.add_to_cart(session(), "other:1", 1)
    assert "담을 수 없습니다" in str(rejected.value)
    assert customer.calls == []


async def test_a_refused_buy_request_relays_delivered_message(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    customer.errors["/rpa-store"] = (
        400,
        {"code": "BR-002", "result": False, "message": "Sold out at the store."},
    )
    with pytest.raises(CartRejected) as rejected:
        await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    assert str(rejected.value) == "구매요청을 만들지 못했습니다: Sold out at the store."
    assert not any("add-carts" in p for p in customer.paths())


async def test_a_full_cart_relays_the_full_message_and_logs_the_orphan(
    cart_backend, customer, caplog
):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    customer.errors["/add-carts"] = (
        400,
        {
            "code": "CART-005",
            "result": False,
            "message": "The maximum number of items in the cart has been exceeded.",
        },
    )
    with caplog.at_level(logging.WARNING), pytest.raises(CartRejected) as rejected:
        await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    assert "가득" in str(rejected.value)
    assert "501" in caplog.text and "orphan" in caplog.text
    assert (await cart_backend.get_cart(session())).items == []


async def test_already_in_cart_is_absorbed_and_the_cart_re_read(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    customer.errors["/add-carts"] = (
        400,
        {"code": "CART-004", "result": False, "message": "The item already exists in the cart."},
    )
    customer.preload("SMART_STORE", "10791906854", "이미 담긴 이어폰")
    cart = await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    assert [item.product_id for item in cart.items] == ["smart_store:10791906854"]


async def test_a_5xx_from_delivered_is_the_frameworks_unavailable_error(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    customer.errors["/rpa-store"] = (503, {"result": False})
    with pytest.raises(DeliveredApiError):
        await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)


# -- T007: get_cart -----------------------------------------------------------------


async def test_a_guest_cart_is_empty_without_a_call(cart_backend, customer):
    assert (await cart_backend.get_cart(session())).items == []
    assert customer.calls == []


async def test_lines_added_on_the_web_resolve_through_the_detail_route_once(cart_backend, customer):
    sign_in_session(cart_backend)
    web_id = customer.preload("WEVERSE", "wv-77", "위버스 앨범", quantity=2)
    cart = await cart_backend.get_cart(session())
    assert [item.product_id for item in cart.items] == ["weverse:wv-77"]
    assert cart.items[0].title == "위버스 앨범" and cart.items[0].quantity == 2
    assert customer.paths() == ["GET /api/customer/v3/cart", f"GET /api/customer/v2/cart/{web_id}"]
    customer.calls.clear()
    await cart_backend.get_cart(session())
    assert customer.paths() == ["GET /api/customer/v3/cart"]


async def test_a_line_the_detail_route_cannot_name_is_still_listed(cart_backend, customer):
    sign_in_session(cart_backend)
    web_id = customer.preload("MUSINSA", "m-1", "후드")
    customer.detail_status = 503
    cart = await cart_backend.get_cart(session())
    assert cart.items[0].product_id == f"musinsa:unknown-{web_id}"


async def test_get_cart_exposes_fees_market_groups_and_expiry_as_extras(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    record = type("Record", (), {"session_id": "s-1"})()
    extras = cart_backend.cart_extras_for(record)
    group = extras["delivered_cart"]["groups"][0]
    assert group["market_sub_type"] == "SMART_STORE"
    line = group["items"][0]
    assert line["product_id"] == "smart_store:10791906854" and line["buy_request_id"] == 501
    assert line["fees"][0]["fee_type"] == "UNIT_PRICE"
    assert (line["is_expired"], line["is_selling"]) == (False, True)
    assert cart_backend.cart_extras_for(type("Record", (), {"session_id": "other"})()) == {}


# -- T009: remove_from_cart ---------------------------------------------------------


async def test_remove_deletes_the_buy_request_and_re_reads(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    customer.calls.clear()
    cart = await cart_backend.remove_from_cart(session(), "smart_store:10791906854")
    assert customer.paths() == [
        "DELETE /api/customer/v2/cart?buyRequestIds=501",
        "GET /api/customer/v3/cart",
    ]
    assert cart.items == []


async def test_removing_a_line_delivered_no_longer_has_is_absorbed(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    customer.attached.clear()
    cart = await cart_backend.remove_from_cart(session(), "smart_store:10791906854")
    assert cart.items == []


async def test_removing_an_unknown_line_only_re_reads(cart_backend, customer):
    sign_in_session(cart_backend)
    cart = await cart_backend.remove_from_cart(session(), "smart_store:nope")
    assert cart.items == [] and customer.paths() == ["GET /api/customer/v3/cart"]


# -- T011: update_cart_item ---------------------------------------------------------


async def test_update_deletes_then_recreates_with_the_new_quantity(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    customer.calls.clear()
    cart = await cart_backend.update_cart_item(session(), "smart_store:10791906854", 2)
    assert customer.paths() == [
        "GET /api/customer/v3/cart",
        "DELETE /api/customer/v2/cart?buyRequestIds=501",
        "POST /api/customer/v1/buy-request/rpa-store",
        "POST /api/customer/v2/cart/add-carts?buyRequestIds=502&entryType=0",
        "GET /api/customer/v3/cart",
    ]
    assert customer.bodies("/rpa-store")[0]["quantity"] == 2
    assert cart.items[0].quantity == 2


async def test_a_web_added_line_can_be_updated_from_its_cart_facts(cart_backend, customer):
    sign_in_session(cart_backend)
    web_id = customer.preload("WEVERSE", "wv-77", "위버스 앨범", quantity=1)
    cart = await cart_backend.update_cart_item(session(), "weverse:wv-77", 3)
    assert f"DELETE /api/customer/v2/cart?buyRequestIds={web_id}" in customer.paths()
    assert customer.bodies("/rpa-store")[0] | {} == customer.bodies("/rpa-store")[0]
    assert (
        customer.bodies("/rpa-store")[0]["pid"] == "wv-77"
        and customer.bodies("/rpa-store")[0]["market_sub_type"] == "WEVERSE"
    )
    assert cart.items[0].quantity == 3


async def test_a_failed_recreation_tells_the_customer_to_add_again(cart_backend, customer):
    sign_in_session(cart_backend)
    await seen(cart_backend, "bts")
    await cart_backend.add_to_cart(session(), "smart_store:10791906854", 1)
    customer.errors["/rpa-store"] = (
        400,
        {"code": "BR-002", "result": False, "message": "Sold out at the store."},
    )
    with pytest.raises(CartRejected) as rejected:
        await cart_backend.update_cart_item(session(), "smart_store:10791906854", 2)
    assert "다시 담아 주세요" in str(rejected.value)
    assert (await cart_backend.get_cart(session())).items == []


# -- T013: the executor relays a rejection as the customer-facing sentence -----------


def test_the_executor_relays_cart_rejections_verbatim():
    from delivered.api.delivered_executor import DeliveredToolExecutor

    executor = object.__new__(DeliveredToolExecutor)
    outcome = executor.domain_error(
        CartRejected("장바구니가 가득 찼습니다 — 웹에서 정리해 주세요.")
    )
    assert outcome is not None and outcome.is_error
    assert "가득 찼습니다" in outcome.result_text


# ---------------------------------------------------------------------------
# option products (RBD-8278): families and variants from the option routes
# ---------------------------------------------------------------------------

RACKET = "smart_store:11314403854"
POUCH = "smart_store:10631022673"


async def test_an_option_product_details_as_a_family_with_variants(backend, gateway):
    family = await backend.get_product_details(session(), RACKET)
    assert family.product_id == RACKET and family.has_options
    assert family.options == {"색상": ["레드블랙", "화이트"]}
    assert [v.product_id for v in family.variants] == [f"{RACKET}#137750", f"{RACKET}#137751"]
    assert (
        family.variants[0].option_values == {"색상": "레드블랙"}
        and family.variants[0].variant_of == RACKET
    )
    assert family.price == 22200.0 and family.in_stock
    assert [c for c in gateway.calls if "11314403854" in c] == [
        "GET /v1/buy-request/stores/smartstore/11314403854",
        "GET /v1/buy-request/stores/smartstore/11314403854/option-groups",
        "GET /v1/buy-request/stores/smartstore/11314403854/options",
    ]


async def test_a_variant_id_resolves_to_its_own_record(backend):
    variant = await backend.get_product_details(session(), f"{RACKET}#137751")
    assert variant.product_id == f"{RACKET}#137751"
    assert variant.variant_of == RACKET and variant.option_values == {"색상": "화이트"}
    assert not variant.has_options and variant.variants == []
    assert backend.product(f"{RACKET}#137751") is not None
    assert backend.product(RACKET).has_options


async def test_a_product_without_options_details_as_before(backend, gateway):
    detail = await backend.get_product_details(session(), "smart_store:10791906854")
    assert not detail.has_options and detail.variants == []
    assert "text_options" not in detail.attributes


async def test_a_failing_option_route_leaves_the_product_plain_with_a_warning(
    backend, gateway, caplog
):
    gateway.options_status = 503
    with caplog.at_level(logging.WARNING):
        detail = await backend.get_product_details(session(), RACKET)
    assert detail is not None and not detail.has_options
    assert "option" in caplog.text and "11314403854" in caplog.text


async def test_a_rejected_option_route_is_logged_and_leaves_the_product_plain(
    backend, gateway, caplog
):
    gateway.options_status = 404
    with caplog.at_level(logging.WARNING):
        detail = await backend.get_product_details(session(), RACKET)
    assert detail is not None and not detail.has_options
    assert "option" in caplog.text and "11314403854" in caplog.text


async def test_a_text_group_marks_the_family(backend):
    family = await backend.get_product_details(session(), POUCH)
    assert family.attributes["text_options"] == "각인X:없음 / 각인O:TEXT를 입력"
    assert len(family.variants) == 12


# -- T006: adding a variant carries its option id; families, sold-out, text groups refuse


async def test_adding_a_variant_sends_its_option_id(cart_backend, customer):
    sign_in_session(cart_backend)
    cart = await cart_backend.add_to_cart(session(), f"{RACKET}#137750", 1)
    body = customer.bodies("/rpa-store")[0]
    assert (
        body["pid"] == "11314403854" and body["options"] == [137750] and body["text_options"] == []
    )
    assert body["market_type"] == "SHOP" and body["market_sub_type"] == "SMART_STORE"
    assert cart.items and cart.items[0].product_id == f"{RACKET}#137750"


async def test_adding_the_family_itself_is_refused_before_any_call(cart_backend, customer):
    sign_in_session(cart_backend)
    with pytest.raises(KeyError):
        await cart_backend.add_to_cart(session(), RACKET, 1)
    assert customer.calls == []


async def test_a_sub_family_id_is_refused_like_the_family(cart_backend, customer):
    sign_in_session(cart_backend)
    family = await cart_backend.get_product_details(session(), RACKET)
    piece = family.model_copy(update={"product_id": f"{RACKET}#g1", "options": {}, "variants": []})
    cart_backend.products[piece.product_id] = piece
    assert not piece.has_options
    with pytest.raises(KeyError):
        await cart_backend.add_to_cart(session(), f"{RACKET}#g1", 1)
    assert customer.calls == []


async def test_a_sold_out_variant_names_its_siblings_in_stock(cart_backend, customer, gateway):
    sign_in_session(cart_backend)
    gateway.sold_out_option_ids = {137750}
    with pytest.raises(Unavailable) as unavailable:
        await cart_backend.add_to_cart(session(), f"{RACKET}#137750", 1)
    assert f"{RACKET}#137751" in str(unavailable.value) and "137750" in str(unavailable.value)
    assert customer.calls == []


async def test_a_product_with_a_text_group_is_sent_to_the_website(cart_backend, customer):
    sign_in_session(cart_backend)
    for product_id in (POUCH, f"{POUCH}#134495"):
        with pytest.raises(CartRejected) as rejected:
            await cart_backend.add_to_cart(session(), product_id, 1)
        assert "웹" in str(rejected.value)
    assert customer.calls == []


async def test_a_guest_cannot_add_a_variant(cart_backend, customer):
    with pytest.raises(SignInRequired):
        await cart_backend.add_to_cart(session(), f"{RACKET}#137750", 1)
    assert customer.calls == []


# -- T008: a cart line with options resolves to the variant through the option routes

WHITE_LINE = [
    {
        "type": "Option",
        "key": "Option",
        "value": "White",
        "value_ko": "화이트",
        "option_key_locale": {
            "product_option_group_id": 18147,
            "product_option_group_name": "색상",
        },
    }
]


async def test_a_web_added_option_line_resolves_to_its_variant(cart_backend, customer, gateway):
    sign_in_session(cart_backend)
    web_id = customer.preload("SMART_STORE", "11314403854", "라켓 세트", options=WHITE_LINE)
    cart = await cart_backend.get_cart(session())
    assert [item.product_id for item in cart.items] == [f"{RACKET}#137751"]
    assert any(c.endswith("/11314403854/options") for c in gateway.calls)
    assert cart_backend._index("s-1").request_of(f"{RACKET}#137751") == web_id


async def test_a_line_naming_only_the_korean_value_still_resolves(cart_backend, customer):
    sign_in_session(cart_backend)
    customer.preload(
        "SMART_STORE",
        "11314403854",
        "라켓 세트",
        options=[{"type": "Option", "key": "Option", "value": "레드블랙"}],
    )
    cart = await cart_backend.get_cart(session())
    assert [item.product_id for item in cart.items] == [f"{RACKET}#137750"]


async def test_an_option_line_that_matches_nothing_is_listed_as_the_family(
    cart_backend, customer, caplog
):
    sign_in_session(cart_backend)
    customer.preload(
        "SMART_STORE",
        "11314403854",
        "라켓 세트",
        options=[{"type": "Option", "key": "Option", "value": "보라"}],
    )
    with caplog.at_level(logging.WARNING):
        cart = await cart_backend.get_cart(session())
    assert [item.product_id for item in cart.items] == [RACKET]
    assert "option" in caplog.text


async def test_a_line_without_options_still_resolves_to_the_plain_id(
    cart_backend, customer, gateway
):
    sign_in_session(cart_backend)
    customer.preload("SMART_STORE", "10791906854", "줄넘기")
    cart = await cart_backend.get_cart(session())
    assert [item.product_id for item in cart.items] == ["smart_store:10791906854"]
    assert not any(c.endswith("/options") for c in gateway.calls)


# -- RBD-8279: the checkout card hands off to the delivered web cart


async def test_a_signed_in_cart_hands_off_to_the_delivered_web_cart(cart_backend):
    sign_in_session(cart_backend)
    handoffs = await cart_backend.checkout_handoff(session(), Cart(currency="KRW"))
    assert [handoff.url for handoff in handoffs] == ["https://www.delivered.co.kr/cart"]
    assert handoffs[0].label == "Continue on delivered"


async def test_a_guest_has_no_checkout_handoff(cart_backend):
    assert await cart_backend.checkout_handoff(session(), Cart(currency="KRW")) == []


async def test_the_web_cart_url_can_be_overridden(cart_backend, monkeypatch):
    monkeypatch.setenv("DELIVERED_WEB_CART_URL", "https://staging.delivered.test/cart")
    sign_in_session(cart_backend)
    handoffs = await cart_backend.checkout_handoff(session(), Cart(currency="KRW"))
    assert handoffs[0].url == "https://staging.delivered.test/cart"
