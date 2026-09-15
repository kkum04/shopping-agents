---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: blueprint
completed: [mission, blueprint]
plan: [tasks, develop]
skip: []
depth: standard
base_sha: 7b13529
gates:
  open_q: 0
risk:
  self: 0.2                     # base 0.2(tx_boundary=외부 연동) + 설계 품질 신호 0 → < 0.4 생략
  review: skipped
design:
  new_api: false                # 게스트 옵션 API 2개를 소비; 우리 endpoint 추가 없음
  db_migration: false
  cross_domain: 1
  tx_boundary: true             # 구매요청에 옵션 ID 전달 (RBD-8277 경로)
  files_touched: 9
integrations:
  - service: delivered-guest-api
    prop_key: DELIVERED_API_URL
    endpoints: ["GET /buy-request/stores/smartstore/{pid}/option-groups", "GET /buy-request/stores/smartstore/{pid}/options"]
    on_failure: absorb          # 옵션 API 실패 → 옵션 없는 상품으로 (경고 로그)
    verified: true              # 2026-09-14 운영 게스트 API 실측 (58개 상품)
  - service: delivered-customer-api
    prop_key: DELIVERED_CUSTOMER_API_URL
    endpoints: ["POST /v1/buy-request/rpa-store (options: [optionId])"]
    on_failure: propagate       # 4xx → CartRejected relay (RBD-8277)
    verified: false             # optionId를 실은 생성은 develop 실측(Q2 승인)
  - service: delivered-customer-api
    prop_key: DELIVERED_CUSTOMER_API_URL
    endpoints: ["GET /v3/cart (items[].options[]{type,key,value})", "GET /v2/cart/{id} (options[])"]
    on_failure: absorb          # 역매핑 실패 → family id로 실음
    verified: false             # 옵션 라인의 options[] 실제 값은 develop 실측
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [옵션, option-groups, options, variant, family, 구매요청, 스마트스토어]
  modules:
    - examples/delivered/api/delivered_options.py
    - examples/delivered/api/delivered_backend.py
    - examples/delivered/api/delivered_cart.py
    - examples/delivered/api/agent_config.py
    - examples/delivered/api/tests/test_delivered_options.py
    - examples/delivered/api/tests/test_delivered_backend.py
    - examples/delivered/api/tests/fixtures/smartstore-option-groups.json
    - examples/delivered/api/tests/fixtures/smartstore-options.json
    - examples/delivered/README.md
coverage:
  - ac: AC1
    modules: [delivered_options.py(family_with_variants), delivered_backend.py(get_product_details·DeliveredClient)]
  - ac: AC2
    modules: [delivered_backend.py(add_to_cart has_options → KeyError; 코어 옵션 게이트)]
  - ac: AC3
    modules: [delivered_options.py(split_variant_id), delivered_cart.py(buy_request_body options)]
  - ac: AC4
    modules: [delivered_backend.py(add_to_cart → Unavailable(siblings))]
  - ac: AC5
    modules: [delivered_options.py(split_families·MAX_VARIANTS), delivered_backend.py(get_product_details sub-family)]
  - ac: AC6
    modules: [tests/test_delivered_options.py, tests/fixtures/smartstore-option-groups.json, tests/fixtures/smartstore-options.json]
  - ac: AC7
    modules: [delivered_options.py(variant_for_option_names), delivered_backend.py(_resolve_product_id)]
  - ac: AC8
    modules: [delivered_backend.py(add_to_cart TEXT → CartRejected), delivered_options.py(text_option_groups)]
---

# Blueprint: 옵션 상품 매핑 — option-groups/options를 family/variant로, 구매요청에 옵션 전달

> Mission: ./mission.md | Jira: RBD-8278

## Tech Stack

- **Language**: Python 3.12, `from __future__ import annotations`, pydantic 코어 타입(`Product`/`ProductDetails` — `options`, `option_values`, `variant_of`, `variants`)
- **HTTP**: 기존 `DeliveredClient._call`(게스트 API), `asyncio.gather`로 상세 + 옵션 2개 병렬
- **테스트**: pytest + `FakeGateway`(게스트) 확장 + 녹화 픽스처 JSON 2개(운영 실측 2026-09-14: pid 11314403854 COMBINATION 2옵션 / pid 10631022673 COMBINATION+TEXT 12옵션)

