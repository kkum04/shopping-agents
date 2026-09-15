# Findings: 장바구니 화면 — delivered 장바구니 항목·수수료·마켓 표시

> Jira: RBD-8279 | Mission: ./mission.md | Blueprint: ./blueprint.md
>
> 📌 `/jarvis:develop` 실행 중 발견한 명세 갭/판단/편차/트레이드오프/미결 질문을 4개 카테고리로 누적합니다.
> 노트 ID: 설계 결정=D###, 편차=DV###, 트레이드오프=T###, 미결 질문=Q###.

## 미결 질문 ❓

(없음)

## 편차 ⚠️

### DV001 — 대화 없는 프레임(/showcase)에서 pending이 풀리지 않음 → develop에서 수정

- **태스크**: T009
- **파일**: `examples/delivered/storefront-web/components/CartPanel.tsx`
- **시각**: 2026-09-15 13:26
- **상태**: ✅ resolved (코드 수정)

**명세**: blueprint Error Handling: "`busy`를 못 받는 `/showcase`(FrameContext 기본값 `chat: null`)는 pending을 만들지 않는다(`ask`가 no-op)"

**실제**: 처음 구현은 `chat` 유무와 무관하게 `setPendingId`를 호출해, `/showcase`에서 누른 줄이 페이지가 살아 있는 동안 진행 중으로 남았다.

**판단**: 격리 평가 직후 `if (chat) setPendingId(...)`로 고치고 기본 컨텍스트 클릭 테스트를 추가했다.

**여파**: -

---
### DV002 — 패널 체크아웃 버튼 문구·동작은 그대로(어시스턴트 메시지)

- **태스크**: T011
- **파일**: `examples/delivered/storefront-web/components/CartPanel.tsx`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**명세**: mission AC7 "패널의 체크아웃 버튼 문구도 같은 뜻으로 바뀐다", 인터랙션 "체크아웃 버튼(패널)과 카드 버튼 → delivered 웹 장바구니 URL 새 창"

**실제**: web-shared `CheckoutButton`(라벨 "Check out" 고정, 수정 금지)을 그대로 두고 delivered 안내는 `TotalRow`의 note로 붙였다. 패널은 핸드오프 URL을 받지 않는다(URL은 체크아웃 카드 페이로드에만 실린다).

**판단**: 프레임워크 설계(체크아웃은 어시스턴트가 카드를 띄우고, 카드가 URL을 연다)를 따르는 편이 맞다고 봤다. 패널 버튼 → 카드 → delivered 링크 두 단계.

**여파**: mission.md AC7·인터랙션 문구를 "패널 버튼은 체크아웃 카드를 띄우고, 카드가 delivered로 잇는다"로 정정 후보

---
### DV003 — 모르는 요금 이름을 Title Case로 표시

- **태스크**: T005
- **파일**: `examples/delivered/storefront-web/lib/buildCartView.ts`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**명세**: mission 데이터 요구사항 "그 외 이름은 그대로 표시" vs blueprint Module Design "그 외는 Title Case 변환" — 명세 내부 충돌

**실제**: `SOME_NEW_FEE → Some New Fee`. 알려진 세 요금 표시는 양쪽과 일치.

**판단**: blueprint를 따랐다 — 원문 코드명(`SOME_NEW_FEE`)을 고객 화면에 그대로 내는 것보다 낫다.

**여파**: mission.md 데이터 요구사항 한 구절 정정

---
### DV004 — `CartLine` props가 blueprint 서술과 다름

- **태스크**: T007
- **파일**: `examples/delivered/storefront-web/components/CartLine.tsx`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**명세**: blueprint "props `{ line: CartLineView; currency; pending; onQuantityChange(quantity); onRemove() }`"

**실제**: `{ view, product, marketName, currency, pending, onQuantityChange(productId, quantity), onRemove(productId) }` — 패널이 `viewsById`와 공유 `useCallback` 두 개를 두고, 카탈로그 해석(`asProduct`)도 패널 쪽.

**판단**: 줄마다 클로저를 만들지 않으려고 핸들러에 productId를 태웠다. 책임(줄은 받은 값만 그린다)과 화면 결과는 같다.

**여파**: blueprint.md Module Design(CartLine) 시그니처 갱신

---

## 설계 결정 📘

### D001 — 체크아웃 카드의 Subtotal 줄 삭제, Estimated total 하나로

- **태스크**: T011
- **파일**: `examples/delivered/storefront-web/components/generative/CheckoutSummary.tsx`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**맥락**: mission 화면 구성은 "소계 → 요금 안내 → 이동 버튼", blueprint는 소계 줄 처리를 말하지 않음.

**판단**: 요금이 줄마다 포함되므로 소계와 추정 합계가 같은 값이라 하나만 남겼다.

**근거**: 같은 숫자 두 줄은 카드 높이만 늘린다.

**여파**: -

---
### D002 — 활성 개수는 활성 줄의 수량 합, 그룹 머리 개수는 줄 수

- **태스크**: T005 · T007
- **파일**: `examples/delivered/storefront-web/lib/buildCartView.ts`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**맥락**: 명세는 `{count, subtotal}`만 말하고 세는 기준을 정하지 않음.

**판단**: 패널 헤더/소계 라벨은 기존 `item_count` 의미(수량 합)를 유지하고, 그룹 머리는 줄 수(만료 포함)를 보인다.

**근거**: 기존 화면과 같은 숫자 의미 유지.

**여파**: mission.md 그룹 머리 "항목 수" 기준 명시 후보

---
### D003 — 셸 헤더 배지도 활성 개수·합계를 따르도록 변경 → develop에서 적용

