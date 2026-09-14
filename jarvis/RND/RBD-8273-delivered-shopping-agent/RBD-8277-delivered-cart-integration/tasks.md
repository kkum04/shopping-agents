---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: tasks
completed: [mission, blueprint, tasks, develop]
plan: []
skip: []
depth: standard
base_sha: d946a06
gates:
  open_q: 0
  findings_pending: 0          # Q001·Q002 2026-09-14 사용자 답 + 운영 실측으로 해소
risk:
  self: 0.0                     # 커버리지 갭 0 · [P] 파일 충돌 0 · 태스크 14(<15) → 생략
  review: skipped
tests: included                 # pytest + httpx.MockTransport 가짜 게이트웨이 (L1 단위 · L2 앱 통합)
task_count: 14
coverage:
  - ac: AC1
    tasks: [T004, T006]
  - ac: AC2
    tasks: [T002, T003, T007, T008]
  - ac: AC3
    tasks: [T011, T012]
  - ac: AC4
    tasks: [T009, T010]
  - ac: AC5
    tasks: [T005, T006]
  - ac: AC6
    tasks: [T001, T005, T013]
  - ac: AC7
    tasks: [T004, T005, T007, T009, T011]
  - ac: AC8
    tasks: [T007, T008]
uncovered_acs: []
parallel_conflicts: []
integration_tasks:
  - service: delivered-customer-api
    endpoint: "POST /v1/buy-request/rpa-store"
    tasks: [T004, T005, T014]
    verified: false
  - service: delivered-customer-api
    endpoint: "POST /v2/buy-request/bunjang · POST /v2/buy-request/shop"
    tasks: [T004, T005, T014]
    verified: false
  - service: delivered-customer-api
    endpoint: "POST /v2/cart/add-carts · DELETE /v2/cart"
    tasks: [T004, T005, T009, T011, T014]
    verified: false
  - service: delivered-customer-api
    endpoint: "GET /v3/cart · GET /v2/cart/{buyRequestId}"
    tasks: [T007, T014]
    verified: false
---

# Tasks: delivered 장바구니 연동 — 구매요청 생성 + add-carts, 조회·삭제·수량 변경, 전 마켓

> Mission: ./mission.md | Blueprint: ./blueprint.md · ./blueprint-integration.md | Jira: RBD-8277
> 경로는 저장소 루트 기준. 테스트는 `examples/delivered/api/tests/`에 두고 `httpx.MockTransport`로 게이트웨이를 대체한다(네트워크 없음). 실행: `.venv/bin/python -m pytest -q -p no:cacheprovider examples/delivered`, 린트: `.venv/bin/ruff check examples/delivered && .venv/bin/ruff format --check examples/delivered`.

## Implementation Strategy

- **실행 모드**: 단계별 분리 — 5개 User Story phase지만 파일은 셋(`delivered_cart.py`·`delivered_backend.py`·테스트)에 집중되므로 PR은 하나다.
- **MVP 경계**: Phase 1~4(담기 + 조회)까지가 MVP — 담은 상품이 delivered 웹 장바구니에 보이고 에이전트 장바구니가 그것을 읽는다. 삭제·수량 변경·relay는 한 phase씩 얹는다.
- **별도 PR 분기점**: 없음.
- **병렬 실행 예시**: T002(순수 함수 테스트, `test_delivered_cart.py`)와 T004(앱 통합 테스트, `test_delivered_backend.py`)는 파일이 달라 동시 작성 가능. 구현 태스크는 같은 파일을 연속으로 만지므로 순차.
- **계약 미확인 처리**: 연동 4건이 `verified: false`다. L2 테스트는 blueprint-integration.md의 가정 스텁으로 먼저 Green을 만들고, T014에서 스테이징 실측(Q2 승인)으로 계약을 확인해 스텁·문서를 맞춘다. 실측 전까지 발견되는 의문은 findings에 Q###로 올린다.
- **코어·demo_common은 수정하지 않는다.** `cart_extras`는 기존 훅이다.

## Phase 1: Setup — 오류 정보 확보

- [X] T001 `DeliveredApiError`에 `code`/`message`/`status` 속성 추가 — `customer_request`가 4xx 응답 본문 `{code, result, message}`를 예외에 싣도록 `examples/delivered/api/delivered_auth.py` 최소 수정(생성자 시그니처·기존 메시지 문자열 유지), `test_delivered_auth.py`에 4xx 본문이 속성으로 실리는 케이스 1개 추가 (`examples/delivered/api/delivered_auth.py`, `examples/delivered/api/tests/test_delivered_auth.py`)

