---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: blueprint
completed: [mission, blueprint]
plan: [tasks, develop]
skip: []
depth: standard
base_sha: bf0fe16
gates:
  open_q: 0
risk:
  self: 0.0                     # base 0 (신규 API·DB·cross-domain·연동 없음) + 설계 품질 신호 0 → < 0.4 생략
  review: skipped
design:
  new_api: false                # BE 경로는 RBD-8275가 이미 제공 — 소비만 한다
  db_migration: false
  cross_domain: 1               # examples/delivered/storefront-web 한 모듈 (web-shared는 읽기만)
  tx_boundary: false
  files_touched: 10
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [로그인, 세션, 게스트, 헤더, 장바구니, 스토어프론트]
  modules:
    - examples/delivered/storefront-web/app/page.tsx
    - examples/delivered/storefront-web/lib/api.ts
    - examples/delivered/storefront-web/lib/types.ts
    - examples/delivered/storefront-web/lib/session.ts
    - examples/delivered/storefront-web/lib/useDeliveredSession.ts
    - examples/delivered/storefront-web/components/LoginSheet.tsx
    - examples/delivered/storefront-web/components/AccountBar.tsx
    - examples/delivered/storefront-web/components/SignInPrompt.tsx
    - examples/delivered/storefront-web/components/Chat.tsx
    - examples/delivered/README.md
coverage:
  - ac: AC1
    modules: [components/LoginSheet.tsx, lib/session.ts, lib/useDeliveredSession.ts, app/page.tsx]
  - ac: AC2
    modules: [lib/session.ts, components/LoginSheet.tsx]
  - ac: AC3
    modules: [lib/session.ts, components/LoginSheet.tsx]
  - ac: AC4
    modules: [lib/session.ts, lib/useDeliveredSession.ts, app/page.tsx]
  - ac: AC5
    modules: [lib/useDeliveredSession.ts]
  - ac: AC6
    modules: [components/AccountBar.tsx, lib/session.ts, app/page.tsx]
  - ac: AC7
    modules: [components/SignInPrompt.tsx, components/Chat.tsx, app/page.tsx]
  - ac: AC8
    modules: [examples/delivered/storefront-web (next build)]
---

# Blueprint: 스토어프론트 로그인 화면 — 이메일 로그인, 게스트 전환

> Mission: ./mission.md | Jira: RBD-8276

## Tech Stack

- **Language**: TypeScript 5.6 (strict), React 19
- **Framework**: Next.js 16 app router (`"use client"` 페이지), Tailwind CSS 4 + 앱 토큰(`--ink`, `--line`, `--card` …), `globals.css`의 `.chip` / `.btn-primary`
- **공용 패키지**: `web-shared`(file 의존) — `AgentApi`, `StoreShell`, `Sheet`, `Button`, `useAgentTurn`, `useStoreFrame`. **수정하지 않는다**(리테일 등 다른 예제와 공유).
- **상태**: 로컬 `useState`/커스텀 훅. 이 워크스페이스는 React Query를 쓰지 않으므로(리소스 읽기는 `useResource`) 공통 컨벤션 4.2 대신 레포 패턴을 따른다.
- **테스트 러너**: 웹 워크스페이스에 없음(`*.test.*` 0건). 검증은 `next build`(타입·린트)와 AC 수동 체크.

## Architecture Overview

브라우저 → `AgentApi`(`X-Session-Id`) → delivered API(:8004). BE는 RBD-8275가 만든 세션 경로를 이미 제공한다:

| 경로 | 용도 | 성공 | 실패 |
|------|------|------|------|
| `POST /api/session` | 게스트 세션 시작 | `{session_id, user_id, name, tier}` | — |
| `POST /api/session/login` (헤더 `X-Session-Id` 선택) | 같은 세션을 회원으로 전환 | `SessionSummary` | 401 `invalid_credentials` · 502 `auth_unavailable` · 422 |
| `POST /api/session/logout` | 같은 세션을 게스트로 | `SessionSummary` | 404(세션 없음) |
| `GET /api/session/me` | 세션 요약 | `SessionSummary` | 404(세션 없음) |
| `GET /api/cart` | 세션 장바구니(게스트는 빈 카트) | `CartPayload` | — |

`SessionSummary = {session_id, user_id, signed_in, name, tier, country}`.

