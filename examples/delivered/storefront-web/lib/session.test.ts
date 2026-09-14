import { AgentApi } from "web-shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearStoredSessionId,
  fetchSessionMe,
  login,
  logout,
  readStoredSessionId,
  SESSION_STORAGE_KEY,
  writeStoredSessionId,
} from "./session";
import type { SessionSummary } from "./types";

const SUMMARY: SessionSummary = {
  session_id: "s-1",
  user_id: "dk:48",
  signed_in: true,
  name: "A0020",
  tier: "Basic",
  country: null,
};

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("login", () => {
  const fetchMock = vi.fn<typeof fetch>();
  let api: AgentApi;

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    api = new AgentApi("http://api.test", "/api");
    api.session = "s-1";
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("200이면 요약을 돌려주고 세션 헤더와 remember_me를 함께 보낸다", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, SUMMARY));
    const result = await login(api, { email: "ken@example.test", password: "pw", remember_me: true });
    expect(result).toEqual({ ok: true, summary: SUMMARY });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/session/login");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({ "X-Session-Id": "s-1", "Content-Type": "application/json" });
    expect(JSON.parse(String(init?.body))).toEqual({ email: "ken@example.test", password: "pw", remember_me: true });
  });

  it("401이면 invalid_credentials", async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: "invalid_credentials" }));
    await expect(login(api, { email: "a@b.c", password: "x", remember_me: false })).resolves.toEqual({ ok: false, reason: "invalid_credentials" });
  });

  it("422(본문 검증 실패)도 invalid_credentials", async () => {
    fetchMock.mockResolvedValue(jsonResponse(422, { detail: [] }));
    await expect(login(api, { email: "a", password: "", remember_me: false })).resolves.toEqual({ ok: false, reason: "invalid_credentials" });
  });

  it("502면 auth_unavailable", async () => {
    fetchMock.mockResolvedValue(jsonResponse(502, { detail: "auth_unavailable" }));
    await expect(login(api, { email: "a@b.c", password: "x", remember_me: false })).resolves.toEqual({ ok: false, reason: "auth_unavailable" });
  });

  it("네트워크 예외면 network", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(login(api, { email: "a@b.c", password: "x", remember_me: false })).resolves.toEqual({ ok: false, reason: "network" });
  });
});

describe("fetchSessionMe / logout", () => {
  const fetchMock = vi.fn<typeof fetch>();
  let api: AgentApi;

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    api = new AgentApi("http://api.test", "/api");
    api.session = "s-1";
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("me가 404면 null", async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: "unknown session" }));
    await expect(fetchSessionMe(api)).resolves.toBeNull();
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/api/session/me");
  });

  it("me가 200이면 요약", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, SUMMARY));
    await expect(fetchSessionMe(api)).resolves.toEqual(SUMMARY);
  });

  it("logout은 게스트 요약을 돌려준다", async () => {
    const guest = { ...SUMMARY, signed_in: false, name: "Guest", tier: null };
    fetchMock.mockResolvedValue(jsonResponse(200, guest));
    await expect(logout(api)).resolves.toEqual(guest);
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/api/session/logout");
  });
});

describe("세션 id 저장소", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it("쓰고 읽고 지운다", () => {
    writeStoredSessionId("s-9");
    expect(window.sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe("s-9");
    expect(readStoredSessionId()).toBe("s-9");
    clearStoredSessionId();
    expect(readStoredSessionId()).toBeNull();
  });

  it("저장소 접근이 막혀 있으면 예외 없이 null", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => writeStoredSessionId("s-9")).not.toThrow();
    expect(readStoredSessionId()).toBeNull();
  });
});
