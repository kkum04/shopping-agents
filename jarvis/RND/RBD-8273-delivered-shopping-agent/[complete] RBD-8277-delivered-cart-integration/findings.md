# Findings: delivered 장바구니 연동 — 구매요청 생성 + add-carts, 조회·삭제·수량 변경, 전 마켓

> Jira: RBD-8277 | Mission: ./mission.md | Blueprint: ./blueprint.md
>
> 📌 `/jarvis:develop` 실행 중 발견한 명세 갭/판단/편차/트레이드오프/미결 질문을 4개 카테고리로 누적합니다.
> 노트 ID: 설계 결정=D###, 편차=DV###, 트레이드오프=T###, 미결 질문=Q###.

## 미결 질문 ❓

### Q001 — 카탈로그(운영)와 고객 API(스테이징)의 환경 불일치 — 데모가 어느 환경을 봐야 하나

- **태스크**: T014
- **파일**: `examples/delivered/api/delivered_backend.py`, `examples/delivered/api/main.py`, `.env.example`
- **시각**: 2026-09-14 12:40
- **상태**: ✅ resolved

**해소**: 2026-09-14 사용자 — **전부 운영**. `DELIVERED_AUTH_URL`/`DELIVERED_CUSTOMER_API_URL` 기본값을 `https://gw.delivered.co.kr`로 바꿨다(`.env.example`, README 동반). 스테이징을 쓰려면 세 변수를 함께 지정한다.

**맥락**: 데모의 상품 검색은 운영 게스트 게이트웨이(`DELIVERED_API_URL` 기본 `gw.delivered.co.kr`), 로그인·장바구니는 스테이징(`gw-staging`)이다. 실측에서 운영 상품 ID로 만든 구매요청을 스테이징 고객 API가 "요청한 상품을 찾을 수 없습니다"(ERR-404-002)로 거절했다. 같은 환경의 상품(스테이징 검색 결과)으로는 번개장터 담기가 전 구간 성공했다.

**임시 판단**: 코드는 환경을 가리지 않고 `DELIVERED_API_URL`을 그대로 쓴다. README에 "카탈로그와 고객 API는 같은 환경을 가리켜야 한다"고 적었다. 기본값은 바꾸지 않았다(운영 카탈로그 + 스테이징 계정).

**답 필요**: 데모를 (a) 전부 스테이징(`DELIVERED_API_URL=https://gw-staging.delivered.co.kr/dk-delivered/api/guests/v1`)으로 맞출지, (b) 운영 카탈로그를 유지하고 로그인·장바구니도 운영 계정으로 갈지(실제 구매요청이 생긴다), (c) 지금처럼 두고 장바구니 데모 때만 환경변수로 바꿀지.

**여파**: mission Out of Scope/NFR 호환성 절과 `.env.example` 기본값, README Run 절.

---

### Q002 — RPA 마켓(스마트스토어 등 13종) 구매요청 경로를 실측하지 못했다

- **태스크**: T014
- **파일**: `examples/delivered/api/delivered_cart.py`(`buy_request_body` rpa 분기)
- **시각**: 2026-09-14 12:40
- **상태**: ✅ resolved

**해소**: 2026-09-14 사용자 — **운영 계정으로 실측**. 같은 계정으로 운영 로그인 후 스마트스토어 상품(수량 2)을 담아 전 구간 확인: `market_type`은 `OTHER`가 아니라 **`SHOP`**(400 `MARKET-003`로 드러남) → 코드를 카탈로그 `marketType`(기본 SHOP)으로 고침. 응답 `{result, data: id}`, `CART-004`, `cart_id`, `UNIT_PRICE` 단가, 상세 경로까지 확인하고 항목은 삭제했다.

**맥락**: 스테이징 `POST /v1/buy-request/rpa-store`가 운영·스테이징 상품 ID 모두에 500 `SYS-001`("서버에 문제가 발생하였습니다") 또는 504를 돌려줬다(2026-09-14 12:3x). 요청 본문은 서버 DTO + Jackson SNAKE_CASE로 맞췄고, 400이 아니라 500이라 본문 형식 문제보다 스테이징 RPA 처리 쪽 장애로 보인다. 번개장터 경로는 같은 시각에 정상이었다.

