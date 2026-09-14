---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: tasks
completed: [mission, blueprint, tasks, develop]
plan: []
skip: []
depth: deep
base_sha: 3285abf
gates:
  open_q: 0
  findings_pending: 0          # Q001·Q002 — 2026-09-14 스테이징 실측으로 해소
risk:
  self: 0.19
  review: skipped               # 0.19 < deep 임계 0.2, 커버리지 갭 없음
coverage:
  - ac: AC1
    tasks: [T002, T003, T006, T007, T008]
  - ac: AC2
    tasks: [T002, T003, T004, T005]
  - ac: AC3
    tasks: [T002, T003, T006, T007]
  - ac: AC4
    tasks: [T009, T010, T011]
  - ac: AC5
    tasks: [T002, T005, T009, T010, T011]
  - ac: AC6
    tasks: [T004, T005, T012]
  - ac: AC7
    tasks: [T002, T004, T006, T009, T013]
uncovered_acs: []
parallel_conflicts: []
task_count: 14
tests: included
integration_tasks:
  - service: delivered-auth-gateway
    endpoint: "POST /auth/sign-in/dk-service/customer"
    tasks: [T002, T006]
    verified: true
  - service: delivered-customer-api
    endpoint: "GET /v2/me"
    tasks: [T002, T004, T006]
    verified: true
---

# Tasks: [shopping-agents] delivered 로그인 연동 — 세션에 토큰 보관, 고객 API Bearer 호출 (1)

> Mission: ./mission.md | Blueprint: ./blueprint.md, ./blueprint-api.md, ./blueprint-integration.md | Jira: RBD-8275

## Implementation Strategy

- **실행 모드**: 단계별 분리 (User Story 3개) — 단 규모가 작아 **단일 PR**로 낸다. Phase 2까지가 공통 기반, US1이 MVP, US2가 게스트·만료 처리, US3은 전체 검증.
- **MVP 경계**: Phase 3(US1)까지 끝나면 로그인 → 프로필 → Bearer 호출이 동작한다. 여기서 별도 PR을 낼 수 있다.
- **별도 PR 가능 분기점**: US2(게스트 차단·만료)는 기존 게스트 장바구니 동작을 바꾸므로 필요하면 뒤로 뺄 수 있다. 다만 RBD-8277이 게스트 예외에 의존하므로 같은 PR을 권장.
- **병렬 실행 예시**: T002 ‖ (T001 없음); T004와 T006은 서로 다른 테스트 파일이라 `[P]`; T012·T014는 다른 파일이라 `[P]`. `delivered_backend.py`를 만지는 T005·T011은 순차.
- **TDD 순서**: 각 phase에서 테스트 태스크가 구현 태스크보다 먼저다. Python 프로젝트라 L1은 `httpx.MockTransport`로 게이트웨이를 격리한 클라이언트·백엔드 단위 테스트, L2는 `fastapi.testclient.TestClient`로 라우트를 통과하는 앱 통합 테스트다(외부 서버는 같은 MockTransport로 격리). L3(DB)은 없다.
- **미확인 계약**: 인증 게이트웨이·`/v2/me` 계약은 고객 프론트 코드에서 읽은 가정이다(`verified: false`). 해당 테스트 태스크(T002·T006)는 완료 시 findings에 `Q###`를 남긴다.

## Phase 1: Setup

- [X] T001 [P] 저장소 루트 `.env.example`에 `DELIVERED_AUTH_URL`·`DELIVERED_CUSTOMER_API_URL` 주석 두 줄 추가 — 값 비움, 기본이 스테이징임을 한 줄로 (`.env.example`)

## Phase 2: Foundational — 인증 클라이언트·자격증명 저장소 (모든 스토리의 선행)

- [X] T002 [L1] `FakeAuthGateway`(MockTransport)로 `DeliveredAuthClient` 단위 테스트 작성 — `sign_in` 200(토큰·userId 반환), 401/404 → `SignInFailed`, 500·타임아웃·연결 실패·비JSON → `AuthUnavailable`, 요청 본문에 `ipAddress: ""`·`country: ""`·`isRememberMe` 포함 확인; `get_me` Bearer 헤더 확인; `customer_request`가 `message == "Expired Token"`(상태 200/401 모두)에서 `TokenExpired`, 5xx에서 `DeliveredApiError`; `SessionCredential.__repr__`에 토큰 문자열 부재; `CredentialStore.put/get/drop`; 예외 메시지에 토큰·비밀번호 부재 (`examples/delivered/api/tests/test_delivered_auth.py`)
  ⚠️ 이 스텁은 상대 계약 미확인 상태의 가정이다. 구현 완료 시 findings에 Q###로 기록할 것 (질문: "delivered-auth-gateway의 POST /auth/sign-in/dk-service/customer 응답 형식을 실제로 확인했는가?", "delivered-customer-api의 GET /v2/me 응답 형식을 실제로 확인했는가?")
