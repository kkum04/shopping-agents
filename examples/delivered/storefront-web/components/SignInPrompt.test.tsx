import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AgentTurn, ChatItem, TraceEntry } from "web-shared";
import { describe, expect, it, vi } from "vitest";
import SignInPrompt, { needsSignIn, SIGN_IN_MARKER } from "./SignInPrompt";

const assistant = (turn: number, text: string, pending = false): ChatItem => ({
  kind: "assistant",
  turn,
  segments: [{ type: "text", text }],
  suggestions: [],
  pending,
  tools: [],
});
const user = (text: string): ChatItem => ({ kind: "user", text });

describe("needsSignIn", () => {
  it("마지막 어시스턴트 턴 본문에 마커가 있으면 true", () => {
    expect(needsSignIn([user("담아줘"), assistant(1, `${SIGN_IN_MARKER}: 장바구니`)], [])).toBe(true);
  });

  it("모델이 다른 표현으로 로그인을 안내해도 true, 로그인 언급이 없으면 false", () => {
    expect(needsSignIn([assistant(1, "게스트 세션에서는 로그인 없이 장바구니에 담을 수 없습니다.")], [])).toBe(true);
    expect(needsSignIn([assistant(1, "Please sign in to use your cart.")], [])).toBe(true);
    expect(needsSignIn([assistant(1, "줄넘기 3개를 찾았어요.")], [])).toBe(false);
  });

  it("아직 스트리밍 중이거나 마지막이 사용자 턴이면 false", () => {
    expect(needsSignIn([assistant(1, SIGN_IN_MARKER, true)], [])).toBe(false);
    expect(needsSignIn([assistant(1, SIGN_IN_MARKER), user("네")], [])).toBe(false);
    expect(needsSignIn([], [])).toBe(false);
  });

  it("본문에는 없어도 같은 턴의 툴 오류 트레이스에 마커가 있으면 true", () => {
    const trace: TraceEntry[] = [{ kind: "tool_result", turn: 2, label: "add_to_cart", detail: `${SIGN_IN_MARKER}: 장바구니`, isError: true, at: 0 }];
    expect(needsSignIn([assistant(2, "I couldn't add that.")], trace)).toBe(true);
    expect(needsSignIn([assistant(3, "I couldn't add that.")], trace)).toBe(false);
  });
});

describe("SignInPrompt", () => {
  const chatWith = (items: ChatItem[]): AgentTurn => ({ items, trace: [] }) as unknown as AgentTurn;

  it("게스트이고 마커가 있으면 칩을 보이고 누르면 onSignIn", async () => {
    const onSignIn = vi.fn();
    render(<SignInPrompt chat={chatWith([assistant(1, SIGN_IN_MARKER)])} signedIn={false} onSignIn={onSignIn} />);
    await userEvent.setup().click(screen.getByRole("button", { name: /sign in to continue/i }));
    expect(onSignIn).toHaveBeenCalled();
  });

  it("로그인 상태면 그리지 않는다", () => {
    render(<SignInPrompt chat={chatWith([assistant(1, SIGN_IN_MARKER)])} signedIn onSignIn={vi.fn()} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
