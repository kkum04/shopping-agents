---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: mission
completed: [mission]
plan: [blueprint, tasks, develop]
skip: []
depth: standard
base_sha: d946a06
gates:
  open_q: 0
risk:
  self: 0.2                     # base 0.2(외부 연동) + 품질 신호 0 → < 0.4(standard) 생략
  review: skipped
difficulty:
  area: BE
  level: L
  size: 중
  signals:
    changed_files: 5
    module_count: 1
    new_api: false
    db_migration: false
    txn_concurrency_external: true
    est_md: 4.0
  computed_at: d946a06
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [장바구니, 구매요청, add-carts, 마켓, rpa-store, bunjang, 수량, 삭제]
  modules: [examples/delivered/api/delivered_backend.py, examples/delivered/api/delivered_auth.py(customer_request), examples/demo_common/storefront.py(cart_extras)]
acceptance:
  - id: AC1
    story: P1
    ears: "WHEN 로그인 세션에서 스마트스토어·번개장터·위버스샵 상품을 각각 add_to_cart하면 THE system SHALL 마켓에 맞는 구매요청 생성 API(rpa-store / bunjang / shop)를 부른 뒤 add-carts로 붙여 delivered 웹 장바구니에 같은 상품이 보이게 한다"
  - id: AC2
    story: P2
    ears: "WHEN get_cart가 호출되면 THE system SHALL delivered v3/cart를 읽어 상품·수량·상품가(KRW)가 delivered 웹 장바구니와 일치하는 Cart를 돌려주고, 수수료·마켓 그룹·만료 여부는 cart_extras로 화면에 넘긴다"
  - id: AC3
    story: P4
    ears: "WHEN update_cart_item으로 수량을 바꾸면 THE system SHALL 기존 구매요청을 삭제하고 새 수량으로 재생성해 delivered 장바구니에 그 수량이 반영되게 한다"
  - id: AC4
    story: P3
    ears: "WHEN remove_from_cart가 호출되면 THE system SHALL 해당 라인의 구매요청 ID로 delivered 장바구니 항목을 삭제한다"
  - id: AC5
    story: P5
    ears: "WHEN 게스트 세션이 담기를 시도하면 THE system SHALL 로그인 안내(SignInRequired)로 끝내고 delivered에 아무 호출도 하지 않는다"
  - id: AC6
    story: P5
    ears: "WHEN delivered가 장바구니 가득 참(CART-OO5)·판매 종료·구매요청 실패를 돌려주면 THE system SHALL 에이전트가 손님에게 그대로 전할 수 있는 한국어 문장으로 오류를 relay한다"
  - id: AC7
    story: P1
    ears: "WHEN 테스트가 실행되면 THE system SHALL 녹화 응답 기반 가짜 게이트웨이로 마켓별 구매요청 경로 분기·매핑·오류 relay를 검증하고 네트워크에 닿지 않는다"
  - id: AC8
    story: P2
    ears: "WHEN delivered 장바구니 항목이 세션에서 본 적 없는 상품이면 THE system SHALL 그 항목을 {market}:{pid}로 되돌려 Cart 라인에 싣고, 세션 provenance에 등록해 수량 변경·삭제가 게이트를 통과하게 한다"
sources: { read: 1, unread: 0, blocked: 0, figma: none }
---

# Mission: delivered 장바구니 연동 — 구매요청 생성 + add-carts, 조회·삭제·수량 변경, 전 마켓

> Jira: RBD-8277 | Epic: RBD-8273 [RND] delivered 쇼핑 에이전트 — 로그인·장바구니·결제 연결 | Priority: Medium

## Background

에이전트의 장바구니는 지금 프로세스 메모리(`SessionCarts`)에만 있어 delivered 실제 장바구니와 무관하다. 손님이 대화에서 담은 상품이 delivered 장바구니에 그대로 들어가야 다음 티켓(결제 핸드오프)이 결제 페이지로 넘길 수 있다.

delivered 장바구니는 **구매요청을 먼저 만들고 그 ID를 장바구니에 붙이는** 2단계 모델이다. 구매요청 생성 경로는 마켓별로 다르다 — RPA 마켓(스마트스토어·다이소·무신사·올리브영·위버스샵·예스24·케이타운포유·포카마켓·메이크스타·알라딘·윗치폼·비온디·팬즈)은 `POST /v1/buy-request/rpa-store`, 번개장터는 `POST /v2/buy-request/bunjang`, DK샵은 `POST /v2/buy-request/shop`. 그 뒤 `POST /v2/cart/add-carts?buyRequestIds=…&entryType=0`으로 붙이고, `GET /v3/cart`로 읽고, `DELETE /v2/cart?buyRequestIds=…`로 지운다. 수량 변경 API는 없다.

RBD-8275(완료)가 세션에 Bearer 토큰을 보관하고 `customer_call`로 고객 API를 부르는 공통 경로를 만들었고, 게스트의 장바구니 쓰기는 이미 `SignInRequired`로 막힌다. 이 티켓은 그 경로 위에서 장바구니 4개 동작(담기·조회·수량 변경·삭제)을 delivered 실제 장바구니로 바꾼다. 상품 ID는 `{market}:{id}`라 `split_product_id`로 마켓을 가른다.