## Phase 2: Foundational — 라우팅·본문·매핑 (순수 함수)

- [X] T002 [P] [L1] `delivered_cart.py` 단위 테스트 작성 (Red) — `route_of`(RPA 13종→rpa, BUNJANG→bunjang, DK_SHOP→shop, OTHER→CartRejected), `buy_request_body` 3종 본문(blueprint-integration의 필드), `buy_request_id_of`({data:n} / 원시 number / {result,data}), `cart_from_v3`(단가 = ITEM_PRICE cost_krw/quantity, 만료·판매종료 항목 포함, extras 구조, KRW), `CartIndex` 양방향, `ERROR_MESSAGES` 문장 (`examples/delivered/api/tests/test_delivered_cart.py`)
- [X] T003 `delivered_cart.py` 구현 (Green) — `RPA_MARKETS`, `route_of`, `buy_request_body`, `buy_request_id_of`, `cart_from_v3(payload, resolve)`, `CartIndex`, `CartRejected`, `ERROR_MESSAGES`; `product_id_of`/`split_product_id`를 이 모듈로 옮기고 `delivered_backend.py`가 재수출; 검색·목록·상세 파서가 `productUrl`을 `attributes["product_url"]`에 보존 (`examples/delivered/api/delivered_cart.py`, `examples/delivered/api/delivered_backend.py`)

## Phase 3: US1 — 담기 (P1)

**목표**: 로그인 세션의 `add_to_cart`가 마켓별 구매요청을 만들고 add-carts로 붙인 뒤 재조회한 Cart를 돌려준다.
**독립 테스트 기준**: 가짜 게이트웨이가 받은 요청 순서가 `POST rpa-store → POST add-carts?buyRequestIds=… → GET v3/cart`이고, 반환 Cart에 그 상품이 있다.

- [X] T004 [P] [US1] [L2] `FakeCustomerGateway`(녹화 응답 스텁: rpa-store/bunjang/shop 성공, add-carts 성공, v3/cart 목록, v2/cart/{id} 상세) + add_to_cart 성공 경로 테스트 작성 (Red) — 스마트스토어·번개장터·DK샵 상품 각각에 대해 보낸 경로·본문(검증 대상 필드)·add-carts 쿼리·재조회를 검증. ⚠️ 이 스텁은 상대 계약 미확인 상태의 가정이다. 구현 완료 시 findings에 Q###로 기록할 것 (질문: "delivered-customer-api의 rpa-store/bunjang/shop 요청·응답 형식을 실제로 확인했는가?") — T014 실측으로 해소 (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T005 [US1] [L2] add_to_cart 실패·미발신 경로 테스트 작성 (Red) — 구매요청 4xx `{code, message}` → `CartRejected` 문장에 message 포함 · add-carts `CART-005` → 가득 참 문장 + 고아 구매요청 id 로그(caplog) · `CART-004` → 흡수 후 재조회 · 미지원 마켓(OTHER) → CartRejected, 게이트웨이 호출 0회 · 게스트 → `SignInRequired`, 호출 0회(AC5) · 5xx → `DeliveredApiError` (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T006 [US1] `DeliveredStorefront.add_to_cart` 구현 (Green) — `_create_buy_request`(customer_call + `buy_request_id_of` + DeliveredApiError→CartRejected 변환), `_add_carts`(CART-004 흡수, CART-005 relay + orphan 로그), 인덱스 등록, 기존 라인이면 `update_cart_item(existing+quantity)` 위임(T012 이전엔 NotImplemented 경로 없이 재생성 흐름 직접 호출), `SessionCarts`·`_carts` 제거 (`examples/delivered/api/delivered_backend.py`)

## Phase 4: US2 — 조회 (P2)

**목표**: `get_cart`가 delivered v3/cart를 Cart로 매핑하고 수수료·마켓·만료를 extras로 넘긴다.
**독립 테스트 기준**: v3 스텁의 항목 수·수량·단가가 Cart와 같고, 웹에서 담긴(인덱스 미스) 항목은 상세 조회 1회로 `{market}:{pid}`가 복원된다.