FE 쪽 새 조각은 셋이다: (1) **세션 훅** `useDeliveredSession`이 web-shared `useSession`을 대체해 `sessionStorage`의 세션 id로 복원하고 로그인/로그아웃 후 요약을 갱신한다. (2) **LoginSheet**가 web-shared `Sheet`(포털 다이얼로그, Esc·스크림 닫힘) 위에 폼을 그린다. (3) **AccountBar**가 `StoreShell`의 `banner` 슬롯에 로그인 상태와 Sign in / Sign out 액션을 둔다 — `StoreShell`의 아바타 버튼은 `AccountSheet`(메모리·프로필)를 열고 액션 슬롯이 없어, 헤더 자체를 건드리지 않고 그 바로 아래 스트립에 둔다. 로그인 필요 안내는 툴 오류가 오류 세그먼트로 오지 않고 어시스턴트 본문 텍스트로만 오므로, **SignInPrompt**가 마지막 어시스턴트 턴의 텍스트에서 "로그인이 필요합니다"를 찾아 대화 하단(컴포저 바로 위)에 칩을 도킹한다 — 그 턴은 항상 마지막 턴이므로 사실상 그 턴 아래에 놓인다.

```text
page.tsx ─ useDeliveredSession(api) ─┬─ restore: sessionStorage → GET /session/me → (404) POST /session
                                     ├─ login(email,pw,remember) → POST /session/login → summary
                                     └─ logout() → POST /session/logout → summary
   ├─ StoreShell banner={<AccountBar/>}        Guest · [Sign in] | {name} · {tier} · [Sign out]
   ├─ Chat ─ SignInPrompt (마지막 턴 텍스트에 "로그인이 필요합니다" → chip → onSignIn)
   └─ {loginOpen && <LoginSheet onSubmit=login onClose/>}
```

## Directory Structure

```text
examples/delivered/storefront-web/
├── app/page.tsx                       (수정) useSession → useDeliveredSession, banner·LoginSheet·SignInPrompt 조립, 로그인/로그아웃 후 카트 갱신
├── lib/api.ts                         (수정) api 인스턴스 유지, fetchCart 재사용
├── lib/types.ts                       (수정) SessionSummary 타입 추가
├── lib/session.ts                     (신규) 세션 저장소 helper + login/logout/me 호출(상태 코드 보존)
├── lib/useDeliveredSession.ts         (신규) 세션 복원·로그인·로그아웃 훅
├── components/LoginSheet.tsx          (신규) 로그인 폼 다이얼로그
├── components/AccountBar.tsx          (신규) 헤더 아래 계정 스트립
├── components/SignInPrompt.tsx        (신규) 로그인 진입 칩
└── components/Chat.tsx                (수정) ChatShell 아래에 SignInPrompt 도킹
examples/delivered/README.md           (수정) 로그인 화면 사용법 한 단락
```

## Module Design

### lib/session.ts — 세션 저장소와 세션 API 호출

- **책임**: `sessionStorage` 키 `delivered.sessionId` 읽기/쓰기/삭제(`try/catch`로 접근 불가 브라우저 대비), `fetchSessionMe(api)`, `login(api, body)`, `logout(api)`. `AgentApi.post`는 실패 시 `null`만 돌려줘 401/502를 구분할 수 없으므로 로그인은 `fetch(\`${api.base}/session/login\`, {headers: api.headers(true)})`로 직접 부르고 상태 코드를 결과로 매핑한다.
- **위치**: `examples/delivered/storefront-web/lib/session.ts`
- **의존성**: `AgentApi`(web-shared), `SessionSummary`(lib/types)
- **주요 로직**: `login` → `{ok: true, summary}` | `{ok: false, reason: "invalid_credentials" | "auth_unavailable" | "network"}` (401→invalid_credentials, 502→auth_unavailable, 그 외 !ok·예외→network). `fetchSessionMe`는 404·네트워크 모두 `null`. `logout`은 요약 또는 `null`.

### lib/useDeliveredSession.ts — 세션 훅

- **책임**: 마운트 시 세션 복원, `login`/`logout` 액션, `shopper`/`signedIn` 파생값 제공. web-shared `useSession`과 같은 반환 모양(`sessionId`, `shopper`)을 유지해 `useAgentTurn(api, {...session})` 호출부가 바뀌지 않게 한다.
- **위치**: `examples/delivered/storefront-web/lib/useDeliveredSession.ts`
- **의존성**: `lib/session.ts`, `AgentApi`
- **주요 로직**:
  1. 복원: 저장된 id가 있으면 `api.session = id` 후 `fetchSessionMe`; 성공이면 요약 적용. 실패(404·네트워크)하거나 저장값이 없으면 `api.startSession()` → 새 id 저장. web-shared `useSession`과 같은 세대(generation) 가드로 늦게 도착한 응답을 버린다.
  2. `login(email, password, rememberMe)`: `session.login` 호출 → 성공 시 `api.session = summary.session_id`(세션 없이 로그인한 경우 새 id), 저장, 상태 갱신, `{ok:true}` 반환; 실패 사유는 그대로 반환해 폼이 문구를 고른다.
  3. `logout()`: `session.logout` → 요약 적용(게스트). 세션 id는 유지(같은 세션이 게스트로 계속).
  4. 파생: `signedIn = summary?.signed_in ?? false`, `shopper = signedIn ? {name, tier ?? undefined} : {name: "Guest"}`.

