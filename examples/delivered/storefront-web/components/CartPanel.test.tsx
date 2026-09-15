import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { AgentTurn } from "web-shared";
import { FrameContext } from "web-shared/storefront/frame";
import { SHOWCASE_CART } from "@/lib/showcase-fixtures";
import type { CartPayload } from "@/lib/types";
import CartPanel from "./CartPanel";

vi.mock("@/lib/api", () => ({ fetchProducts: async () => [] }));

interface FrameProps {
  ask: (message: string) => void;
  busy: boolean;
  children: ReactNode;
}

function Frame({ ask, busy, children }: FrameProps) {
  const chat = { busy } as AgentTurn;
  return <FrameContext.Provider value={{ chat, assistantName: "delivered Assistant", ask, closePanel: () => {} }}>{children}</FrameContext.Provider>;
}

const lineOf = (title: RegExp) => screen.getByRole("listitem", { name: title });

describe("CartPanel — 마켓 그룹과 항목 정보", () => {
  it("마켓별 그룹 머리와 항목마다 마켓명을 보인다", () => {
    render(<CartPanel cart={SHOWCASE_CART} />);
    expect(screen.getByRole("heading", { level: 3, name: /스마트스토어/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: /번개장터/ })).toBeInTheDocument();
    expect(within(lineOf(/라켓/)).getByText("스마트스토어")).toBeInTheDocument();
    expect(within(lineOf(/키보드/)).getByText("번개장터")).toBeInTheDocument();
  });

  it("옵션 항목은 제목 아래에 옵션을 보인다", () => {
    render(<CartPanel cart={SHOWCASE_CART} />);
    expect(within(lineOf(/라켓/)).getByText("색상: White")).toBeInTheDocument();
  });

  it("만료 항목은 배지가 붙고 수량 변경 없이 삭제만 남으며 개수에서 빠진다", () => {
    render(<CartPanel cart={SHOWCASE_CART} />);
    const expired = lineOf(/키보드/);
    expect(within(expired).getByText("Expired")).toBeInTheDocument();
    expect(within(expired).queryByRole("button", { name: /increase/i })).toBeNull();
    expect(within(expired).getByRole("button", { name: /remove/i })).toBeInTheDocument();
    expect(within(lineOf(/라켓/)).getByRole("button", { name: /increase/i })).toBeInTheDocument();
    expect(screen.getByText("3 items")).toBeInTheDocument();
  });

  it("delivered 정보가 없는 카트는 그룹 머리 없이 한 목록으로 보인다", () => {
    const plain: CartPayload = {
      items: [{ product_id: "AR-1", title: "Block Set", price: 34, quantity: 1, line_total: 34 }],
      item_count: 1,
      subtotal: 34,
      currency: "USD",
    };
    render(<CartPanel cart={plain} />);
    expect(screen.queryByRole("heading", { level: 3 })).toBeNull();
    expect(lineOf(/block set/i)).toBeInTheDocument();
    expect(screen.getByText("1 item")).toBeInTheDocument();
  });
});

describe("CartPanel — 요금과 소계", () => {
  it("상품가와 국내 배송비를 따로 보이고 항목 합계는 delivered 합계다", () => {
    render(<CartPanel cart={SHOWCASE_CART} />);
    const racket = lineOf(/라켓/);
    expect(within(racket).getByText("Item price")).toBeInTheDocument();
    expect(within(racket).getByText("₩60,000")).toBeInTheDocument();
    expect(within(racket).getByText("Domestic shipping")).toBeInTheDocument();
    expect(within(racket).getByText("₩3,000")).toBeInTheDocument();
    expect(within(racket).getByText("₩63,000")).toBeInTheDocument();
    expect(within(lineOf(/줄넘기/)).queryByText("Domestic shipping")).toBeNull();
  });

  it("패널 소계는 만료 항목을 뺀 합계이고 delivered 정산 안내가 붙는다", () => {
    render(<CartPanel cart={SHOWCASE_CART} />);
    expect(screen.getByText("₩68,000")).toBeInTheDocument();
    expect(screen.queryByText("₩113,000")).toBeNull();
    expect(screen.getByText(/settled on delivered/i)).toBeInTheDocument();
  });
});

describe("CartPanel — 진행 중 상태", () => {
  it("대화가 없는 프레임(/showcase)에서는 눌러도 진행 중 상태를 만들지 않는다", async () => {
    render(<CartPanel cart={SHOWCASE_CART} />);
    await userEvent.setup().click(within(lineOf(/라켓/)).getByRole("button", { name: /increase/i }));
    expect(lineOf(/라켓/)).not.toHaveAttribute("aria-busy", "true");
    expect(within(lineOf(/라켓/)).queryByText(/updating/i)).toBeNull();
  });

  it("수량을 바꾸면 어시스턴트에게 메시지를 보내고 그 줄만 진행 중이 된다", async () => {
    const ask = vi.fn();
    render(
      <Frame ask={ask} busy={false}>
        <CartPanel cart={SHOWCASE_CART} />
      </Frame>,
    );
    await userEvent.setup().click(within(lineOf(/라켓/)).getByRole("button", { name: /increase/i }));
    expect(ask).toHaveBeenCalledWith(expect.stringMatching(/quantity to 3\.$/));
    const racket = lineOf(/라켓/);
    expect(racket).toHaveAttribute("aria-busy", "true");
    expect(within(racket).getByText(/updating/i)).toBeInTheDocument();
    expect(within(racket).getByRole("button", { name: /remove/i })).toBeDisabled();
    expect(within(lineOf(/줄넘기/)).getByRole("button", { name: /remove/i })).toBeEnabled();
  });

  it("카트가 새로 오면 진행 중 표시가 풀린다", async () => {
    const view = render(
      <Frame ask={vi.fn()} busy={false}>
        <CartPanel cart={SHOWCASE_CART} />
      </Frame>,
    );
    await userEvent.setup().click(within(lineOf(/라켓/)).getByRole("button", { name: /remove/i }));
    expect(lineOf(/라켓/)).toHaveAttribute("aria-busy", "true");
    view.rerender(
      <Frame ask={vi.fn()} busy={false}>
        <CartPanel cart={{ ...SHOWCASE_CART }} />
      </Frame>,
    );
    expect(lineOf(/라켓/)).not.toHaveAttribute("aria-busy", "true");
  });

  it("장바구니 갱신 없이 턴이 끝나도 진행 중 표시가 풀린다", async () => {
    const view = render(
      <Frame ask={vi.fn()} busy={false}>
        <CartPanel cart={SHOWCASE_CART} />
      </Frame>,
    );
    await userEvent.setup().click(within(lineOf(/라켓/)).getByRole("button", { name: /remove/i }));
    view.rerender(
      <Frame ask={vi.fn()} busy>
        <CartPanel cart={SHOWCASE_CART} />
      </Frame>,
    );
    expect(lineOf(/라켓/)).toHaveAttribute("aria-busy", "true");
    view.rerender(
      <Frame ask={vi.fn()} busy={false}>
        <CartPanel cart={SHOWCASE_CART} />
      </Frame>,
    );
    expect(lineOf(/라켓/)).not.toHaveAttribute("aria-busy", "true");
  });
});
