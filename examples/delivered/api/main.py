# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""delivered example API: the live delivered guest catalog behind the shared storefront
routes.

    uvicorn delivered.api.main:app --app-dir examples --reload --port 8004

``DELIVERED_API_URL`` points the backend at another gateway (the production guest API
is the default). Memory is in-process; each boot starts fresh.
"""

from __future__ import annotations

from commerce_common.memory import InMemoryMemoryStore
from demo_common import (
    REPO_ROOT,
    CartAddRequest,
    MemorySeeder,
    build_storefront_host,
    load_demo_env,
)
from shopping_agent_runtime import ShoppingAgent

from .agent_config import build_shopping_config
from .delivered_backend import DATA_DIR, DeliveredStorefront

load_demo_env(DATA_DIR.parent)

backend = DeliveredStorefront()
agent = ShoppingAgent(
    backend=backend,
    skills_dir=REPO_ROOT / "shopping-agent" / "skills",
    config=build_shopping_config(),
    memory_store=InMemoryMemoryStore(),
)

host = build_storefront_host(
    title="delivered demo API",
    example_root=DATA_DIR.parent,
    backend=backend,
    agent=agent,
    memory_seeder=MemorySeeder(DATA_DIR / "memory-seed.json"),
    on_startup=[backend.warm_up],
)
app = host.app


@app.post("/api/cart/add")
async def cart_add(request: CartAddRequest, record: host.CurrentSession) -> dict:
    return await host.direct_add(
        record,
        request,
        note="Customer tapped the add-to-cart button on {title} ({product_id}), quantity {quantity}.",
    )
