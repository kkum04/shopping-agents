# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The delivered backend over recorded guest API responses; nothing here reaches the
network. ``fixtures/`` holds trimmed copies of real responses."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from delivered.api.delivered_backend import (
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
from shopping_agent import SearchFilters, ShoppingSessionContext, Unavailable

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
        # The real search accepts known keywords only (뉴진스 yes, 뉴진스 굿즈 no).
        self.supported_queries = {"bts"}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        path = request.url.path
        if path.endswith("/search-products"):
            body = json.loads(request.content)
            if body["size"] < 20:
                return httpx.Response(404, json={"code": "SP-001", "result": False})
            if body["query"] not in self.supported_queries:
                return httpx.Response(400, json={"code": "NOT_SUPPORT_MARKETS", "result": False})
            if self.search_status != 200:
                return httpx.Response(self.search_status, json={"result": False})
            return httpx.Response(200, json=fixture("search-products.json"))
        if path.endswith("/buy-request/stores/smartstore"):
            if self.list_status != 200:
                return httpx.Response(self.list_status, json={"result": False})
            return httpx.Response(200, json=fixture("smartstore-list.json"))
        if "/buy-request/stores/smartstore/" in path:
            if self.detail_status != 200:
                return httpx.Response(self.detail_status, json={"result": False})
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


def test_query_variants_try_each_word_longest_first():
    assert query_variants("뉴진스 굿즈 추천") == ["뉴진스", "굿즈", "추천"]
    assert query_variants("bts 앨범 포토카드 (한정판)") == ["포토카드", "bts", "한정판"]
    assert query_variants("줄넘기") == []


async def test_a_rejected_query_retries_its_words_before_the_smart_store_only_answer(
    backend, gateway
):
    results = await backend.search_products(session(), "bts 앨범 포토카드", limit=12)
    searches = [c for c in gateway.calls if c.endswith("/search-products")]
    assert len(searches) == 3  # full query, 포토카드, then bts matched
    assert results[0].product_id.startswith("bunjang:")


async def test_a_4xx_from_the_multi_market_search_is_a_miss_not_an_error(backend, gateway):
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


async def test_cart_is_in_won_and_refuses_sold_out_lines(backend, gateway):
    await backend.search_products(session(), "bts")
    cart = await backend.add_to_cart(session(), "smart_store:10791906854", 2)
    assert cart.currency == "KRW"
    assert cart.items[0].quantity == 2 and cart.items[0].price == 4000
    cart = await backend.add_to_cart(session(), "smart_store:10791906854", 1)
    assert cart.items[0].quantity == 3
    cart = await backend.update_cart_item(session(), "smart_store:10791906854", 1)
    assert cart.items[0].quantity == 1
    assert (await backend.remove_from_cart(session(), "smart_store:10791906854")).items == []

    sold_out = backend.product("bunjang:429925416").model_copy(update={"in_stock": False})
    backend._remember(sold_out)
    with pytest.raises(Unavailable):
        await backend.add_to_cart(session(), "bunjang:429925416", 1)
    with pytest.raises(KeyError):
        await backend.add_to_cart(session(), "bunjang:0", 1)


async def test_switched_off_systems_answer_empty(backend):
    assert await backend.get_orders(session()) == []
    assert await backend.get_order(session(), "o-1") is None
    assert await backend.search_policies(session(), "환불") == []
    assert await backend.get_fulfillment_options(session(), ["smart_store:1"]) == []
    profile = await backend.get_preferences(session())
    assert profile.user_id == "demo-user"
