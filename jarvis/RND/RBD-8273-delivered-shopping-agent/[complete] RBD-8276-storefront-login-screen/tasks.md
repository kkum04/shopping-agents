---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: tasks
completed: [mission, blueprint, tasks, develop]
plan: []
skip: []
depth: standard
base_sha: bf0fe16
gates:
  open_q: 0
  findings_pending: 0
risk:
  self: 0.0                     # 커버리지 갭 0 · [P] 파일 충돌 0 · 태스크 14(<15) → 생략
  review: skipped
tests: included                 # vitest + Testing Library (T001이 워크스페이스에 추가)
task_count: 14
coverage:
  - ac: AC1
    tasks: [T005, T007, T008]
  - ac: AC2
    tasks: [T002, T003, T004, T005]
  - ac: AC3
    tasks: [T002, T003, T004, T005]
  - ac: AC4
    tasks: [T006, T007, T008]
  - ac: AC5
    tasks: [T006, T007]
  - ac: AC6
    tasks: [T009, T010, T008]
  - ac: AC7
    tasks: [T011, T012]
  - ac: AC8
    tasks: [T014]
uncovered_acs: []
parallel_conflicts: []
---

# Tasks: 스토어프론트 로그인 화면 — 이메일 로그인, 게스트 전환

> Mission: ./mission.md | Blueprint: ./blueprint.md | Jira: RBD-8276
> 모든 경로는 `examples/delivered/storefront-web/` 기준. 테스트는 vitest + @testing-library/react(jsdom), API 호출은 `fetch` 모킹(외부 의존성만 모킹 — MSW는 워크스페이스 규모상 도입하지 않는다).

## Implementation Strategy

- **실행 모드**: 일괄 흐름 — 작은 FE 티켓(10파일)이라 phase 구분은 TDD 순서용이며 PR은 하나다.
- **MVP 경계**: Phase 1~3(US1 로그인)까지가 MVP — 폼에서 로그인하면 헤더 배너에 이름이 뜬다. US2·US3·US4는 각각 한 phase씩 얹는다.
- **별도 PR 분기점**: 없음(단일 PR). 굳이 나누면 US4(진입 칩)는 독립.
- **병렬 실행 예시**: T004(LoginSheet 테스트)와 T006(훅 테스트)은 파일이 달라 동시 작성 가능. T009(AccountBar 테스트)와 T011(SignInPrompt 테스트)도 동시 가능.
- **web-shared는 건드리지 않는다.** 필요한 프리미티브는 `Sheet`·`Button`·`useStoreFrame`뿐이며 전부 이미 export되어 있다.

## Phase 1: Setup

- [X] T001 vitest 테스트 러너 추가 — `package.json` devDependencies(vitest, @vitejs/plugin-react, jsdom, @testing-library/react, @testing-library/user-event, @testing-library/jest-dom)와 `"test": "vitest run"` 스크립트, `vitest.config.ts`(jsdom, `@/*` alias, setup 파일에 jest-dom), `examples/package-lock.json` 갱신 (`npm install`은 `examples/`에서). `next build`에 테스트 파일이 섞이지 않도록 `tsconfig.json` exclude에 `**/*.test.tsx` 추가 여부 확인 (파일 경로: `package.json`, `vitest.config.ts`, `vitest.setup.ts`, `tsconfig.json`)

## Phase 2: Foundational — 세션 API 계층

- [X] T002 `lib/session.ts` 단위 테스트 작성 (Red) — `fetch` 모킹으로 `login`이 200→`{ok:true, summary}`, 401→`invalid_credentials`, 502→`auth_unavailable`, 네트워크 예외→`network`를 돌려주는지, `fetchSessionMe`가 404→`null`인지, 저장소 helper가 `sessionStorage` 예외를 삼키는지 (`lib/session.test.ts`)
- [X] T003 `lib/types.ts`에 `SessionSummary`(`session_id, user_id, signed_in, name, tier, country`)·`LoginResult`(ok/reason 유니온) 추가하고 `lib/session.ts` 구현 (Green) — `SESSION_STORAGE_KEY = "delivered.sessionId"`, `readStoredSessionId/writeStoredSessionId/clearStoredSessionId`, `fetchSessionMe(api)`, `login(api, {email, password, remember_me})`(`fetch(\`${api.base}/session/login\`, {method:"POST", headers: api.headers(true)})`로 상태 코드 보존), `logout(api)` (`lib/types.ts`, `lib/session.ts`)

