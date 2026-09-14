// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import type { AgentTurn, ChatItem, TraceEntry } from "web-shared";

export const SIGN_IN_MARKER = "로그인이 필요합니다";
const SIGN_IN_PATTERN = /로그인|sign[ -]?in|log[ -]?in/i;

export interface SignInPromptProps {
  chat: AgentTurn;
  signedIn: boolean;
  onSignIn: () => void;
}

export function needsSignIn(items: ChatItem[], trace: TraceEntry[]): boolean {
  const last = items[items.length - 1];
  if (!last || last.kind !== "assistant" || last.pending) return false;
  const inText = last.segments.some((segment) => segment.type === "text" && SIGN_IN_PATTERN.test(segment.text));
  const inTrace = trace.some(
    (entry) => entry.turn === last.turn && entry.isError === true && [entry.detail, entry.excerpt].some((value) => value?.includes(SIGN_IN_MARKER)),
  );
  return inText || inTrace;
}

export default function SignInPrompt({ chat, signedIn, onSignIn }: SignInPromptProps) {
  const visible = !signedIn && needsSignIn(chat.items, chat.trace);
  if (!visible) return null;
  return (
    <div className="mx-auto flex w-full max-w-[760px] justify-center px-4 pb-2 sm:px-6">
      <button type="button" onClick={onSignIn} className="chip">
        Sign in to continue
      </button>
    </div>
  );
}
