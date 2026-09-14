// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { type ReactNode, useCallback } from "react";
import { ActivityLine, type AgentTurn, type AssistantChatItem, Chat as ChatShell } from "web-shared";
import { addToCart } from "@/lib/api";
import type { CartPayload, Product } from "@/lib/types";
import GenerativeBlock from "./generative";
import SignInPrompt from "./SignInPrompt";

const WIDE = new Set(["comparison", "plan"]);

/** Shimmers where the carousel will land while a search runs. */
function Pending({ item }: { item: AssistantChatItem }) {
  const searching = item.tools.includes("search_products") && !item.segments.some((s) => s.type === "ui");
  if (!searching) return <ActivityLine item={item} />;
  return (
    <section role="status" className="rounded-2xl border border-(--line) bg-(--card) p-3 shadow-(--shadow-sm)">
      <div className="mb-3 animate-pulse text-[15px] text-(--ink-soft)">{item.activity ?? "Searching the catalog…"}</div>
      <div className="flex gap-3 overflow-hidden pb-1">
        {[0, 1, 2, 3].map((slot) => (
          <div key={slot} className="ac-skeleton h-[150px] w-48 shrink-0 rounded-xl" />
        ))}
      </div>
    </section>
  );
}

export interface ChatProps {
  chat: AgentTurn;
  home: ReactNode;
  signedIn: boolean;
  onCartUpdate: (cart: CartPayload) => void;
  onSignIn: () => void;
}

export default function Chat({ chat, home, signedIn, onCartUpdate, onSignIn }: ChatProps) {
  const handleAdd = useCallback(
    async (product: Product) => {
      const cart = await addToCart(product.product_id);
      if (cart) onCartUpdate(cart);
      else if (!signedIn) onSignIn();
      return cart !== null;
    },
    [onCartUpdate, onSignIn, signedIn],
  );
  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1">
        <ChatShell
          chat={chat}
          home={home}
          wide={WIDE}
          renderPending={(item) => <Pending item={item} />}
          renderBlock={(segment) => <GenerativeBlock block={segment.block} status={segment.status} onAdd={handleAdd} />}
        />
      </div>
      <SignInPrompt chat={chat} signedIn={signedIn} onSignIn={onSignIn} />
    </div>
  );
}
