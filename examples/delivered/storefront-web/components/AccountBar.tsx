// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { Button } from "web-shared";
import type { Shopper } from "@/lib/useDeliveredSession";

export interface AccountBarProps {
  shopper: Shopper;
  signedIn: boolean;
  busy: boolean;
  onSignIn: () => void;
  onSignOut: () => void;
}

const GUEST_LABEL = "Browsing as a guest · Sign in to use your delivered cart";

function memberLabel(shopper: Shopper): string {
  const tier = shopper.tier ? ` · ${shopper.tier}` : "";
  return `Signed in as ${shopper.name}${tier}`;
}

export default function AccountBar({ shopper, signedIn, busy, onSignIn, onSignOut }: AccountBarProps) {
  const label = signedIn ? memberLabel(shopper) : GUEST_LABEL;
  const action = signedIn ? onSignOut : onSignIn;
  const actionLabel = signedIn ? "Sign out" : "Sign in";
  const variant = signedIn ? "secondary" : "primary";

  return (
    <div className="flex shrink-0 items-center justify-between gap-3 border-b border-(--line) bg-(--card) px-4 py-2 text-[13px] text-(--ink-2) sm:px-5">
      <span className="min-w-0 truncate">{label}</span>
      <Button size="sm" variant={variant} disabled={busy} onClick={action}>
        {actionLabel}
      </Button>
    </div>
  );
}
