// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { useCallback, useEffect, useState } from "react";
import type { AgentApi } from "web-shared";
import { clearStoredSessionId, fetchSessionMe, login as requestLogin, logout as requestLogout, readStoredSessionId, writeStoredSessionId } from "./session";
import type { LoginResult, SessionSummary } from "./types";

export interface Shopper {
  name: string;
  tier?: string;
}

export interface DeliveredSession {
  sessionId: string | null;
  shopper: Shopper;
  signedIn: boolean;
  busy: boolean;
  login: (email: string, password: string, rememberMe: boolean) => Promise<LoginResult>;
  logout: () => Promise<void>;
}

const GUEST: Shopper = { name: "Guest" };
const generations = new WeakMap<AgentApi, number>();

function shopperOf(summary: SessionSummary | null): Shopper {
  if (!summary?.signed_in) return GUEST;
  return { name: summary.name, tier: summary.tier ?? undefined };
}

export function useDeliveredSession(api: AgentApi): DeliveredSession {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const generation = (generations.get(api) ?? 0) + 1;
    generations.set(api, generation);
    const current = () => generations.get(api) === generation;
    void (async () => {
      const stored = readStoredSessionId();
      if (stored) {
        api.session = stored;
        const restored = await fetchSessionMe(api);
        if (!current()) return;
        if (restored) {
          setSessionId(restored.session_id);
          setSummary(restored);
          return;
        }
      }
      api.session = null;
      const started = await api.startSession();
      if (!current()) return;
      const startedId = started?.sessionId ?? null;
      api.session = startedId;
      if (startedId) writeStoredSessionId(startedId);
      else clearStoredSessionId();
      setSessionId(startedId);
      setSummary(null);
    })();
    return () => {
      generations.set(api, (generations.get(api) ?? 0) + 1);
    };
  }, [api]);

  const login = useCallback(
    async (email: string, password: string, rememberMe: boolean): Promise<LoginResult> => {
      setBusy(true);
      try {
        const result = await requestLogin(api, { email, password, remember_me: rememberMe });
        if (result.ok) {
          api.session = result.summary.session_id;
          writeStoredSessionId(result.summary.session_id);
          setSessionId(result.summary.session_id);
          setSummary(result.summary);
        }
        return result;
      } finally {
        setBusy(false);
      }
    },
    [api],
  );

  const logout = useCallback(async (): Promise<void> => {
    setBusy(true);
    try {
      const next = await requestLogout(api);
      if (next) setSummary(next);
    } finally {
      setBusy(false);
    }
  }, [api]);

  return { sessionId, shopper: shopperOf(summary), signedIn: summary?.signed_in ?? false, busy, login, logout };
}
