# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""delivered's cart as the framework sees it. delivered keeps a cart in two steps: a buy
request is created on the route for the product's market, then its id is attached to the
cart. The functions here are pure — the route for a market, the request body, the id in
an answer, and the ``v3/cart`` listing as a ``Cart`` — so the tests feed them recorded
answers; ``DeliveredStorefront`` makes the calls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from shopping_agent import Cart, CartItem, ProductDetails

from .delivered_auth import DeliveredApiError
from .delivered_options import split_variant_id

CURRENCY = "KRW"

RPA_MARKETS = frozenset(
    {
        "SMART_STORE",
        "DAISO",
        "MUSINSA",
        "OLIVE_YOUNG",
        "WEVERSE",
        "YES24",
        "K_TOWN_4U",
        "POCA_MARKET",
        "MAKE_STAR",
        "ALADIN",
        "WITCHFORM",
        "BE_ON_D",
        "FANS",
    }
)
BUNJANG = "BUNJANG"
DK_SHOP = "DK_SHOP"

RPA_STORE_PATH = "/v1/buy-request/rpa-store"
BUNJANG_PATH = "/v2/buy-request/bunjang"
SHOP_PATH = "/v2/buy-request/shop"
ADD_CARTS_PATH = "/v2/cart/add-carts"
CART_PATH = "/v2/cart"
CART_LIST_PATH = "/v3/cart"

RPA_MARKET_TYPE = "SHOP"
BUNJANG_BID_CONFIRM = "REJECTED"
ITEM_PRICE_FEE = "UNIT_PRICE"
BUNJANG_PRODUCT_PAGE = "https://m.bunjang.co.kr/products/{pid}"

ALREADY_IN_CART = "CART-004"
NOT_IN_CART = "CART-001"
CART_FULL = "CART-005"

ERROR_MESSAGES = {
    "CART-001": "장바구니에 없는 항목입니다.",
    "CART-002": "장바구니에서 삭제하지 못했습니다.",
    "CART-003": "장바구니 담기에 실패했습니다.",
    "CART-004": "이미 장바구니에 있는 상품입니다.",
    "CART-005": (
        "장바구니가 가득 찼습니다(최대 개수 초과) — delivered 웹에서 항목을 정리한 뒤 "
        "다시 담아 주세요."
    ),
}
UNSUPPORTED_MARKET = "이 마켓의 상품은 아직 장바구니에 담을 수 없습니다."
TEXT_OPTIONS_REJECTED = (
    "이 상품은 문구 입력(각인 등)이 필요해 이 대화에서는 담을 수 없습니다 — delivered 웹에서 담아 "
    "주세요."
)
BUY_REQUEST_FAILED = "구매요청을 만들지 못했습니다"
ADD_FAILED = "장바구니에 담지 못했습니다"
DELETE_FAILED = "장바구니에서 빼지 못했습니다"
RECREATE_FAILED = "수량을 바꾸는 중 항목이 삭제됐지만 다시 담지 못했습니다 — 다시 담아 주세요."


class CartRejected(Exception):
    """delivered refused a cart write; the message is what the customer is told."""


def rejection_for(error: DeliveredApiError, fallback: str) -> CartRejected:
    if error.code in ERROR_MESSAGES:
        return CartRejected(ERROR_MESSAGES[error.code])
    if error.detail:
        return CartRejected(f"{fallback}: {error.detail}")
    return CartRejected(f"{fallback}.")


def product_id_of(market: str, raw_id: str | int) -> str:
    """One id space across markets: ``bunjang:429925416``, ``smart_store:10791906854``."""
    return f"{market.lower()}:{raw_id}"


def split_product_id(product_id: str) -> tuple[str, str]:
    """``("SMART_STORE", "10791906854")`` for ``smart_store:10791906854``; a variant's
    ``#`` suffix is not part of the market id."""
    market, _, raw_id = product_id.partition(":")
    return market.upper(), raw_id.partition("#")[0]


def route_of(market: str) -> str:
    if market in RPA_MARKETS:
        return "rpa"
    if market == BUNJANG:
        return "bunjang"
    if market == DK_SHOP:
        return "shop"
    raise CartRejected(UNSUPPORTED_MARKET)


def buy_request_body(product: ProductDetails, quantity: int) -> tuple[str, dict[str, Any]]:
    """The path and body that create a buy request for ``quantity`` of ``product``."""
    market, raw_id = split_product_id(product.product_id)
    _, option_id = split_variant_id(product.product_id)
    route = route_of(market)
    images = [product.image_url] if product.image_url else []
    if route == "rpa":
        return RPA_STORE_PATH, {
            "pid": raw_id,
            "market_type": product.attributes.get("market_type") or RPA_MARKET_TYPE,
            "market_sub_type": market,
            "quantity": quantity,
            "uploaded_image_urls": [],
            "additional_information": "",
            "options": [int(option_id)] if option_id else [],
            "text_options": [],
            "pre_order_yn": False,
        }
    product_url = product.attributes.get("product_url") or BUNJANG_PRODUCT_PAGE.format(pid=raw_id)
    if route == "bunjang":
        return BUNJANG_PATH, {
            "market_type": BUNJANG,
            "market_sub_type": BUNJANG,
            "product_url": product_url,
            "pid": int(raw_id),
            "item_description": product.title,
            "quantity": quantity,
            "bid_confirm_type": BUNJANG_BID_CONFIRM,
            "item_image_urls": images,
            "bunjang_image_urls": [],
            "additional_information": "",
        }
    return SHOP_PATH, {
        "product_url": product.attributes.get("product_url") or "",
        "pid": raw_id,
        "item_description": product.title,
        "quantity": quantity,
        "item_image_urls": images,
        "market_type": "SHOP",
        "market_sub_type": DK_SHOP,
        "options": [],
    }