## Architecture Overview

```text
get_product_details("smart_store:{pid}")
  ├─ gather(detail, option-groups, options)          옵션 API 실패 → 옵션 없는 상품 (경고 로그)
  ├─ family_with_variants(detail, groups, options)
  │    ├─ COMBINATION 그룹 → family.options = {그룹명: [값…]}   (그룹명 = productOptionGroupName ko)
  │    ├─ 옵션 행 하나 = variant 하나: id "{family_id}#{optionId}", option_values = {그룹명: 값}, price = optionPriceKrw, in_stock = stockQuantity > 0
  │    ├─ TEXT 그룹 → family.attributes["text_options"] = "그룹명, …"  (variant를 만들지 않음, 담기 거절 표식)
  │    ├─ family.price = 재고 있는 variant 최저가(없으면 전체 최저가), in_stock = any
  │    └─ variants > 60 → 첫 그룹 값별 sub-family "{family_id}#g{index}" (아래 「분할」)
  ├─ _remember(family) + _remember(각 variant)      → product(variant_id)가 해석된다
  └─ return family        (variant id 요청이면 family 해석 후 그 variant 반환, sub-family id면 해당 조각)

add_to_cart(product_id, qty)
  ├─ require_credential
  ├─ record = get_product_details(product_id)     variant면 variant 레코드
  ├─ family = record 자신 또는 record.variant_of 의 family
  ├─ family.attributes.text_options 있으면 → CartRejected("이 상품은 문구 입력(각인 등)이 필요해 delivered 웹에서 담아 주세요")   (AC8)
  ├─ record.has_options → KeyError (코어 옵션 게이트가 먼저 잡지만 백엔드도 거절)                                    (AC2)
  ├─ variant.in_stock False → Unavailable("{id} is sold out; in stock: {형제 variant id…}")                          (AC4)
  └─ RBD-8277 흐름 그대로 — buy_request_body가 split_variant_id로 optionId를 뽑아 options=[optionId]                (AC3)

get_cart → _resolve_product_id(buy_request_id)     (AC7)
  ├─ GET /v2/cart/{id} → pid, market, options[]{type,key,value}
  ├─ options 비었으면 → "{market}:{pid}"
  └─ 있으면 → 옵션 API(options)로 pid의 옵션 행을 읽어 key/value(그룹명/값) 전부 일치하는 optionId → variant id; 못 찾으면 family id (경고)
```

id 형식: family `smart_store:{pid}` · variant `smart_store:{pid}#{optionId}` · sub-family `smart_store:{pid}#g{n}`(n = 첫 그룹 값의 순번). `split_product_id`는 `#` 앞까지가 마켓:pid이므로 RBD-8277의 라우팅·본문 생성은 그대로 동작한다.

## Directory Structure

```text
examples/delivered/api/
├── delivered_options.py                     (신규) 옵션 응답 → family/variant 매핑, variant id 형식·역매핑, 분할, 이름 대조
├── delivered_backend.py                     (수정) DeliveredClient 옵션 2메서드, get_product_details 병렬·variant/sub-family 해석, add_to_cart 옵션 규칙, _resolve_product_id 옵션 역매핑
├── delivered_cart.py                        (수정) buy_request_body: options=[optionId] (variant일 때), text_options=[]
├── agent_config.py                          (수정) 옵션 상품 안내 한 줄 (TEXT 그룹은 웹에서)
└── tests/
    ├── fixtures/smartstore-option-groups.json  (신규) 녹화 — 두 상품의 option-groups
    ├── fixtures/smartstore-options.json        (신규) 녹화 — 두 상품의 options
    ├── test_delivered_options.py               (신규) L1 순수 함수
    └── test_delivered_backend.py               (수정) L2 상세·담기·역매핑
examples/delivered/README.md                 (수정) 옵션 상품 절
```

## Module Design

### delivered_options.py — 순수 함수

