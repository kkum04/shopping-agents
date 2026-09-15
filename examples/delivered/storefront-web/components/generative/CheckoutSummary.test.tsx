import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SHOWCASE } from "@/lib/showcase-fixtures";
import CheckoutSummary from "./CheckoutSummary";

vi.mock("@/lib/api", () => ({ fetchProducts: async () => [] }));

describe("CheckoutSummary — delivered로 넘어가기", () => {
  it("핸드오프가 있으면 delivered 웹 장바구니를 새 창으로 여는 링크를 보인다", () => {
    render(<CheckoutSummary payload={SHOWCASE.checkout} />);
    const link = screen.getByRole("link", { name: /continue on delivered/i });
    expect(link).toHaveAttribute("href", "https://www.delivered.co.kr/cart");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText(/payment happens on delivered/i)).toBeInTheDocument();
  });

  it("핸드오프가 없으면 비활성 버튼으로 남는다", () => {
    render(<CheckoutSummary payload={{ ...SHOWCASE.checkout, handoffs: [] }} />);
    expect(screen.getByRole("button", { name: /continue on delivered/i })).toBeDisabled();
    expect(screen.queryByRole("link", { name: /continue on delivered/i })).toBeNull();
  });

  it("항목마다 마켓명을, 만료 항목에는 표시를, 합계는 활성 항목만으로 보인다", () => {
    render(<CheckoutSummary payload={SHOWCASE.checkout} />);
    expect(screen.getAllByText("스마트스토어")).toHaveLength(2);
    expect(screen.getByText("Expired")).toBeInTheDocument();
    expect(screen.getByText("Estimated total")).toBeInTheDocument();
    expect(screen.getByText("₩68,000")).toBeInTheDocument();
    expect(screen.queryByText("Tax")).toBeNull();
    expect(screen.getByText(/domestic shipping & fees/i)).toBeInTheDocument();
  });
});
