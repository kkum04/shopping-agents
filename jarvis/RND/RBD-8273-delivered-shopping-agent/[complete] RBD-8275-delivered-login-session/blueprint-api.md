# Blueprint — API: delivered 로그인 연동 — 세션에 토큰 보관, 고객 API Bearer 호출

> Main: ./blueprint.md

모든 경로는 delivered 데모 API(`examples/delivered/api`, :8004)에 추가된다. 세션 식별은 기존과 같이 `X-Session-Id` 헤더다. 응답 어디에도 토큰은 없다.

## Endpoints

### POST /api/session/login

- **목적**: delivered 계정으로 로그인해 토큰을 서버 세션 옆에 두고, 그 손님의 세션을 시작하거나 기존 세션에 붙인다.
- **인증**: 없음(본문 자격증명). `X-Session-Id` 헤더가 있으면 그 세션에 붙인다.

**Request:**

```json
{
  "email": "string — delivered 계정 이메일",
  "password": "string — 비밀번호 (로그·예외에 기록하지 않음)",
  "remember_me": "bool — 기본 false; 게이트웨이 isRememberMe로 전달"
}
```

**Response (성공, 200):**

```json
{
  "session_id": "string — 기존 세션이면 같은 값, 새 세션이면 새 값",
  "user_id": "string — dk:{customerId}",
  "signed_in": true,
  "name": "string — firstName lastName",
  "tier": "string|null — memberTier",
  "country": "string|null"
}
```

**Response (에러):**

| Status | detail | 설명 |
|--------|--------|------|
| 401 | `invalid_credentials` | 게이트웨이가 401/404로 답함. 세션·토큰 변경 없음 |
| 422 | (pydantic) | 필드 누락·형식 오류 |
| 502 | `auth_unavailable` | 게이트웨이 5xx·타임아웃·연결 실패·비JSON, 또는 `/me` 실패 |

### POST /api/session/logout

- **목적**: 세션의 토큰을 지우고 같은 세션을 게스트로 이어간다.
- **인증**: `X-Session-Id` 필수(없거나 모르는 세션이면 기존 규칙대로 401).

**Request:** 본문 없음.

**Response (200):**

```json
{
  "session_id": "string — 같은 값",
  "user_id": "string — 로그인 시 바뀐 값 유지",
  "signed_in": false,
  "name": "Guest",
  "tier": null,
  "country": null
}
```

### GET /api/session/me

- **목적**: 스토어프론트 헤더가 로그인 상태와 이름을 그리기 위한 프로필 요약.
- **인증**: `X-Session-Id` 필수.

**Response (200):** `POST /api/session/login` 성공 응답과 같은 형태. 게스트면 `signed_in: false`, `name: "Guest"`.

## 세션 시작과의 관계

`POST /api/session`(공용 라우트)은 바뀌지 않는다. FE는 시작 직후 `GET /api/session/me`로 상태를 읽고, 로그인은 시작해 둔 세션 ID를 헤더에 실어 `POST /api/session/login`을 부른다.
