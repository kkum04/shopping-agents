// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { type ChangeEvent, type FormEvent, useCallback, useState } from "react";
import { Button, Sheet } from "web-shared";
import type { LoginFailureReason, LoginResult } from "@/lib/types";

export interface LoginSheetProps {
  onSubmit: (email: string, password: string, rememberMe: boolean) => Promise<LoginResult>;
  onClose: () => void;
}

const FAILURE_MESSAGES: Record<LoginFailureReason, string> = {
  invalid_credentials: "That email and password don't match.",
  auth_unavailable: "delivered sign-in is unavailable right now. Try again in a moment.",
  network: "delivered sign-in is unavailable right now. Try again in a moment.",
};

const FIELD_CLASS =
  "w-full rounded-[10px] border border-(--line-strong) bg-(--card) px-3 py-2 text-[14px] text-(--ink) outline-none focus:border-(--ink)";

export default function LoginSheet({ onSubmit, onClose }: LoginSheetProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEmailChange = useCallback((event: ChangeEvent<HTMLInputElement>) => setEmail(event.target.value), []);
  const handlePasswordChange = useCallback((event: ChangeEvent<HTMLInputElement>) => setPassword(event.target.value), []);
  const handleRememberChange = useCallback((event: ChangeEvent<HTMLInputElement>) => setRememberMe(event.target.checked), []);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (submitting) return;
      setSubmitting(true);
      setError(null);
      const result = await onSubmit(email, password, rememberMe);
      setSubmitting(false);
      if (result.ok) {
        onClose();
        return;
      }
      setError(FAILURE_MESSAGES[result.reason]);
      setPassword("");
    },
    [email, onClose, onSubmit, password, rememberMe, submitting],
  );

  const buttonLabel = submitting ? "Signing in…" : "Sign in";

  return (
    <Sheet title="Sign in to delivered" onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <p className="text-[14px] leading-relaxed text-(--ink-soft)">Use your delivered account to keep what the assistant finds in your own cart.</p>
        <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-(--ink)">
          Email
          <input type="email" name="email" value={email} onChange={handleEmailChange} autoComplete="email" autoFocus required disabled={submitting} className={FIELD_CLASS} />
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-(--ink)">
          Password
          <input type="password" name="password" value={password} onChange={handlePasswordChange} autoComplete="current-password" required disabled={submitting} className={FIELD_CLASS} />
        </label>
        <label className="flex items-center gap-2 text-[13px] text-(--ink-2)">
          <input type="checkbox" name="remember" checked={rememberMe} onChange={handleRememberChange} disabled={submitting} />
          Keep me signed in
        </label>
        {error ? (
          <p role="alert" className="rounded-[10px] bg-(--warn-soft) px-3 py-2 text-[13px] text-(--warn)">
            {error}
          </p>
        ) : null}
        <Button type="submit" variant="primary" disabled={submitting}>
          {buttonLabel}
        </Button>
      </form>
    </Sheet>
  );
}
