// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import type { AgentApi } from "web-shared";
import type { LoginRequest, LoginResult, SessionSummary } from "./types";

export const SESSION_STORAGE_KEY = "delivered.sessionId";

export function readStoredSessionId(): string | null {
  try {
    return window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function writeStoredSessionId(sessionId: string): void {
  try {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  } catch {
    return;
  }
}

export function clearStoredSessionId(): void {
  try {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    return;
  }
}

export function fetchSessionMe(api: AgentApi): Promise<SessionSummary | null> {
  return api.get<SessionSummary>("/session/me");
}

export async function login(api: AgentApi, request: LoginRequest): Promise<LoginResult> {
  try {
    const response = await fetch(`${api.base}/session/login`, {
      method: "POST",
      headers: api.headers(true),
      body: JSON.stringify(request),
    });
    if (response.ok) return { ok: true, summary: (await response.json()) as SessionSummary };
    if (response.status === 401 || response.status === 422) return { ok: false, reason: "invalid_credentials" };
    if (response.status === 502) return { ok: false, reason: "auth_unavailable" };
    return { ok: false, reason: "network" };
  } catch {
    return { ok: false, reason: "network" };
  }
}

export function logout(api: AgentApi): Promise<SessionSummary | null> {
  return api.post<SessionSummary>("/session/logout");
}
