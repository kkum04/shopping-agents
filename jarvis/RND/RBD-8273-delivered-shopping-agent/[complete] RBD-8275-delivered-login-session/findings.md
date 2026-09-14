# Findings: [shopping-agents] delivered 로그인 연동 — 세션에 토큰 보관, 고객 API Bearer 호출 (1)

> Jira: RBD-8275 | Mission: ./mission.md | Blueprint: ./blueprint.md
>
> 📌 `/jarvis:develop` 실행 중 발견한 명세 갭/판단/편차/트레이드오프/미결 질문을 4개 카테고리로 누적합니다.
> 노트 ID: 설계 결정=D###, 편차=DV###, 트레이드오프=T###, 미결 질문=Q###.

## 미결 질문 ❓

### Q001 — 인증 게이트웨이 로그인 성공 응답 형식을 실제 계정으로 확인하지 못함

- **태스크**: T002, T006
- **파일**: `examples/delivered/api/delivered_auth.py`, `examples/delivered/api/tests/test_delivered_auth.py`
- **시각**: 2026-09-11 15:40
- **상태**: ✅ resolved

**해소**: 2026-09-14 스테이징 계정으로 실제 로그인 — 응답은 평면 객체 `{id, accessToken, refreshToken, userId, userName, role, service, refreshTokenExpiredAt}`로 가정과 일치. `userName`을 이름 폴백으로 추가 사용.

**맥락**: `POST /auth/sign-in/dk-service/customer`의 성공 응답(`accessToken`, `refreshToken`, `userId`, `userName`)은 고객 프론트 타입(`authApiDto.ts:47-56`)에서 읽은 가정이다. 스테이징에 자격증명 없이 호출해 실패 경로(404 `NOT_FOUND_USER`, `apiKey` 헤더 불필요)는 확인했지만, 성공 응답은 스테이징 계정이 없어 관찰하지 못했다.

**임시 판단**: 프론트 타입대로 파싱하고, `accessToken`이 없으면 `AuthUnavailable`(502)로 실패시킨다.

**답 필요**: 스테이징 계정으로 한 번 로그인해 응답 필드가 위와 같은지 확인해 주세요. 다르면 `DeliveredAuthClient.sign_in`의 파싱을 맞춥니다. (delivered-auth-gateway의 POST /auth/sign-in/dk-service/customer 응답 형식을 실제로 확인했는가?)

**여파**: blueprint-integration.md 「이메일 로그인」 `verified: false` → true

---

### Q002 — 고객 API `/v2/me` 성공 응답 형식을 실제 토큰으로 확인하지 못함

- **태스크**: T002, T004, T006
- **파일**: `examples/delivered/api/delivered_auth.py`, `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-11 15:40
- **상태**: ✅ resolved

**해소**: 2026-09-14 실제 토큰으로 호출 — 응답은 **`{result: true, data: {customerId, customerEmail, firstName, lastName, country, memberTier, ...}, message}` 엔벨로프**였다(가정과 다름). `CustomerProfile.from_me`가 `data`를 벗겨 읽도록 고쳤고, 이름이 null인 계정은 로그인 응답의 `userName`으로 폴백한다. `Expired Token` 문자열은 아직 미관찰(고객 프론트 코드 기준).

**맥락**: `GET /v2/me`의 필드(`customerId`, `firstName`, `lastName`, `country`, `memberTier`, `customerEmail`)는 고객 프론트의 `MeResponseT`(평면 객체) 가정이다. 스테이징에서 토큰 없이 401 `Authorization Key not found`, 잘못된 토큰으로 401 `Request Not Available(Token is altered)`는 확인했다. `Expired Token` 메시지 문자열은 고객 프론트 인터셉터 코드 기준이다.

**임시 판단**: 평면 객체로 파싱하고 이름은 `firstName lastName`, 등급은 `memberTier`로 매핑한다. 응답이 `{result, data}` 엔벨로프면 이름이 "delivered customer"로 떨어진다.

**답 필요**: 실제 토큰으로 `/v2/me`를 한 번 호출해 평면 객체인지, 필드명이 맞는지 확인해 주세요. (delivered-customer-api의 GET /v2/me 응답 형식을 실제로 확인했는가?)

**여파**: blueprint-integration.md 「내 프로필」 `verified: false` → true; `CustomerProfile.from_me`

---

## 편차 ⚠️

### DV001 — 로그아웃이 장바구니까지 비웠음 (정정됨)

- **태스크**: T005
- **파일**: `examples/delivered/api/delivered_backend.py` `sign_out`
- **시각**: 2026-09-11 16:20
- **상태**: ✅ resolved

**명세**: mission 「데이터 요구사항」 "토큰만 지우고 세션과 대화는 유지한다", blueprint-api.md 로그아웃 "세션의 토큰을 지우고 같은 세션을 게스트로 이어간다".

**실제**: `sign_out`이 `_carts.reset(session_id)`로 인메모리 장바구니도 비웠고, 만료 경로는 자격증명만 지워 두 경로가 달랐다.

**판단**: 격리 평가 지적 직후 `sign_out`에서 장바구니 초기화를 제거해 명세대로 토큰만 지운다. 재로그인 시 장바구니가 살아난다.

**여파**: -

---

### DV002 — `require_credential`·`customer_call` 시그니처에 필수 `feature` 인자 추가 (정정됨)

- **태스크**: T005
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-11 16:20
- **상태**: ✅ resolved

**명세**: blueprint.md Module Design "`require_credential(session) -> SessionCredential`", "`customer_call(session, method, path, **kw)` — RBD-8277·RBD-8280의 진입점".

**실제**: 두 메서드에 위치 인자 `feature`를 필수로 넣어 후속 티켓이 쓸 시그니처와 어긋났다.

**판단**: `feature`를 키워드 인자(기본값 "이 기능")로 바꿔 blueprint 시그니처를 유지하면서 안내 문장에 기능명을 넣을 수 있게 했다.

**여파**: -

---

## 설계 결정 📘

### D001 — 로그인 게이트웨이의 401/404 외 4xx는 전부 `AuthUnavailable`(502)

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_auth.py` `sign_in`
- **시각**: 2026-09-11 16:20
- **상태**: ✅ resolved

