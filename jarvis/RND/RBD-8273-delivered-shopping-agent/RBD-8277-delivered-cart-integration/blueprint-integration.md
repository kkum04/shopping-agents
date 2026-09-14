# Blueprint — Integration: delivered 장바구니 연동 — 구매요청 생성 + add-carts, 조회·삭제·수량 변경

> Main: ./blueprint.md
> 모든 호출은 `DELIVERED_CUSTOMER_API_URL`(기본 `https://gw-staging.delivered.co.kr/dk-delivered/api/customer`) 아래이며 `customer_call`이 Bearer를 붙인다. 테스트는 `httpx.MockTransport` 가짜 게이트웨이로 대체한다. 계약 근거는 webuy-cat-service 컨트롤러/DTO와 고객 프론트 요청 코드이며, 실제 호출은 develop에서 스테이징 계정으로 확인했다(2026-09-14): 번개장터 구매요청·add-carts·v3/cart·DELETE는 ✅ 확인, RPA(rpa-store)는 운영 계정으로 ✅ 확인(2026-09-14, `market_type: SHOP` — OTHER는 400 MARKET-003), DK샵만 ⚠️ 미확인.

## delivered-customer-api · RPA 구매요청 생성

- **호출**: `POST /v1/buy-request/rpa-store`
- **주소 출처**: `DELIVERED_CUSTOMER_API_URL`
- **트리거**: `add_to_cart`/`update_cart_item`에서 RPA 13개 마켓 상품일 때 1회. 동기.
- **계약 근거**: webuy-cat-service `RPAStoreController.kt:20-28`, `BuyRequestCrawlVo.kt:59-81`(`BuyRequestRPAStoreRequest`), Jackson 전역 `property-naming-strategy: SNAKE_CASE`(application.yml) → snake_case 전송 확정 — ✅ 운영 실측(2026-09-14): `market_type: "SHOP"`(카탈로그 목록의 `marketType`; `OTHER`는 400 `MARKET-003` "존재하지 않는 마켓"), 응답 `{result: true, data: 1010001}`; `add-carts` 재호출 400 `CART-004`; `v3/cart` 항목 `cart_id` 1010001·`UNIT_PRICE cost_krw` 23500 = 단가(수량 2, USD 합계 37.4); `GET /v2/cart/{id}` → `data.product_id`·`market.sub_type` 확인; 스테이징 500 `SYS-001`도 같은 원인으로 추정

**보내는 것** (검증 대상 필드만):

```json
{ "pid": "10791906854", "market_type": "SHOP", "market_sub_type": "SMART_STORE", "quantity": 1, "options": [], "text_options": [], "uploaded_image_urls": [], "additional_information": "", "pre_order_yn": false }
```

**성공 응답**: `{ "result": true, "data": 123456 }` — `data`가 구매요청 ID.

**실패하면 우리는**: 4xx(`{code, message}`) → `CartRejected("구매요청을 만들지 못했습니다: {message}")` 상위 전파 · 5xx/전송 → `DeliveredApiError`. 재시도 없음. 장바구니에는 아무것도 붙지 않는다.

**보내지 않는 경우**: 게스트(`SignInRequired`), 옵션 상품(`KeyError` — RBD-8278), 지원하지 않는 마켓(`CartRejected`).

## delivered-customer-api · 번개장터 / DK샵 구매요청 생성

- **호출**: `POST /v2/buy-request/bunjang` · `POST /v2/buy-request/shop`
- **트리거**: 상품 마켓이 `BUNJANG` / `DK_SHOP`일 때. 동기.
- **계약 근거**: 고객 프론트 `buyRequestApiDto.ts:1-30`(`BunjangBuyRequestRequestT`, `DkshopBuyRequestRequestT`), `fetchBuyRequest.ts:14-40`(번개장터 응답은 원시 number, DK샵은 `{data: number}`), `bid_confirm_type: 'ACCEPTED_ALL' | 'REJECTED'` — ✅ 번개장터 실측(2026-09-14, 스테이징): 위 본문으로 200, 응답은 원시 number `587490`; 검색 결과에 `productUrl`이 없어 `https://m.bunjang.co.kr/products/{pid}` 폴백을 썼고 서버가 받아들임. DK샵은 ⚠️ 미확인(스테이징 검색에 DK샵 상품 없음)

**보내는 것** (번개장터):

```json
{ "market_type": "BUNJANG", "market_sub_type": "BUNJANG", "product_url": "https://m.bunjang.co.kr/products/429925416", "pid": 429925416, "item_description": "상품명", "quantity": 1, "bid_confirm_type": "REJECTED", "item_image_urls": ["…"], "bunjang_image_urls": [], "additional_information": "" }
```

