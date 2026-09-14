# Findings: 스토어프론트 로그인 화면 — 이메일 로그인, 게스트 전환

> Jira: RBD-8276 | Mission: ./mission.md | Blueprint: ./blueprint.md
>
> 📌 `/jarvis:develop` 실행 중 발견한 명세 갭/판단/편차/트레이드오프/미결 질문을 4개 카테고리로 누적합니다.
> 노트 ID: 설계 결정=D###, 편차=DV###, 트레이드오프=T###, 미결 질문=Q###.

## 미결 질문 ❓

(없음 — 발생 시 여기 append)

## 편차 ⚠️

### DV001 — 로그인 진입 칩 판정을 정확한 문구가 아니라 "로그인 언급 전반"으로 넓힘

- **태스크**: T012
- **파일**: `examples/delivered/storefront-web/components/SignInPrompt.tsx`
- **시각**: 2026-09-14 11:05
- **상태**: ✅ resolved

**명세**: mission AC7 "'로그인이 필요합니다'가 포함되면", blueprint SignInPrompt 절 "`SIGN_IN_MARKER`가 있으면 칩을 그린다".

**실제**: 본문 판정은 정규식 `/로그인|sign[ -]?in|log[ -]?in/i`. `SIGN_IN_MARKER`는 툴 오류 트레이스 경로에만 쓴다.

**판단**: 실측(2026-09-14, 게스트 담기 턴 SSE)에서 에이전트가 `signed_in: false` 컨텍스트를 보고 툴을 부르지 않은 채 "게스트 세션에서는 로그인 없이 장바구니에 담을 수 없습니다"처럼 다른 표현으로 안내했다. 정확한 문구 매칭은 실제 대화에서 거의 맞지 않으므로 넓혔다. 게스트에게만 보이는 칩이라 과잉 매치("로그인 없이도 검색 가능")의 비용은 로그인 유도 칩 하나뿐이다.

**여파**: mission AC7·P4 인터랙션과 blueprint SignInPrompt 절을 "로그인 안내 전반"으로 재기술 (epilogue 역류 후보).

---

### DV002 — `needsSignIn`이 같은 턴의 툴 오류 트레이스도 스캔

- **태스크**: T012
- **파일**: `examples/delivered/storefront-web/components/SignInPrompt.tsx`
- **시각**: 2026-09-14 11:05
- **상태**: ✅ resolved

**명세**: blueprint "툴 오류가 오류 세그먼트로 오지 않고 어시스턴트 본문 텍스트로만 오므로", 시그니처 `needsSignIn(items)`.

**실제**: `needsSignIn(items, trace)` — 마지막 턴과 같은 `turn`의 `isError` 트레이스 `detail`/`excerpt`에 마커가 있어도 true.

**판단**: mission AC7의 "(툴 오류 포함)"을 따랐다. 모델이 로그인 언급 없이 실패만 전하는 경우를 트레이스가 보완한다.

**여파**: blueprint Architecture Overview·SignInPrompt 절 갱신 (mission과 blueprint가 어긋났던 지점).

---

### DV003 — 로그인 422도 `invalid_credentials`로 매핑

- **태스크**: T003
- **파일**: `examples/delivered/storefront-web/lib/session.ts`
- **시각**: 2026-09-14 10:54
- **상태**: ✅ resolved

**명세**: blueprint lib/session.ts "401→invalid_credentials, 502→auth_unavailable, 그 외 !ok·예외→network".

**실제**: 422(본문 검증 실패)도 `invalid_credentials`.

**판단**: 422는 입력 문제라 "잠시 후 재시도"보다 "이메일·비밀번호가 맞지 않습니다"가 손님에게 맞는 안내다.

**여파**: blueprint lib/session.ts 주요 로직 한 줄 갱신.

---

### DV004 — 로그인 상태·액션을 헤더가 아니라 헤더 아래 배너 스트립에 둠

- **태스크**: T010
- **파일**: `examples/delivered/storefront-web/components/AccountBar.tsx`, `app/page.tsx`
- **시각**: 2026-09-14 10:54
- **상태**: ✅ resolved

**명세**: mission UI/Design "헤더 우측 손님 영역: 게스트면 'Guest' + Sign in 버튼 … `StoreShell`의 `shopper` 표시는 그대로 두고 Sign in/Sign out 액션을 붙인다".