## Goal

로그인한 손님이 에이전트에서 담고·바꾸고·빼는 것이 delivered 웹 장바구니와 항상 같게 만든다 — delivered가 취급하는 전 마켓에 대해, 프레임워크의 장바구니 게이트(세션에서 본 상품만, 수량 상한)는 그대로 둔 채.

## User Stories

우선순위 순으로 정렬:

### P1: 담기 — 마켓별 구매요청 생성 후 장바구니에 붙이기

- **As a** 로그인한 손님
- **I want** 에이전트에 "담아줘"라고 하면 그 상품이 delivered 장바구니에 들어가기를
- **So that** 웹이나 결제 페이지에서 같은 장바구니로 이어갈 수 있다

**Acceptance Criteria:**
- [ ] AC1: 스마트스토어·번개장터·위버스샵 상품 각 1개를 담으면 delivered 웹 장바구니에 같은 상품이 보인다(마켓별 구매요청 경로 분기 후 add-carts).
- [ ] AC7: 녹화 응답 기반 가짜 게이트웨이 테스트로 마켓별 경로 분기·매핑·오류 relay를 검증하며 네트워크에 닿지 않는다.

### P2: 조회 — delivered 장바구니를 프레임워크 Cart로

- **As a** 로그인한 손님
- **I want** 에이전트의 장바구니 보기가 delivered 웹 장바구니와 같기를
- **So that** 어디서 보든 담긴 것이 하나다

**Acceptance Criteria:**
- [ ] AC2: `get_cart` 결과의 상품·수량·상품가(KRW)가 delivered 웹 장바구니와 일치한다. 수수료 내역·마켓 그룹·만료 여부는 `cart_extras`로 화면에 함께 넘긴다.
- [ ] AC8: 웹에서 담아 세션이 본 적 없는 항목도 `{market}:{pid}`로 Cart 라인에 실리고 provenance에 등록되어 수량 변경·삭제가 게이트를 통과한다.

### P3: 삭제

- **As a** 로그인한 손님
- **I want** "빼줘"가 delivered 장바구니에서 그 항목을 없애기를
- **So that** 웹에서 다시 지울 필요가 없다

**Acceptance Criteria:**
- [ ] AC4: `remove_from_cart`가 라인의 구매요청 ID로 `DELETE /v2/cart`를 불러 delivered에서 항목이 사라진다.

### P4: 수량 변경 — 삭제 후 재생성

- **As a** 로그인한 손님
- **I want** "2개로 바꿔줘"가 delivered 장바구니 수량에 반영되기를
- **So that** 결제 페이지에서 수량을 다시 맞추지 않아도 된다

**Acceptance Criteria:**
- [ ] AC3: `update_cart_item`이 기존 구매요청을 삭제하고 새 수량으로 재생성해 delivered 장바구니 수량이 바뀐다. 재생성이 실패하면 삭제도 되돌릴 수 없으므로 손님에게 "다시 담아 달라"고 안내한다.

### P5: 게이트와 오류 relay

- **As a** 손님
- **I want** 게스트일 때는 로그인 안내를, delivered가 거절하면 이유를 알기 쉬운 말로 듣기를
- **So that** 다음 행동을 바로 정할 수 있다

**Acceptance Criteria:**
- [ ] AC5: 게스트 세션의 담기는 로그인 안내로 끝나고 delivered에 아무 호출도 만들지 않는다(기존 `require_credential` 유지).
- [ ] AC6: 장바구니 가득 참(`CART-OO5`), 판매 종료 상품, 구매요청 생성 실패 등 delivered 오류가 에이전트가 손님에게 전할 수 있는 한국어 문장으로 relay된다(툴 오류 → 모델 안내).

## UI/Design Requirements

> 백엔드 티켓 — 화면 변경 없음. 스토어프론트 `CartPanel`은 기존 `CartPayload`(items·item_count·subtotal·currency)를 그대로 읽고, `cart_extras`로 추가되는 필드(수수료·마켓 그룹·만료)는 이번엔 payload에만 실린다(화면 반영은 장바구니 화면 티켓).

### 데이터 요구사항 (from Design)
- `CartItem.product_id = "{market}:{pid}"`, `title = product_title`, `price = ITEM_PRICE cost_krw / quantity`(단가), `quantity`, `image_url = thumbnail_image_url`.
- 구매요청 ID(delivered 장바구니 항목 ID)는 세션 안 매핑(`product_id → buy_request_id`)으로 보관해 삭제·재생성에 쓴다.
- `cart_extras`: `delivered_cart: {groups: [{market_sub_type, market_name, is_bundled, items: [{buy_request_id, product_id, fees: [{fee_type, cost_krw, cost_usd}], is_expired, is_selling}]}]}`.

## Non-Functional Requirements

