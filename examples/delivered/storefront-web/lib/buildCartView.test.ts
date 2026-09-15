import { describe, expect, it } from "vitest";
import { activeTotals, buildCartView, feeLabel, feeRows, lineStatus } from "./buildCartView";
import type { CartItem, CartPayload, DeliveredCartLine } from "./types";

const line = (over: Partial<DeliveredCartLine>): DeliveredCartLine => ({
  buy_request_id: 1,
  product_id: "smart_store:1",
  product_url: null,
  fees: [],
  line_total: 0,
  options: [],
  is_expired: false,
  is_selling: true,
  ...over,
});

const RACKET: CartItem = { product_id: "smart_store:1", title: "라켓", price: 30000, quantity: 2, line_total: 60000 };
const KEYBOARD: CartItem = { product_id: "bunjang:2", title: "키보드", price: 45000, quantity: 1, line_total: 45000 };
const ROPE: CartItem = { product_id: "smart_store:3", title: "줄넘기", price: 5000, quantity: 1, line_total: 5000 };

const RACKET_LINE = line({
  product_id: "smart_store:1",
  fees: [
    { fee_type: "UNIT_PRICE", cost_krw: 30000 },
    { fee_type: "DOMESTIC_SHIPPING_PRICE", cost_krw: 3000 },
  ],
  line_total: 63000,
  options: [{ name: "색상", value: "White" }],
});

const CART: CartPayload = {
  items: [RACKET, KEYBOARD, ROPE],
  item_count: 4,
  subtotal: 110000,
  currency: "KRW",
  delivered_cart: {
    groups: [
      {
        market_sub_type: "SMART_STORE",
        market_name: "스마트스토어",
        is_bundled: false,
        items: [RACKET_LINE, line({ product_id: "smart_store:missing" })],
      },
      {
        market_sub_type: "BUNJANG",
        market_name: "번개장터",
        is_bundled: true,
        items: [line({ product_id: "bunjang:2", line_total: 45000, is_expired: true, is_selling: false })],
      },
    ],
  },
};

describe("buildCartView", () => {
  it("delivered 그룹 순서대로 묶고, 그룹에 없는 항목은 마켓 없는 기본 그룹으로 보낸다", () => {
    const groups = buildCartView(CART);
    expect(groups.map((group) => group.marketName)).toEqual(["스마트스토어", "번개장터", null]);
    expect(groups[0].lines.map((view) => view.item.product_id)).toEqual(["smart_store:1"]);
    expect(groups[0].lines[0].total).toBe(63000);
    expect(groups[1].isBundled).toBe(true);
    expect(groups[2].lines[0].item).toBe(ROPE);
    expect(groups[2].lines[0].total).toBe(5000);
  });

  it("delivered_cart가 없으면 기본 그룹 하나에 모든 항목이 들어간다", () => {
    const groups = buildCartView({ items: [RACKET, ROPE], item_count: 3, subtotal: 65000, currency: "KRW" });
    expect(groups).toHaveLength(1);
    expect(groups[0].marketName).toBeNull();
    expect(groups[0].lines.map((view) => view.status)).toEqual([null, null]);
  });

  it("빈 카트나 null이면 그룹이 없다", () => {
    expect(buildCartView(null)).toEqual([]);
    expect(buildCartView({ items: [], item_count: 0, subtotal: 0, currency: "KRW" })).toEqual([]);
  });
});

describe("lineStatus", () => {
  it("만료가 판매 종료보다 앞서고, 줄 정보가 없으면 상태가 없다", () => {
    expect(lineStatus(line({ is_expired: true, is_selling: false }))).toBe("expired");
    expect(lineStatus(line({ is_selling: false }))).toBe("sold_out");
    expect(lineStatus(line({}))).toBeNull();
    expect(lineStatus(null)).toBeNull();
  });
});

describe("feeLabel", () => {
  it("delivered 요금 이름을 사람 말로 바꾸고 모르는 이름은 Title Case로 둔다", () => {
    expect(feeLabel("UNIT_PRICE")).toBe("Item price");
    expect(feeLabel("DOMESTIC_SHIPPING_PRICE")).toBe("Domestic shipping");
    expect(feeLabel("HANDLING_FEE")).toBe("Handling fee");
    expect(feeLabel("SOME_NEW_FEE")).toBe("Some New Fee");
  });
});

describe("feeRows", () => {
  it("상품가는 단가×수량이고 UNIT_PRICE가 아닌 요금이 뒤따른다", () => {
    expect(feeRows(RACKET, RACKET_LINE)).toEqual([
      { label: "Item price", amount: 60000 },
      { label: "Domestic shipping", amount: 3000 },
    ]);
  });

  it("원화가 없는 요금은 생략하고, 줄 정보가 없으면 상품가만 남는다", () => {
    const noKrw = line({ fees: [{ fee_type: "HANDLING_FEE", cost_krw: null, cost_usd: 2 }] });
    expect(feeRows(ROPE, noKrw)).toEqual([{ label: "Item price", amount: 5000 }]);
    expect(feeRows(ROPE, null)).toEqual([{ label: "Item price", amount: 5000 }]);
  });
});

describe("activeTotals", () => {
  it("만료·판매 종료 줄을 빼고 수량과 합계를 센다", () => {
    expect(activeTotals(buildCartView(CART))).toEqual({ count: 3, subtotal: 68000 });
    expect(activeTotals([])).toEqual({ count: 0, subtotal: 0 });
  });
});