**임시 판단**: 코드 근거(DTO·프론트 요청)대로 구현하고 `verified: false`로 남겼다. 가짜 게이트웨이 테스트는 `{result, data: id}` 응답을 가정한다.

**답 필요**: (a) 스테이징 RPA가 복구된 뒤 다시 실측하고 그때까지 미확인으로 두는가, (b) 운영 계정으로 스마트스토어 상품을 실제 담아 확인해도 되는가(실제 구매요청이 생긴다), (c) 코드 근거로 충분하다고 보고 넘어가는가.

**여파**: blueprint-integration rpa-store 절 `verified`, tasks T014.

---

## 편차 ⚠️

### DV001 — 로그인·고객 API 기본값이 스테이징이 아니라 운영

- **태스크**: T014
- **파일**: `examples/delivered/api/delivered_auth.py`, `.env.example`, `examples/delivered/README.md`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**명세**: blueprint-integration 헤더 "기본 `https://gw-staging.delivered.co.kr/dk-delivered/api/customer`", mission Q2 "스테이징 계정으로 검증".

**실제**: auth·customer 기본이 운영 `https://gw.delivered.co.kr`; 스테이징은 세 변수를 함께 지정.

**판단**: Q001 해소(사용자 "전부 운영") — 카탈로그(운영)와 고객 API가 같은 환경이어야 구매요청이 상품을 안다.

**여파**: blueprint-integration 헤더 기본 URL 문장, mission Q2 전제 문구, RBD-8275 문서의 스테이징 기본 언급.

---

### DV002 — 단가는 `UNIT_PRICE cost_krw`를 나누지 않고 그대로 쓴다

- **태스크**: T003/T014
- **파일**: `examples/delivered/api/delivered_cart.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**명세**: mission 데이터 요구사항 "price = ITEM_PRICE cost_krw / quantity", blueprint "ITEM_PRICE cost_krw / quantity(라인 합계로 가정)".

**실제**: fee_type은 `UNIT_PRICE`(서버 FeeType enum)이고 값은 단가 — 운영 실측(수량 2, cost_krw 23,500, USD 합계 37.4)으로 확인. 나누지 않는다.

**판단**: 실측이 명세 가정을 뒤집었다. blueprint-integration만 갱신됐고 mission·blueprint 본문은 옛 문장.

**여파**: mission 데이터 요구사항, blueprint Architecture/Module Design v3 매핑 문장.

---

### DV003 — cart_extras 항목에 `product_url` 키 추가

- **태스크**: T008/T012
- **파일**: `examples/delivered/api/delivered_cart.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**명세**: mission cart_extras items `{buy_request_id, product_id, fees, is_expired, is_selling}`.

**실제**: `product_url`도 싣는다 — 웹에서 담긴 라인의 수량 변경 시 `_line_product`가 재생성 본문에 쓴다.

**판단**: AC8(웹 담김 라인 수량 변경)에 필요한 최소 추가.

**여파**: mission 데이터 요구사항 cart_extras 스키마, blueprint v3 매핑.

---

### DV004 — 판매 종료 전용 문장 대신 delivered 메시지를 그대로 relay

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_cart.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**명세**: blueprint Module Design ERROR_MESSAGES에 "판매 종료 '판매가 끝난 상품입니다'".

**실제**: 전용 문장 없음 — 구매요청 4xx는 `구매요청을 만들지 못했습니다: {delivered message}`(blueprint Error Handling 표와 일치). CART-002/CART-004 문장은 추가.

**판단**: delivered가 사유를 이미 문장으로 주므로 그대로 전하는 편이 정확하다.

**여파**: blueprint Module Design ERROR_MESSAGES 항목 정리.

---

### DV005 — 수량 변경·기존 라인 재담기는 4회가 아니라 5회 호출

- **태스크**: T006/T012
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**명세**: mission NFR 성능 "한 담기에 최대 3회 호출 … 수량 변경은 4회"; blueprint 흐름도에 선행 GET 없음.

**실제**: `update_cart_item`·기존 라인 재담기는 `GET v3/cart → DELETE → POST 구매요청 → POST add-carts → GET v3/cart`(5회) — CartIndex에 수량이 없어 먼저 읽는다.