- [X] T003 `delivered_auth.py` 구현 — 예외 `SignInFailed`/`AuthUnavailable`/`SignInRequired`/`TokenExpired`, 환경변수 기본값(스테이징), `DeliveredAuthClient(sign_in, get_me, customer_request)`, `CustomerProfile.from_me`, `SessionCredential`(repr redaction), `CredentialStore`; 로깅은 INFO에 메서드·경로·상태만 (`examples/delivered/api/delivered_auth.py`) — T002 의존

## Phase 3: US1 — delivered 계정으로 로그인해 내 정보로 대화한다 (P1)

**목표**: 로그인 → 토큰이 세션 옆에 → 프로필이 에이전트 컨텍스트로 → Bearer 공통 경로 동작.
**독립 테스트 기준**: T004·T006이 통과하고, 데모에서 `POST /api/session/login`(스테이징 계정) 후 `GET /api/session/me`가 이름·등급·국가를 돌려준다.

- [X] T004 [P] [US1] [L1] 백엔드 단위 테스트 작성 — `CredentialStore`에 자격증명이 있는 세션의 `get_preferences`가 프로필(이름·등급·국가)을, 없는 세션은 게스트 프로필을 반환; `get_account_context`가 `signed_in` true/false와 등급·국가를 반환; `customer_call`이 Bearer로 호출하고 `TokenExpired` 시 자격증명을 `drop`한 뒤 재raise (`examples/delivered/api/tests/test_delivered_auth.py`)
- [X] T005 [US1] `DeliveredStorefront` 변경 — 생성자에 `auth: DeliveredAuthClient`, `credentials: CredentialStore` 주입(기본 새 인스턴스); `credential_of`, `require_credential`, `get_preferences`(자격증명 → 프로필, 없으면 users.json), `get_account_context`, `customer_call`(TokenExpired → drop → 재raise), `sign_in`/`attach`/`sign_out` 조립 메서드 (`examples/delivered/api/delivered_backend.py`) — T003·T004 의존
- [X] T006 [P] [US1] [L2] 라우트 앱 통합 테스트 작성 — `build_storefront_host`를 `on_startup=()`·MockTransport 백엔드로 직접 조립한 `TestClient`로: `POST /api/session/login` 200(헤더 없음 → 새 세션 / `X-Session-Id` 있음 → 같은 `session_id`·`user_id`가 `dk:{customerId}`), 401 `invalid_credentials`, 502 `auth_unavailable`(게이트웨이 5xx · `/me` 5xx 각각), 알 수 없는 세션 ID → 새 세션; `POST /api/session/logout` → 같은 세션 `signed_in: false`; `GET /api/session/me` 게스트/로그인; 모든 응답 본문과 `caplog`(INFO)에 액세스·리프레시 토큰·비밀번호 문자열 부재 (`examples/delivered/api/tests/test_session_routes.py`)
  ⚠️ 이 스텁은 상대 계약 미확인 상태의 가정이다. 구현 완료 시 findings에 Q###로 기록할 것 (질문: "delivered-auth-gateway 로그인 응답의 userId·userName 필드와 실패 상태 코드(401/404)를 실제로 확인했는가?")
- [X] T007 [US1] `session_routes.py` 구현 — `register_session_routes(app, host, backend)`: `LoginRequest`·`SessionSummary` 모델, `POST /api/session/login`(SignInFailed → 401, AuthUnavailable → 502, 세션 확보·`user_id` 갱신·`sessions.save`·`backend.attach`), `POST /api/session/logout`(`sign_out` + `pending_app_events` 한 줄), `GET /api/session/me`; 비밀번호는 지역 변수로만 (`examples/delivered/api/session_routes.py`) — T005·T006 의존
- [X] T008 [US1] `main.py` 조립 — `DeliveredAuthClient`·`CredentialStore` 생성, `DeliveredStorefront(auth=…, credentials=…)`, `ShoppingAgent(executor_class=DeliveredToolExecutor)`, `register_session_routes(app, host, backend)` (`examples/delivered/api/main.py`) — T007·T010 의존

