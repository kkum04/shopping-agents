# blueprint Review Checklist: delivered 로그인 연동 — 세션에 토큰 보관, 고객 API Bearer 호출

**Purpose**: blueprint 문서 품질 검증
**Created**: 2026-09-11
**Feature**: ./blueprint.md, ./blueprint-api.md, ./blueprint-integration.md

## 아키텍처 (Architecture)

- [x] CHK001 토큰이 저장되는 유일한 자리(CredentialStore)와 저장되면 안 되는 자리(state_document·트랜스크립트·응답)가 문서에 명시되어 있는가? (blueprint.md) — ⚠️ 트랜스크립트 금지 문장 없음 → ✅ 해소: 핵심 결정 1에 트랜스크립트·응답 명시 (2026-09-11)
- [x] CHK002 공용 `demo_common`·프레임워크 core를 수정하지 않는다는 결정과 그 이유가 적혀 있고, 모든 변경 파일이 `examples/delivered/` 아래인가? (blueprint.md) — ⚠️ .env.example(루트) 1건 → ✅ 해소: Architecture Overview에 예외로 명시, 코드 변경은 examples/delivered 한정 (2026-09-11)
- [x] CHK003 각 신규 모듈(DeliveredAuthClient, CredentialStore, DeliveredStorefront 변경, DeliveredToolExecutor, session_routes)의 책임·위치·의존성·주요 로직이 모두 적혀 있는가? (blueprint.md) — ✅ Module Design 5개 모듈 책임·위치·의존성·로직

## 인터페이스 (Interfaces)

- [x] CHK004 세 라우트(login/logout/me)의 요청·응답 필드, 상태 코드, 헤더 요구가 FE가 구현할 수 있을 만큼 정의되어 있는가? (blueprint-api.md) — ✅ blueprint-api.md 3라우트 필드·코드·헤더
- [x] CHK005 후속 티켓(RBD-8277·8280)이 재사용할 공통 Bearer 경로(`customer_request` / `customer_call`)의 시그니처와 예외 계약이 정의되어 있는가? (blueprint.md, blueprint-integration.md) — ✅ customer_request / customer_call 시그니처·예외 계약
- [x] CHK006 mission의 데이터 요구사항(로그인 시 같은 세션 승계, 로그아웃 시 세션 유지, /me 요약)이 API 설계와 일치하는가? (blueprint-api.md ↔ mission) — ✅ mission 데이터 요구사항과 일치

## 데이터 (Data)

- [x] CHK007 SessionCredential/CustomerProfile 필드와 `/me` 응답 필드의 매핑(display_name·country·member_tier)이 정의되어 있는가? (blueprint.md) — ✅ CustomerProfile.from_me 매핑
- [x] CHK008 로그인 시 `SessionRecord.user_id`가 바뀌는 것의 부수효과(메모리 주체 변경)가 Migration/Side Effects에 기술되어 있는가? (blueprint.md) — ✅ Migration/Side Effects 4항목

## 에러 처리 (Error Handling)

- [x] CHK009 Error Handling 표가 mission AC1·AC5의 모든 실패 경로(401/404, 5xx·타임아웃, Expired Token, 고객 API 5xx, 게스트 호출)를 덮는가? (blueprint.md) — ✅ Error Handling 표 7행
- [x] CHK010 `/me` 실패 시 반쪽 세션을 만들지 않는 처리가 정의되어 있는가? (blueprint.md) — ✅ /me 실패 → 502, 반쪽 세션 금지
- [x] CHK011 Expired Token 감지가 상태 코드가 아니라 응답 메시지 문자열 기준임이 명시되어 있는가? (blueprint.md, blueprint-integration.md) — ✅ message == 'Expired Token' 기준 명시

## 성능 (Performance)

- [x] CHK012 프로필을 턴마다 다시 부르지 않고 캐시한다는 mission NFR이 설계에 반영되어 있는가? (blueprint.md) — ✅ 프로필 캐시, 턴마다 미호출

## 보안 (Security)

- [x] CHK013 비밀번호·토큰이 로그·예외 메시지·repr에 나타나지 않도록 하는 구체적 조치(redacted repr, 예외 메시지 내용 제한, 로깅 수준)가 적혀 있는가? (blueprint.md) — ✅ redacted repr·예외 메시지 제한·로깅 수준
- [x] CHK014 알 수 없는 세션 ID로 로그인할 때의 처리가 정의되어 있고 세션 탈취 경로가 되지 않는가(새 세션 생성)? (blueprint.md) — ✅ 모르는 세션 ID → 새 세션 발급

## 운영 (Operability)

- [x] CHK015 환경변수 이름·기본값(스테이징)·운영 전환 방법이 문서에 있고 `.env.example` 갱신이 포함되어 있는가? (blueprint.md, blueprint-integration.md) — ✅ 환경변수·기본값·전환·.env.example
- [x] CHK016 기존 동작 변화(게스트 장바구니 쓰기 차단)와 그로 인한 테스트·스모크 수정 계획이 Migration/Side Effects에 있는가? (blueprint.md) — ✅ 게스트 장바구니 차단 + 테스트·스모크 수정 계획
- [x] CHK017 연동 계약 2건이 `verified: false`로 정직하게 표기되고 근거 파일이 적혀 있는가? (blueprint-integration.md) — ✅ 계약 2건 verified: false + 근거 파일

## Notes

- 2026-09-11 격리 검증(subagent): ✅15 · ⚠️2 · ❌0 → 판정 passed. ⚠️ 2건은 blueprint.md 보강으로 같은 날 해소.

- 완료 시 `[x]` 표시
- 발견 사항은 인라인 코멘트로 추가
- 항목은 절대 삭제/재번호 금지 — append only