- `MAX_VARIANTS = 60`, `VARIANT_SEPARATOR = "#"`, `SUB_FAMILY_PREFIX = "g"`
- `variant_id_of(family_id, option_id) -> str` / `split_variant_id(product_id) -> tuple[str, str | None]`: `"smart_store:1#137750"` → `("smart_store:1", "137750")`; `#g2`는 옵션이 아니라 sub-family 표식(`sub_family_index(product_id) -> int | None`).
- `group_names(groups) -> dict[int, str]`(COMBINATION·SIMPLE), `text_option_groups(groups) -> list[str]`(TEXT 그룹명).
- `family_with_variants(detail: ProductDetails, groups: list[dict], options: list[dict]) -> ProductDetails`: 위 규칙. 옵션 행의 `productOptionName`이 알려진 그룹을 가리키지 않으면 그 행은 건너뛴다. variant는 family 필드를 상속하고 `price`·`in_stock`·`option_values`·`variant_of`·`attributes["option_id"]`만 다르다. `specs`는 variant에서 비운다(행 길이 70~120자 유지).
- `split_families(family) -> list[ProductDetails]`: variants ≤ 60이면 `[family]`; 넘으면 첫 그룹 값별로 sub-family(`options`는 나머지 그룹만, `attributes["option_group_1"] = 값`, id `#g{n}`)를 만들고, 원 family는 `variants=[]`·`attributes["variant_families"] = "#g1 값A, #g2 값B, …"`로 안내만 남긴다.
- `variant_for_option_names(options, names: dict[str, str]) -> int | None`: `{그룹명: 값}`이 전부 일치하는 optionId.

### delivered_backend.py

- `DeliveredClient.smartstore_option_groups(pid)` / `smartstore_options(pid)` — `_call("GET", …)`.
- `get_product_details`: `base_id, option_id = split_variant_id(product_id)`; `base_id`가 SMART_STORE면 `asyncio.gather(detail, groups, options, return_exceptions=True)` → 옵션 둘 중 하나라도 예외/빈 응답이면 옵션 없는 상세(현행). 옵션이 있으면 `family_with_variants` → `split_families` → family·sub-family·variant 전부 `_remember`. 요청 id가 variant면 그 variant, sub-family면 그 조각, 아니면 family를 돌려준다. `self.products`(홈 목록)에는 family만.
- `add_to_cart`: 위 흐름도. 형제 재고 목록은 family(`product(variant.variant_of)`)의 `variants`에서 `in_stock`인 id를 최대 10개.
- `_resolve_product_id`: 상세 응답의 `options`가 비어 있지 않고 SMART_STORE면 `client.smartstore_options(pid)`로 대조(`variant_for_option_names`) — 옵션 API 실패·불일치는 family id로 두고 경고.

### delivered_cart.py

- `buy_request_body`: `options = [int(option_id)] if option_id else []`(`split_variant_id`), `text_options = []`. `pid`는 `#` 앞 raw id. 번개장터·DK샵 분기는 옵션이 없으므로 그대로.

### agent_config.py / README

- 안내 한 줄: "옵션 상품은 상세의 variants 중 하나로 담는다; `attributes.text_options`가 있으면 delivered 웹에서 담아야 한다고 안내". README 「Options」 절.

## Error Handling

| 상황 | 처리 |
|------|------|
| 옵션 API 4xx/5xx/전송 오류 | 옵션 없는 상품으로 상세 반환 + 경고(경로·상태만) — 상세 자체는 막지 않음 |
| family id로 담기 | `KeyError`(현행) → 코어 옵션 게이트/provenance 안내 |
| TEXT 그룹 상품(family·variant) 담기 | `CartRejected`(웹에서 담기 안내), delivered 호출 없음 |
| 품절 variant | `Unavailable("… in stock: id, id")`, 호출 없음 |
| 알 수 없는 variant id(옵션 행 없음) | `KeyError` |
| 역매핑 불일치 | family id로 실음 + 경고 |

## Migration / Side Effects

- DB·코어·demo_common 변경 없음. 옵션 없는 상품 경로는 현행 유지(옵션 API가 빈 배열이면 결과 동일).
- 스마트스토어 상세 1회가 게이트웨이 호출 3회가 된다(병렬). 게이트웨이 지연에 노출.
- `_seen` 캐시(`SEEN_CAP`)에 variants가 함께 들어가 용량을 더 쓴다 — 상한 내.
