---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: mission
completed: [mission]
plan: [blueprint, tasks, develop]
skip: []
depth: standard
base_sha: bf0fe16
gates:
  open_q: 0
risk:
  self: 0.2                     # base 0 + UI 티켓 Figma 없음 0.2 → < 0.4(standard) 생략
  review: skipped
difficulty:
  area: FE
  level: M
  size: 중
  signals:
    changed_files: 7
    module_count: 1
    new_api: false
    db_migration: false
    txn_concurrency_external: false
    est_md: 2.5
  computed_at: bf0fe16
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [로그인, 세션, 게스트, 헤더, 장바구니, 스토어프론트]
  modules: [examples/delivered/storefront-web, examples/web-shared(읽기만)]
acceptance:
  - id: AC1
    story: P1
    ears: "WHEN 손님이 로그인 폼에 올바른 delivered 계정을 제출하면 THE system SHALL 같은 세션을 회원 세션으로 전환하고 헤더에 손님 이름(있으면 등급)을 표시한다"
  - id: AC2
    story: P1
    ears: "WHEN 로그인 API가 401(invalid_credentials)을 돌려주면 THE system SHALL 폼 안에 자격 증명 오류 문구를 보이고 세션을 게스트로 유지한다"
  - id: AC3
    story: P1
    ears: "WHEN 로그인 API가 502(auth_unavailable)이나 네트워크 오류로 실패하면 THE system SHALL 폼 안에 잠시 후 재시도 문구를 보이고 세션을 게스트로 유지한다"
  - id: AC4
    story: P2
    ears: "WHEN 손님이 페이지를 새로고침하면 THE system SHALL 저장된 세션 id로 GET /api/session/me를 확인해 로그인 상태·이름·장바구니를 그대로 이어간다"
  - id: AC5
    story: P2
    ears: "WHEN 저장된 세션 id를 서버가 모르면(404) THE system SHALL 오류 없이 새 게스트 세션을 시작하고 저장값을 교체한다"
  - id: AC6
    story: P3
    ears: "WHEN 손님이 로그아웃을 누르면 THE system SHALL 헤더를 Guest로 바꾸고 장바구니 패널을 비우며 같은 세션에서 대화를 게스트로 계속한다"
  - id: AC7
    story: P4
    ears: "WHEN 에이전트 답변(툴 오류 포함)에 '로그인이 필요합니다'가 포함되면 THE system SHALL 그 턴 아래에 로그인 진입 칩을 보이고 누르면 로그인 폼을 연다"
  - id: AC8
    story: P1
    ears: "WHEN examples/delivered/storefront-web에서 next build를 실행하면 THE system SHALL 타입·린트 오류 없이 통과한다"
sources: { read: 1, unread: 0, blocked: 0, figma: none }
---

# Mission: 스토어프론트 로그인 화면 — 이메일 로그인, 게스트 전환

> Jira: RBD-8276 | Epic: RBD-8273 [RND] delivered 쇼핑 에이전트 — 로그인·장바구니·결제 연결 | Priority: Medium

## Background

delivered 스토어프론트 데모(`examples/delivered/storefront-web`)는 리테일 예제를 복사한 것이라 로그인이 없다. 페이지가 열리면 `POST /api/session`으로 데모 프로필(`demo-user`) 세션이 바로 시작되고, 헤더의 손님 이름은 백엔드 `get_preferences`가 돌려주는 값(게스트면 "Guest")을 그대로 보여준다. 세션 id는 메모리에만 있어 새로고침마다 새 세션이 열린다.

BE 티켓 RBD-8275(완료)가 같은 세션에 붙는 로그인 경로를 만들었다: `POST /api/session/login`(X-Session-Id 선택, 성공 시 `{session_id, user_id: "dk:{id}", signed_in, name, tier, country}`, 실패 401 `invalid_credentials` / 502 `auth_unavailable`), `POST /api/session/logout`(같은 세션을 게스트로 되돌림), `GET /api/session/me`. 게스트가 장바구니에 담으려 하면 에이전트가 "로그인이 필요합니다: 장바구니…"라고 안내한다. 토큰은 서버가 세션 옆에 들고 있고 브라우저는 세션 id만 보낸다(`docs/safety.md` Identity).

이 티켓은 그 경로를 화면에 연결한다 — 손님이 delivered 계정으로 로그인해 자기 장바구니를 쓸 수 있도록 로그인 폼, 헤더의 로그인 상태, 로그아웃, 에이전트 안내에서 로그인으로 이어지는 진입점을 둔다.

## Goal

손님이 스토어프론트 안에서 delivered 계정으로 로그인·로그아웃할 수 있고, 새로고침해도 세션이 이어지며, 에이전트가 로그인을 요구한 자리에서 바로 로그인으로 넘어갈 수 있게 한다.

## User Stories

우선순위 순으로 정렬:

### P1: 이메일·비밀번호 로그인

- **As a** delivered 고객
- **I want** 스토어프론트 헤더에서 이메일과 비밀번호로 로그인하기를
- **So that** 대화 중 담은 상품을 내 delivered 장바구니로 이어갈 수 있다

**Acceptance Criteria:**
- [ ] AC1: 올바른 계정을 제출하면 폼이 닫히고 헤더에 손님 이름(있으면 등급)이 보인다. 진행 중이던 대화는 같은 세션에서 그대로 이어진다.
- [ ] AC2: 잘못된 비밀번호(401)는 폼 안에 오류 문구로 보이고, 폼은 열린 채 세션은 게스트로 남는다.
- [ ] AC3: 인증 게이트웨이 장애(502)나 네트워크 오류는 폼 안에 "잠시 후 다시 시도" 문구로 보이고 세션은 게스트로 남는다.
- [ ] AC8: `examples/delivered/storefront-web`의 `next build`가 통과한다.

### P2: 새로고침 후 세션 유지

- **As a** 로그인한 고객
- **I want** 페이지를 새로고침해도 로그인 상태가 유지되기를
- **So that** 다시 로그인하지 않고 대화와 장바구니를 이어갈 수 있다

**Acceptance Criteria:**
- [ ] AC4: 새로고침 후 저장된 세션 id로 `GET /api/session/me`를 확인해 로그인 상태·이름·장바구니가 그대로 보인다.
- [ ] AC5: 저장된 세션 id를 서버가 모르면(API 재시작 등) 오류 화면 없이 새 게스트 세션으로 시작하고 저장값을 교체한다.

### P3: 로그아웃과 게스트 전환

- **As a** 로그인한 고객
- **I want** 헤더에서 로그아웃하기를
- **So that** 공용 기기에서 내 계정을 남기지 않는다

**Acceptance Criteria:**
- [ ] AC6: 로그아웃하면 헤더가 "Guest"로 바뀌고 장바구니 패널이 비워지며, 같은 세션에서 대화가 게스트로 계속된다.

### P4: 에이전트 안내에서 로그인으로 진입

- **As a** 게스트 손님
- **I want** 에이전트가 "로그인이 필요합니다"라고 안내한 그 자리에서 로그인으로 넘어가기를
- **So that** 헤더를 찾아 헤매지 않고 담기를 이어갈 수 있다

**Acceptance Criteria:**
- [ ] AC7: 에이전트 답변(툴 오류 포함)에 "로그인이 필요합니다"가 포함된 턴 아래에 로그인 진입 칩이 보이고, 누르면 로그인 폼이 열린다.

## UI/Design Requirements

> Figma 미제공 — 참고 화면은 고객 프론트 `src/containers/(auth)/signin/SigninContainer.tsx`와 `src/containers/_shared/signin/SigninModal`. 디자인 시스템은 현재 스토어프론트(`web-shared` StoreShell·chip·BagPanel 스타일)를 그대로 쓴다.

### 화면 구성
- 헤더 우측 손님 영역: 게스트면 "Guest" + **Sign in** 버튼, 회원이면 이름(+등급) + **Sign out**.
- 로그인 모달(현재 화면 위 다이얼로그 — Q1 확정): 이메일, 비밀번호, 로그인 유지(remember me) 체크, 제출 버튼, 폼 내부 오류 줄.
- 에이전트 턴 아래 진입 칩: 기존 chip 스타일("Sign in to continue" 성격의 한 개 칩).

### 컴포넌트
- `LoginDialog`(모달): 폼 상태(제출 중/오류), 제출 시 `POST /api/session/login` 호출, 성공 시 세션 갱신.
- 헤더 손님 영역: `StoreShell`의 `shopper` 표시는 그대로 두고, Sign in/Sign out 액션을 붙인다.
- 세션 훅: `sessionStorage`에 저장된 세션 id 복원(Q2 확정) → `GET /api/session/me` → 없으면 `POST /api/session`.

### 인터랙션
- 제출 중 버튼 비활성 + 이중 제출 방지. 성공 → 폼 닫힘, 헤더 갱신, 장바구니 재조회. 401 → 오류 줄 "이메일 또는 비밀번호가 맞지 않습니다"(영문 UI면 동등 문구), 비밀번호 입력 초기화. 502/네트워크 → "잠시 후 다시 시도해 주세요".
- 로그아웃 → `POST /api/session/logout` → 헤더 Guest, 장바구니 비움(빈 상태 표시), 대화 유지.
- 진입 칩 클릭 → 로그인 폼 열림. 로그인 성공 후 손님이 "다시 담아줘"라고 말하면 되므로 자동 재시도는 하지 않는다.

