// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** The cart page's view of a `CartPayload`: delivered's market groups joined to the framework's lines. */

import type { CartItem, CartPayload, DeliveredCartLine } from "./types";

export type CartLineStatus = "expired" | "sold_out" | null;

export interface FeeRow {
  label: string;
  amount: number;
}

export interface CartLineView {
  item: CartItem;
  line: DeliveredCartLine | null;
  status: CartLineStatus;
  total: number;
}

export interface CartGroupView {
  key: string;
  marketName: string | null;
  isBundled: boolean;
  lines: CartLineView[];
}

export interface CartTotals {
  count: number;
  subtotal: number;
}

const UNIT_PRICE_FEE = "UNIT_PRICE";
const UNGROUPED_KEY = "cart";
const FEE_LABELS: Record<string, string> = {
  UNIT_PRICE: "Item price",
  DOMESTIC_SHIPPING_PRICE: "Domestic shipping",
  HANDLING_FEE: "Handling fee",
};

const titleCase = (feeType: string): string =>
  feeType
    .toLowerCase()
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");

export const lineStatus = (line: DeliveredCartLine | null | undefined): CartLineStatus => {
  if (!line) return null;
  if (line.is_expired) return "expired";
  if (!line.is_selling) return "sold_out";
  return null;
};

export const feeLabel = (feeType: string): string => FEE_LABELS[feeType] ?? titleCase(feeType);

/** The item price (unit × quantity) first, then every other fee delivered priced in won. */
export const feeRows = (item: CartItem, line: DeliveredCartLine | null | undefined): FeeRow[] => {
  const rows: FeeRow[] = [{ label: FEE_LABELS[UNIT_PRICE_FEE], amount: item.price * item.quantity }];
  for (const fee of line?.fees ?? []) {
    if (fee.fee_type === UNIT_PRICE_FEE || fee.cost_krw == null) continue;
    rows.push({ label: feeLabel(fee.fee_type), amount: fee.cost_krw });
  }
  return rows;
};

const toLineView = (item: CartItem, line: DeliveredCartLine | null): CartLineView => ({
  item,
  line,
  status: lineStatus(line),
  total: line?.line_total ?? item.line_total,
});

/** delivered's groups in their order, each line joined to its `CartItem`; lines delivered did not group (or a cart without delivered data) close the list as one group without a market. */
export const buildCartView = (cart: CartPayload | null): CartGroupView[] => {
  if (!cart || cart.items.length === 0) return [];
  const itemsById = new Map(cart.items.map((item) => [item.product_id, item]));
  const grouped = new Set<string>();
  const groups: CartGroupView[] = [];
  (cart.delivered_cart?.groups ?? []).forEach((group, index) => {
    const lines: CartLineView[] = [];
    for (const line of group.items) {
      const item = itemsById.get(line.product_id);
      if (!item || grouped.has(line.product_id)) continue;
      grouped.add(line.product_id);
      lines.push(toLineView(item, line));
    }
    if (lines.length === 0) return;
    groups.push({
      key: `${group.market_sub_type ?? "market"}-${index}`,
      marketName: group.market_name ?? null,
      isBundled: group.is_bundled,
      lines,
    });
  });
  const rest = cart.items.filter((item) => !grouped.has(item.product_id)).map((item) => toLineView(item, null));
  if (rest.length) groups.push({ key: UNGROUPED_KEY, marketName: null, isBundled: false, lines: rest });
  return groups;
};

/** Quantity and won total of the lines that can still be bought. */
export const activeTotals = (groups: CartGroupView[]): CartTotals => {
  let count = 0;
  let subtotal = 0;
  for (const group of groups) {
    for (const view of group.lines) {
      if (view.status) continue;
      count += view.item.quantity;
      subtotal += view.total;
    }
  }
  return { count, subtotal };
};
