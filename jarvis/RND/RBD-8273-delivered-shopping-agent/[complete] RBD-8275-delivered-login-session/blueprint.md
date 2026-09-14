---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: blueprint
completed: [mission, blueprint]
plan: [tasks, develop]
skip: []
depth: deep
base_sha: 3285abf
gates:
  open_q: 0
risk:
  self: 0.24
  review: passed  # 격리 검증 2026-09-11: ✅15 · ⚠️2(non-blocking) → 문서 보강으로 해소
design:
  new_api: true                 # POST /api/session/login, /logout, GET /api/session/me
  db_migration: false
  cross_domain: 1               # examples/delivered 안에서만 변경 — demo_common·core는 손대지 않는다
  tx_boundary: true             # 외부 인증 게이트웨이·고객 API 연동
  files_touched: 9
integrations:
  - service: delivered-auth-gateway
    prop_key: DELIVERED_AUTH_URL
    endpoints: ["POST /auth/sign-in/dk-service/customer"]
    on_failure: propagate       # 401/404 → 로그인 401, 5xx·타임아웃 → 로그인 502; 세션에 토큰을 남기지 않는다
    verified: true              # 2026-09-14 스테이징 실제 로그인으로 확인
  - service: delivered-customer-api
    prop_key: DELIVERED_CUSTOMER_API_URL
    endpoints: ["GET /v2/me"]
    on_failure: absorb          # 'Expired Token' → 토큰 폐기 + 게스트 지속 + 재로그인 안내; 그 외 5xx → 툴 "일시 불가"
    verified: true              # 2026-09-14 실제 토큰으로 확인 — 응답은 {result, data} 엔벨로프
domain_cache:
  squad: RND
  keywords: [로그인, 세션, 토큰, Bearer, 고객 API, 게스트, 프로필, 만료, 자격증명 저장소]
  modules:
    - examples/delivered/api/delivered_auth.py
    - examples/delivered/api/session_routes.py
    - examples/delivered/api/delivered_executor.py
    - examples/delivered/api/delivered_backend.py
    - examples/delivered/api/main.py
coverage:
  - ac: AC1
    modules: [examples/delivered/api/session_routes.py, examples/delivered/api/delivered_auth.py]
  - ac: AC2
    modules: [examples/delivered/api/delivered_auth.py, examples/delivered/api/delivered_backend.py]
  - ac: AC3
    modules: [examples/delivered/api/delivered_auth.py, examples/delivered/api/session_routes.py, examples/delivered/api/tests/test_delivered_auth.py]
  - ac: AC4
    modules: [examples/delivered/api/delivered_backend.py, examples/delivered/api/delivered_executor.py]
  - ac: AC5
    modules: [examples/delivered/api/delivered_auth.py, examples/delivered/api/delivered_backend.py, examples/delivered/api/delivered_executor.py]
  - ac: AC6
    modules: [examples/delivered/api/delivered_backend.py, examples/delivered/api/agent_config.py]
  - ac: AC7
    modules: [examples/delivered/api/tests/test_delivered_auth.py, examples/delivered/api/tests/test_session_routes.py]
---

# Blueprint: [shopping-agents] delivered 로그인 연동 — 세션에 토큰 보관, 고객 API Bearer 호출 (1)

> Mission: ./mission.md | Jira: RBD-8275

## Tech Stack

- **Language**: Python 3.11+ (venv 3.12)
- **Framework**: FastAPI 0.141 + uvicorn (데모 호스트), httpx 0.28 (게이트웨이 호출), pydantic 2 (요청/응답 모델)
- **Test**: pytest + pytest-asyncio(auto), `httpx.MockTransport`, `fastapi.testclient.TestClient`
- **기타**: commerce-agents 프레임워크 — `StorefrontBackend`, `ShoppingToolExecutor`(`executor_class` seam), `build_storefront_host`

## Architecture Overview

코드 변경은 전부 `examples/delivered/` 안에서 끝난다(예외는 저장소 루트 `.env.example`의 주석 두 줄뿐). 공용 `demo_common`(세션 저장소·라우트)과 프레임워크 core는 수정하지 않는다 — 두 곳의 계약 테스트가 다른 버티컬에도 걸려 있고, 자격증명은 "배포가 세션 옆에 두는 것"이라는 프레임워크 규약(`docs/backends.md` Step 1)에 따라 배포 코드에 두는 것이 맞다.

