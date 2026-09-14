# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The delivered example's ``StorefrontBackend`` over the delivered guest catalog API:
the multi-market product search and the Smart Store listing with its detail route. The
mapping functions are pure (the tests feed them recorded responses); ``DeliveredClient``
makes the HTTP calls; ``DeliveredStorefront`` is the backend the shared host routes and
the agent read.

Two catalog sources answer one search. The multi-market search covers every market
delivered buys from (Bunjang, Weverse, Poca Market, Smart Store, and more); it is asked
with every supported market named (``SUPPORTED_SHOP_TYPES``), which lets any keyword
through, and a rejection is retried one word at a time. The Smart Store listing matches a
keyword against product names. Both run for every search and their results merge. Carts
are per-session state in this process, as in the other examples; delivered's own checkout
takes over from the cart card.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import OrderedDict
from dataclasses import replace
from typing import Any

import httpx

from demo_common.storefront_fixtures import (
    example_data_dir,
    load_users,
    preferences_of,
)
from shopping_agent import (
    Cart,
    FulfillmentOption,
    Order,
    Policy,
    Product,
    ProductDetails,
    SearchFilters,
    ShoppingSessionContext,
    StorefrontBackend,
    Unavailable,
    UserPreferences,
)

from .delivered_auth import (
    AuthUnavailable,
    CredentialStore,
    CustomerProfile,
    DeliveredApiError,
    DeliveredAuthClient,
    SessionCredential,
    SignInRequired,
    SignInResult,
    TokenExpired,
)
from .delivered_cart import (
    ADD_CARTS_PATH,
    ADD_FAILED,
    ALREADY_IN_CART,
    BUY_REQUEST_FAILED,
    CART_LIST_PATH,
    CART_PATH,
    DELETE_FAILED,
    NOT_IN_CART,
    RECREATE_FAILED,
    CartIndex,
    CartRejected,
    buy_request_body,
    buy_request_id_in,
    buy_request_id_of,
    cart_from_v3,
    product_id_of,
    rejection_for,
    split_product_id,
)

logger = logging.getLogger(__name__)

DATA_DIR = example_data_dir(__file__)
DEFAULT_BASE_URL = "https://gw.delivered.co.kr/dk-delivered/api/guests/v1"
CURRENCY = "KRW"
# The multi-market search answers 404 below 20, fills the first twenty slots from the shop
# markets (Smart Store, Daiso, Musinsa, ...) and only then appends Bunjang, so a page of 20
# never carries a Bunjang listing. Forty is the customer frontend's page size too.
SEARCH_PAGE_SIZE = 40
SEARCH_MIN_PAGE_SIZE = 20
HOME_PAGE_SIZE = 24
SEEN_CAP = 2000
# delivered ships every product abroad itself; the seller's export flags do not apply.
INTERNATIONAL_SHIPPING = "가능 (delivered 해외배송)"

MARKET_LABELS = {
    "SMART_STORE": "네이버 스마트스토어",
    "BUNJANG": "번개장터",
    "POCA_MARKET": "포카마켓",
    "DK_SHOP": "delivered 샵",
    "WEVERSE": "위버스샵",
    "YES24": "예스24",
    "ALADIN": "알라딘",
    "K_TOWN_4U": "케이타운포유",
    "MAKE_STAR": "메이크스타",
    "GIFTIFAN": "기프티팬",
    "GIFTIFAN_SHOP": "기프티팬 샵",
    "DAISO": "다이소",
    "MUSINSA": "무신사",
    "OLIVE_YOUNG": "올리브영",
    "FANS": "팬즈",
    "WITCHFORM": "윗치폼",
    "BE_ON_D": "비온디",
}

# The multi-market search picks markets from the keyword unless the request names them,
# and a keyword it cannot place (나이키, 화장품) then answers 400. Naming every supported
# type makes any keyword searchable; ``OTHER`` is refused, so it is not listed.
SUPPORTED_SHOP_TYPES: tuple[str, ...] = (
    "BUNJANG",
    "DK_SHOP",
    "OLIVE_YOUNG",
    "K_TOWN_4U",
    "FANS",
    "ALADIN",
    "MAKE_STAR",
    "POCA_MARKET",
    "DAISO",
    "WITCHFORM",
    "BE_ON_D",
    "SMART_STORE",
    "WEVERSE",
    "MUSINSA",
    "YES24",
    "GIFTIFAN_SHOP",
)


