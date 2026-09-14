---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: blueprint
completed: [mission, blueprint]
plan: [tasks, develop]
skip: []
depth: standard
base_sha: d946a06
gates:
  open_q: 0
risk:
  self: 0.2                     # base 0.2(tx_boundary=외부 연동) + 설계 품질 신호 0 → < 0.4 생략
  review: skipped
design:
  new_api: false                # 우리 API에 새 endpoint 없음 — StorefrontBackend 4메서드 교체 + cart_extras 훅
  db_migration: false
  cross_domain: 1               # examples/delivered/api 한 모듈 (demo_common·코어는 수정 없음)
  tx_boundary: true             # 구매요청 생성 → add-carts 2단계, 수량 변경 = 삭제 → 재생성 (원자성 없음)
  files_touched: 8
integrations:
  - service: delivered-customer-api
    prop_key: DELIVERED_CUSTOMER_API_URL
    endpoints: ["POST /v1/buy-request/rpa-store"]
    on_failure: propagate       # 구매요청 실패 → CartRejected(한국어 문장)로 툴 오류
    verified: true              # 2026-09-14 운영 실측 — market_type은 SHOP (OTHER는 MARKET-003)
  - service: delivered-customer-api
    prop_key: DELIVERED_CUSTOMER_API_URL
    endpoints: ["POST /v2/buy-request/bunjang", "POST /v2/buy-request/shop"]
    on_failure: propagate
    verified: true              # 번개장터 2026-09-14 스테이징 실측(원시 number 응답). DK샵은 미실측(같은 레거시 서비스)
  - service: delivered-customer-api
    prop_key: DELIVERED_CUSTOMER_API_URL
    endpoints: ["POST /v2/cart/add-carts", "DELETE /v2/cart"]
    on_failure: propagate       # CART-004(이미 담김)만 흡수, 나머지는 relay
    verified: true              # 2026-09-14 실측 — id는 v3 항목의 cart_id
  - service: delivered-customer-api
    prop_key: DELIVERED_CUSTOMER_API_URL
    endpoints: ["GET /v3/cart", "GET /v2/cart/{buyRequestId}"]
    on_failure: propagate       # 조회 실패 → DeliveredApiError(프레임워크 "일시 불가")
    verified: true              # v3 2026-09-14 실측(UNIT_PRICE·cart_id); 상세 경로는 코드 근거
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [장바구니, 구매요청, add-carts, 마켓, rpa-store, bunjang, 수량, 삭제]
  modules:
    - examples/delivered/api/delivered_cart.py
    - examples/delivered/api/delivered_backend.py
    - examples/delivered/api/delivered_executor.py
    - examples/delivered/api/agent_config.py
    - examples/delivered/api/main.py
    - examples/delivered/api/tests/test_delivered_cart.py
    - examples/delivered/api/tests/test_delivered_backend.py
    - examples/delivered/README.md
coverage:
  - ac: AC1
    modules: [delivered_cart.py(buy_request_body·route), delivered_backend.py(add_to_cart)]
  - ac: AC2
    modules: [delivered_cart.py(cart_from_v3), delivered_backend.py(get_cart·cart_extras), main.py]
  - ac: AC3
    modules: [delivered_backend.py(update_cart_item)]
  - ac: AC4
    modules: [delivered_backend.py(remove_from_cart)]
  - ac: AC5
    modules: [delivered_backend.py(require_credential — 기존), tests/test_delivered_backend.py]
  - ac: AC6
    modules: [delivered_cart.py(CartRejected·ERROR_MESSAGES), delivered_executor.py]
  - ac: AC7
    modules: [tests/test_delivered_cart.py(FakeCustomerGateway 녹화 응답)]
  - ac: AC8
    modules: [delivered_cart.py(CartIndex), delivered_backend.py(get_cart — 상세 폴백)]
---

# Blueprint: delivered 장바구니 연동 — 구매요청 생성 + add-carts, 조회·삭제·수량 변경, 전 마켓

> Mission: ./mission.md | Jira: RBD-8277

## Tech Stack