```text
스토어프론트(FE)                      delivered API (examples/delivered/api)                   delivered
  POST /api/session/login ─────────▶ session_routes.login ──▶ DeliveredAuthClient.sign_in ──▶ {AUTH}/auth/sign-in/...
        X-Session-Id?                     │                       └─ get_me(token) ─────────▶ {CUSTOMER}/v2/me
                                          ▼
                                   CredentialStore[session_id] = SessionCredential(tokens, profile)   ← 서버 메모리, 상태 문서 밖
                                          ▲
  POST /api/chat ────────────────▶ ShoppingAgent(executor_class=DeliveredToolExecutor)
                                          │  _prefetch → backend.get_preferences / get_account_context (CredentialStore 조회)
                                          │  tool call → backend.<cart write> → require_credential() ── 없음 → SignInRequired
                                          │                                   └─ customer_request(token) ── 'Expired Token' → drop + TokenExpired
                                          ▼
                                   DeliveredToolExecutor.domain_error: SignInRequired/TokenExpired → 모델용 문장 (토큰 없음)
```

핵심 결정 세 가지:

1. **토큰은 `CredentialStore`(세션 ID → `SessionCredential`)에만 둔다.** `SessionRecord.state_document`와 트랜스크립트(`messages`)는 매 요청 끝에 저장소에 쓰이고 DEBUG 로그에 본문이 찍히므로 토큰 자리가 아니며, 라우트 응답(`SessionSummary`)에도 토큰 필드를 두지 않는다. 백엔드 메서드는 `session.session_id`로 저장소를 조회하므로 `ShoppingSessionContext`를 확장할 필요가 없다.
2. **로그인은 같은 세션에 붙는다.** `POST /api/session/login`에 `X-Session-Id`가 오면 그 `SessionRecord`의 `user_id`를 `dk:{customerId}`로 바꿔 저장하고 자격증명을 붙인다(대화·본 상품 provenance 유지). 헤더가 없으면 새 세션을 만든다. 세션 시작 응답(`POST /api/session`)은 공용 라우트라 손대지 않고, 프로필 요약은 `GET /api/session/me`와 로그인·로그아웃 응답이 제공한다.
3. **게스트 거절과 만료는 예외로 흐른다.** 백엔드가 `SignInRequired`/`TokenExpired`를 던지고, `DeliveredToolExecutor.domain_error`가 프레임워크의 `unavailable_text` 대신 로그인 안내 문장으로 relay한다(`TicketingToolExecutor`와 같은 패턴). 토큰·비밀번호는 예외 메시지에 넣지 않는다.

## Directory Structure

```text
examples/delivered/
├── api/
│   ├── delivered_auth.py          # 신규 — DeliveredAuthClient, SessionCredential, CredentialStore, 예외 4종, 환경변수 기본값
│   ├── delivered_executor.py      # 신규 — DeliveredToolExecutor(domain_error: SignInRequired / TokenExpired)
│   ├── session_routes.py          # 신규 — register_session_routes(app, host, backend): /api/session/login·logout·me
│   ├── delivered_backend.py       # 수정 — CredentialStore 주입, get_preferences/get_account_context, require_credential, 장바구니 쓰기 게이트
│   ├── agent_config.py            # 수정 — DOMAIN_SEARCH_NOTES에 로그인 상태 안내 한 줄
│   ├── main.py                    # 수정 — auth 클라이언트·저장소 조립, executor_class, register_session_routes
│   └── tests/
│       ├── test_delivered_auth.py     # 신규 — FakeAuthGateway(MockTransport): sign_in 200/401/500/timeout, me, expired, CredentialStore redaction
│       └── test_session_routes.py     # 신규 — TestClient로 login/logout/me + 게스트 거절·만료 executor relay (네트워크 없음)
├── README.md                      # 수정 — 로그인·환경변수 절
└── (repo root) .env.example       # 수정 — DELIVERED_AUTH_URL / DELIVERED_CUSTOMER_API_URL 주석
```

## Module Design

### DeliveredAuthClient (`delivered_auth.py`)

- **책임**: 인증 게이트웨이와 고객 API 호출. 토큰을 헤더에 붙이는 유일한 자리.
- **위치**: `examples/delivered/api/delivered_auth.py`
- **의존성**: httpx. `DeliveredClient`와 같은 생성자 모양(`base_url`, `transport`, `timeout_s`)으로 테스트에서 `MockTransport` 주입.
- **주요 로직**:
  - `AUTH_BASE_URL = env DELIVERED_AUTH_URL or "https://gw-staging.delivered.co.kr"`, `CUSTOMER_BASE_URL = env DELIVERED_CUSTOMER_API_URL or "https://gw-staging.delivered.co.kr/dk-delivered/api/customer"` (Q1 확정: 스테이징 기본).
  - `async sign_in(email, password, remember_me=False) -> SignInResult(access_token, refresh_token, user_id, user_name)`: `POST {AUTH}/auth/sign-in/dk-service/customer?isRememberMe=`, 본문 `{email, password, ipAddress: "", country: "", isRememberMe}` (고객 프론트와 동일하게 빈 값). 401/404 → `SignInFailed`; 5xx·`httpx.HTTPError`·비JSON → `AuthUnavailable`. 예외 메시지는 상태 코드와 경로만 담는다.
  - `async get_me(access_token) -> dict`: `GET {CUSTOMER}/v2/me` (Bearer). 응답은 평면 객체.
  - `async customer_request(method, path, access_token, **kwargs) -> dict`: Bearer 부착 공통 경로. 응답 JSON `message == "Expired Token"`(상태 무관) → `TokenExpired`; 5xx·전송 오류 → `DeliveredApiError`(기존 예외 재사용). RBD-8277이 장바구니 호출에 그대로 쓴다.
  - 로깅: `INFO`에 메서드·경로·상태만. 헤더·본문은 어떤 레벨에도 찍지 않는다.