MAX_QUERY_VARIANTS = 3


def query_variants(query: str) -> list[str]:
    """Shorter queries to try when the multi-market search still rejects the full one
    (a gateway that judges the keyword despite ``shop_types``): each word is tried alone,
    longest first."""
    words = [word.strip(",.!?()[]\"'") for word in query.split()]
    variants: list[str] = []
    for word in sorted(words, key=len, reverse=True):
        if len(word) >= 2 and word != query and word not in variants:
            variants.append(word)
    return variants[:MAX_QUERY_VARIANTS]


def interleave_by_market(records: list[ProductDetails]) -> list[ProductDetails]:
    """Round-robin across markets, keeping each market's own order, so the first page
    shows every market that answered rather than the one the gateway listed first."""
    by_market: dict[str, list[ProductDetails]] = {}
    for record in records:
        by_market.setdefault(record.category or "", []).append(record)
    queues = list(by_market.values())
    ordered: list[ProductDetails] = []
    while queues:
        for queue in list(queues):
            ordered.append(queue.pop(0))
            if not queue:
                queues.remove(queue)
    return ordered


# ---------------------------------------------------------------------------
# Mapping: delivered records -> shopping_agent records
# ---------------------------------------------------------------------------


def image_of(url: str | None) -> str | None:
    """Bunjang image URLs carry a literal ``{cnt}`` slot for the image index."""
    if not url:
        return None
    return url.replace("{cnt}", "1")