## Phase 3: US1 — 이메일·비밀번호 로그인 (P1)

**목표**: 헤더 아래 배너의 Sign in → 폼 제출 → 같은 세션이 회원으로 전환되고 이름이 보인다.
**독립 테스트 기준**: 데모 API(:8004)에 스테이징 계정으로 로그인하면 배너에 `A0020 · Basic`이 뜨고, 틀린 비밀번호는 폼 안 오류로만 보인다.

- [X] T004 [P] [US1] `LoginSheet` 컴포넌트 테스트 작성 (Red) — 이메일·비밀번호 입력 후 제출하면 `onSubmit(email, password, rememberMe)` 호출, 제출 중 버튼 disabled, `invalid_credentials` 결과면 "don't match" 문구 + 비밀번호 필드 비움, `auth_unavailable`이면 "unavailable" 문구, 성공이면 `onClose` 호출, Esc로 `onClose` (`components/LoginSheet.test.tsx`)
- [X] T005 [US1] `LoginSheet` 구현 (Green) — web-shared `Sheet`(`title="Sign in to delivered"`) 안에 `<form>`: 이메일(`type=email`, autoFocus, `autoComplete=email`), 비밀번호(`autoComplete=current-password`), "Keep me signed in" 체크, `Button variant=primary` 제출, `role="alert"` 오류 줄. props `LoginSheetProps { onSubmit; onClose }`, 핸들러는 `useCallback`, 인라인 함수 금지 (`components/LoginSheet.tsx`)
- [X] T006 [P] [US1] `useDeliveredSession` 훅 테스트 작성 (Red) — `renderHook`으로 (a) 저장된 id 없음 → `startSession` 호출·id 저장·`shopper.name === "Guest"`, (b) 저장된 id + `me` 성공 → 그 id 유지·`signedIn`·이름 반영, (c) 저장된 id + `me` 404 → 새 세션 시작·저장값 교체, (d) `login` 성공 → `api.session`·저장값·`shopper` 갱신, 실패 → 상태 불변 + 사유 반환, (e) `logout` → `shopper` Guest·같은 sessionId (`lib/useDeliveredSession.test.ts`)
- [X] T007 [US1] `useDeliveredSession(api)` 구현 (Green) — 반환 `{ sessionId, shopper, signedIn, busy, login, logout }`; 마운트 복원(세대 가드로 늦은 응답 폐기), `login`/`logout`은 `lib/session.ts` 호출 후 요약 적용. web-shared `useSession`과 같은 `sessionId/shopper` 모양 유지 (`lib/useDeliveredSession.ts`)
- [X] T008 [US1] `app/page.tsx` 조립 — `useSession` → `useDeliveredSession`(미사용 import 제거), `loginOpen` 상태, `handleLogin`(성공 시 닫기 + `api.fetchCart` 재조회 + `checkoutStaged` 초기화), `handleLogout`(카트 재조회), `banner={<AccountBar …/>}`, `{loginOpen ? <LoginSheet …/> : null}` (`app/page.tsx`)

## Phase 4: US2 — 새로고침 후 세션 유지 (P2)

**목표**: 새로고침해도 같은 세션·로그인 상태·장바구니가 이어진다.
**독립 테스트 기준**: 로그인 → 새로고침 → 배너 이름 유지·카트 유지. API 재시작 → 새로고침 → 오류 없이 Guest.

- [X] (T006·T007에서 복원 경로를 함께 다룬다 — 별도 코드 없음) 검증만: T014에서 새로고침·API 재시작 시나리오를 확인한다

