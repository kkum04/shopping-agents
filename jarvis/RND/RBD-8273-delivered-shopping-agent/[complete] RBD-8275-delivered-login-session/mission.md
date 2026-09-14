---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: mission
completed: [mission]
plan: [blueprint, tasks, develop]
skip: []
depth: deep
base_sha: 3285abf
difficulty:
  area: BE
  level: L
  size: 중
  signals:
    changed_files: 5
    module_count: 2
    new_api: true
    db_migration: false
    txn_concurrency_external: true
    est_md: 4.0
  computed_at: 3285abf
gates:
  open_q: 0
risk:
  self: 0.30
  review: passed  # 격리 검증 2026-09-11: ❌1(엣지, non-blocking)·⚠️4 → mission 보강으로 해소
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [로그인, 세션, 토큰, Bearer, 고객 API, 게스트, 프로필, 만료]
  modules: [examples/delivered/api, examples/demo_common, shopping-agent/core executor]
acceptance:
  - id: AC1
    story: P1
    ears: "WHEN a customer signs in with email and password through POST /api/session/login THE system SHALL store the delivered access token beside the session on the server and answer with the signed-in profile; WHEN the credentials are wrong THE system SHALL answer 401 without a token; WHEN the auth gateway fails with 5xx or a timeout THE system SHALL answer 502 without a token"
  - id: AC2
    story: P1
    ears: "WHEN a signed-in session's backend calls a delivered customer API THE system SHALL send the session's token as a Bearer header and the profile call to /api/customer/v2/me SHALL return 200"
  - id: AC3
    story: P1
    ears: "WHEN the agent's prompt, tool arguments, tool results, INFO-level logs, session state document, transcript, or session-start response are inspected THE system SHALL contain no access or refresh token"
  - id: AC4
    story: P2
    ears: "WHEN a guest session asks for an account-only action such as adding to the delivered cart THE system SHALL tell the customer that sign-in is required and write nothing"
  - id: AC5
    story: P2
    ears: "WHEN a customer API answers with the message 'Expired Token' THE system SHALL drop the session's token, continue the same session as a guest, and return a tool result containing '다시 로그인' so the agent tells the customer to sign in again"
  - id: AC6
    story: P1
    ears: "WHEN a signed-in session starts a turn THE system SHALL give the agent the customer's name, country, and member tier from the delivered profile"
  - id: AC7
    story: P3
    ears: "WHEN the test suite runs THE system SHALL exercise login, Bearer attachment, guest refusal, and expiry with httpx.MockTransport and never reach the network"
sources: { read: 1, unread: 0, blocked: 0, figma: none }
---

# Mission: [shopping-agents] delivered 로그인 연동 — 세션에 토큰 보관, 고객 API Bearer 호출 (1)

> Jira: RBD-8275 | Epic: RBD-8273 [RND] delivered 쇼핑 에이전트 — 로그인·장바구니·결제 연결 | Priority: Medium

## Background

delivered 스토어프론트 데모는 지금 데모 프로필 ID 하나로 세션을 열고, 상품 검색·상세는 delivered 게스트 카탈로그 API로 처리한다. 다음 티켓들(장바구니 RBD-8277, 결제 핸드오프 RBD-8280)은 "손님 본인"의 시스템을 부르므로 delivered 로그인으로 받은 액세스 토큰이 필요하다. 프레임워크는 세션 시작 때 주체를 묶고 자격증명은 서버가 들고 있으며 모델에는 절대 보이지 않는 구조(`docs/backends.md` Step 1, `docs/safety.md` Identity)라, 이 티켓은 그 자리에 delivered 토큰을 넣는다.

고객 프론트는 이메일·비밀번호로 인증 게이트웨이에 로그인해 액세스·리프레시 토큰을 쿠키에 두고, 고객 API 호출마다 Bearer로 붙이며, 응답 메시지가 `Expired Token`이면 로그아웃시킨다. 리프레시 토큰은 저장만 하고 어디에도 보내지 않는다. 로그인 요청의 `country`·`ipAddress`는 고객 프론트도 빈 문자열로 보낸다. 이 티켓은 그 정책을 서버 세션 쪽에 그대로 옮긴다.

⚠️ 가정 (티켓에서 승계): 고객 프론트가 붙이는 `apiKey` 헤더는 게스트 API처럼 불필요하다고 가정한다. 고객 API가 이 헤더를 요구하면 그때 키를 받아 환경변수로 주입한다.

## Goal

손님이 스토어프론트에서 delivered 계정으로 로그인하면 그 토큰이 서버 세션 옆에 보관되고, 백엔드가 delivered 고객 API를 손님 명의로 호출할 수 있게 한다. 토큰은 모델·로그·툴 인자 어디에도 나타나지 않는다.

## User Stories

우선순위 순으로 정렬:

### P1: delivered 계정으로 로그인해 내 정보로 대화한다

- **As a** delivered 회원인 손님
- **I want** 스토어프론트에서 이메일·비밀번호로 로그인하기
- **So that** 에이전트가 내 이름·국가·회원 등급을 알고, 이후 장바구니·결제가 내 계정으로 이어진다