def _krw(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _base_fields(
    *,
    market: str,
    raw_id: str,
    name: str,
    english_name: str | None,
    brand: str | None,
    list_krw: float | None,
    sale_krw: float | None,
    usd: float | None,
    shipping_krw: float | None,
    image: str | None,
    sold_out: bool,
    used: bool,
    product_url: str | None = None,
    market_type: str | None = None,
) -> dict[str, Any]:
    price = sale_krw if sale_krw is not None else (list_krw or 0.0)
    labels: list[str] = []
    attributes: dict[str, str] = {
        "market": MARKET_LABELS.get(market, market.title()),
        "condition": "중고" if used else "새상품",
        "international_shipping": INTERNATIONAL_SHIPPING,
    }
    if used:
        labels.append("중고")
    if list_krw is not None and sale_krw is not None and sale_krw < list_krw:
        labels.append("할인")
        attributes["list_price_krw"] = f"{list_krw:,.0f}"
    if usd is not None:
        attributes["price_usd"] = f"${usd:,.2f}"
    if shipping_krw is not None:
        attributes["domestic_shipping_krw"] = f"{shipping_krw:,.0f}"
    if english_name:
        attributes["english_name"] = english_name
    if product_url:
        attributes["product_url"] = product_url
    if market_type:
        attributes["market_type"] = market_type
    return {
        "product_id": product_id_of(market, raw_id),
        "title": name,
        "brand": brand or None,
        "price": price,
        "currency": CURRENCY,
        "image_url": image_of(image),
        "category": market.lower(),
        "labels": labels,
        "attributes": attributes,
        "in_stock": not sold_out,
        "short_description": english_name or None,
    }


def search_response_to_products(payload: dict[str, Any]) -> list[ProductDetails]:
    """The multi-market search's ``data.products`` as catalog records."""
    if not payload.get("result"):
        return []
    records = []
    for item in (payload.get("data") or {}).get("products") or []:
        market = str(item.get("marketSubType") or "UNKNOWN")
        fields = _base_fields(
            market=market,
            raw_id=str(item["id"]),
            name=item.get("productName") or "",
            english_name=item.get("productNameEn"),
            brand=item.get("brand"),
            list_krw=_krw(item.get("productPriceKrw")),
            sale_krw=_krw(item.get("discountedProductPriceKrw")),
            usd=_krw(item.get("discountedProductPrice")),
            shipping_krw=_krw(item.get("domesticShippingFeeKrw")),
            image=item.get("imageUrl"),
            sold_out=bool(item.get("isSoldOut")),
            used=bool(item.get("isUsed")),
            product_url=item.get("productUrl"),
        )
        records.append(ProductDetails.model_validate(fields))
    return records


def list_response_to_products(payload: dict[str, Any]) -> list[ProductDetails]:
    """The Smart Store listing's ``data.content`` as catalog records."""
    if not payload.get("result"):
        return []
    records = []
    for item in (payload.get("data") or {}).get("content") or []:
        market = str(item.get("marketSubType") or "SMART_STORE")
        fields = _base_fields(
            market=market,
            raw_id=str(item["pid"]),
            name=item.get("productName") or "",
            english_name=item.get("productEngName"),
            brand=item.get("brand"),
            list_krw=_krw(item.get("productPriceKrw")),
            sale_krw=_krw(item.get("discountedProductPriceKrw")),
            usd=_krw(item.get("discountedProductPrice")),
            shipping_krw=None,
            image=item.get("thumbnailImage"),
            sold_out=bool(item.get("isSoldOut")),
            used=bool(item.get("isUsed")),
            product_url=item.get("productLink"),
            market_type=item.get("marketType"),
        )
        link = item.get("productLink")
        records.append(ProductDetails.model_validate(fields | {"specs": _specs(link=link)}))
    return records


def _specs(**values: Any) -> dict[str, str]:
    names = {
        "link": "판매 페이지",
        "stock": "재고 수량",
        "shipping": "국내 배송비",
        "max_quantity": "1회 최대 구매 수량",
        "export": "해외 배송",
    }
    return {names[key]: str(value) for key, value in values.items() if value not in (None, "")}


def detail_to_product_details(payload: dict[str, Any]) -> ProductDetails | None:
    """The Smart Store detail route's ``data`` as one full record, or None on a miss."""
    if not payload.get("result"):
        return None
    item = payload.get("data") or {}
    market = str(item.get("marketSubType") or "SMART_STORE")
    shipping = _krw(item.get("domesticShippingPriceKrw"))
    stock = item.get("stockQuantity")
    images = [url for url in item.get("images") or [] if url]
    fields = _base_fields(
        market=market,
        raw_id=str(item["pid"]),
        name=item.get("productName") or "",
        english_name=item.get("productEngName"),
        brand=item.get("brand"),
        list_krw=_krw(item.get("productPriceKrw")),
        sale_krw=_krw(item.get("discountedProductPriceKrw")),
        usd=_krw(item.get("discountedProductPriceUsd")),
        shipping_krw=shipping,
        image=images[0] if images else None,
        sold_out=isinstance(stock, int) and stock <= 0,
        used=bool(item.get("isUsed")),
        product_url=item.get("productUrl"),
        market_type=item.get("marketType"),
    )
    return ProductDetails.model_validate(
        fields
        | {
            "specs": _specs(
                link=item.get("productUrl"),
                stock=stock,
                shipping=f"{shipping:,.0f}원" if shipping is not None else None,
                max_quantity=item.get("availablePurchaseQuantityMax"),
                export=INTERNATIONAL_SHIPPING,
            ),
        }
    )


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


class DeliveredClient:
    """The three guest catalog calls. A 4xx from the multi-market search is a miss (the
    API answers unsupported queries and small pages that way); transport errors and 5xx
    raise :class:`DeliveredApiError`."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("DELIVERED_API_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            transport=transport,
            timeout=timeout_s,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise DeliveredApiError(f"{method} {path}: {error}") from error
        if response.status_code >= 500:
            raise DeliveredApiError(f"{method} {path}: HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as error:
            raise DeliveredApiError(f"{method} {path}: not JSON") from error
        return body if isinstance(body, dict) else {"result": False}

    async def search_products(self, query: str, size: int = SEARCH_PAGE_SIZE) -> dict[str, Any]:
        body = {
            "query": query,
            "page": 0,
            "size": max(size, SEARCH_MIN_PAGE_SIZE),
            "bunjang_next_cursor": None,
            "bunjang_has_next": None,
            "dk_shop_next_cursor": None,
            "dk_shop_has_next": None,
            "shop_types": list(SUPPORTED_SHOP_TYPES),
        }
        return await self._call("POST", "/search-products", json=body)

    async def list_smartstore(
        self, query: str = "", page: int = 0, size: int = 12
    ) -> dict[str, Any]:
        params = {"query": query, "page": page, "size": size}
        return await self._call("GET", "/buy-request/stores/smartstore", params=params)

    async def smartstore_detail(self, pid: str) -> dict[str, Any]:
        return await self._call("GET", f"/buy-request/stores/smartstore/{pid}")


# ---------------------------------------------------------------------------
# The backend
# ---------------------------------------------------------------------------


class DeliveredStorefront(StorefrontBackend):
    """``products`` holds the home page listing (the first Smart Store pages, fetched at
    boot); ``_seen`` holds every record any call returned, so ids resolve after a search
    on markets that have no detail route. Both are per process."""

    store_name = "delivered"

    def __init__(
        self,
        client: DeliveredClient | None = None,
        *,
        auth: DeliveredAuthClient | None = None,
        credentials: CredentialStore | None = None,
    ) -> None:
        self.client = client or DeliveredClient()
        self.auth = auth or DeliveredAuthClient()
        self.credentials = credentials or CredentialStore()
        self.products: dict[str, ProductDetails] = {}
        self._seen: OrderedDict[str, ProductDetails] = OrderedDict()
        self._cart_index: dict[str, CartIndex] = {}
        self._cart_extras: dict[str, dict[str, Any]] = {}
        self._users = load_users(DATA_DIR)

    # -- Sign-in ----------------------------------------------------------------

    async def sign_in(
        self, email: str, password: str, remember_me: bool = False
    ) -> tuple[SignInResult, CustomerProfile]:
        """Sign in and read the profile; nothing is stored until ``attach``. A profile
        call that fails leaves no half-signed-in session behind."""
        result = await self.auth.sign_in(email, password, remember_me)
        try:
            me = await self.auth.get_me(result.access_token)
        except (DeliveredApiError, TokenExpired) as error:
            raise AuthUnavailable(f"GET /v2/me: {type(error).__name__}") from error
        profile = CustomerProfile.from_me(me, fallback_name=result.user_name)
        if not profile.customer_id:
            profile = replace(profile, customer_id=result.user_id)
        return result, profile

    def attach(self, session_id: str, result: SignInResult, profile: CustomerProfile) -> None:
        self.credentials.put(
            session_id,
            SessionCredential(
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                customer_id=profile.customer_id,
                profile=profile,
            ),
        )

    def sign_out(self, session_id: str) -> bool:
        return self.credentials.drop(session_id)

    def credential_of(self, session: ShoppingSessionContext) -> SessionCredential | None:
        return self.credentials.get(session.session_id)

    def require_credential(
        self, session: ShoppingSessionContext, feature: str = "이 기능"
    ) -> SessionCredential:
        credential = self.credential_of(session)
        if credential is None:
            raise SignInRequired(feature)
        return credential

    async def customer_call(
        self,
        session: ShoppingSessionContext,
        method: str,
        path: str,
        *,
        feature: str = "이 기능",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """A customer API call for the signed-in customer; an expired token drops the
        credential so the session continues as a guest."""
        credential = self.require_credential(session, feature)
        try:
            return await self.auth.customer_request(method, path, credential.access_token, **kwargs)
        except TokenExpired:
            self.credentials.drop(session.session_id)
            raise

    # -- Boot -----------------------------------------------------------------

    async def warm_up(self, pages: int = 2) -> None:
        """Fill the home page listing; a failure leaves it empty and logs."""
        for page in range(pages):
            try:
                payload = await self.client.list_smartstore("", page=page, size=HOME_PAGE_SIZE)
            except DeliveredApiError as error:
                logger.warning("delivered catalog warm-up stopped: %s", error)
                return
            for record in list_response_to_products(payload):
                self.products[record.product_id] = record
                self._remember(record)

    async def aclose(self) -> None:
        await self.client.aclose()
        await self.auth.aclose()

    # -- Lookup ---------------------------------------------------------------

    def _remember(self, record: ProductDetails) -> None:
        self._seen[record.product_id] = record
        self._seen.move_to_end(record.product_id)
        while len(self._seen) > SEEN_CAP:
            self._seen.popitem(last=False)

    def product(self, product_id: str) -> ProductDetails | None:
        return self.products.get(product_id) or self._seen.get(product_id)

    # -- Catalog --------------------------------------------------------------

    async def search_products(
        self,
        session: ShoppingSessionContext,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 8,
    ) -> list[Product]:
        del session
        query = query.strip()
        results = await asyncio.gather(
            self._multi_market_search(query),
            self.client.list_smartstore(query, size=max(limit, 12)),
            return_exceptions=True,
        )
        search_payload, list_payload = results
        failures = [r for r in results if isinstance(r, BaseException)]
        if len(failures) == len(results):
            raise failures[0]
        for failure in failures:
            logger.warning("one delivered catalog source failed: %s", failure)

        merged: dict[str, ProductDetails] = {}
        if isinstance(search_payload, dict):
            for record in search_response_to_products(search_payload):
                merged.setdefault(record.product_id, record)
        if isinstance(list_payload, dict):
            for record in list_response_to_products(list_payload):
                merged.setdefault(record.product_id, record)
        for record in merged.values():
            self._remember(record)

        records = interleave_by_market([r for r in merged.values() if _passes(r, filters)])
        if filters and filters.sort == "price_asc":
            records.sort(key=lambda r: r.price)
        elif filters and filters.sort == "price_desc":
            records.sort(key=lambda r: -r.price)
        return [Product.model_validate(r.model_dump(exclude={"variants"})) for r in records[:limit]]

    async def _multi_market_search(self, query: str) -> dict[str, Any]:
        """The full query, then its words one at a time until the search accepts one."""
        payload = await self.client.search_products(query)
        for variant in query_variants(query) if _is_miss(payload) else ():
            payload = await self.client.search_products(variant)
            if not _is_miss(payload):
                logger.info("multi-market search matched %r for %r", variant, query)
                break
        return payload

    async def get_product_details(
        self, session: ShoppingSessionContext, product_id: str
    ) -> ProductDetails | None:
        del session
        market, raw_id = split_product_id(product_id)
        if market == "SMART_STORE" and raw_id:
            try:
                detail = detail_to_product_details(await self.client.smartstore_detail(raw_id))
            except DeliveredApiError as error:
                logger.warning("smart store detail unavailable for %s: %s", product_id, error)
                detail = None
            if detail is not None:
                self._remember(detail)
                if product_id in self.products:
                    self.products[product_id] = detail
                return detail
        return self.product(product_id)

    # -- Cart -----------------------------------------------------------------
    # delivered's cart holds buy requests: one is created on the route for the product's
    # market, then attached. Every write ends with a fresh read of ``v3/cart``.

    def _index(self, session_id: str) -> CartIndex:
        return self._cart_index.setdefault(session_id, CartIndex())

    def cart_extras_for(self, record: Any) -> dict[str, Any]:
        """The host's ``cart_extras`` hook: fees, market groups, and expiry from the
        session's last cart read."""
        return self._cart_extras.get(record.session_id, {})

    async def get_cart(self, session: ShoppingSessionContext) -> Cart:
        if self.credential_of(session) is None:
            return Cart(currency=CURRENCY)
        payload = await self.customer_call(session, "GET", CART_LIST_PATH, feature="장바구니")
        index = self._index(session.session_id)
        listing = payload if isinstance(payload, dict) else {"result": False}
        for order in (
            ((listing.get("data") or {}).get("orders") or []) if listing.get("result") else []
        ):
            for item in order.get("items") or []:
                buy_request_id = buy_request_id_in(item)
                if buy_request_id and index.product_of(buy_request_id) is None:
                    market = str(
                        (item.get("market_info") or {}).get("sub_type")
                        or order.get("market_sub_type")
                        or "unknown"
                    )
                    index.put(
                        buy_request_id,
                        await self._resolve_product_id(session, buy_request_id, market),
                    )
        cart, extras = cart_from_v3(
            listing, lambda item: index.product_of(buy_request_id_in(item)) or "unknown:0"
        )
        self._cart_extras[session.session_id] = extras
        return cart

    async def _resolve_product_id(
        self, session: ShoppingSessionContext, buy_request_id: int, market: str
    ) -> str:
        try:
            detail = await self.customer_call(
                session, "GET", f"{CART_PATH}/{buy_request_id}", feature="장바구니"
            )
        except DeliveredApiError:
            logger.warning("delivered cart detail unavailable for buy request %s", buy_request_id)
            return product_id_of(market, f"unknown-{buy_request_id}")
        data = (detail or {}).get("data") or {} if isinstance(detail, dict) else {}
        raw_id = data.get("product_id")
        sub_type = str((data.get("market") or {}).get("sub_type") or market)
        if not raw_id:
            return product_id_of(sub_type, f"unknown-{buy_request_id}")
        return product_id_of(sub_type, str(raw_id))

    async def _create_buy_request(
        self, session: ShoppingSessionContext, product: ProductDetails, quantity: int
    ) -> int:
        path, body = buy_request_body(product, quantity)
        try:
            payload = await self.customer_call(session, "POST", path, feature="장바구니", json=body)
        except DeliveredApiError as error:
            if error.status is not None and 400 <= error.status < 500:
                raise rejection_for(error, BUY_REQUEST_FAILED) from error
            raise
        return buy_request_id_of(payload)

    async def _add_carts(self, session: ShoppingSessionContext, buy_request_ids: list[int]) -> None:
        ids = ",".join(str(value) for value in buy_request_ids)
        try:
            await self.customer_call(
                session,
                "POST",
                ADD_CARTS_PATH,
                feature="장바구니",
                params={"buyRequestIds": ids, "entryType": "0"},
            )
        except DeliveredApiError as error:
            if error.code == ALREADY_IN_CART:
                return
            if error.status is not None and 400 <= error.status < 500:
                logger.warning(
                    "delivered add-carts refused (%s); orphan buy request %s", error.code, ids
                )
                raise rejection_for(error, ADD_FAILED) from error
            raise

    async def _delete_from_cart(
        self, session: ShoppingSessionContext, buy_request_ids: list[int]
    ) -> None:
        ids = ",".join(str(value) for value in buy_request_ids)
        try:
            await self.customer_call(
                session, "DELETE", CART_PATH, feature="장바구니", params={"buyRequestIds": ids}
            )
        except DeliveredApiError as error:
            if error.code == NOT_IN_CART:
                return
            if error.status is not None and 400 <= error.status < 500:
                raise rejection_for(error, DELETE_FAILED) from error
            raise

    async def _line_product(
        self, session: ShoppingSessionContext, product_id: str, cart: Cart
    ) -> ProductDetails:
        product = await self.get_product_details(session, product_id)
        if product is not None:
            return product
        line = next((item for item in cart.items if item.product_id == product_id), None)
        if line is None:
            raise KeyError(product_id)
        extras = self._cart_extras.get(session.session_id, {})
        product_url = next(
            (
                item.get("product_url")
                for group in extras.get("delivered_cart", {}).get("groups", [])
                for item in group.get("items", [])
                if item.get("product_id") == product_id
            ),
            None,
        )
        return ProductDetails(
            product_id=product_id,
            title=line.title,
            price=line.price,
            currency=CURRENCY,
            image_url=line.image_url,
            attributes={"product_url": product_url} if product_url else {},
        )

    async def add_to_cart(
        self, session: ShoppingSessionContext, product_id: str, quantity: int
    ) -> Cart:
        self.require_credential(session, "장바구니")
        product = await self.get_product_details(session, product_id)
        if product is None or product.has_options:
            raise KeyError(product_id)
        if not product.in_stock:
            raise Unavailable(f"{product_id} is sold out")
        buy_request_body(product, quantity)
        index = self._index(session.session_id)
        if index.request_of(product_id) is not None:
            cart = await self.get_cart(session)
            existing = next((item for item in cart.items if item.product_id == product_id), None)
            if existing is not None:
                return await self._recreate(
                    session, product, index.request_of(product_id), existing.quantity + quantity
                )
        buy_request_id = await self._create_buy_request(session, product, quantity)
        await self._add_carts(session, [buy_request_id])
        index.put(buy_request_id, product_id)
        return await self.get_cart(session)

    async def update_cart_item(
        self, session: ShoppingSessionContext, product_id: str, quantity: int
    ) -> Cart:
        self.require_credential(session, "장바구니")
        cart = await self.get_cart(session)
        buy_request_id = self._index(session.session_id).request_of(product_id)
        if buy_request_id is None:
            return cart
        product = await self._line_product(session, product_id, cart)
        return await self._recreate(session, product, buy_request_id, quantity)

    async def _recreate(
        self,
        session: ShoppingSessionContext,
        product: ProductDetails,
        buy_request_id: int | None,
        quantity: int,
    ) -> Cart:
        index = self._index(session.session_id)
        if buy_request_id is not None:
            await self._delete_from_cart(session, [buy_request_id])
            index.drop_request(buy_request_id)
        try:
            fresh_id = await self._create_buy_request(session, product, quantity)
            await self._add_carts(session, [fresh_id])
        except (CartRejected, DeliveredApiError) as error:
            logger.warning(
                "delivered cart line %s dropped but not recreated (%s)",
                buy_request_id,
                type(error).__name__,
            )
            raise CartRejected(RECREATE_FAILED) from error
        index.put(fresh_id, product.product_id)
        return await self.get_cart(session)

    async def remove_from_cart(self, session: ShoppingSessionContext, product_id: str) -> Cart:
        self.require_credential(session, "장바구니")
        index = self._index(session.session_id)
        buy_request_id = index.request_of(product_id)
        if buy_request_id is None:
            cart = await self.get_cart(session)
            buy_request_id = index.request_of(product_id)
            if buy_request_id is None:
                return cart
        await self._delete_from_cart(session, [buy_request_id])
        index.drop_request(buy_request_id)
        return await self.get_cart(session)

    def reset_session(self, session_id: str) -> None:
        self._cart_index.pop(session_id, None)
        self._cart_extras.pop(session_id, None)
        self.credentials.drop(session_id)

    # -- Customer context, orders, policies, fulfillment ------------------------
    # Orders, policies, and fulfillment are switched off in agent_config.py; the
    # methods stay so the interface is complete, and answer as empty.

    async def get_preferences(self, session: ShoppingSessionContext) -> UserPreferences:
        credential = self.credential_of(session)
        if credential is None:
            return preferences_of(self._users, session.user_id)
        profile = credential.profile
        return UserPreferences(
            user_id=session.user_id,
            display_name=profile.display_name,
            loyalty_tier=profile.member_tier,
            default_location=profile.country,
        )

    async def get_account_context(self, session: ShoppingSessionContext) -> dict[str, Any] | None:
        credential = self.credential_of(session)
        if credential is None:
            return {
                "signed_in": False,
                "note": "Guest session: search and product details work; the cart and "
                "checkout need the customer to sign in to delivered first.",
            }
        return {
            "signed_in": True,
            "member_tier": credential.profile.member_tier,
            "country": credential.profile.country,
        }

    async def get_orders(self, session: ShoppingSessionContext, limit: int = 5) -> list[Order]:
        return []

    async def get_order(self, session: ShoppingSessionContext, order_id: str) -> Order | None:
        return None

    def recent_orders(self, limit: int = 6) -> list[Order]:
        return []

    async def search_policies(self, session: ShoppingSessionContext, query: str) -> list[Policy]:
        return []

    async def get_fulfillment_options(
        self, session: ShoppingSessionContext, product_ids: list[str]
    ) -> list[FulfillmentOption]:
        return []


def _is_miss(payload: dict[str, Any]) -> bool:
    """A rejected query (``result: false``) or an accepted one with no products."""
    if not payload.get("result"):
        return True
    return not ((payload.get("data") or {}).get("products") or [])


def _market_slug(name: str) -> str | None:
    """``smart_store`` for "smart_store", "SMART_STORE", or "네이버 스마트스토어"; None otherwise."""
    wanted = name.strip().lower()
    for market, label in MARKET_LABELS.items():
        if wanted in (market.lower(), label.lower()):
            return market.lower()
    return None


def _passes(record: ProductDetails, filters: SearchFilters | None) -> bool:
    if filters is None:
        return True
    # The catalog has no category tree: a category that names a market narrows to it,
    # and any other category is ignored rather than emptying the page.
    market = _market_slug(filters.category) if filters.category else None
    if market and record.category != market:
        return False
    if filters.min_price is not None and record.price < filters.min_price:
        return False
    if filters.max_price is not None and record.price > filters.max_price:
        return False
    for key, wanted in filters.attributes.items():
        actual = record.attributes.get(key)
        if actual is not None and wanted.lower() not in actual.lower():
            return False
    return True