### SessionCredential · CredentialStore (`delivered_auth.py`)

- **책임**: 세션 ID별 토큰과 프로필 캐시. 프로세스 메모리, 상태 문서 밖.
- **주요 로직**:
  - `@dataclass(repr=False) SessionCredential`: `access_token`, `refresh_token`, `customer_id: str`, `profile: CustomerProfile(display_name, country, member_tier, email)`, `signed_in_at`. `__repr__`은 `SessionCredential(customer_id=…, tokens=<redacted>)`.
  - `CredentialStore`: `get(session_id) -> SessionCredential | None`, `put(session_id, cred)`, `drop(session_id) -> bool`. `dict` 한 개. 리프레시 토큰은 보관만 한다(사용 안 함 — mission Out of Scope).
  - `CustomerProfile.from_me(payload)`: `firstName`+`lastName` → `display_name`, `country`, `memberTier` → `member_tier`, `customerId`, `customerEmail`.

### DeliveredStorefront 변경 (`delivered_backend.py`)

- **책임**: 로그인 상태를 에이전트 컨텍스트로 넘기고, 계정이 필요한 쓰기를 게이트한다.
- **의존성**: `CredentialStore`(생성자 주입, 기본 새 인스턴스), `DeliveredAuthClient`(주입, 기본 새 인스턴스).
- **주요 로직**:
  - `credential_of(session) -> SessionCredential | None` = `self._credentials.get(session.session_id)`.
  - `require_credential(session) -> SessionCredential`: 없으면 `SignInRequired("장바구니")` 같은 기능명만 담아 raise.
  - `get_preferences(session)`: 자격증명이 있으면 `UserPreferences(user_id=session.user_id, display_name=profile.display_name, loyalty_tier=profile.member_tier, default_location=profile.country)`; 없으면 기존 `users.json` 게스트 프로필.
  - `get_account_context(session)`: `{"signed_in": true, "member_tier": …, "country": …}` 또는 `{"signed_in": false, "note": "Guest session — cart and checkout need sign-in"}`. 프롬프트의 계정 블록으로 들어가 모델이 로그인 상태를 안다(AC6·AC4의 근거).
  - `add_to_cart / update_cart_item / remove_from_cart`: 맨 앞에서 `require_credential(session)`. 기존 인메모리 `SessionCarts`는 그대로(RBD-8277이 교체). `get_cart`는 게스트면 빈 `Cart`.
  - `customer_call(session, method, path, **kw)`: `require_credential` → `auth.customer_request(..., cred.access_token)`; `TokenExpired`를 잡아 `self._credentials.drop(session_id)` 후 재raise. RBD-8277·RBD-8280의 진입점.
  - `sign_in(email, password, remember_me) -> tuple[SignInResult, CustomerProfile]`와 `attach(session_id, result, profile)`, `sign_out(session_id)`: 라우트가 부르는 얇은 조립 메서드(라우트에 httpx를 두지 않는다).

### DeliveredToolExecutor (`delivered_executor.py`)

- **책임**: 인증 예외를 모델이 손님에게 전할 문장으로 바꾼다.
- **위치**: `examples/delivered/api/delivered_executor.py`; `main.py`에서 `ShoppingAgent(executor_class=DeliveredToolExecutor)`.
- **주요 로직**: `domain_error(error)`:
  - `SignInRequired` → `ToolOutcome.error("로그인이 필요합니다: {feature}은(는) delivered 계정으로 로그인한 뒤 쓸 수 있습니다. 손님에게 로그인을 안내하고 같은 호출을 다시 시도하지 마세요.")`
  - `TokenExpired` → `ToolOutcome.error("로그인이 만료되어 다시 로그인이 필요합니다. 손님에게 다시 로그인하라고 안내하세요.")` — 툴 결과 문자열에 `다시 로그인` 포함(AC5).
  - 그 외 → `super().domain_error(error)`.

### session_routes (`session_routes.py`)

