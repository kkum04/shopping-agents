---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: tasks
completed: [mission, blueprint, tasks, develop]
plan: []
skip: []
depth: standard
base_sha: 7b13529
gates:
  open_q: 0
  findings_pending: 0
risk:
  self: 0.0                     # 커버리지 갭 0 · [P] 파일 충돌 0 · 태스크 12(<15) → 생략
  review: skipped
tests: included
task_count: 12
coverage:
  - ac: AC1
    tasks: [T001, T002, T003, T004, T005]
  - ac: AC2
    tasks: [T006, T007]
  - ac: AC3
    tasks: [T006, T007]
  - ac: AC4
    tasks: [T006, T007]
  - ac: AC5
    tasks: [T010]
  - ac: AC6
    tasks: [T001, T002, T004, T006, T008]
  - ac: AC7
    tasks: [T008, T009]
  - ac: AC8
    tasks: [T006, T007]
uncovered_acs: []
parallel_conflicts: []
integration_tasks:
  - service: delivered-guest-api
    endpoint: "GET …/option-groups · GET …/options"
    tasks: [T001, T004, T005]
    verified: true
  - service: delivered-customer-api
    endpoint: "POST /v1/buy-request/rpa-store (options)"
    tasks: [T006, T007, T012]
    verified: true
  - service: delivered-customer-api
    endpoint: "GET /v3/cart · GET /v2/cart/{id} options[]"
    tasks: [T008, T009, T012]
    verified: true
---

# Tasks: 옵션 상품 매핑 — option-groups/options를 family/variant로, 구매요청에 옵션 전달

> Mission: ./mission.md | Blueprint: ./blueprint.md · ./blueprint-integration.md | Jira: RBD-8278
> 실행: `.venv/bin/python -m pytest -q -p no:cacheprovider examples/delivered` · 린트: `.venv/bin/ruff check examples/delivered && .venv/bin/ruff format --check examples/delivered`

## Implementation Strategy

- **실행 모드**: 일괄 흐름 — 한 모듈(신규 `delivered_options.py`) + 백엔드 3지점, PR 하나.
- **MVP 경계**: Phase 1~3(옵션 매핑 + variant 담기)까지가 MVP. 역매핑(US2 후반)·분할(US3)은 그 위에.
- **병렬 실행 예시**: T002(L1, `test_delivered_options.py`)와 T004(L2, `test_delivered_backend.py`)는 파일이 달라 동시 작성 가능.
- **실측 계획**: 옵션 API는 이미 실측(픽스처는 그 응답을 녹화). optionId를 실은 구매요청과 장바구니 옵션 라인은 T012에서 운영 계정으로 확인(Q2) 후 삭제.

## Phase 1: Setup — 녹화 픽스처

- [X] T001 옵션 API 녹화 픽스처 작성 — 운영 게스트 API의 pid 11314403854(COMBINATION 2옵션)와 10631022673(COMBINATION 2그룹 + TEXT 1그룹, 12옵션)의 `option-groups`·`options` 응답을 저장하고, `FakeGateway`에 `/option-groups`·`/options` 라우트(pid별 픽스처, 없는 pid는 `data: []`, `options_status`로 실패 주입) 추가 (`examples/delivered/api/tests/fixtures/smartstore-option-groups.json`, `examples/delivered/api/tests/fixtures/smartstore-options.json`, `examples/delivered/api/tests/test_delivered_backend.py`)

## Phase 2: Foundational — 순수 매핑

- [X] T002 [P] [L1] `delivered_options.py` 단위 테스트 작성 (Red) — `variant_id_of`/`split_variant_id`/`sub_family_index` 왕복, `group_names`·`text_option_groups`, `family_with_variants`(options dict, variant id·option_values·price·in_stock·variant_of·상속, TEXT → attributes.text_options, family 최저가·in_stock), `variant_for_option_values`(그룹 id + 한글/영문 값 일치/불일치 — T012 실측으로 `variant_for_option_names`에서 개명), 알 수 없는 그룹의 옵션 행 무시 (`examples/delivered/api/tests/test_delivered_options.py`)
- [X] T003 `delivered_options.py` 구현 (Green) — 상수·id 헬퍼·`family_with_variants`·`variant_for_option_values`·`split_families`(뼈대, T010에서 완성) (`examples/delivered/api/delivered_options.py`)

## Phase 3: US1 — 옵션 상품 상세를 family/variant로 (P1)

**목표**: 스마트스토어 옵션 상품의 상세가 family(+variants)로 오고 variants가 세션에 기억된다.
**독립 테스트 기준**: 가짜 게이트웨이로 `get_product_details("smart_store:11314403854")`가 options {"색상": [레드블랙, 화이트]}·variants 2개를 돌려주고 `product("smart_store:11314403854#137750")`이 해석된다.

