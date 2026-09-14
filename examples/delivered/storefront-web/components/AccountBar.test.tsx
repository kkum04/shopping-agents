import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AccountBar from "./AccountBar";

describe("AccountBar", () => {
  it("게스트면 안내 문구와 Sign in 버튼을 보이고 누르면 onSignIn", async () => {
    const onSignIn = vi.fn();
    render(<AccountBar shopper={{ name: "Guest" }} signedIn={false} busy={false} onSignIn={onSignIn} onSignOut={vi.fn()} />);
    expect(screen.getByText(/browsing as a guest/i)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /sign in/i }));
    expect(onSignIn).toHaveBeenCalled();
  });

  it("회원이면 이름·등급과 Sign out 버튼을 보이고 누르면 onSignOut", async () => {
    const onSignOut = vi.fn();
    render(<AccountBar shopper={{ name: "A0020", tier: "Basic" }} signedIn busy={false} onSignIn={vi.fn()} onSignOut={onSignOut} />);
    expect(screen.getByText(/signed in as A0020/i)).toHaveTextContent(/Basic/);
    await userEvent.setup().click(screen.getByRole("button", { name: /sign out/i }));
    expect(onSignOut).toHaveBeenCalled();
  });

  it("busy면 버튼이 비활성이다", () => {
    render(<AccountBar shopper={{ name: "A0020" }} signedIn busy onSignIn={vi.fn()} onSignOut={vi.fn()} />);
    expect(screen.getByRole("button", { name: /sign out/i })).toBeDisabled();
  });
});