- **보안**: 토큰은 기존 `customer_call` 경로로만 붙인다. 로그에 토큰·본문을 남기지 않는다(메서드·경로·상태만).
- **일관성**: 담기·수량 변경·삭제 뒤에는 delivered에서 다시 읽은 장바구니를 돌려준다(로컬 상태를 신뢰하지 않는다). 담기 중 구매요청은 만들어졌는데 add-carts가 실패하면 고아 구매요청이 남는다 — 그 ID를 로그로 남기고 오류를 relay한다.
- **성능**: 한 담기에 최대 3회 호출(구매요청 생성 → add-carts → 재조회). 수량 변경은 4회. 세션 락(`gated_*`)이 동시 호출을 직렬화한다.
- **호환성**: `Cart(currency="KRW")` 유지. 프레임워크 코어(`shopping_agent`)와 `demo_common`은 수정하지 않는다(`cart_extras`는 이미 있는 훅).

## Out of Scope

- 옵션(색상·사이즈) 있는 상품의 옵션 선택 — RBD-8278. 이 티켓에서는 옵션 상품 담기를 기존처럼 거절한다(`has_options` → KeyError → 에이전트가 옵션 선택 필요를 안내).
- 게스트 장바구니(`guests/guest-add-carts`).
- 배송비·수수료 계산 자체(delivered 응답을 그대로 실어 나른다).
- 스토어프론트 장바구니 화면의 수수료·마켓 그룹 표시.
- 결제 페이지 핸드오프 — RBD-8280.

## Open Questions

- [x] Q1: delivered 장바구니의 만료(`is_expired`)·판매 종료(`is_selling=false`) 항목을 `get_cart`에서 어떻게 다룰까 — Cart 라인에 포함하고 `cart_extras`에 표시만 하는가, 아니면 Cart에서 제외하는가?
  → 확정: **포함하고 표시** (2026-09-14, 사용자). Cart 라인에 그대로 싣고 `cart_extras`의 `is_expired`/`is_selling`으로 화면·에이전트가 안내한다 — 웹 장바구니와 항목이 1:1로 맞는다.
- [x] Q2: 스테이징 계정으로 실제 구매요청·장바구니를 만들어 검증해도 되는가(개발 중 생성한 구매요청은 테스트 후 삭제한다)?
  → 확정: **된다** (2026-09-14, 사용자). develop에서 스테이징 계정으로 구매요청·add-carts·조회·삭제를 실측해 계약을 확인하고, 만든 항목은 삭제한다.

> 모든 Open Questions가 해소되어야(`- [x]`) blueprint 단계로 진행할 수 있습니다. (frontmatter `gates.open_q` 와 동기)

---

## 🤖 소스 추적 (기계용 — 사람은 읽지 않아도 됨)

### Sources

| 소스 | 상태 | 비고 |
|------|------|------|
| Jira 티켓 | ✅ 확인 | RBD-8277 (`/jarvis:draft` 산출물 — 품질 검증 통과, 선행 RBD-8275 완료, 후속 RBD-8278) |
| PM 티켓 (에픽 링크) | ⚠️ 없음 | 기획 티켓 없음 — 에픽 RBD-8273 이슈 링크·리모트 링크·첨부 0건(이 세션에서 확인) |
| Figma 디자인 | ⏭️ 없음 | 백엔드 티켓 |

### PM 티켓 관련 링크 (전수)

| 제목 | kind | source | 상태 | URL |
|------|------|--------|------|-----|
| (없음) | — | — | — | — |

### Reference Code

| 프로젝트 | 파일 경로 | 참조 목적 |
|---------|---------|---------|
| 현재 프로젝트 | `examples/delivered/api/delivered_backend.py` | 교체 대상 `get_cart/add_to_cart/update_cart_item/remove_from_cart`, `split_product_id`, `customer_call` |
| 현재 프로젝트 | `examples/delivered/api/delivered_auth.py` | `DeliveredAuthClient.customer_request`(Bearer·Expired Token 처리) |
| 현재 프로젝트 | `examples/demo_common/storefront_fixtures.py`, `examples/demo_common/storefront.py` | `SessionCarts`·`cart_line`(현행), `cart_extras` 훅 |
| 현재 프로젝트 | `shopping-agent/core/shopping_agent/gates.py`, `types.py` | provenance·수량 게이트, `Cart`/`CartItem` 모양 |
| deliveredkorea-customer-frontend | `src/features/repository/cart/*.ts`, `src/features/repository/buyRequest/fetchBuyRequest.ts`, `src/types/api/cart/cartApiDto.ts`, `src/types/api/buyRequest/buyRequestApiDto.ts`, `src/libs/enums/_common.ts` | 장바구니·구매요청 API 경로와 요청/응답 형태, 마켓 enum |
| deliveredkorea-webuy-cat-service | `src/main/kotlin/com/delivered/api/buyrequest/controller/RPAStoreController.kt`, `api/cart/controller/CartController.kt` | 서버 측 계약·오류 코드 (blueprint에서 발췌) |