**실제**: `StoreShell banner` 슬롯의 한 줄 스트립("Browsing as a guest · …" / "Signed in as {name} · {tier}") — blueprint가 이미 이렇게 설계했고 코드는 blueprint를 따른다.

**판단**: web-shared `StoreShell` 헤더에는 액션 슬롯이 없고 web-shared는 수정하지 않기로 했다. 헤더의 아바타·이름 표시는 그대로 남아 있다.

**여파**: mission UI/Design 화면 구성·컴포넌트 절을 blueprint와 맞춘다.

---

### DV005 — 로그인 실패 시 비밀번호 필드를 모든 실패에서 비움

- **태스크**: T005
- **파일**: `examples/delivered/storefront-web/components/LoginSheet.tsx`
- **시각**: 2026-09-14 10:54
- **상태**: ✅ resolved

**명세**: blueprint LoginSheet "`invalid_credentials`면 … 비밀번호 필드 비움"; mission NFR "비밀번호는 제출 직후 폼 상태에서 지운다".

**실제**: 응답이 온 뒤 실패 사유와 무관하게 비운다(제출 중에는 유지).

**판단**: mission NFR(제출 후 지운다) 쪽을 따랐다. 502에서도 비밀번호를 폼에 남겨둘 이유가 없다.

**여파**: blueprint LoginSheet 절 문구를 mission NFR과 통일.

---

### DV006 — 웹 워크스페이스에 vitest 테스트 러너 추가

- **태스크**: T001
- **파일**: `examples/delivered/storefront-web/package.json`, `vitest.config.ts`, `vitest.setup.ts`, `*.test.ts(x)` 6건
- **시각**: 2026-09-14 10:52
- **상태**: ✅ resolved

**명세**: blueprint Tech Stack "테스트 러너: 웹 워크스페이스에 없음 … 검증은 `next build`와 AC 수동 체크".

**실제**: vitest + @testing-library를 storefront-web devDependencies에 추가하고 테스트 29건 작성.

**판단**: tasks 스테이지가 테스트 포함(기본)으로 T001을 만들었고 develop이 그대로 수행했다. 테스트 파일은 `tsconfig.json` exclude로 `next build`에서 제외된다.

**여파**: blueprint Tech Stack 절 갱신.

---

## 설계 결정 📘

### D001 — 게스트가 상품 카드 Add를 눌러 실패하면 로그인 시트를 연다

- **태스크**: T012
- **파일**: `examples/delivered/storefront-web/components/Chat.tsx`
- **시각**: 2026-09-14 10:54
- **상태**: ✅ resolved

**맥락**: mission 인터랙션 절의 로그인 진입점은 배너 버튼과 어시스턴트 칩 둘뿐이고, 카드 Add 버튼 경로는 언급이 없다.

**판단**: `addToCart`가 null이고 게스트면 `onSignIn()`으로 시트를 연다.

**근거**: 게스트의 Add는 항상 400(로그인 필요)으로 끝나므로 아무 반응 없이 끝나는 것보다 낫다. 단 `addToCart`는 원인 불문 null이라 게스트의 네트워크 실패도 시트를 연다(무해).

**여파**: mission P4 인터랙션에 진입점 셋째 항목으로 추가 후보. README에는 이미 기술.

---

### D002 — "Keep me signed in"은 API 본문 `remember_me`로만 전달하고 클라이언트 동작은 없다

- **태스크**: T007
- **파일**: `examples/delivered/storefront-web/lib/useDeliveredSession.ts`, `components/LoginSheet.tsx`
- **시각**: 2026-09-14 10:54
- **상태**: ✅ resolved

**맥락**: mission은 "로그인 유지 체크"만 두고 의미는 침묵. 브라우저 저장은 `sessionStorage`의 세션 id 하나로 고정(Q2).

**판단**: 체크값은 로그인 요청의 `remember_me`(게이트웨이 refresh 토큰 수명)로만 쓴다.

**근거**: mission "토큰·비밀번호는 저장하지 않는다"와 양립하는 유일한 해석. 브라우저 쪽 유지 범위는 Q2가 정한 탭 단위 그대로다.

**여파**: mission UI/Design 컴포넌트 절에 한 줄 설명 추가 후보.

---

## 트레이드오프 🔀

(없음 — 명세가 열어둔 양자택일 지점이 없었다)
