# Blueprint — Integration: 옵션 상품 매핑

> Main: ./blueprint.md
> 게스트 옵션 API는 `DELIVERED_API_URL`(기본 운영 `…/dk-delivered/api/guests/v1`) 아래 `DeliveredClient`가, 구매요청·장바구니는 RBD-8277의 `customer_call` 경로가 부른다. 테스트는 `FakeGateway`/`FakeCustomerGateway`(MockTransport) + 녹화 픽스처.

## delivered-guest-api · 옵션 그룹 / 옵션 목록

- **호출**: `GET /buy-request/stores/smartstore/{pid}/option-groups` · `GET /buy-request/stores/smartstore/{pid}/options`
- **트리거**: 스마트스토어 상세 조회마다, 상세와 병렬 1회씩. 동기.
- **계약 근거**: 고객 프론트 `endPoints.ts:157-160`, `storeApiDto.ts:66-93` — ✅ 운영 실측 2026-09-14 (58개 상품; 그룹 타입 COMBINATION 56·COMBINATION+TEXT 2; SIMPLE 미관측)

**성공 응답** (검증 대상 필드만):

```json
{ "result": true, "data": [ { "productOptionGroupId": 18147, "productOptionGroupType": "COMBINATION", "productOptionGroupName": { "productOptionGroupName": "색상", "productOptionGroupNameEn": "Colors" } } ] }
```

```json
{ "result": true, "data": [ { "optionId": 137750, "productOptionName": [ { "productOptionGroupId": 18147, "productOptionName": "레드블랙", "productOptionNameEn": "Red Black" } ], "optionPriceKrw": 22200.0, "optionPriceUsd": 17.66, "stockQuantity": 99672 } ] }
```

- `optionPriceKrw`는 그 조합의 **전체 가격**(예: 18,900 / 26,000 / 31,000 — 상세의 대표가와 별개). 옵션 없는 상품은 `data: []`.

**실패하면 우리는**: 흡수 — 옵션 없는 상품으로 상세를 돌려주고 경고 로그.

## delivered-customer-api · 옵션을 실은 구매요청

- **호출**: `POST /v1/buy-request/rpa-store` 본문 `options: [optionId]`, `text_options: []` (나머지는 RBD-8277과 동일)
- **계약 근거**: webuy-cat-service `BuyRequestRPAStoreRequest.options: List<Long>`, 고객 프론트 `usePurchaseAction.ts`(선택한 optionId 목록) — ✅ 운영 실측 2026-09-14 — `options=[137751]`로 구매요청 1010074 생성 `{result:true, data:1010074}`, `add-carts` 후 `v3/cart` 응답의 해당 라인에 `options[]`(색상 / White)가 실려 옴을 확인(웹 화면은 열어 보지 않음), 삭제 완료

**실패하면 우리는**: RBD-8277과 동일(4xx → `CartRejected` relay).

**보내지 않는 경우**: family id(옵션 미선택) · TEXT 그룹 상품 · 품절 variant · 게스트.

## delivered-customer-api · 장바구니 라인의 옵션 (역매핑 입력)

- **호출**: `GET /v3/cart` 항목 `options[]` · `GET /v2/cart/{id}` `options[]`
- **계약 근거**: 고객 프론트 `cartApiDto.ts` `OptionT{type, key, value}` — ✅ 운영 실측 2026-09-14 — `v3/cart` 라인 `options[] = [{type:"Option", key:"Option", value:"White", option_key_locale:{product_option_group_id:18147, product_option_group_name:"색상"}}]`(값 영문, 그룹 id 동반), `v2/cart/{id}` `options[] = [{…, value:"화이트", option_key_locale:null}]`(값 한글). optionId는 없으므로 그룹 id + 한글/영문 값 대조로 variant를 찾는다(`variant_for_option_values`).

**실패하면 우리는**: 흡수 — family id로 싣고 경고.

## 수신 계약

없음.