**판단**: 신선한 인덱스·수량을 위한 선행 읽기. 명세의 흐름도는 그 읽기를 빠뜨렸다.

**여파**: mission NFR 성능 문장, blueprint 흐름도·update 절.

---

### DV006 — 재생성 실패 경고 로그가 delivered 응답 문장을 담았음 (정정됨)

- **태스크**: T012
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**명세**: mission NFR 보안 "로그에 토큰·본문을 남기지 않는다(메서드·경로·상태만)".

**실제**: `_recreate` 경고가 `str(error)`(delivered 4xx `message` 포함)를 남겼다 → 예외 타입명만 남기도록 정정. `CartRejected` 문장 자체는 손님 안내용이라 응답 `message`를 포함한다(토큰·요청 본문 없음).

**판단**: 로그는 정정. 손님 안내 문장에 응답 message를 쓰는 것은 AC6의 의도.

**여파**: mission NFR 보안에 "응답 message는 손님 안내에 쓸 수 있다" 한 줄.

---

## 설계 결정 📘

### D001 — `customer_request` 반환을 dict에서 임의 JSON 값으로 넓힘

- **태스크**: T006
- **파일**: `examples/delivered/api/delivered_auth.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**맥락**: 번개장터 구매요청 응답은 원시 number(`587490`)라 dict만 받던 파서가 예외를 냈다.

**판단**: `_json_value`/`_NOT_JSON`을 두고 반환형을 `Any`로; Expired Token 검사는 dict일 때만.

**근거**: blueprint·integration이 원시 number 응답을 요구; `DeliveredApiError` 시그니처는 그대로.

**여파**: blueprint 「오류 정보 확보」 절에 반환형 한 줄.

---

### D002 — 웹에서 담긴 라인은 Cart 라인 + extras `product_url`로 ProductDetails를 합성

- **태스크**: T012
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**맥락**: AC8 라인은 세션 카탈로그에 없어 재생성 본문의 title·image·url 출처가 없었다.

**판단**: `_line_product`가 Cart 라인과 extras로 합성; RPA `market_type`은 기본 SHOP.

**근거**: blueprint는 `_create_buy_request(product…)`만 적고 출처를 비워 두었다.

**여파**: blueprint update 절 보강.

---

### D003 — 미지원 마켓은 delivered 호출 전에 거절

- **태스크**: T006
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**맥락**: 명세는 거절 시점을 정하지 않았다.

**판단**: `buy_request_body`를 먼저 불러 `CartRejected`를 어떤 호출보다 앞에 낸다.

**근거**: tasks T005 "미지원 마켓 → 호출 0회".

**여파**: -

---

### D004 — 인덱스 미스 삭제는 장바구니를 읽어 채운 뒤 다시 찾는다

- **태스크**: T010
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**맥락**: blueprint는 "라인이 없으면 그대로 get_cart"만 적었다.

**판단**: `get_cart`로 인덱스를 채운 뒤 있으면 DELETE — 웹에서 담긴 라인도 지운다.

**근거**: AC8의 "수량 변경·삭제가 게이트를 통과".

**여파**: blueprint remove 절 한 줄.

---

## 트레이드오프 🔀

### T001 — 재생성 실패는 사유별 relay 대신 일괄 "다시 담아 주세요"

- **태스크**: T012
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**옵션 A**: CART-005 등 구체 사유를 그대로 relay(5xx는 DeliveredApiError).

**옵션 B**: 삭제는 이미 됐으므로 사유와 무관하게 "다시 담아 주세요" 한 문장.

**선택**: B — 손님이 할 일은 같고, 원인은 로그에 남는다.

**여파**: -

---

### T002 — 턴 단위 캐시 대신 호출마다 `v3/cart` 재조회

- **태스크**: T008
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 13:05
- **상태**: ✅ resolved

**옵션 A**: 턴 단위 캐시로 게이트웨이 왕복 절감.

**옵션 B**: 매 호출 재조회 — 로컬 상태를 신뢰하지 않는다.

**선택**: B — mission NFR·integration 절이 이미 지정. 게이트웨이 지연(~10초 관측)에는 노출된다.

**여파**: -

---