def buy_request_id_of(payload: Any) -> int:
    """The id in a buy-request answer: ``{result, data: n}``, ``{data: n}``, or bare ``n``."""
    value = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(value, bool) or value is None:
        raise CartRejected(f"{BUY_REQUEST_FAILED}.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise CartRejected(f"{BUY_REQUEST_FAILED}.") from None


def buy_request_id_in(item: dict[str, Any]) -> int:
    """The id ``add-carts`` and ``DELETE /v2/cart`` take for a listed item: ``cart_id``
    (the buy request), not the row's ``id`` — probed on staging, 2026-09-14."""
    value = item.get("cart_id") if item.get("cart_id") is not None else item.get("id")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def unit_price_of(item: dict[str, Any]) -> float:
    """``UNIT_PRICE`` is the per-unit price in won, as the customer frontend shows it."""
    for price in item.get("prices") or []:
        if price.get("fee_type") == ITEM_PRICE_FEE:
            cost = price.get("cost_krw")
            return round(float(cost), 2) if isinstance(cost, (int, float)) else 0.0
    return 0.0


TOTAL_FEE = "TOTAL"
ORDER_MARKER_OPTION_TYPES = {"PRI_ORDER", "PRE_ORDER"}
DEFAULT_OPTION_NAME = "Option"


def line_total_of(item: dict[str, Any]) -> float:
    """The won total of a listing line: the listing's own ``TOTAL`` row or object when it
    carries one, else the unit price times the quantity plus the other fee rows."""
    total = item.get("total_price")
    for row in total if isinstance(total, list) else []:
        if isinstance(row, dict) and row.get("fee_type") == TOTAL_FEE:
            return float(row.get("cost_krw") or 0)
    if isinstance(total, dict) and total.get("total_price") is not None:
        return float(total["total_price"] or 0)
    quantity = max(int(item.get("quantity") or 1), 1)
    fees = sum(
        float(row.get("cost_krw") or 0)
        for row in item.get("prices") or []
        if isinstance(row, dict) and row.get("fee_type") != ITEM_PRICE_FEE
    )
    return unit_price_of(item) * quantity + fees


def option_rows_of(item: dict[str, Any]) -> list[dict[str, str]]:
    """A line's chosen options as ``{name, value}`` for the page; order markers are not
    options."""
    rows: list[dict[str, str]] = []
    for row in item.get("options") or []:
        if not isinstance(row, dict) or row.get("type") in ORDER_MARKER_OPTION_TYPES:
            continue
        value = row.get("value")
        if not value:
            continue
        locale = row.get("option_key_locale")
        group_name = locale.get("product_option_group_name") if isinstance(locale, dict) else None
        rows.append(
            {"name": str(group_name or row.get("key") or DEFAULT_OPTION_NAME), "value": str(value)}
        )
    return rows


def cart_from_v3(
    payload: dict[str, Any], resolve: Callable[[dict[str, Any]], str]
) -> tuple[Cart, dict[str, Any]]:
    """``GET /v3/cart`` as a ``Cart`` plus the extras the framework's line has no field
    for (fees, market group, expiry); ``resolve`` names the product id of an item."""
    lines: list[CartItem] = []
    groups: list[dict[str, Any]] = []
    orders = (payload.get("data") or {}).get("orders") or [] if payload.get("result") else []
    for order in orders:
        group_items: list[dict[str, Any]] = []
        for item in order.get("items") or []:
            product_id = resolve(item)
            lines.append(
                CartItem(
                    product_id=product_id,
                    title=item.get("product_title") or product_id,
                    price=unit_price_of(item),
                    quantity=max(int(item.get("quantity") or 1), 1),
                    image_url=item.get("thumbnail_image_url") or None,
                )
            )
            group_items.append(
                {
                    "buy_request_id": buy_request_id_in(item),
                    "product_id": product_id,
                    "product_url": item.get("product_url"),
                    "fees": item.get("prices") or [],
                    "line_total": line_total_of(item),
                    "options": option_rows_of(item),
                    "is_expired": bool(item.get("is_expired")),
                    "is_selling": item.get("is_selling") is not False,
                }
            )
        groups.append(
            {
                "market_sub_type": order.get("market_sub_type"),
                "market_name": order.get("market_name"),
                "is_bundled": bool(order.get("is_bundled")),
                "items": group_items,
            }
        )
    return Cart(items=lines, currency=CURRENCY), {"delivered_cart": {"groups": groups}}


class CartIndex:
    """Which buy request holds which product, per session; delivered's listing does not
    name the product id, so the id is remembered when the line is created and read back
    from the detail route otherwise."""

    def __init__(self) -> None:
        self._by_request: dict[int, str] = {}
        self._by_product: dict[str, int] = {}

    def put(self, buy_request_id: int, product_id: str) -> None:
        self.drop_request(buy_request_id)
        self.drop_product(product_id)
        self._by_request[buy_request_id] = product_id
        self._by_product[product_id] = buy_request_id

    def request_of(self, product_id: str) -> int | None:
        return self._by_product.get(product_id)

    def product_of(self, buy_request_id: int) -> str | None:
        return self._by_request.get(buy_request_id)

    def drop_request(self, buy_request_id: int) -> None:
        product_id = self._by_request.pop(buy_request_id, None)
        if product_id is not None:
            self._by_product.pop(product_id, None)

    def drop_product(self, product_id: str) -> None:
        buy_request_id = self._by_product.pop(product_id, None)
        if buy_request_id is not None:
            self._by_request.pop(buy_request_id, None)
