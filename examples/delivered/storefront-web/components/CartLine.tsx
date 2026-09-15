// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { Fragment, useCallback } from "react";
import { formatMoney, optionValuesLabel, Pill, RemoveLink, Stepper } from "web-shared";
import { feeRows } from "@/lib/buildCartView";
import type { CartLineView } from "@/lib/buildCartView";
import type { Product } from "@/lib/types";
import { ProductImage, ProductTitle } from "./ProductTile";

interface CartLineProps {
  view: CartLineView;
  product: Product;
  marketName: string | null;
  currency: string;
  pending: boolean;
  onQuantityChange: (productId: string, quantity: number) => void;
  onRemove: (productId: string) => void;
}

const STATUS_LABELS = { expired: "Expired", sold_out: "Sold out" } as const;

export const optionsLabel = (view: CartLineView): string => {
  const chosen = view.line?.options ?? [];
  if (chosen.length) return chosen.map((option) => `${option.name}: ${option.value}`).join(" · ");
  return optionValuesLabel(view.item) ?? "";
};

export const lineName = (view: CartLineView): string => {
  const chosen = optionsLabel(view);
  return chosen ? `${view.item.title} (${chosen})` : view.item.title;
};

export default function CartLine({ view, product, marketName, currency, pending, onQuantityChange, onRemove }: CartLineProps) {
  const { item, line, status, total } = view;
  const rows = feeRows(item, line);
  const chosen = optionsLabel(view);
  const name = lineName(view);
  const dimmed = pending || status !== null;

  const handleQuantityChange = useCallback((quantity: number) => onQuantityChange(item.product_id, quantity), [item.product_id, onQuantityChange]);
  const handleRemove = useCallback(() => onRemove(item.product_id), [item.product_id, onRemove]);

  return (
    <li aria-label={item.title} aria-busy={pending || undefined} className={`ac-reveal flex gap-3 py-3 first:pt-0 ${dimmed ? "opacity-60" : ""}`}>
      <ProductImage product={product} className="h-16 w-16 shrink-0 rounded-[10px] !text-3xl" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 flex-col gap-0.5">
            {product.brand ? <div className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">{product.brand}</div> : null}
            <ProductTitle title={item.title} className="line-clamp-3 text-[13.5px] font-semibold leading-snug text-(--ink)" />
            {chosen ? <div className="text-[11.5px] text-(--ink-soft)">{chosen}</div> : null}
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-(--ink-soft)">
              {marketName ? <span>{marketName}</span> : null}
              {status ? <Pill tone="warn">{STATUS_LABELS[status]}</Pill> : null}
              {pending ? <span className="font-semibold text-(--ink-2)">Updating…</span> : null}
            </div>
          </div>
          <div className="shrink-0 text-right text-[14px] font-bold tabular-nums text-(--ink)">{formatMoney(total, currency, { whole: true })}</div>
        </div>
        <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 text-[11.5px] text-(--ink-soft)">
          {rows.map((row) => (
            <Fragment key={row.label}>
              <dt>{row.label}</dt>
              <dd className="text-right tabular-nums">{formatMoney(row.amount, currency, { whole: true })}</dd>
            </Fragment>
          ))}
        </dl>
        <fieldset disabled={pending} className="flex items-center gap-2.5">
          {status ? null : <Stepper quantity={item.quantity} itemTitle={name} onChange={handleQuantityChange} />}
          <RemoveLink itemTitle={name} onClick={handleRemove} />
          {line?.product_url ? (
            <a href={line.product_url} target="_blank" rel="noopener noreferrer" className="ml-auto text-[12px] text-(--accent-ink) underline-offset-2 hover:underline">
              View on {marketName ?? "delivered"}
            </a>
          ) : null}
        </fieldset>
      </div>
    </li>
  );
}