- [X] T007 [US2] [L2] get_cart 테스트 작성 (Red) — 게스트 빈 Cart(호출 0회) · 회원 v3 매핑(상품·수량·단가·이미지·KRW) · 인덱스 히트 항목은 상세 미호출 · 미스 항목은 `GET /v2/cart/{id}` 1회 후 캐시(두 번째 get_cart에서 미호출) · 상세 실패 → `{market}:unknown-{id}` · extras에 fees·is_expired·is_selling·market 그룹 · 만료 항목도 Cart 포함(Q1) (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T008 [US2] `get_cart`·`cart_extras_for`·`reset_session` 구현 (Green) + `main.py`에 `cart_extras=backend.cart_extras_for` 연결 (`examples/delivered/api/delivered_backend.py`, `examples/delivered/api/main.py`)

## Phase 5: US3 — 삭제 (P3)

**목표**: `remove_from_cart`가 구매요청 ID로 delivered 항목을 지운다.
**독립 테스트 기준**: `DELETE /v2/cart?buyRequestIds={id}` 1회 후 재조회 Cart에 그 라인이 없다.

- [X] T009 [US3] [L2] remove_from_cart 테스트 작성 (Red) — 인덱스의 id로 DELETE 쿼리 검증 · `CART-001` 흡수 · 라인 없는 product_id는 호출 없이 재조회만 · 인덱스에서 제거 (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T010 [US3] `remove_from_cart`·`_delete` 구현 (Green) (`examples/delivered/api/delivered_backend.py`)

## Phase 6: US4 — 수량 변경 (P4)

**목표**: `update_cart_item`이 삭제 → 재생성 → add-carts → 재조회로 수량을 바꾼다.
**독립 테스트 기준**: 요청 순서가 `DELETE → POST 구매요청(quantity=2) → POST add-carts → GET v3/cart`이고, 재생성 실패 시 "다시 담아 주세요" 문장이 나온다.

- [X] T011 [US4] [L2] update_cart_item 테스트 작성 (Red) — 성공 순서·본문 quantity · 재생성 4xx → `CartRejected("… 다시 담아 주세요")` + 인덱스에서 제거 · add_to_cart가 기존 라인에 대해 update 경로(existing+quantity)를 타는지 (`examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T012 [US4] `update_cart_item` 구현 (Green) + `add_to_cart` 기존 라인 위임 마무리 (`examples/delivered/api/delivered_backend.py`)

## Phase 7: US5 — 오류 relay와 에이전트 안내 (P5)

- [X] T013 [US5] `DeliveredToolExecutor.domain_error`에 `CartRejected` relay + 테스트(툴 결과 텍스트에 한국어 문장 그대로) — `agent_config.DOMAIN_SEARCH_NOTES`에 "장바구니는 delivered 실제 장바구니(수수료·만료는 별도 전달)" 한 줄 (`examples/delivered/api/delivered_executor.py`, `examples/delivered/api/agent_config.py`, `examples/delivered/api/tests/test_session_routes.py` 또는 `test_delivered_backend.py`)

## Final Phase: Polish & 검증

- [X] T014 검증·실측·문서 — (1) `ruff` + `pytest examples/delivered` 전체 통과 (2) 스테이징 계정(Q2)으로 데모에서 스마트스토어·번개장터 상품 담기 → `GET /v3/cart` 실측 → 수량 변경 → 삭제까지 확인하고, 요청/응답 형태(단가 vs 합계, 응답 3형태, market_type 값, 오류 본문)를 가짜 게이트웨이 스텁·blueprint-integration.md에 반영해 `verified: true`로 갱신, 만든 항목은 삭제 (3) 위버스샵 상품이 검색되면 같은 절차로 1회 (4) README Cart 절 갱신 (`examples/delivered/README.md`, `jarvis/.../blueprint-integration.md`, `examples/delivered/api/tests/test_delivered_backend.py`) ✅ 2026-09-14: ruff·pytest(delivered 90 / 전체 1193) 통과 · 스테이징 실측 — 번개장터 구매요청→add-carts→v3→삭제 전 구간 확인(id=`cart_id`, `UNIT_PRICE`, CART-001 본문), RPA(rpa-store)는 사용자 승인으로 운영 계정 실측 — `market_type: SHOP`으로 전 구간 확인(항목 삭제), 위버스샵은 카탈로그에서 골라지지 않아 미실측 · 데모 대화 e2e(운영): "실리카겔 정규 3집 담아줘" → add_to_cart(23,500원) → "2개로 바꿔줘" → update(삭제·재생성, 47,000원) → "빼줘" → 빈 장바구니, 고객 API 로그 순서 확인 · 만든 항목 삭제 완료 · 운영 카탈로그 상품 ID로는 스테이징 고객 API가 상품을 모름(환경 불일치 → Q001)

## Dependencies

- T001 → T005(오류 코드 읽기) · T002 → T003 → T004·T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014
- [P] 표시 태스크(T002, T004)는 서로 다른 파일만 만진다.