## Phase 5: US3 — 로그아웃과 게스트 전환 (P3)

**목표**: 배너의 Sign out → Guest, 카트 패널 비움, 대화 유지.
**독립 테스트 기준**: 로그인 상태에서 Sign out → 배너 "Browsing as a guest", 카트 "Nothing in the cart yet.", 이전 대화 그대로.

- [X] T009 [P] [US3] `AccountBar` 테스트 작성 (Red) — 게스트면 guest 문구 + "Sign in" 버튼(`onSignIn`), 회원이면 `name`·`tier` + "Sign out" 버튼(`onSignOut`), `busy`면 버튼 disabled (`components/AccountBar.test.tsx`)
- [X] T010 [US3] `AccountBar` 구현 (Green) — props `AccountBarProps { shopper; signedIn; busy; onSignIn; onSignOut }`, `StoreShell banner` 슬롯용 한 줄 스트립(토큰 색상, `gap`으로 간격), web-shared `Button size=sm` (`components/AccountBar.tsx`)

## Phase 6: US4 — 에이전트 안내에서 로그인 진입 (P4)

**목표**: 어시스턴트 답변에 "로그인이 필요합니다"가 오면 대화 하단에 "Sign in to continue" 칩.
**독립 테스트 기준**: 게스트로 "장바구니에 담아줘" → 안내 턴 아래 칩 → 클릭 → 로그인 시트.

- [X] T011 [P] [US4] `needsSignIn(items)`·`SignInPrompt` 테스트 작성 (Red) — 마지막 어시스턴트 아이템(`pending=false`)의 `text` 세그먼트에 "로그인이 필요합니다"가 있으면 true, pending이거나 사용자 턴이 마지막이면 false; 컴포넌트는 `signedIn`이면 렌더 안 함, 칩 클릭 → `onSignIn` (`components/SignInPrompt.test.tsx`)
- [X] T012 [US4] `SignInPrompt` 구현 + `Chat.tsx` 도킹 — `SIGN_IN_MARKER` 상수와 순수 `needsSignIn`, `.chip` 버튼 "Sign in to continue"; `Chat`을 `flex h-full flex-col`로 감싸 `ChatShell`(`min-h-0 flex-1`) 아래에 배치, props `signedIn`·`onSignIn` 추가하고 `page.tsx`에서 전달 (`components/SignInPrompt.tsx`, `components/Chat.tsx`, `app/page.tsx`)

## Final Phase: Polish & 검증

- [X] T013 README에 스토어프론트 로그인 사용법 한 단락 추가 — 배너의 Sign in, 스테이징 계정, 새로고침 유지(탭 단위), 로그아웃 (`examples/delivered/README.md`)
- [X] T014 검증 — `examples/delivered/storefront-web`에서 `npm test`와 `next build` 통과(AC8), 데모(`scripts/run_demo.py delivered --no-install`)를 띄워 AC1~AC7을 실제 스테이징 계정으로 확인(새로고침 유지, API 재시작 후 게스트 복귀, 로그아웃 후 카트 비움, 진입 칩). 결과를 tasks.md 체크와 findings에 남긴다 ✅ 2026-09-14: `npm test` 29건 통과 · `next build` 통과 · dev 서버(3004) 200 · 게스트 담기 턴 SSE 실측(에이전트가 툴 호출 없이 다른 표현으로 로그인 안내 → 판정 넓힘) · 브라우저 클릭스루(AC1·AC2·AC6 화면)는 사용자 확인 대상

## Dependencies

- T001 → 모든 테스트 태스크(T002, T004, T006, T009, T011)
- T002 → T003 → T005, T007
- T004 → T005 · T006 → T007 · T009 → T010 · T011 → T012
- T005, T007, T010 → T008(조립) → T012(칩 연결) → T013 → T014
- [P] 표시 태스크는 서로 다른 파일만 만진다(충돌 없음).