**Acceptance Criteria:**
- [ ] AC1: 스토어프론트의 로그인 경로(백엔드가 제공)로 이메일·비밀번호를 보내면 백엔드가 delivered 인증 게이트웨이(`POST /auth/sign-in/dk-service/customer`)를 대신 호출하고, 받은 액세스 토큰(과 리프레시 토큰)을 서버 세션 옆에 보관한 채 그 손님의 세션을 시작한다. 잘못된 자격증명(게이트웨이 401/404)은 세션을 만들지 않고 HTTP 401로 돌려주고, 인증 게이트웨이가 5xx·타임아웃·연결 실패로 답하지 못하면 HTTP 502로 돌려준다. 어느 경우에도 비밀번호는 기록되지 않는다.
- [ ] AC2: 로그인한 세션의 백엔드가 delivered 고객 API(`/api/customer/*`)를 부를 때 세션의 토큰을 `Authorization: Bearer`로 붙이고, `GET /api/customer/v2/me`가 200으로 응답한다.
- [ ] AC3: 액세스·리프레시 토큰이 모델 프롬프트, 툴 인자, 툴 결과(펜스 안 포함), INFO 이상 로그, 세션·로그인·프로필 응답 본문 어디에도 나타나지 않는다.
- [ ] AC6: 로그인한 세션의 턴 시작 시 에이전트가 받는 고객 컨텍스트(`get_preferences`)에 delivered 프로필의 이름, 국가, 회원 등급이 들어 있다.

### P2: 게스트와 만료 세션은 안전하게 안내받는다

- **As a** 로그인하지 않았거나 토큰이 만료된 손님
- **I want** 계정이 필요한 요청에서 무엇이 필요한지 바로 듣기
- **So that** 오류 대신 로그인으로 이어갈 수 있다

**Acceptance Criteria:**
- [ ] AC4: 게스트 세션(토큰 없음)에서 계정이 필요한 기능을 요청하면 에이전트가 "로그인이 필요합니다"로 안내하고 delivered에 아무것도 쓰지 않는다. 검색·상품 상세는 게스트로 계속 동작한다.
- [ ] AC5: 고객 API 응답 메시지가 `Expired Token`이면 백엔드가 세션의 토큰을 지우고 같은 세션을 게스트로 이어가며, 그 툴 호출은 "로그인이 만료되어 다시 로그인이 필요합니다"라는 결과로 모델에 전달되어 에이전트가 재로그인을 안내한다(툴 결과 문자열에 `다시 로그인` 포함). 리프레시 흐름은 만들지 않는다.

### P3: 네트워크 없이 검증된다

- **As a** 개발자
- **I want** 로그인·Bearer 부착·게스트 거절·만료 처리를 녹화 응답으로 검증하기
- **So that** CI가 운영 인증 게이트웨이에 닿지 않는다

**Acceptance Criteria:**
- [ ] AC7: `httpx.MockTransport`로 인증 게이트웨이와 고객 API를 흉내 내는 테스트가 AC1·AC2·AC4·AC5를 각각 검증하고, 기존 테스트 전체와 ruff가 통과한다.

## UI/Design Requirements

> [Figma 미제공 — BE 티켓. 스토어프론트 로그인 화면은 RBD-8276(FE)이 담당하며, 이 티켓은 그 화면이 부를 로그인 경로와 세션 시작 응답의 계약만 정한다.]

### 데이터 요구사항 (from contract)
- `POST /api/session`(공용 라우트)은 그대로 두고, `GET /api/session/me`가 `signed_in: bool`, `name`, `tier`, `country`를 돌려준다. 토큰은 어느 응답에도 들어가지 않는다. 게스트 시작은 지금처럼 본문 없이 가능하다.
- `POST /api/session/login` 요청: `email`, `password`, `remember_me`(선택, 기본 false). `X-Session-Id` 헤더가 있으면 **그 세션에 토큰을 붙여 대화를 이어가고**, 없으면 새 세션을 만든다. 응답: `session_id`와 위 프로필 요약(`signed_in: true`). 실패: 자격증명 오류 401 `{"detail": "invalid_credentials"}`, 게이트웨이 장애 502 `{"detail": "auth_unavailable"}`.
- `POST /api/session/logout` 요청: 본문 없음, `X-Session-Id` 헤더. 응답: 같은 `session_id`에 `signed_in: false` — 토큰만 지우고 세션과 대화는 유지한다.
- 만료 후 재로그인도 `POST /api/session/login`에 `X-Session-Id`를 실어 같은 세션에 다시 붙인다(대화 승계).

## Non-Functional Requirements