- **Language**: Python 3.12, `from __future__ import annotations`, 타입 힌트, `pydantic`(코어 `Cart`/`CartItem`), `httpx.AsyncClient`
- **Framework**: FastAPI 호스트(`demo_common.build_storefront_host`), `StorefrontBackend` 구현체 `DeliveredStorefront`
- **테스트**: pytest(importlib 모드, `pythonpath=examples`), `httpx.MockTransport` 가짜 게이트웨이 — 기존 `FakeAuthGateway`(test_delivered_auth.py) 패턴을 확장
- **기타**: ruff(루트 `ruff.toml`), 로그는 메서드·경로·상태만

## Architecture Overview

에이전트 툴(`add_to_cart/update_cart_item/remove_from_cart/get_cart`) → 프레임워크 게이트(`gated_*`: provenance·수량 상한·세션 락) → `DeliveredStorefront` → **`DeliveredCart`**(신규 모듈, 구매요청·장바구니 호출과 매핑) → `customer_call`(RBD-8275, Bearer·Expired Token) → delivered 고객 API.

```text
add_to_cart(pid, qty)
  ├─ require_credential("장바구니")                       게스트 → SignInRequired (AC5)
  ├─ product = get_product_details(pid)  (옵션 상품 → KeyError, 품절 → Unavailable — 기존)
  ├─ line = index.by_product(pid)?  → 있으면 update(existing+qty)로 위임   (delivered는 같은 상품 중복 담기 = CART-004)
  ├─ buy_request_id = create_buy_request(product, qty)   마켓 분기: RPA 13종 → rpa-store / BUNJANG → bunjang / DK_SHOP → shop
  ├─ add_carts([buy_request_id])                          CART-004 흡수 · CART-005 등 → CartRejected
  └─ return get_cart()                                    delivered에서 다시 읽음 (로컬 상태 신뢰 X)

get_cart()
  ├─ GET /v3/cart → orders[].items[]
  ├─ product_id 복원: index(buy_request_id→product_id) 히트 → 그대로 / 미스 → GET /v2/cart/{id}.product_id + market.sub_type → product_id_of() 후 index 등록
  ├─ Cart(items=[CartItem(product_id, title, price=ITEM_PRICE cost_krw/quantity, quantity, image_url)], currency="KRW")
  └─ extras[session] = {delivered_cart: {groups: [...fees, is_expired, is_selling...]}}   → host cart_extras 훅

update_cart_item(pid, qty)  = delete(buy_request_id) → create(product, qty) → add_carts → get_cart   (재생성 실패 → CartRejected "다시 담아 주세요")
remove_from_cart(pid)       = delete(buy_request_id) → get_cart
```

프레임워크 게이트 `_check_provenance_or_cart`는 **장바구니가 이미 들고 있는 상품**이면 세션에서 본 적 없어도 수량 변경·삭제를 통과시키므로, 웹에서 담은 항목은 `product_id`만 정확히 복원하면 된다(AC8).

## Directory Structure

```text
examples/delivered/api/
├── delivered_cart.py                 (신규) 마켓 라우팅·구매요청 본문·v3 매핑·CartIndex·CartRejected·오류 문장
├── delivered_backend.py              (수정) SessionCarts 제거, 장바구니 4메서드를 DeliveredCart 위임으로 교체, cart_extras(session_id)
├── delivered_executor.py             (수정) CartRejected → 메시지 relay
├── agent_config.py                   (수정) DOMAIN_SEARCH_NOTES에 "장바구니는 delivered 실제 장바구니, 수수료·만료는 extras" 한 줄
├── main.py                           (수정) build_storefront_host(cart_extras=backend.cart_extras_for)
└── tests/
    ├── test_delivered_cart.py        (신규) FakeCustomerGateway(녹화 응답) — 라우팅·본문·매핑·오류 relay·삭제/재생성
    └── test_delivered_backend.py     (수정) 기존 메모리 카트 테스트를 delivered 경로로 교체, 게스트 게이트 유지 확인
examples/delivered/README.md          (수정) Cart 절 갱신
```

## Module Design

### delivered_cart.py — 라우팅·본문·매핑 (순수 함수 + 작은 상태)

