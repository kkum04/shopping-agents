import { act, renderHook, waitFor } from "@testing-library/react";
import { AgentApi } from "web-shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SESSION_STORAGE_KEY } from "./session";
import type { SessionSummary } from "./types";
import { useDeliveredSession } from "./useDeliveredSession";

const MEMBER: SessionSummary = { session_id: "s-old", user_id: "dk:48", signed_in: true, name: "A0020", tier: "Basic", country: null };
const GUEST: SessionSummary = { session_id: "s-old", user_id: "demo-user", signed_in: false, name: "Guest", tier: null, country: null };

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

interface Route {
  method: string;
  path: string;
  status: number;
  body: unknown;
}

function routeFetch(routes: Route[]) {
  return vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const route = routes.find((r) => r.method === method && url.endsWith(r.path));
    if (!route) return jsonResponse(500, { detail: `unexpected ${method} ${url}` });
    return jsonResponse(route.status, route.body);
  });
}

describe("useDeliveredSession", () => {
  let api: AgentApi;

  beforeEach(() => {
    api = new AgentApi("http://api.test", "/api");
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("저장된 id가 없으면 게스트 세션을 시작하고 id를 저장한다", async () => {
    const fetchMock = routeFetch([{ method: "POST", path: "/api/session", status: 200, body: { session_id: "s-new", user_id: "demo-user", name: "Guest", tier: null } }]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useDeliveredSession(api));
    await waitFor(() => expect(result.current.sessionId).toBe("s-new"));
    expect(result.current.shopper).toEqual({ name: "Guest" });
    expect(result.current.signedIn).toBe(false);
    expect(window.sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe("s-new");
    expect(api.session).toBe("s-new");
  });

  it("저장된 id로 me가 성공하면 그 세션을 이어간다", async () => {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, "s-old");
    const fetchMock = routeFetch([{ method: "GET", path: "/api/session/me", status: 200, body: MEMBER }]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useDeliveredSession(api));
    await waitFor(() => expect(result.current.signedIn).toBe(true));
    expect(result.current.sessionId).toBe("s-old");
    expect(result.current.shopper).toEqual({ name: "A0020", tier: "Basic" });
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/api/session"))).toBe(false);
  });

  it("저장된 id를 서버가 모르면 새 게스트 세션으로 바꾼다", async () => {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, "s-gone");
    const fetchMock = routeFetch([
      { method: "GET", path: "/api/session/me", status: 404, body: { detail: "unknown" } },
      { method: "POST", path: "/api/session", status: 200, body: { session_id: "s-new", user_id: "demo-user", name: "Guest", tier: null } },
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useDeliveredSession(api));
    await waitFor(() => expect(result.current.sessionId).toBe("s-new"));
    expect(result.current.signedIn).toBe(false);
    expect(window.sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe("s-new");
  });

  it("login 성공이면 요약을 적용하고 실패면 상태를 바꾸지 않는다", async () => {
    const fetchMock = routeFetch([
      { method: "POST", path: "/api/session", status: 200, body: { session_id: "s-old", user_id: "demo-user", name: "Guest", tier: null } },
      { method: "POST", path: "/api/session/login", status: 401, body: { detail: "invalid_credentials" } },
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useDeliveredSession(api));
    await waitFor(() => expect(result.current.sessionId).toBe("s-old"));

    const failed = await act(() => result.current.login("a@b.c", "wrong", false));
    expect(failed).toEqual({ ok: false, reason: "invalid_credentials" });
    expect(result.current.signedIn).toBe(false);

    fetchMock.mockImplementation(async (input, init) => {
      if (String(input).endsWith("/api/session/login") && init?.method === "POST") return jsonResponse(200, MEMBER);
      return jsonResponse(500, {});
    });
    const ok = await act(() => result.current.login("ken@example.test", "pw", true));
    expect(ok.ok).toBe(true);
    await waitFor(() => expect(result.current.signedIn).toBe(true));
    expect(result.current.shopper).toEqual({ name: "A0020", tier: "Basic" });
    expect(result.current.sessionId).toBe("s-old");
    expect(api.session).toBe("s-old");
  });

  it("logout이면 같은 세션에서 게스트로 돌아간다", async () => {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, "s-old");
    const fetchMock = routeFetch([
      { method: "GET", path: "/api/session/me", status: 200, body: MEMBER },
      { method: "POST", path: "/api/session/logout", status: 200, body: GUEST },
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useDeliveredSession(api));
    await waitFor(() => expect(result.current.signedIn).toBe(true));
    await act(() => result.current.logout());
    expect(result.current.signedIn).toBe(false);
    expect(result.current.shopper).toEqual({ name: "Guest" });
    expect(result.current.sessionId).toBe("s-old");
  });
});
