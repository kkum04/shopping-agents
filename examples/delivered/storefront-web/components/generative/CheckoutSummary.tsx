// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { useId } from "react";
import { formatMoney, useCatalogIndex, safeHandoffs } from "web-shared";
import { fetchProducts } from "@/lib/api";
import { activeTotals, buildCartView } from "@/lib/buildCartView";
import type { CheckoutPayload, Product } from "@/lib/types";
import { STORE_POLICY } from "@/lib/storePolicy";
import { ProductImage } from "../ProductTile";

interface CheckoutSummaryProps {
  payload: CheckoutPayload;
}

const HANDOFF_LABEL = "Continue on delivered";
const HANDOFF_NOTE = "Nothing is charged here. Payment happens on delivered.";
const STATUS_LABELS = { expired: "Expired", sold_out: "Sold out" } as const;

export default function CheckoutSummary({ payload }: CheckoutSummaryProps) {
  const cart = payload.cart;
  const handoffs = safeHandoffs(payload.handoffs);
  // Several summaries can coexist across turns, so the describedby id is per card.
  const handoffNoteId = useId();
  // Summary lines carry only title, price, and quantity; the catalog supplies thumbnails.
  const catalog = useCatalogIndex(fetchProducts);
  const groups = buildCartView(cart);
  const totals = activeTotals(groups);
  const whole = { whole: true };

  return (
    <section data-checkout-card className="rounded-2xl border-2 border-(--accent) bg-(--card) p-4 shadow-(--shadow-sm)">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[15px] font-semibold text-(--ink)">Ready to check out</h3>
        <div className="flex items-center gap-1.5">
          <span className="whitespace-nowrap rounded-full border border-(--line) bg-(--well)/60 px-2.5 py-0.5 text-[11px] font-semibold text-(--ink-soft)">
            Not charged
          </span>
          {payload.fulfillment_method ? (
            <span className="rounded-full bg-(--accent-soft) px-2.5 py-0.5 text-[13px] font-semibold capitalize text-(--ink)">
              {payload.fulfillment_method}
            </span>
          ) : null}
        </div>
      </div>
      {payload.note ? <p className="mt-1 text-[13px] text-(--ink-soft)">{payload.note}</p> : null}
      <div className="mt-3 space-y-2 rounded-lg bg-(--well)/60 p-3 text-sm">
        {groups.flatMap((group) =>
          group.lines.map((view) => {
            const { item, status, total } = view;
            const product: Product = catalog[item.product_id] ?? { product_id: item.product_id, title: item.title, price: item.price, image_url: item.image_url };
            return (
              <div key={item.product_id} className={`flex items-center gap-2.5 ${status ? "opacity-60" : ""}`}>
                <ProductImage product={product} className="h-10 w-10 shrink-0 rounded-lg !text-xl" />
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-2">
                    <span className="line-clamp-1 text-(--ink)" title={item.title}>
                      {item.title} × {item.quantity}
                    </span>
                    <span className="shrink-0 text-(--ink)">{formatMoney(total, cart.currency, whole)}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11.5px] text-(--ink-soft)">
                    {group.marketName ? <span>{group.marketName}</span> : null}
                    {status ? <span className="font-semibold text-(--warn)">{STATUS_LABELS[status]}</span> : null}
                  </div>
                </div>
              </div>
            );
          }),
        )}
        <div className="flex justify-between gap-2 border-t border-(--line) pt-1.5 text-(--ink)">
          <span>
            Domestic shipping &amp; fees <span className="text-[13px] text-(--ink-soft)">included above</span>
          </span>
          <span className="text-[13px] text-(--ink-soft)">International shipping quoted on delivered</span>
        </div>
        <div className="flex justify-between border-t border-(--line) pt-1.5 text-base font-bold text-(--ink)">
          <span>Estimated total</span>
          <span>{formatMoney(totals.subtotal, cart.currency, whole)}</span>
        </div>
        <p className="text-[11px] leading-snug text-(--ink-soft)">Before international shipping; the final total appears on delivered.</p>
      </div>
      <p className="mt-2 text-[11px] text-(--ink-soft)">{STORE_POLICY.shippingNote}.</p>
      {handoffs.length ? (
        // The backend named where payment happens: delivered's own cart page.
        <div className="mt-3 flex flex-col gap-2">
          {handoffs.map((handoff) => (
            <a
              key={handoff.url}
              href={handoff.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-describedby={handoffNoteId}
              className="w-full rounded-xl bg-(--accent) py-2.5 text-center text-sm font-bold text-(--ink)"
            >
              {handoff.label ?? (handoff.seller ? `Continue to checkout with ${handoff.seller}` : HANDOFF_LABEL)}
            </a>
          ))}
        </div>
      ) : (
        // Disabled so assistive tech is not offered a focusable no-op.
        <button
          disabled
          aria-disabled
          aria-describedby={handoffNoteId}
          className="mt-3 w-full cursor-not-allowed rounded-xl bg-(--accent) py-2.5 text-sm font-bold text-(--ink) opacity-90"
          title={HANDOFF_NOTE}
        >
          {HANDOFF_LABEL}
        </button>
      )}
      <p id={handoffNoteId} className="mt-2 text-center text-[11px] text-(--ink-soft)/80">
        {HANDOFF_NOTE}
      </p>
    </section>
  );
}
