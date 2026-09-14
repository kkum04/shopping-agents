# Blueprint — Integration: delivered 로그인 연동 — 세션에 토큰 보관, 고객 API Bearer 호출

> Main: ./blueprint.md

## delivered-auth-gateway · 이메일 로그인

- **호출**: `POST /auth/sign-in/dk-service/customer?isRememberMe={bool}`
- **주소 출처**: `DELIVERED_AUTH_URL` — 환경변수, 기본 `https://gw-staging.delivered.co.kr` (테스트에서는 `httpx.MockTransport`로 대체)
- **트리거**: `POST /api/session/login` 처리 중, 동기 1회
- **발신 시점**: 동기 (트랜잭션 없음)
- **계약 근거**: 고객 프론트 `deliveredkorea-customer-frontend/src/features/repository/auth/fetchAuth.ts`, `src/types/api/auth/authApiDto.ts:1-7, 47-56`, `src/hooks/auth/useLogin.ts:44` — ✅ 2026-09-14 스테이징 실제 로그인으로 확인(평면 객체, `userId`·`userName` 포함)

**보내는 것** (검증 대상 필드만):

```json
{ "email": "string", "password": "string", "ipAddress": "", "country": "", "isRememberMe": false }
```

**성공 응답** (비엔벨로프):

```json
{ "accessToken": "string", "refreshToken": "string", "userId": "string|number", "userName": "string" }
```

**실패하면 우리는**: 401/404 → 상위 전파(`SignInFailed` → 로그인 401) · 5xx/타임아웃/연결 실패/비JSON → 상위 전파(`AuthUnavailable` → 로그인 502). 어느 경우도 토큰을 세션에 남기지 않고 재시도하지 않는다.

**보내지 않는 경우**: 본문 검증(422)에 걸리면 호출하지 않는다.

## delivered-customer-api · 내 프로필

- **호출**: `GET /v2/me` (Authorization: Bearer)
- **주소 출처**: `DELIVERED_CUSTOMER_API_URL` — 환경변수, 기본 `https://gw-staging.delivered.co.kr/dk-delivered/api/customer`
- **트리거**: 로그인 직후 1회(프로필 캐시). 턴마다 부르지 않는다.
- **발신 시점**: 동기
- **계약 근거**: 고객 프론트 `src/types/api/auth/authApiDto.ts:134-157` — ✅ 2026-09-14 실제 토큰으로 확인: 게이트웨이는 **`{result, data: {...}, message}` 엔벨로프**로 답한다(프론트 타입은 `data`를 벗긴 형태). `firstName`/`lastName`은 null일 수 있다

**성공 응답** (검증 대상 필드만):

```json
{ "result": true, "data": { "customerId": "number", "customerEmail": "string", "firstName": "string|null", "lastName": "string|null", "country": "string|null", "memberTier": "string" } }
```

**실패하면 우리는**: 5xx/전송 오류 → 로그인 502로 상위 전파(반쪽 세션 금지) · `message == "Expired Token"` → 흡수: 토큰 폐기 + 게스트 지속 + `TokenExpired` 예외로 재로그인 안내(로그인 직후에는 발생하지 않는다고 가정).

## delivered-customer-api · 공통 Bearer 경로 (후속 티켓용)

- **호출**: `DeliveredAuthClient.customer_request(method, path, access_token)` — 이 티켓에서는 `/v2/me`만 쓰지만 RBD-8277(장바구니)·RBD-8280(결제)이 같은 경로로 `/v1/buy-request/rpa-store`, `/v2/cart/add-carts`, `/v3/cart` 등을 부른다.
- **실패하면 우리는**: `Expired Token` → 흡수(위와 동일) · 그 외 5xx → `DeliveredApiError`(프레임워크 "일시 불가" 문장).

## 수신 계약

없음 — delivered가 이 데모를 호출하지 않는다.
