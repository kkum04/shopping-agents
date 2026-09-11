---
difficulty:
  area: BE
  level: S
  size: 중
  signals:
    changed_files: 3
    module_count: 1
    new_api: false
    db_migration: false
    txn_concurrency_external: false
    est_md: 1.5
  computed_at: 5dadbe1
---

# Brief: [shopping-agents] 통합검색 shop_types 명시 — 일반 키워드도 여러 마켓에서 검색

> Jira: RBD-8274 | Epic: RBD-8273 [RND] delivered 쇼핑 에이전트 — 로그인·장바구니·결제 연결 | Mode: quick

## Sources

| 소스 | 상태 | 비고 |
|------|------|------|
| Jira 티켓 | ✅ 확인 | RBD-8274 (draft 생성 A 변형, AC 3개) |
| PM 티켓 (에픽 링크) | ⚠️ 없음 | 에픽에 이슈 링크·PRD 필드 없음 (기획 티켓 없이 분해된 에픽) |
| Figma 디자인 | ⏭️ 스킵 | BE 티켓, 티켓·에픽 어디에도 Figma URL 없음 |

## Goal

에이전트가 "줄넘기", "화장품", "나이키" 같은 일반 키워드로 검색해도 delivered 통합검색이 여러 마켓의 상품을 돌려주게 한다. 지금은 요청에 `shop_types`가 없어 게이트웨이가 키워드로 마켓을 고르다 400을 내고, 스마트스토어 목록만 남는다.

## Acceptance Criteria

- [X] AC1: "줄넘기", "화장품", "나이키", "삼성 이어폰", "jump rope"로 검색하면 통합검색 응답이 200이고 2개 이상 마켓의 상품이 결과에 들어온다 (녹화 응답 테스트 + 실제 게이트웨이 1회 확인).
- [X] AC2: "뉴진스", "BTS" 같은 기존 성공 키워드의 결과 수가 줄지 않는다.
- [X] AC3: 녹화 응답 기반 테스트에 `shop_types`가 요청 본문에 포함되는지 검증이 추가되고, 기존 테스트 전부와 ruff가 통과한다.

## Plan

> What/Why는 위 Goal/AC가 책임진다. 이 섹션은 How만 — 대상 파일과 변경 흐름.

- **대상 파일/모듈**:
  - `examples/delivered/api/delivered_backend.py` — `SUPPORTED_SHOP_TYPES` 상수 추가, `DeliveredClient.search_products` 본문에 `shop_types` 포함, `MARKET_LABELS`에 4개 마켓 한글 표기 추가
  - `examples/delivered/api/agent_config.py` — `DOMAIN_SEARCH_NOTES`에서 "일반 키워드는 거부된다" 문구 제거, 한 키워드 권고는 유지
  - `examples/delivered/api/tests/test_delivered_backend.py` — FakeGateway가 `shop_types` 없는 요청과 `OTHER` 포함 요청을 400으로 답하게 하고, 일반 키워드가 통합검색에서 성공하는 테스트 추가
  - `examples/delivered/README.md` — 「Quirks」 절의 키워드 설명을 shop_types 기준으로 갱신
- **핵심 변경 흐름**:
  1. 지원 마켓 16종을 모듈 상수 하나로 두고 `MARKET_LABELS`와 같은 자리에서 관리한다.
  2. 통합검색 요청 본문에 `shop_types: SUPPORTED_SHOP_TYPES`를 항상 실어 보낸다. `size`는 20 이상 유지.
  3. `_multi_market_search`의 단어 단위 재시도는 그대로 두되 첫 호출이 성공하면 실행되지 않는다(기존 동작).
  4. 프롬프트 노트에서 "일반 키워드·영어는 거부된다"는 문장을 걷어낸다.
- **참조 코드**:
  - 고객 프론트 `deliveredkorea-customer-frontend/src/types/api/store/searchStoreApiDto.ts:31-40` — `shop_types?: string[]`
  - 실측(2026-09-09): `OTHER`만 400, 나머지 16종은 200

## Tasks

> develop과 동일 포맷. 각 라인은 `- [ ] T### [P?] 설명 (파일 경로)`.

- [X] T001 FakeGateway에 shop_types 검증 추가 + 일반 키워드 성공 테스트 작성 (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T002 `SUPPORTED_SHOP_TYPES` 상수 + 요청 본문 `shop_types` + `MARKET_LABELS` 4종 추가 (`examples/delivered/api/delivered_backend.py`) — T001 의존
- [X] T003 [P] `DOMAIN_SEARCH_NOTES` 문구 갱신 (`examples/delivered/api/agent_config.py`)
- [X] T004 [P] README Quirks 절 갱신 (`examples/delivered/README.md`)
- [X] T005 격리 검증 지적 반영 — 프롬프트·README 마켓 목록 16종으로 갱신, 200+빈 결과도 단어 재시도(`_is_miss`), AC1 키워드 5종 parametrize·OTHER 거부 테스트 (`examples/delivered/api/delivered_backend.py`, `examples/delivered/api/agent_config.py`, `examples/delivered/README.md`, `examples/delivered/api/tests/test_delivered_backend.py`)

- [X] T006 V3 스크린샷 원인 반영 — 게이트웨이가 앞 20칸을 샵 마켓으로 채우고 번개장터는 21번째부터 붙이므로 `SEARCH_PAGE_SIZE`를 40으로 상향(고객 프론트와 동일), 테스트·README 갱신 (`examples/delivered/api/delivered_backend.py`, `examples/delivered/api/tests/test_delivered_backend.py`, `examples/delivered/README.md`)

## Validation

> 9단계 자동 검사 대상. 모든 항목이 `- [X]` 또는 명시적 보류 상태가 되어야 완료 처리.
> AC 매핑: AC1 → T001·T002(+T005 parametrize), AC2 → T002·T005(`_is_miss` 재시도), AC3 → T001·T005.

- [X] V1: 테스트 통과 (`.venv/bin/python -m pytest -q examples/delivered` + 전체 `pytest`, `ruff check .`, `ruff format --check .`)
- [X] V2: 실제 게이트웨이에 백엔드 코드로 "나이키"·"화장품"을 검색하면 2개 이상 마켓의 상품이 돌아온다 (1회 수동 확인) — 2026-09-11 확인: 나이키 {무신사, 올리브영, 스마트스토어} · 화장품 {다이소, 무신사, 스마트스토어} · jump rope 5개 마켓 · 뉴진스/BTS 12건 유지
- [X] V3: 데모(`run_demo.py delivered`) 대화에서 "나이키 운동화 찾아줘"에 여러 마켓 카드가 뜬다 — 사람이 검증 — 2026-09-11 사용자 확인 완료 (번개장터 나이키 운동화 카드 표시)
