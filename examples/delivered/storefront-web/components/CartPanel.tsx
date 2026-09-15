// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AskLink, BagPanel, CheckoutButton, formatMoney, Pill, plural, TotalRow, useCatalogIndex, useStoreFrame } from "web-shared";
import { fetchProducts } from "@/lib/api";
import { activeTotals, buildCartView } from "@/lib/buildCartView";
import type { CartLineView } from "@/lib/buildCartView";
import type { CartPayload, Product } from "@/lib/types";
import CartLine, { lineName } from "./CartLine";

interface CartPanelProps {
  cart: CartPayload | null;
  checkoutStaged?: boolean;
}

const SETTLEMENT_NOTE = "Fees and payment are settled on delivered";

/** The listing behind a line; a variant's line borrows its family's brand and image. */
const asProduct = (view: CartLineView, catalog: Record<string, Product>): Product => {
  const { item } = view;
  const family = item.variant_of ? catalog[item.variant_of] : undefined;
  return (
    catalog[item.product_id] ?? {
      ...family,
      product_id: item.product_id,
      title: item.title,
      price: item.price,
      image_url: item.image_url ?? family?.image_url,
      options: undefined,
      option_values: item.option_values,
    }
  );
};

/** The docked cart. Quantity and checkout are messages to the assistant, so every write is one it made. */
export default function CartPanel({ cart, checkoutStaged = false }: CartPanelProps) {
  const { ask, chat } = useStoreFrame();
  const catalog = useCatalogIndex(fetchProducts);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const groups = useMemo(() => buildCartView(cart), [cart]);
  const totals = useMemo(() => activeTotals(groups), [groups]);
  const viewsById = useMemo(() => new Map(groups.flatMap((group) => group.lines).map((view) => [view.item.product_id, view])), [groups]);
  const busy = chat?.busy ?? false;
  const currency = cart?.currency ?? "KRW";
  const isEmpty = groups.length === 0;

  useEffect(() => {
    setPendingId(null);
  }, [cart]);

  useEffect(() => {
    if (!busy) setPendingId(null);
  }, [busy]);

  const handleQuantityChange = useCallback(
    (productId: string, quantity: number) => {
      const view = viewsById.get(productId);
      if (!view) return;
      if (chat) setPendingId(productId);
      ask(quantity < 1 ? `Remove the ${lineName(view)} from my cart.` : `Change the ${lineName(view)} quantity to ${quantity}.`);
    },
    [ask, chat, viewsById],
  );

  const handleRemove = useCallback(
    (productId: string) => {
      const view = viewsById.get(productId);
      if (!view) return;
      if (chat) setPendingId(productId);
      ask(`Remove the ${lineName(view)} from my cart.`);
    },
    [ask, chat, viewsById],
  );

  return (
    <BagPanel
      title="Cart"
      count={plural(totals.count, "item")}
      isEmpty={isEmpty}
      empty={
        <>
          Nothing in the cart yet.
          <br />
          Ask delivered Assistant for anything in the store.
        </>
      }
      footer={
        <>
          <TotalRow label={totals.count ? `Subtotal · ${plural(totals.count, "item")}` : "Subtotal"} value={formatMoney(totals.subtotal, currency, { whole: true })} note={SETTLEMENT_NOTE} />
          <CheckoutButton staged={checkoutStaged} disabled={totals.count === 0} prompt="Check out my cart." />
          {isEmpty ? null : (
            <div className="mt-2.5 flex justify-center">
              <AskLink label="Ask about this cart" prompt="Look over my cart: anything missing or worth swapping?" />
            </div>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {groups.map((group) => (
          <section key={group.key} className="flex flex-col gap-1.5">
            {group.marketName ? (
              <div className="flex items-center gap-2">
                <h3 className="text-[12.5px] font-semibold text-(--ink-2)">{group.marketName}</h3>
                <span className="text-[11px] text-(--ink-soft)">{plural(group.lines.length, "item")}</span>
                {group.isBundled ? <Pill tone="info">Bundled shipping</Pill> : null}
              </div>
            ) : null}
            <ul className="divide-y divide-(--line)">
              {group.lines.map((view) => (
                <CartLine
                  key={view.item.product_id}
                  view={view}
                  product={asProduct(view, catalog)}
                  marketName={group.marketName}
                  currency={currency}
                  pending={pendingId === view.item.product_id}
                  onQuantityChange={handleQuantityChange}
                  onRemove={handleRemove}
                />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </BagPanel>
  );
}