- **보안**: 토큰은 서버 세션 저장소에만 있고 브라우저에는 `X-Session-Id`만 간다. 세션 상태 문서(`state_document`)와 트랜스크립트에 토큰을 넣지 않는다(두 곳은 디버그 로그와 저장소에 기록된다). 비밀번호는 로그인 경로 처리 중에만 메모리에 있고 어디에도 기록하지 않는다.
- **호환성**: 인증 게이트웨이·고객 API 루트는 환경변수로 바꿀 수 있고 기본은 스테이징(`https://gw-staging.delivered.co.kr`)이다(Q1 확정). 기존 게스트 카탈로그 경로(`DELIVERED_API_URL`, 운영)와는 별도 변수로 둔다.
- **성능**: 로그인 경로는 인증 게이트웨이 1회 + 프로필 1회 호출로 끝난다. 턴마다 프로필을 다시 부르지 않고 세션에 캐시한다.

## Out of Scope

- 소셜 로그인(구글·애플·번개장터), 회원가입, 비밀번호 찾기.
- 스토어프론트 로그인 화면·헤더 표시(RBD-8276).
- delivered 실제 장바구니 호출(RBD-8277) — 이 티켓은 게스트 거절과 Bearer 공통 경로까지만.
- 리프레시 토큰으로 액세스 토큰을 갱신하는 흐름(고객 프론트에도 없음).
- `apiKey` 헤더 수령·주입(가정 유지, 막히면 후속).

## Open Questions

- [x] Q1: 데모 백엔드가 기본으로 부를 인증 게이트웨이는 운영(`gw.delivered.co.kr`)인가 스테이징(`gw-staging.delivered.co.kr`)인가? 게스트 카탈로그는 이미 운영을 쓰고 있지만, 로그인은 실제 고객 계정과 토큰을 다루므로 기본값을 정해야 한다.
  - 확정: **스테이징 기본** (`https://gw-staging.delivered.co.kr`) — 로그인·고객 API는 스테이징 게이트웨이, 게스트 카탈로그는 운영 그대로. 환경변수 `DELIVERED_AUTH_URL`(인증 게이트웨이 루트)·`DELIVERED_CUSTOMER_API_URL`(고객 API 루트)로 전환한다. (출처: 사용자 2026-09-11)
  - 영향: 스테이징 계정이 필요하다. 카탈로그(운영)와 장바구니(스테이징)의 데이터가 갈릴 수 있으므로 RBD-8277(장바구니)에서 확인할 항목으로 넘긴다.

> 모든 Open Questions가 해소되어야(`- [x]`) blueprint 단계로 진행할 수 있습니다. (frontmatter `gates.open_q` 와 동기)

---

## 🤖 소스 추적 (기계용 — 사람은 읽지 않아도 됨)

> 추적성 메타. "모두 확인"의 보장이자 frontmatter `sources` 카운트의 원장. 사람용 본문에는 넣지 않는다.

### Sources

| 소스 | 상태 | 비고 |
|------|------|------|
| Jira 티켓 | ✅ 확인 | RBD-8275 (draft 생성 A 변형 — footer 마커로 인식, 품질검증 통과) |
| PM 티켓 (에픽 링크) | ⚠️ 없음 | 에픽 RBD-8273에 이슈 링크·PRD 필드·리모트 링크 없음 (기획 티켓 없이 분해된 에픽) |
| Figma 디자인 | ⏭️ 없음 | BE 티켓, 티켓·에픽 어디에도 Figma URL 없음 |

### PM 티켓 관련 링크 (전수)

> PM 티켓이 없어 링크 0건.

### Reference Code

| 프로젝트 | 파일 경로 | 참조 목적 |
|---------|---------|---------|
| 현재 프로젝트 | `examples/demo_common/sessions.py` | `SessionRecord`/`SessionStore` — 토큰을 세션 옆에 두는 자리, `state_document`에 넣지 않을 것 |
| 현재 프로젝트 | `examples/demo_common/storefront.py` | `StartSessionRequest`, `/api/session`, `host.context()` — 세션 시작 계약과 `ShoppingSessionContext` 조립 |
| 현재 프로젝트 | `examples/entertainment/api/mock_ticketing.py` `TicketingToolExecutor` | `domain_error` 오버라이드로 백엔드 예외를 모델용 문장으로 relay하는 패턴 (게스트 거절에 재사용) |
| 현재 프로젝트 | `examples/delivered/api/delivered_backend.py` `DeliveredClient` | 게스트 API 클라이언트 — 인증 게이트웨이·고객 API 호출을 같은 모듈에 붙인다 |
| 현재 프로젝트 | `docs/backends.md` Step 1, `docs/safety.md` Identity | 자격증명은 세션 옆, 모델에 노출 금지 |
| deliveredkorea-customer-frontend | `src/features/repository/auth/fetchAuth.ts`, `src/types/api/auth/authApiDto.ts:1-7, 47-56, 134-157` | 로그인 요청/응답 필드, `/me` 응답 필드 |
| deliveredkorea-customer-frontend | `libs/api/clients.ts:29-45`, `src/features/repository/auth/authService.ts` | Bearer 부착 조건(만료 전만), `Expired Token` → 로그아웃 정책, 리프레시 미사용 |
| deliveredkorea-customer-frontend | `src/hooks/auth/useLogin.ts:20-44` | 로그인 본문의 `country`·`ipAddress`가 빈 문자열로 전송됨 |