**보내는 것** (DK샵): `{ "product_url", "pid", "item_description", "quantity", "item_image_urls", "market_type": "SHOP", "market_sub_type": "DK_SHOP", "options": [] }`

**성공 응답**: 번개장터 `123456`(원시 number) · DK샵 `{ "data": 123456 }` — 세 형태를 한 파서(`buy_request_id_of(payload)`)가 처리한다.

**실패하면 우리는**: RPA와 동일(상위 전파, 재시도 없음).

## delivered-customer-api · 장바구니에 붙이기 / 삭제

- **호출**: `POST /v2/cart/add-carts?buyRequestIds=1,2&entryType=0` (본문 없음) · `DELETE /v2/cart?buyRequestIds=1,2`
- **트리거**: 구매요청 생성 직후 / `remove_from_cart`·`update_cart_item` 첫 단계. 동기.
- **계약 근거**: webuy-cat-service `CartController.kt:68-100`(`@RequestParam buyRequestIds: List<Long>`, `entryType` 기본 0), 오류 코드 `BusinessErrorCode` CART-001~005 — ✅ 실측(2026-09-14): `add-carts?buyRequestIds=587490&entryType=0` 200 `{result, data: null}`, `DELETE /v2/cart?buyRequestIds=587490` 200, 재삭제 400 `{code: "CART-001", result: false, message}`. **id는 `v3/cart` 항목의 `cart_id`**(행 `id`가 아님)

**성공 응답**: `{ "result": true, "data": … }` (data 값은 쓰지 않는다).

**실패하면 우리는**: `CART-004`(이미 담김) → 흡수 후 재조회 · `CART-005`(개수 초과) → `CartRejected(가득 참 문장)` + 고아 구매요청 id 로그 · `CART-001`(삭제 시 없음) → 흡수 · 그 외 4xx → `CartRejected(message)` · 5xx → `DeliveredApiError`.

## delivered-customer-api · 장바구니 조회

- **호출**: `GET /v3/cart` · `GET /v2/cart/{buyRequestId}`(항목의 `product_id` 복원 폴백)
- **트리거**: `get_cart`마다 `v3/cart` 1회(턴 전·게이트·checkout·화면). 상세는 인덱스 미스 항목당 1회, 결과 캐시.
- **계약 근거**: webuy-cat-service `CartController.kt:122-146`(`CartBundleListDto`), 고객 프론트 `cartApiDto.ts:52-116`(`OrderGroupT{market_sub_type, market_name, is_bundled, items: CartItemT[]}`, `CartItemT{id, quantity, product_title, product_url, thumbnail_image_url, prices[{fee_type, cost_krw, cost_usd}], total_price[], options[], is_expired, is_selling}`, `CartDetailDataT{product_id, market: {sub_type}}`) — ✅ v3 실측(2026-09-14): 항목 `{id: 658429, cart_id: 587490, quantity, product_title, product_url, thumbnail_image_url, total_price[{item_total_price, total_price}], prices[{fee_type: "UNIT_PRICE", cost_krw, cost_usd}], options[], is_expired, is_selling, market_info{type, sub_type, name, is_rpa}}`. `fee_type`은 `UNIT_PRICE`(프론트가 '개당 판매가'로 표시 — 단가). `GET /v2/cart/{id}`도 운영 실측(`data.product_id`, `market.sub_type`, `quantity`)

**성공 응답** (검증 대상 필드만):

```json
{ "result": true, "data": { "orders": [ { "market_sub_type": "BUNJANG", "market_name": "BUNJANG", "is_bundled": false, "items": [ { "id": 658429, "cart_id": 587490, "quantity": 1, "product_title": "…", "product_url": "…", "thumbnail_image_url": "…", "prices": [ { "fee_type": "UNIT_PRICE", "cost_krw": 350000, "cost_usd": 289.63 } ], "is_expired": false, "is_selling": true, "market_info": { "sub_type": "BUNJANG" } } ] } ] }, "message": null }
```

**실패하면 우리는**: 5xx/전송 → `DeliveredApiError`("일시 불가") · `Expired Token` → 기존 `TokenExpired` 경로 · 상세 조회 실패 → 그 항목은 `product_id = "{market_sub_type}:unknown-{id}"`로 실어 삭제만 가능하게 두고 로그.

## 수신 계약

없음 — delivered가 이 데모를 호출하지 않는다.