- **책임**: 로그인·로그아웃·프로필 요약 라우트. 세션 저장소는 `host.sessions`를 쓴다.
- **주요 로직**: `register_session_routes(app, host, backend)`:
  - `POST /api/session/login` — 본문 `LoginRequest(email: EmailStr|str, password: str, remember_me: bool=False)`, 헤더 `X-Session-Id`(선택, `Header(alias=…)`). 흐름: `backend.sign_in` → (`SignInFailed` → 401 `invalid_credentials`, `AuthUnavailable` → 502 `auth_unavailable`) → 세션 확보(헤더 있으면 `host.sessions.require`, `UnknownSessionError`면 새 세션) → `record.user_id = f"dk:{customer_id}"` + `host.sessions.save(record)` → `backend.attach(record.session_id, …)` → `SessionSummary`. 비밀번호는 지역 변수로만 존재하고 어떤 예외·로그에도 넣지 않는다.
  - `POST /api/session/logout` — `record: host.CurrentSession`; `backend.sign_out(session_id)`; 같은 `session_id`로 `signed_in: false` 응답. `pending_app_events`에 "Customer signed out"을 넣어 다음 턴이 안다.
  - `GET /api/session/me` — `record: host.CurrentSession`; `SessionSummary`.
  - `SessionSummary(session_id, user_id, signed_in, name, tier, country)` — 토큰 필드 없음.

### 조립 (`main.py`)

- `auth = DeliveredAuthClient()`, `credentials = CredentialStore()`, `backend = DeliveredStorefront(auth=auth, credentials=credentials)`, `ShoppingAgent(..., executor_class=DeliveredToolExecutor)`, `register_session_routes(app, host, backend)`. 테스트는 같은 조립을 `MockTransport`로 재현한다(`test_session_routes.py`가 `build_storefront_host`를 직접 부른다 — 부팅 워밍업은 `on_startup`을 비워 네트워크를 피한다).

## Error Handling

| 상황 | 어디서 | 처리 |
|------|--------|------|
| 자격증명 오류(게이트웨이 401/404) | `DeliveredAuthClient.sign_in` → 라우트 | `SignInFailed` → HTTP 401 `{"detail": "invalid_credentials"}`, 세션·토큰 변경 없음 |
| 게이트웨이 5xx·타임아웃·연결 실패·비JSON | 같은 곳 | `AuthUnavailable` → HTTP 502 `{"detail": "auth_unavailable"}` |
| `/me` 실패(5xx) 로그인 직후 | 라우트 | 로그인 자체를 502로 실패 처리(토큰을 붙이지 않는다) — 프로필 없는 반쪽 세션을 만들지 않는다 |
| 게스트가 계정 필요 툴 호출 | 백엔드 `require_credential` | `SignInRequired` → executor 문장. delivered에 쓰기 없음 |
| 고객 API `Expired Token` | `customer_request` → 백엔드 | 토큰 폐기(`drop`) → `TokenExpired` → executor "다시 로그인" 문장. 세션은 유지 |
| 고객 API 5xx·전송 오류 | `customer_request` | `DeliveredApiError` → 프레임워크 기본 "일시 불가" 문장 |
| 알 수 없는 `X-Session-Id`로 로그인 | 라우트 | 새 세션을 만들어 붙인다(401 대신) — FE가 만료된 세션 ID를 들고 있어도 로그인은 된다 |

## Migration / Side Effects

- DB 없음. 세션·자격증명은 프로세스 메모리라 재시작 시 전부 사라진다(데모 범위).
- 기존 동작 변화: **게스트 장바구니 쓰기가 막힌다**(add/update/remove → 로그인 안내). 기존 테스트 `test_cart_is_in_won_and_refuses_sold_out_lines` 등은 자격증명을 넣은 세션으로 갱신한다. 스모크 시나리오(`scripts/smoke_chat.py` delivered 3턴)의 "장바구니에 담아줘" 턴은 로그인 없이는 안내로 끝나므로, 스모크 기대값을 `expect_tools: set()`로 낮추거나 스모크에 로그인 단계를 넣는다(후자는 자격증명이 필요해 이번엔 전자).
- `.env.example`에 `DELIVERED_AUTH_URL`, `DELIVERED_CUSTOMER_API_URL` 주석 추가(값은 비움). 기본이 스테이징이므로 값이 없어도 동작한다.
- `SessionRecord.user_id`가 로그인 시 `dk:{customerId}`로 바뀌면 메모리 주체(`memory_subject`)도 바뀐다 — 게스트 시절 저장된 기억은 승계하지 않는다(의도).
- 프롬프트 바이트: `agent_config.py` 노트 한 줄 추가로 정적 프롬프트가 바뀐다 → `scripts/check.py`는 예제 config를 대조하지 않으므로 영향 없음(delivered는 `system.md` 파생 대상이 아님).
