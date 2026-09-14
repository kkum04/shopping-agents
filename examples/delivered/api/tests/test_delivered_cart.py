# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The pure cart mapping of the delivered example: market routing, buy-request bodies,
id parsing, and the v3 cart as the framework's ``Cart``. The shapes follow the customer
frontend's DTOs and webuy-cat-service's ``CartListDto``; the staging probe confirms them
in T014."""

from __future__ import annotations

import pytest

from delivered.api.delivered_auth import DeliveredApiError
from delivered.api.delivered_cart import (
    ERROR_MESSAGES,
    RPA_MARKETS,
    CartIndex,
    CartRejected,
    buy_request_body,
    buy_request_id_in,
    buy_request_id_of,
    cart_from_v3,
    product_id_of,
    rejection_for,
    route_of,
    split_product_id,
    unit_price_of,
)
from shopping_agent import ProductDetails


def product(market: str, raw_id: str, **extra) -> ProductDetails:
    attributes = {"market": market, **extra.pop("attributes", {})}
    return ProductDetails.model_validate(
        {
            "product_id": product_id_of(market, raw_id),
            "title": f"{market} 상품 {raw_id}",
            "price": 12000.0,
            "currency": "KRW",
            "image_url": f"https://img.test/{raw_id}.jpg",
            "attributes": attributes,
            **extra,
        }
    )


V3_ITEM = {
    "id": 658429,
    "cart_id": 501,
    "quantity": 2,
    "product_title": "무선 이어폰",
    "product_url": "https://smartstore.naver.com/x/products/10791906854",
    "thumbnail_image_url": "https://img.test/earbuds.jpg",
    "total_price": [{"fee_type": "TOTAL", "cost_krw": 30000, "cost_usd": 22.1}],
    "prices": [
        {"fee_type": "UNIT_PRICE", "cost_krw": 30000, "cost_usd": 22.1},
        {"fee_type": "DOMESTIC_SHIPPING_PRICE", "cost_krw": 3000, "cost_usd": 2.2},
    ],
    "options": [],
    "is_expired": False,
    "is_selling": True,
    "market_info": {"type": "OTHER", "sub_type": "SMART_STORE", "name": "스마트스토어"},
}

V3_PAYLOAD = {
    "result": True,
    "data": {
        "orders": [
            {
                "market_sub_type": "SMART_STORE",
                "market_name": "스마트스토어",
                "is_bundled": False,
                "items": [V3_ITEM],
            },
            {
                "market_sub_type": "BUNJANG",
                "market_name": "번개장터",
                "is_bundled": False,
                "items": [
                    {
                        **V3_ITEM,
                        "id": 658430,
                        "cart_id": 502,
                        "quantity": 1,
                        "product_title": "중고 키보드",
                        "prices": [{"fee_type": "UNIT_PRICE", "cost_krw": 45000, "cost_usd": 33.0}],
                        "is_expired": True,
                        "is_selling": False,
                        "market_info": {
                            "type": "BUNJANG",
                            "sub_type": "BUNJANG",
                            "name": "번개장터",
                        },
                    }
                ],
            },
        ]
    },
    "message": None,
}


def test_ids_round_trip_across_markets():
    assert product_id_of("SMART_STORE", 10791906854) == "smart_store:10791906854"
    assert split_product_id("bunjang:429925416") == ("BUNJANG", "429925416")


def test_every_supported_market_routes_to_one_buy_request_path():
    assert len(RPA_MARKETS) == 13
    for market in RPA_MARKETS:
        assert route_of(market) == "rpa"
    assert route_of("BUNJANG") == "bunjang"
    assert route_of("DK_SHOP") == "shop"
    with pytest.raises(CartRejected) as rejected:
        route_of("OTHER")
    assert "담을 수 없습니다" in str(rejected.value)


def test_the_rpa_body_carries_the_market_and_no_options():
    path, body = buy_request_body(product("SMART_STORE", "10791906854"), 3)
    assert path == "/v1/buy-request/rpa-store"
    assert body == {
        "pid": "10791906854",
        "market_type": "SHOP",
        "market_sub_type": "SMART_STORE",
        "quantity": 3,
        "uploaded_image_urls": [],
        "additional_information": "",
        "options": [],
        "text_options": [],
        "pre_order_yn": False,
    }


def test_the_rpa_body_takes_the_market_type_the_catalog_named():
    _, body = buy_request_body(product("MUSINSA", "m-1", attributes={"market_type": "OTHER"}), 1)
    assert body["market_type"] == "OTHER"


def test_the_bunjang_body_needs_the_product_url_and_a_numeric_pid():
    item = product(
        "BUNJANG",
        "429925416",
        attributes={"product_url": "https://m.bunjang.co.kr/products/429925416"},
    )
    path, body = buy_request_body(item, 1)
    assert path == "/v2/buy-request/bunjang"
    assert body["pid"] == 429925416
    assert body["product_url"] == "https://m.bunjang.co.kr/products/429925416"
    assert body["market_type"] == "BUNJANG" and body["market_sub_type"] == "BUNJANG"
    assert body["item_description"] == item.title
    assert body["bid_confirm_type"] == "REJECTED"
    assert body["item_image_urls"] == [item.image_url]
    assert body["quantity"] == 1


def test_a_bunjang_product_without_a_url_falls_back_to_the_canonical_page():
    _, body = buy_request_body(product("BUNJANG", "429925416"), 1)
    assert body["product_url"] == "https://m.bunjang.co.kr/products/429925416"


def test_the_shop_body_names_the_dk_shop():
    path, body = buy_request_body(
        product("DK_SHOP", "abc-1", attributes={"product_url": "https://shop.test/abc-1"}), 2
    )
    assert path == "/v2/buy-request/shop"
    assert body["market_type"] == "SHOP" and body["market_sub_type"] == "DK_SHOP"
    assert body["pid"] == "abc-1" and body["quantity"] == 2 and body["options"] == []


def test_buy_request_ids_parse_from_the_three_answer_shapes():
    assert buy_request_id_of({"result": True, "data": 123}) == 123
    assert buy_request_id_of({"data": "456"}) == 456
    assert buy_request_id_of(789) == 789
    with pytest.raises(CartRejected):
        buy_request_id_of({"result": True, "data": None})
    with pytest.raises(CartRejected):
        buy_request_id_of({"result": False})


def test_unit_price_is_the_per_unit_fee():
    assert unit_price_of(V3_ITEM) == 30000.0
    assert unit_price_of({**V3_ITEM, "prices": []}) == 0.0


def test_the_v3_cart_maps_lines_and_keeps_expired_ones():
    cart, extras = cart_from_v3(
        V3_PAYLOAD,
        lambda item: product_id_of(item["market_info"]["sub_type"], buy_request_id_in(item)),
    )
    assert cart.currency == "KRW"
    assert [item.product_id for item in cart.items] == ["smart_store:501", "bunjang:502"]
    first = cart.items[0]
    assert (first.title, first.price, first.quantity, first.image_url) == (
        "무선 이어폰",
        30000.0,
        2,
        "https://img.test/earbuds.jpg",
    )
    assert cart.subtotal == 30000.0 * 2 + 45000.0
    groups = extras["delivered_cart"]["groups"]
    assert [group["market_sub_type"] for group in groups] == ["SMART_STORE", "BUNJANG"]
    line = groups[0]["items"][0]
    assert line["buy_request_id"] == 501 and line["product_id"] == "smart_store:501"
    assert line["fees"] == V3_ITEM["prices"]
    assert (line["is_expired"], line["is_selling"]) == (False, True)
    assert (groups[1]["items"][0]["is_expired"], groups[1]["items"][0]["is_selling"]) == (
        True,
        False,
    )


def test_an_empty_or_failed_cart_answer_is_an_empty_cart():
    cart, extras = cart_from_v3({"result": True, "data": {"orders": []}}, lambda item: "x")
    assert cart.items == [] and extras["delivered_cart"]["groups"] == []
    cart, _ = cart_from_v3({"result": False}, lambda item: "x")
    assert cart.items == []


def test_the_listing_item_id_is_the_cart_id_with_the_row_id_as_fallback():
    assert buy_request_id_in({"id": 658429, "cart_id": 587490}) == 587490
    assert buy_request_id_in({"id": 7}) == 7
    assert buy_request_id_in({"id": "x"}) == 0


def test_the_index_maps_both_ways_and_forgets():
    index = CartIndex()
    index.put(501, "smart_store:10791906854")
    assert index.request_of("smart_store:10791906854") == 501
    assert index.product_of(501) == "smart_store:10791906854"
    index.put(501, "smart_store:10791906854")
    index.drop_request(501)
    assert index.request_of("smart_store:10791906854") is None
    assert index.product_of(501) is None


def test_rejections_read_the_delivered_error_code_or_message():
    full = DeliveredApiError(
        "POST /v2/cart/add-carts: HTTP 400", status=400, code="CART-005", detail="exceeded"
    )
    assert str(rejection_for(full, "담지 못했습니다")) == ERROR_MESSAGES["CART-005"]
    other = DeliveredApiError(
        "POST /v1/buy-request/rpa-store: HTTP 400", status=400, code="BR-009", detail="Sold out"
    )
    assert (
        str(rejection_for(other, "구매요청을 만들지 못했습니다"))
        == "구매요청을 만들지 못했습니다: Sold out"
    )
    bare = DeliveredApiError("POST /x: HTTP 400", status=400)
    assert (
        str(rejection_for(bare, "구매요청을 만들지 못했습니다")) == "구매요청을 만들지 못했습니다."
    )