### components/LoginSheet.tsx — 로그인 폼

- **책임**: web-shared `Sheet`(`role="dialog"`, Esc·스크림 닫힘) 안에 이메일·비밀번호·"Keep me signed in" 체크·Sign in 버튼·오류 줄을 그린다.
- **위치**: `examples/delivered/storefront-web/components/LoginSheet.tsx`
- **의존성**: `Sheet`, `Button`(web-shared `ui`), `LoginResult`(lib/session)
- **주요 로직**: props `{ onSubmit(email, password, rememberMe): Promise<LoginResult>; onClose }`. 제출 중 `submitting`으로 버튼·입력 비활성(이중 제출 방지). 결과가 `invalid_credentials`면 "That email and password don't match." + 비밀번호 필드 비움, `auth_unavailable`/`network`면 "delivered sign-in is unavailable right now. Try again in a moment." 성공이면 `onClose`. 이메일 필드 autofocus, `autoComplete` 지정. 문구는 영문 UI 유지(mission Out of Scope).

### components/AccountBar.tsx — 계정 스트립

- **책임**: `StoreShell banner`에 들어가는 한 줄: 게스트면 "Browsing as a guest · Sign in to use your delivered cart" + Sign in 버튼, 회원이면 "Signed in as {name}{tier ? · tier}" + Sign out 버튼.
- **위치**: `examples/delivered/storefront-web/components/AccountBar.tsx`
- **의존성**: `Button`(web-shared)
- **주요 로직**: props `{ shopper, signedIn, busy, onSignIn, onSignOut }`. 로그아웃 진행 중 버튼 비활성.

### components/SignInPrompt.tsx + components/Chat.tsx — 로그인 진입 칩

- **책임**: `chat.items`의 마지막 어시스턴트 아이템(`pending === false`)의 `text` 세그먼트에 `SIGN_IN_MARKER = "로그인이 필요합니다"`가 있으면 `.chip` 버튼 "Sign in to continue"를 그린다. 게스트일 때만.
- **위치**: `examples/delivered/storefront-web/components/SignInPrompt.tsx`, `components/Chat.tsx`(도킹)
- **의존성**: `AssistantChatItem`·`ChatItem` 타입(web-shared `protocol`), `AgentTurn.items`
- **주요 로직**: `Chat`이 `flex h-full flex-col`로 감싸 위에는 기존 `ChatShell`(`min-h-0 flex-1`), 아래에 `SignInPrompt`. props `{ chat, signedIn, onSignIn }`. 마커 판정은 순수 함수 `needsSignIn(items)`로 분리해 web-shared를 건드리지 않는다.

### app/page.tsx — 조립

- **책임**: `useDeliveredSession(api)`로 교체, `loginOpen` 로컬 상태, `banner={<AccountBar … />}`, `Chat`에 `signedIn`·`onSignIn`, 로그인 성공·로그아웃 후 `api.fetchCart()` 재조회(게스트 카트는 비어 `items: []`로 패널이 비워짐), `checkoutStaged` 초기화.
- **주요 로직**: `handleLogin` → 훅 `login` → ok면 `setLoginOpen(false)` + 카트 재조회. `handleLogout` → 훅 `logout` → 카트 재조회. `session.sessionId` 변화에 걸린 기존 카트 effect는 유지(복원 시 카트 로드).

## Error Handling

- 로그인 401 → 폼 내부 오류(AC2), 502/네트워크 → 폼 내부 재시도 문구(AC3). 어느 경우도 세션·저장값을 바꾸지 않는다.
- 복원 시 `me` 404/실패 → 조용히 새 게스트 세션(AC5). `startSession`마저 실패하면 `sessionId: null`로 두어 기존 `UNREACHABLE` 안내 경로가 그대로 동작한다.
- 로그아웃 실패(404 등) → 배너 상태 유지, 콘솔 오류 없이 무시(다음 액션에서 복원 경로가 정리).
- `sessionStorage` 접근 예외(프라이빗 모드 등) → 저장 없이 진행(새로고침 유지만 안 됨).

## Migration / Side Effects

- DB·마이그레이션 없음. `web-shared` 변경 없음 → 다른 예제 영향 없음.
- `page.tsx`가 `useSession`을 더 이상 쓰지 않으므로 web-shared import 목록에서 제거(미사용 import는 `next build` 린트에 걸린다).
- 새로고침 후 같은 세션을 이어가므로 API 프로세스가 살아 있는 동안 대화·장바구니가 유지된다. 데모를 초기화하려면 탭을 닫거나 기존 `/api/reset` 경로(변경 없음)를 쓴다.
- `scripts/smoke_chat.py`·`verify_all.py`에는 영향 없음(빌드만 돈다).
