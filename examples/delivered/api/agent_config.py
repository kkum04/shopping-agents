# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The delivered deployment's shopping agent config. Orders, policies, and fulfillment
are switched off: the guest catalog API has no such systems, so their tools, prompt
lines, and grounding rules leave the agent on every path."""

from __future__ import annotations

from shopping_agent import ShoppingAgentConfig

DOMAIN_SEARCH_NOTES = (
    "The catalog is Korean and spans every market delivered buys from: Naver Smart Store "
    "sellers, Musinsa, Olive Young, Daiso, and delivered's own shop for everyday goods, "
    "and Bunjang, Weverse Shop, Poca Market, YES24, Aladin, Ktown4u, Makestar, Fans, "
    "Witchform, Be On D, and Giftifan Shop for K-pop merchandise (albums, photocards, "
    "light sticks, goods). Prices are in Korean won (KRW); "
    "`attributes.price_usd` carries the dollar figure. Search matches product names across "
    "every market, so word each query as ONE keyword, in Korean where the product is "
    "Korean: a product noun (텀블러, 라면, 운동화) or an artist or group name (뉴진스, 아이브, "
    "BTS). Put anything beyond the keyword in filters or in your own ranking of the results. "
    "`filters.attributes` accepts `market` (a market name) and `condition` (중고 or 새상품); "
    "there is no category tree, so leave `filters.category` unset and rank the results "
    "yourself for the kind of item the customer wants. "
    "`attributes.domestic_shipping_krw` is the seller's domestic shipping fee where known. "
    "delivered ships every product abroad itself, so international shipping is always "
    "available; its fee is quoted at delivered's checkout, never here."
)


def build_shopping_config() -> ShoppingAgentConfig:
    return ShoppingAgentConfig(
        brand_name="delivered",
        assistant_name="delivered Assistant",
        brand_voice=(
            "friendly, concise, and plain about trade-offs; replies in the customer's "
            "language, Korean by default"
        ),
        domain_search_notes=DOMAIN_SEARCH_NOTES,
        enable_orders=False,
        enable_policies=False,
        enable_fulfillment=False,
        max_search_results=12,
    )