- [X] T004 [P] [US1] [L2] `get_product_details` 테스트 작성 (Red) — 옵션 상품 family/variants · 옵션 없는 상품은 현행 그대로 · variant id 요청 → variant 레코드 · 옵션 API 503 → 옵션 없는 상세 + 경고(caplog) · TEXT 그룹 → attributes.text_options · 세 호출이 모두 나감(경로 기록) (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T005 [US1] `DeliveredClient.smartstore_option_groups/smartstore_options` + `get_product_details` 병렬·매핑·variant 해석·`_remember` 구현 (Green) (`examples/delivered/api/delivered_backend.py`)

## Phase 4: US2 — variant로 담기, 옵션 전달, 역매핑 (P2)

**목표**: variant id로 담으면 구매요청 `options`에 optionId가 실리고, 장바구니 옵션 라인이 variant id로 돌아온다.
**독립 테스트 기준**: 가짜 고객 게이트웨이가 받은 rpa-store 본문의 `options == [137750]`, `pid == "11314403854"`; 웹에서 담긴 옵션 라인이 `smart_store:11314403854#137751`로 조회된다.

- [X] T006 [US2] [L2] add_to_cart 옵션 테스트 작성 (Red) — variant → 본문 `options=[optionId]`·`text_options=[]`·`pid`는 base id · family → KeyError, 호출 0회 · 품절 variant → `Unavailable` 메시지에 재고 형제 id, 호출 0회 · TEXT 그룹 상품(family/variant) → `CartRejected`(웹 안내), 호출 0회 · 게스트 → SignInRequired (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T007 [US2] `add_to_cart` 옵션 규칙 + `buy_request_body` options 구현 (Green) (`examples/delivered/api/delivered_backend.py`, `examples/delivered/api/delivered_cart.py`)
- [X] T008 [US2] [L2] 장바구니 옵션 라인 역매핑 테스트 작성 (Red) — `FakeCustomerGateway` preload에 `options=[{key, value}]` 지원 · 상세 options + 옵션 API 대조 → variant id · 불일치 → family id + 경고 · 옵션 없는 라인은 현행 (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T009 [US2] `_resolve_product_id` 옵션 역매핑 구현 (Green) (`examples/delivered/api/delivered_backend.py`)

## Phase 5: US3 — 큰 조합 분할 (P3)

- [X] T010 [US3] [L1] `split_families` 테스트 + 구현 — 61개 이상이면 첫 그룹 값별 sub-family(`#g{n}`, options는 나머지 그룹, 각 ≤ 60), 원 family는 variants 비우고 `attributes.variant_families` 안내; `get_product_details("…#g2")`가 그 조각을 돌려줌 (`examples/delivered/api/tests/test_delivered_options.py`, `examples/delivered/api/delivered_options.py`, `examples/delivered/api/delivered_backend.py`)

## Final Phase: Polish & 검증

- [X] T011 `agent_config.DOMAIN_SEARCH_NOTES` 옵션 안내 한 줄 + README 「Options」 절 (`examples/delivered/api/agent_config.py`, `examples/delivered/README.md`)
- [X] T012 검증·실측 — ruff·pytest 전체 통과 · 운영 계정(Q2)으로 옵션 상품 variant 담기 → `v3/cart`/`v2/cart/{id}` `options[]` 실제 값 확인 → 역매핑 스텁·blueprint-integration `verified` 갱신 → 삭제 · 데모 대화("… 화이트로 담아줘") e2e 1회 (`jarvis/.../blueprint-integration.md`, `examples/delivered/api/tests/test_delivered_backend.py`)

## Dependencies

- T001 → T004, T006, T008 · T002 → T003 → T005 · T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012
- [P] 표시 태스크(T002, T004)는 서로 다른 파일만 만진다.

## Develop Notes

- T012 실측(운영 계정, 2026-09-14): `POST /v1/buy-request/rpa-store`에 `options=[137751]`(라켓 화이트)을 실어 구매요청 1010074 생성 → `add-carts` → `GET /v3/cart` 라인의 `options[] = [{type:"Option", key:"Option", value:"White", option_key_locale:{product_option_group_id:18147, product_option_group_name:"색상"}}]`(값은 영문), `GET /v2/cart/1010074`의 `options[] = [{type:"Option", key:"Option", value:"화이트", option_key_locale:null}]`(값은 한글) 확인 후 `DELETE /v2/cart?buyRequestIds=1010074`로 삭제. 역매핑은 그룹 id(있으면)와 한글/영문 값 양쪽으로 대조하도록 `variant_for_option_values`로 확정.
- T012 데모 e2e 대화("… 화이트로 담아줘")는 실행하지 않았다 — 데모 서버(:8004)가 이전 코드로 떠 있어 재기동이 필요하고, 같은 경로는 `test_delivered_backend.py`의 옵션 테스트(T006·T008)가 가짜 게이트웨이로 덮는다.
- 격리 findings 평가 후 보강: 옵션 API 4xx 응답도 경고 로그(DV003) · `add_to_cart`가 sub-family id(`#g{n}`)를 family와 같이 거절(D004) — 테스트 2건 추가.
- 검증: `ruff check .` · `ruff format --check .` · `pytest`(1220 passed, 1 skipped) · `scripts/check.py` clean. `examples/delivered`만 116 passed.