- **태스크**: T014
- **파일**: `examples/delivered/storefront-web/app/page.tsx`
- **시각**: 2026-09-15 13:26
- **상태**: ✅ resolved (코드 수정)

**맥락**: AC3는 "패널의 개수·소계"만 말하고 blueprint 파일 목록에 `page.tsx`가 없음. 처음 구현은 헤더 배지가 4 items / ₩110,000(만료 포함), 패널이 3 items / ₩68,000이었다.

**판단**: 격리 평가 직후 `page.tsx`의 bag 배지를 `activeTotals(buildCartView(cart))`로 바꿔 두 숫자를 맞췄다(원화 정수 표기 포함).

**근거**: 같은 화면에서 개수가 다르면 만료 항목이 살아 있는 것처럼 보인다.

**여파**: blueprint.md Directory Structure에 `app/page.tsx` 추가

---
### D004 — delivered 정보가 없는 카트는 그룹 머리를 생략

- **태스크**: T007
- **파일**: `examples/delivered/storefront-web/components/CartPanel.tsx`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**맥락**: blueprint Module Design "h3 마켓명(없으면 'Cart')" vs Error Handling "현행과 같은 화면" 충돌.

**판단**: 머리 자체를 생략해 게스트·리테일 카트가 기존과 같은 목록으로 보인다.

**근거**: 패널 제목이 이미 "Cart"라 머리 "Cart"는 중복.

**여파**: blueprint.md Module Design 한 줄 정정

---
### D005 — `cost_krw` null 요금 줄 생략·빈 그룹 제거·product_id 그룹 간 중복 제거

- **태스크**: T005
- **파일**: `examples/delivered/storefront-web/lib/buildCartView.ts`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**맥락**: blueprint Module Design "amount: cost_krw ?? 0" vs Error Handling "null → 생략" 충돌; 빈 그룹·중복 id는 침묵.

**판단**: 생략을 택했고, 매칭 줄이 없는 그룹은 버리며 같은 product_id는 먼저 나온 그룹에만 둔다.

**근거**: 0원 요금 줄은 정보가 없고, 빈 머리는 화면을 어지럽힌다.

**여파**: blueprint.md Module Design 정리

---
### D006 — 옵션 행: 빈 value 제외, 이름 폴백 "Option"

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_cart.py`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**맥락**: 명세는 `{name: group_name or key, value}`만 명시.

**판단**: 값이 빈 행은 버리고, 그룹명·key 모두 없으면 "Option"으로 둔다.

**근거**: 빈 문자열 옵션은 화면에 `색상: `처럼 남는다.

**여파**: -

---
### D007 — 쇼케이스 카트 줄은 카탈로그 픽스처 없이 `ProductImage` 폴백

- **태스크**: T012
- **파일**: `examples/delivered/storefront-web/lib/showcase-fixtures.ts`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**맥락**: blueprint "products 픽스처의 id·이미지 경로와 맞춘다(… 이미지 없으면 폴백)"; 옵션·배송비를 한 항목에 얹고 둘째 항목은 요금 없음.

**판단**: 리테일 `products` 픽스처는 그대로 두고 delivered id로 카트만 바꿨다 — AC8 요소(그룹 2·요금·만료·옵션)와 AC4(요금 없는 항목)를 모두 한 카트로 덮는다.

**근거**: 리테일 상품 이미지를 delivered 상품에 붙이면 거짓 화면이 된다.

**여파**: -

---
### D008 — 페이로드 타입을 명세보다 느슨하게(`cost_usd?`, `buy_request_id: number | null`, `market_*?`)

- **태스크**: T001
- **파일**: `examples/delivered/storefront-web/lib/types.ts`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**맥락**: 명세는 `cost_usd: number`, `buy_request_id: number` 등 필수로 적음.

**판단**: 백엔드가 건너뛸 수 있는 값은 선택·null 허용으로 두어 구버전 페이로드에도 타입이 맞게 했다.

**근거**: NFR 호환성(선택 필드).

**여파**: -

---

## 트레이드오프 🔀

### T001 — 환경변수 URL: 임포트 시 상수 vs 호출 시 함수 → 함수

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**옵션 A**: blueprint대로 `DELIVERED_CART_URL = os.environ.get(...) or ...` 모듈 상수(임포트 시 고정)

**옵션 B**: `web_cart_url()`이 호출 때마다 env를 읽음

**선택**: B — T002의 `DELIVERED_WEB_CART_URL` 반영 테스트(`monkeypatch.setenv`)가 상수로는 통과하지 않고, 데모 프로세스도 재시작 없이 값을 바꿀 수 있다. 이름은 `DEFAULT_WEB_CART_URL` + `web_cart_url()`.

**여파**: blueprint.md Module Design 이름 정정

---
### T002 — 항목 합계: 목록의 TOTAL 행 우선 vs 단가×수량+요금 계산

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_cart.py`
- **시각**: 2026-09-15 13:26
- **상태**: 📌 역류 대기

**옵션 A**: 목록이 준 `TOTAL` 행(또는 `{total_price}` 객체)을 그대로 믿는다

**옵션 B**: 항상 단가×수량+요금으로 계산한다

**선택**: A(둘 다 없을 때만 B) — delivered가 정산한 값과 같아야 한다는 AC5 때문. 다만 운영 `v3/cart` 실측이 401로 막혀 실제 형태는 미확인이고, `V3_ITEM` 픽스처는 TOTAL 30,000 vs 계산 63,000으로 두 경로 값이 다르다.

**여파**: 다음 로그인 가능 시점에 `GET /v3/cart` 1회로 형태 확인 후 픽스처 정정

---