- **책임**: (1) `route_of(market) -> "rpa" | "bunjang" | "shop"` — `RPA_MARKETS` 13종(SMART_STORE, DAISO, MUSINSA, OLIVE_YOUNG, WEVERSE, YES24, K_TOWN_4U, POCA_MARKET, MAKE_STAR, ALADIN, WITCHFORM, BE_ON_D, FANS), `BUNJANG`, `DK_SHOP`; 그 외 → `CartRejected("이 마켓은 아직 장바구니에 담을 수 없습니다")`. (2) `buy_request_body(product, quantity) -> tuple[path, json]` — 아래 표. (3) `cart_from_v3(payload, resolve) -> tuple[Cart, dict]` — `orders[].items[]`를 `CartItem`으로, extras 딕셔너리 동반. (4) `CartIndex`: 세션별 `buy_request_id ↔ product_id` 양방향 맵. (5) `CartRejected(Exception)`: delivered 오류 코드/상황 → 한국어 문장 (`ERROR_MESSAGES`: CART-005 "장바구니가 가득 찼습니다(최대 개수 초과) — 웹에서 항목을 정리한 뒤 다시 담아 주세요", CART-001 "장바구니에 없는 항목입니다", CART-003 "장바구니 담기에 실패했습니다", 구매요청 실패 "구매요청을 만들지 못했습니다: {message}", 판매 종료 "판매가 끝난 상품입니다").
- **위치**: `examples/delivered/api/delivered_cart.py`
- **의존성**: `shopping_agent.types.Cart/CartItem/ProductDetails`, `delivered_backend.split_product_id/product_id_of`(순환 방지를 위해 두 헬퍼는 `delivered_cart.py`로 옮기고 backend가 재수출)
- **주요 로직 — 구매요청 본문** (고객 프론트가 보내는 snake_case 그대로; 서버 DTO는 camelCase지만 프론트가 동작하므로 snake_case 매핑을 신뢰 — 실측으로 확인):

| 라우트 | 경로 | 본문 |
|--------|------|------|
| rpa | `POST /v1/buy-request/rpa-store` | `{pid, market_type: <catalog marketType, 기본 "SHOP">, market_sub_type: <market>, quantity, uploaded_image_urls: [], additional_information: "", options: [], text_options: [], pre_order_yn: false}` → `{result, data: <id>}` |
| bunjang | `POST /v2/buy-request/bunjang` | `{market_type: "BUNJANG", market_sub_type: "BUNJANG", product_url, pid: int, item_description: title, quantity, bid_confirm_type: "REJECTED", item_image_urls: [image], bunjang_image_urls: [], additional_information: ""}` → 원시 number |
| shop | `POST /v2/buy-request/shop` | `{product_url, pid, item_description: title, quantity, item_image_urls: [image], market_type: "SHOP", market_sub_type: "DK_SHOP", options: []}` → `{data: <id>}` |

  `market_type`은 카탈로그 목록이 주는 `marketType`(스마트스토어 = SHOP)을 쓰고 없으면 SHOP — 운영 실측으로 확정(OTHER는 400 MARKET-003). 번개장터·DK샵은 `product_url`이 필요하므로 검색 결과의 `productUrl`을 `ProductDetails.attributes["product_url"]`에 보존한다(delivered_backend `_base_fields` 소폭 수정).

- **주요 로직 — v3 매핑**: 항목마다 `price = ITEM_PRICE cost_krw / quantity`(라인 합계로 가정 — 실측으로 단가/합계 여부 확정), `title = product_title`, `image_url = thumbnail_image_url`, `product_id = resolve(buy_request_id)`. extras: `{"delivered_cart": {"groups": [{"market_sub_type", "market_name", "is_bundled", "items": [{"buy_request_id", "product_id", "fees": prices[], "is_expired", "is_selling"}]}]}}`. 만료·판매 종료 항목도 Cart에 포함(Q1).

### delivered_backend.py — DeliveredStorefront 장바구니 4메서드

