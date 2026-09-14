import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { LoginResult } from "@/lib/types";
import LoginSheet from "./LoginSheet";

const SUMMARY = { session_id: "s-1", user_id: "dk:48", signed_in: true, name: "A0020", tier: "Basic", country: null };

function setup(result: LoginResult | Promise<LoginResult>) {
  const onSubmit = vi.fn(async () => result);
  const onClose = vi.fn();
  render(<LoginSheet onSubmit={onSubmit} onClose={onClose} />);
  return { onSubmit, onClose, user: userEvent.setup() };
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, remember = false) {
  await user.type(screen.getByLabelText(/email/i), "ken@example.test");
  await user.type(screen.getByLabelText(/password/i), "secret");
  if (remember) await user.click(screen.getByLabelText(/keep me signed in/i));
  await user.click(screen.getByRole("button", { name: /^sign in$/i }));
}

describe("LoginSheet", () => {
  it("입력값과 remember 체크로 onSubmit을 부르고 성공하면 닫는다", async () => {
    const { onSubmit, onClose, user } = setup({ ok: true, summary: SUMMARY });
    await fillAndSubmit(user, true);
    expect(onSubmit).toHaveBeenCalledWith("ken@example.test", "secret", true);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("자격 증명 오류면 폼 안에 문구를 보이고 비밀번호를 비운다", async () => {
    const { onClose, user } = setup({ ok: false, reason: "invalid_credentials" });
    await fillAndSubmit(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(/don't match/i);
    expect(screen.getByLabelText(/password/i)).toHaveValue("");
    expect(screen.getByLabelText(/email/i)).toHaveValue("ken@example.test");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("게이트웨이 장애면 재시도 문구를 보인다", async () => {
    const { user } = setup({ ok: false, reason: "auth_unavailable" });
    await fillAndSubmit(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
  });

  it("제출 중에는 버튼이 비활성이다", async () => {
    let resolve: (value: LoginResult) => void = () => {};
    const pending = new Promise<LoginResult>((r) => {
      resolve = r;
    });
    const { user } = setup(pending);
    await fillAndSubmit(user);
    expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();
    resolve({ ok: true, summary: SUMMARY });
  });

  it("Escape로 닫는다", async () => {
    const { onClose, user } = setup({ ok: true, summary: SUMMARY });
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