### 데이터 요구사항 (from Design)
- 세션 요약: `{session_id, user_id, signed_in, name, tier, country}` (RBD-8275 `SessionSummary`).
- 헤더 표시: `name`(회원) / "Guest"(게스트), `tier`(예: "Basic").
- 브라우저 저장: `sessionStorage`에 세션 id 문자열 1개만(탭 단위 — 탭을 닫으면 게스트로 새로 시작). 토큰·비밀번호는 저장하지 않는다.

## Non-Functional Requirements

- **보안**: 토큰은 브라우저에 두지 않는다(서버 세션 보관, 브라우저는 `X-Session-Id`만). 비밀번호는 제출 직후 폼 상태에서 지운다. 저장하는 것은 세션 id뿐이다.
- **호환성**: 현재 스토어프론트 스택(Next.js app router, `web-shared` 공용 컴포넌트) 안에서 구현하고 `web-shared`는 수정하지 않는다(리테일 등 다른 예제와 공유).
- **성능**: 세션 복원은 페이지 로드 시 요청 1~2회(`me` → 필요 시 `session`)로 끝낸다.

## Out of Scope

- 소셜 로그인 버튼, 회원가입, 비밀번호 찾기, 디자인 시스템 교체(티켓 명시).
- 한국어 UI 문구 전환 — 스토어프론트는 영문 UI를 유지한다(에픽 범위 밖). 헤더의 "게스트"는 기존 "Guest" 표기를 쓴다.
- API 프로세스 재시작 후 세션 복원 — 세션 스토어가 인메모리라 재시작하면 AC5 경로(새 게스트 세션)로 떨어진다.
- 로그인 후 실패했던 담기 동작의 자동 재시도.

## Open Questions

- [x] Q1: 로그인 UI 형태 — 현재 화면 위 모달(대화·장바구니 유지) vs 별도 페이지 `/signin`(고객 프론트와 같은 형태)?
  → 확정: **모달** (2026-09-14, 사용자). 대화·장바구니를 유지하고 에이전트 칩에서 바로 열린다.
- [x] Q2: 새로고침 유지 저장소 — `sessionStorage`(탭을 닫으면 게스트로 시작, 공용 기기에 안전) vs `localStorage`(브라우저를 다시 열어도 유지)?
  → 확정: **sessionStorage** (2026-09-14, 사용자). 탭 단위 유지, 공용 기기 안전.

> 모든 Open Questions가 해소되어야(`- [x]`) blueprint 단계로 진행할 수 있습니다. (frontmatter `gates.open_q` 와 동기)

---

## 🤖 소스 추적 (기계용 — 사람은 읽지 않아도 됨)

> 추적성 메타. "모두 확인"의 보장이자 frontmatter `sources` 카운트의 원장. 사람용 본문에는 넣지 않는다.

### Sources

| 소스 | 상태 | 비고 |
|------|------|------|
| Jira 티켓 | ✅ 확인 | RBD-8276 (`/jarvis:draft` 산출물 — 품질 검증 통과) |
| PM 티켓 (에픽 링크) | ⚠️ 없음 | 기획 티켓 없음 — 에픽 RBD-8273은 2026-09-09 draft 세션 검토로 분해됨. 에픽 이슈 링크·리모트 링크·첨부 0건 |
| Figma 디자인 | ⏭️ 없음 | 티켓·에픽·PM 어디에도 Figma URL 없음 — 고객 프론트 로그인 화면을 참고 |

### PM 티켓 관련 링크 (전수)

> PM 티켓이 없어 링크 목록도 없다.

| 제목 | kind | source | 상태 | URL |
|------|------|--------|------|-----|
| (없음) | — | — | — | — |

### Reference Code

| 프로젝트 | 파일 경로 | 참조 목적 |
|---------|---------|---------|
| 현재 프로젝트 | `examples/delivered/storefront-web/app/page.tsx` | 헤더·`StoreShell` 조립, `useSession`·장바구니 상태 위치 |
| 현재 프로젝트 | `examples/delivered/storefront-web/lib/api.ts` | `AgentApi` 인스턴스, 카트 호출 패턴 |
| 현재 프로젝트 | `examples/web-shared/session.ts`, `examples/web-shared/api.ts` | 세션 시작 흐름(`startSession`, `X-Session-Id`) — 수정하지 않고 같은 패턴으로 대체 훅 작성 |
| 현재 프로젝트 | `examples/web-shared/storefront/Shell.tsx`, `storefront/frame.ts` | `shopper` 표시 자리, `useStoreFrame().ask` |
| 현재 프로젝트 | `examples/delivered/api/session_routes.py` | 로그인/로그아웃/me 응답 형태와 오류 코드 (RBD-8275) |
| deliveredkorea-customer-frontend | `src/containers/(auth)/signin/SigninContainer.tsx`, `src/containers/_shared/signin/SigninModal/SigninModal.tsx`, `src/hooks/auth/useLogin.ts` | 로그인 폼 구성과 실패 처리 관례 (읽기 참조, 복사 없음) |