**맥락**: blueprint-integration.md는 401/404와 5xx·타임아웃·비JSON만 다루고 400·403·422·429는 침묵.

**판단**: `status_code >= 400`이면 자격증명 오류가 아닌 한 전부 `AuthUnavailable`로 fail-closed. 어떤 경우도 토큰을 세션에 남기지 않는다.

**근거**: 게이트웨이의 나머지 4xx 의미를 모르는 상태에서 로그인 성공으로 오인할 길을 막는다.

---

### D002 — 고객 API의 4xx와 비JSON 2xx도 `DeliveredApiError`로 합류

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_auth.py` `customer_request`
- **시각**: 2026-09-11 16:20
- **상태**: ✅ resolved

**맥락**: blueprint-integration.md "그 외 5xx → `DeliveredApiError`"만 언급.

**판단**: `Expired Token` 메시지를 먼저 검사하고, 그 외 4xx·5xx·비JSON은 모두 `DeliveredApiError` 한 종류로 던져 프레임워크의 "일시 불가" 문장에 합류시킨다.

**근거**: 예외 종류를 늘려도 모델에게 줄 문장이 달라지지 않는다.

---

### D003 — 로그인 직후 `/me`가 `Expired Token`이면 흡수하지 않고 로그인 502

- **태스크**: T005
- **파일**: `examples/delivered/api/delivered_backend.py` `sign_in`
- **시각**: 2026-09-11 16:20
- **상태**: ✅ resolved

**맥락**: blueprint-integration.md는 "로그인 직후에는 발생하지 않는다고 가정".

**판단**: 발생하면 `AuthUnavailable`로 승격해 로그인 자체를 실패시킨다.

**근거**: blueprint "프로필 없는 반쪽 세션을 만들지 않는다".

---

### D004 — 로그인 본문 길이 제한(email 3~254, password 1~256)으로 게이트웨이 호출 전 422

- **태스크**: T007
- **파일**: `examples/delivered/api/session_routes.py` `LoginRequest`
- **시각**: 2026-09-11 16:20
- **상태**: ✅ resolved

**맥락**: blueprint는 `LoginRequest(email, password, remember_me)`만 정의.

**판단**: pydantic 길이 제한으로 빈 값·비정상 길이를 게이트웨이에 보내지 않는다.

**근거**: blueprint-integration.md "본문 검증(422)에 걸리면 호출하지 않는다".

---

### D005 — `customerId`가 비면 로그인 응답의 `userId`로 채운다 (한 곳에서)

- **태스크**: T005, T007
- **파일**: `examples/delivered/api/delivered_backend.py` `sign_in`
- **시각**: 2026-09-11 16:20
- **상태**: ✅ resolved

**맥락**: blueprint-api.md는 `user_id: dk:{customerId}`만 정하고 `/me`에 `customerId`가 없는 경우는 침묵. 평가 시점에는 `attach`만 폴백하고 라우트는 폴백이 없어 `dk:`가 될 수 있었다.

**판단**: `sign_in`이 프로필을 돌려주기 전에 `customer_id`를 `result.user_id`로 채워, 라우트와 `attach`가 같은 값을 쓴다.

**근거**: 단일 출처 — 후속 티켓이 `credential.customer_id`와 `record.user_id`를 대조할 때 어긋나지 않는다.

---

## 트레이드오프 🔀

### T001 — `DeliveredApiError` 정의 위치를 `delivered_auth.py`로 이전

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_auth.py`, `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-11 16:20
- **상태**: ✅ resolved

**옵션 A**: `delivered_backend.py`에 두고 `delivered_auth`가 import — backend → auth → backend 순환 import.

**옵션 B**: `delivered_auth.py`에 정의하고 backend가 re-import — 기존 `delivered_backend.DeliveredApiError` 경로 유지.

**선택**: B. blueprint의 "예외 4종"이 실제로는 5종(`DeliveredApiError` 포함)이 됐다.

**여파**: blueprint.md Directory Structure의 delivered_auth 책임 목록 한 줄 (epilogue 역류 후보)