- **책임**: 게이트를 통과한 호출을 delivered로 실행하고 항상 재조회한 Cart를 돌려준다.
- **주요 로직**:
  - `_create_buy_request(session, product, quantity) -> int`: `buy_request_body` → `customer_call(session, "POST", path, json=body, feature="장바구니")` → 응답 형태 3종(`{data: n}` / 원시 number / `{result, data}`)에서 id 추출. `DeliveredApiError`는 `CartRejected("구매요청을 만들지 못했습니다")`로 감싼다(코드·메시지 포함 — 아래 오류 처리).
  - `_add_carts(session, ids)`: `POST /v2/cart/add-carts?buyRequestIds=a,b&entryType=0`(본문 없음). CART-004는 성공으로 본다.
  - `_delete(session, ids)`: `DELETE /v2/cart?buyRequestIds=…`. CART-001(이미 없음)은 성공으로 본다.
  - `get_cart`: 게스트면 빈 Cart(기존). 회원이면 `GET /v3/cart` → `cart_from_v3` + 미스 항목은 `GET /v2/cart/{id}`로 `product_id`·`market.sub_type` 복원(1항목당 1회, 결과는 `CartIndex`에 캐시). extras를 `self._cart_extras[session_id]`에 저장.
  - `cart_extras_for(record) -> dict`: 호스트 훅 — 마지막 `get_cart`의 extras(없으면 `{}`).
  - `add_to_cart`: 위 흐름도. 같은 상품 라인이 이미 있으면 `update_cart_item(existing.quantity + quantity)`로 위임(게이트가 넘긴 `quantity`는 추가분).
  - `update_cart_item`: `_delete([id])` → `_create_buy_request` → `_add_carts` → `get_cart`. 재생성 단계 실패 시 index에서 제거하고 `CartRejected("수량을 바꾸는 중 항목이 삭제됐지만 다시 담지 못했습니다 — 다시 담아 주세요")`.
  - `remove_from_cart`: `_delete([id])` → index 제거 → `get_cart`. 라인이 없으면 그대로 `get_cart`.
  - `reset_session`: index·extras 삭제(기존 credentials drop 유지). `SessionCarts`·`_carts` 제거.
- **오류 정보 확보**: `customer_request`는 4xx에서 상태만 남기므로 `DeliveredApiError`에 `code`/`message` 속성(응답 `{code, result, message}`)을 실어 주도록 `delivered_auth.py`를 최소 수정한다(생성자 시그니처 유지, 속성 추가) — CART-004/001 흡수와 CART-005 relay가 이 코드를 읽는다.

### delivered_executor.py — CartRejected relay

- `domain_error`에 `CartRejected` → `str(error)`(이미 한국어 문장). 기존 SignInRequired/TokenExpired 유지.

### agent_config.py / main.py / README

- `DOMAIN_SEARCH_NOTES`에 장바구니가 delivered 실제 장바구니이며 수수료·만료는 `cart_extras`로 전달된다는 한 줄. `main.py`는 `cart_extras=backend.cart_extras_for` 연결. README Cart 절 갱신.

## Error Handling

| 상황 | 처리 |
|------|------|
| 게스트 | `SignInRequired`(기존) — delivered 호출 없음 |
| 옵션 상품 / 세션 미보유 상품 | `KeyError`(기존) → 프레임워크 옵션·provenance 안내 (옵션은 RBD-8278) |
| 지원하지 않는 마켓(OTHER 등) | `CartRejected("이 마켓은 아직 장바구니에 담을 수 없습니다")` |
| 구매요청 4xx (품절·판매 종료·검증 실패) | `CartRejected("구매요청을 만들지 못했습니다: {delivered message}")` |
| add-carts CART-005 | `CartRejected(가득 참 문장)`; 만들어진 구매요청 id를 로그(`orphan buy request`)로 남김 |
| add-carts CART-004 | 흡수(이미 담김) → 재조회 |
| DELETE CART-001 | 흡수 → 재조회 |
| 5xx / 전송 오류 / 비JSON | `DeliveredApiError`(프레임워크 "일시 불가") |
| Expired Token | 기존 `TokenExpired` 경로(토큰 폐기 + 재로그인 안내) |
| 수량 변경 중 재생성 실패 | 삭제는 되돌릴 수 없음 → `CartRejected("… 다시 담아 주세요")` + 로그 |

## Migration / Side Effects

- DB·마이그레이션 없음. 프레임워크 코어·`demo_common` 수정 없음(`cart_extras`는 기존 훅).
- `delivered_auth.DeliveredApiError`에 속성 추가는 하위 호환(메시지 문자열 그대로).
- 기존 메모리 카트 테스트(test_delivered_backend.py의 cart 부분)는 delivered 경로로 다시 쓴다. `storefront_fixtures.SessionCarts` import 제거.
- 스토어프론트 `CartPayload`는 그대로 동작하고, payload에 `delivered_cart` 키가 추가로 실린다(화면은 무시 — 장바구니 화면 티켓에서 사용).
- 데모 실측(Q2)에서 만든 스테이징 구매요청은 테스트 후 `DELETE /v2/cart`로 지운다.