## Phase 4: US2 — 게스트와 만료 세션은 안전하게 안내받는다 (P2)

**목표**: 계정이 필요한 쓰기는 로그인 안내로 끝나고, 만료는 같은 세션에서 재로그인 안내로 이어진다.
**독립 테스트 기준**: T009가 통과하고, 데모 게스트 세션에서 "장바구니에 담아줘"가 로그인 안내로 끝난다.

- [X] T009 [US2] [L1] 게스트·만료 단위 테스트 작성 — `DeliveredToolExecutor.domain_error`가 `SignInRequired`를 "로그인이 필요합니다…" 결과로, `TokenExpired`를 "로그인이 만료되어 다시 로그인이 필요합니다…"(`다시 로그인` 포함) 결과로 바꾸고 그 외는 부모에 위임; 게스트 세션의 `add_to_cart/update_cart_item/remove_from_cart`가 `SignInRequired`를 던지고 장바구니가 비어 있음; 게스트 `get_cart`가 빈 `Cart`; 만료 흐름 후 `CredentialStore`에서 세션이 빠짐; 기존 장바구니 테스트(`test_cart_is_in_won_and_refuses_sold_out_lines` 등)를 자격증명을 넣은 세션으로 갱신 (`examples/delivered/api/tests/test_delivered_auth.py`, `examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T010 [US2] `delivered_executor.py` 구현 — `DeliveredToolExecutor(ShoppingToolExecutor)`의 `domain_error` 매핑 두 건 + `super()` 위임 (`examples/delivered/api/delivered_executor.py`) — T009 의존
- [X] T011 [US2] 장바구니 쓰기 게이트 — `add_to_cart/update_cart_item/remove_from_cart` 첫 줄에 `require_credential(session)`, `get_cart`는 게스트면 빈 `Cart(currency="KRW")` (`examples/delivered/api/delivered_backend.py`) — T005·T009 의존
- [X] T012 [P] [US2] `DOMAIN_SEARCH_NOTES`에 한 줄 추가 — 계정 컨텍스트의 `signed_in`으로 로그인 상태를 알 수 있고, 장바구니·결제는 로그인 후에만 가능하며 게스트에게는 로그인을 안내하라는 규칙 (`examples/delivered/api/agent_config.py`)

## Phase 5: US3 — 네트워크 없이 검증된다 (P3)

**목표**: 전체 스위트·린트가 네트워크 없이 통과한다.
**독립 테스트 기준**: `.venv/bin/python -m pytest -q` 전체 통과, `ruff check .`·`ruff format --check .` 통과, `scripts/check.py` clean.

- [X] T013 [US3] 전체 검증 + 스모크 기대값 조정 — `pytest` 전체·`ruff`·`scripts/check.py` 실행; `scripts/smoke_chat.py`의 delivered 3번째 턴(장바구니 담기)이 게스트라 로그인 안내로 끝나므로 `expect_tools: set()`·`expect_events: {"turn_complete"}`로 하향하고 주석으로 사유 기록 (`scripts/smoke_chat.py`)

## Final Phase: Polish & 횡단 관심사

- [X] T014 [P] README 갱신 — 「Run」에 환경변수(`DELIVERED_AUTH_URL`·`DELIVERED_CUSTOMER_API_URL`, 기본 스테이징)와 로그인 경로 3개, 「What is specific」에 `delivered_auth.py`·`session_routes.py`·`delivered_executor.py`, 「Try」에 로그인 후 프롬프트 1개와 게스트 담기 안내 1개 (`examples/delivered/README.md`)

## Dependencies

```text
T002 ─▶ T003 ─┬─▶ T004 ─▶ T005 ─┬─▶ T007 ─▶ T008
              │                  └─▶ T011
              └─▶ T006 ─────────────▶ T007
T009 ─▶ T010 ─▶ T008
T009 ─▶ T011
T012, T014, T001: 독립 (병렬)
T013: 전부 끝난 뒤
```

- US1(T004~T008)은 Phase 2 이후 바로 시작. US2(T009~T012)는 T005 이후 시작 가능(T011이 backend 변경에 의존).
- `delivered_backend.py`는 T005 → T011 순으로만 만진다 (병렬 금지).

## 병렬 실행 예시

- Phase 2 직후: T004 ‖ T006 (서로 다른 테스트 파일) — 둘 다 T003 완료 후.
- US2 도중: T012 ‖ T014 ‖ T001 (각각 agent_config / README / .env.example).
