---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: blueprint
completed: [mission, blueprint]
plan: [tasks, develop]
skip: []
depth: standard
base_sha: 432c401
gates:
  open_q: 0
risk:
  self: 0.2                     # cross_domain 2(storefront-web + api 소폭) 0.2 · 신규 API·DB·연동 없음 → < 0.4(standard) 생략
  review: skipped
design:
  new_api: false                # 새 HTTP 경로 없음 — checkout_handoff는 프레임워크 훅, extras는 기존 페이로드 키 확장
  db_migration: false
  cross_domain: 2               # examples/delivered/storefront-web(주) + examples/delivered/api(extras 필드 2개·handoff 1개)
  tx_boundary: false            # 새 아웃바운드 호출 없음 (v3/cart는 RBD-8277이 이미 연동)
  files_touched: 14
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [장바구니, cart, CartPanel, cart_extras, delivered_cart, 마켓, 수수료, 만료, 체크아웃 핸드오프]
  modules:
    - examples/delivered/storefront-web/lib/types.ts
    - examples/delivered/storefront-web/lib/buildCartView.ts
    - examples/delivered/storefront-web/components/CartLine.tsx
    - examples/delivered/storefront-web/components/CartPanel.tsx
    - examples/delivered/storefront-web/components/generative/CheckoutSummary.tsx
    - examples/delivered/storefront-web/lib/showcase-fixtures.ts
    - examples/delivered/api/delivered_cart.py
    - examples/delivered/api/delivered_backend.py
    - examples/delivered/README.md
coverage:
  - ac: AC1
    modules: [lib/buildCartView.ts, components/CartPanel.tsx, lib/types.ts]
  - ac: AC2
    modules: [api/delivered_cart.py(cart_from_v3 options), components/CartLine.tsx]
  - ac: AC3
    modules: [lib/buildCartView.ts(lineStatus·activeTotals), components/CartLine.tsx, components/CartPanel.tsx]
  - ac: AC4
    modules: [lib/buildCartView.ts(feeLabel·feeRows), components/CartLine.tsx]
  - ac: AC5
    modules: [api/delivered_cart.py(line_total_of), lib/buildCartView.ts(activeTotals), components/CartPanel.tsx]
  - ac: AC6
    modules: [components/CartPanel.tsx(pending), components/CartLine.tsx]
  - ac: AC7
    modules: [api/delivered_backend.py(checkout_handoff), components/generative/CheckoutSummary.tsx, components/CartPanel.tsx(footer)]
  - ac: AC8
    modules: [lib/showcase-fixtures.ts, components/*.test.tsx, lib/buildCartView.test.ts, examples/delivered/storefront-web (next build)]
---

# Blueprint: 장바구니 화면 — delivered 장바구니 항목·수수료·마켓 표시

> Mission: ./mission.md | Jira: RBD-8279

## Tech Stack

- **Language**: TypeScript 5.6 (strict), React 19 · Python 3.11 (extras 필드·핸드오프 훅만)
- **Framework**: Next.js 16 app router(`"use client"`), Tailwind CSS 4 + 앱 토큰(`--ink`, `--ink-soft`, `--line`, `--well`, `--danger`), `globals.css`의 `.chip`/`.btn-primary`
- **공용 패키지**: `web-shared`(file 의존) — `BagPanel`, `TotalRow`, `Stepper`, `RemoveLink`, `CheckoutButton`, `AskLink`, `Pill`, `formatMoney`, `optionValuesLabel`, `useCatalogIndex`, `useStoreFrame`/`FrameContext`, `safeHandoffs`. **수정하지 않는다**(다른 예제와 공유).
- **상태**: 로컬 `useState`/`useEffect`. React Query 없음(레포 패턴이 공통 컨벤션 4.2보다 우선).
- **테스트**: vitest 5 + RTL + user-event(jsdom, `vitest.setup.ts`에 `afterEach(cleanup)`) · pytest(백엔드 L1)
- **타입 이름**: 레포 기존 타입(`CartPayload`, `CartItem`)이 접미사 없이 쓰이므로 새 타입도 그 패턴을 따른다(공통 컨벤션 2.3의 `T` 접미사보다 프로젝트 관례 우선).

## Architecture Overview

데이터는 RBD-8277이 이미 흘려보낸다: 백엔드 `get_cart` → `cart_from_v3` → 프레임워크 `Cart`(항목·단가·수량) + extras `delivered_cart.groups` → 호스트가 `/api/cart` 응답과 `cart_update` 이벤트 양쪽에 `serialize_cart(cart) | extras`로 싣는다. 이 티켓은 (1) extras에 화면이 필요로 하는 두 값(항목 합계 `line_total`, 옵션 `options`)을 더하고, (2) 스토어프론트가 `cart.items`와 `delivered_cart.groups`를 **product_id로 합쳐** 마켓별 그룹 뷰 모델을 만든 뒤 그리며, (3) 프레임워크의 `checkout_handoff` 훅을 delivered 백엔드가 구현해 체크아웃 카드에 delivered 웹 장바구니 링크를 싣는다(`enrich_checkout`이 `handoffs`로 붙이고 카드가 `safeHandoffs`로 검사).

```text
delivered API (:8004)
  cart_from_v3 ──► Cart{items[product_id,title,price,qty,image]}
              └──► extras.delivered_cart.groups[{market_name, is_bundled,
                     items[{buy_request_id, product_id, product_url, fees[], line_total, options[], is_expired, is_selling}]}]
  checkout_handoff ──► [CheckoutHandoff(url=delivered 웹 장바구니)]  (enrich_checkout → payload.handoffs)

storefront-web
  page.tsx ── cart(CartPayload, delivered_cart 포함) ──► CartPanel
                                                         ├─ buildCartView(cart) → groups[{market, lines[{item, line, status}]}], activeTotals
                                                         ├─ <section> per group ── CartLine × n (pending, Stepper, Remove, fees, badge)
                                                         └─ footer: TotalRow(active subtotal) · CheckoutButton · note
  ui event "checkout" ──► CheckoutSummary(payload.cart + payload.handoffs) — 마켓 라벨·요금·delivered 이동 버튼
```

쓰기 경로는 그대로다(Q1): Stepper/Remove는 `ask("Change … quantity to N.")`를 보내고, 패널은 **누른 줄의 product_id를 pending으로 기억**했다가 다음 `cart` prop 변경 또는 `chat.busy`가 false가 되는 시점에 푼다.

## Directory Structure

```text
examples/delivered/storefront-web/
├── lib/types.ts                          (수정) DeliveredCartFee · DeliveredCartOption · DeliveredCartLine · DeliveredCartGroup, CartPayload.delivered_cart?
├── lib/buildCartView.ts                  (신규) 순수 뷰 모델: buildCartView · lineStatus · feeLabel · feeRows · activeTotals
├── lib/buildCartView.test.ts             (신규) L1 — 그룹 결합·상태·요금·활성 합계
├── components/CartLine.tsx               (신규) 항목 한 줄(옵션·마켓·배지·요금·합계·Stepper·Remove·pending·원본 링크)
├── components/CartPanel.tsx              (수정) 그룹 렌더링·pending 상태·활성 소계·푸터 문구
├── components/CartPanel.test.tsx         (신규) 그룹/배지/요금/소계/pending
├── components/generative/CheckoutSummary.tsx (수정) 마켓 라벨·요금 줄·delivered 이동 버튼·문구
├── components/generative/CheckoutSummary.test.tsx (신규) 핸드오프 링크·합계
└── lib/showcase-fixtures.ts              (수정) SHOWCASE_CART·checkout 픽스처를 delivered 형태(KRW, 그룹 2, 요금, 만료, 옵션, handoffs)로
examples/delivered/api/
├── delivered_cart.py                     (수정) line_total_of · option_rows_of, cart_from_v3 extras에 line_total · options
├── delivered_backend.py                  (수정) DELIVERED_CART_URL 상수(env DELIVERED_WEB_CART_URL) · checkout_handoff
├── tests/test_delivered_cart.py          (수정) line_total_of 3경로 · options 매핑
└── tests/test_delivered_backend.py       (수정) checkout_handoff: 회원 → delivered URL 1건, 게스트 → []
examples/delivered/README.md              (수정) Cart 절에 화면 필드·핸드오프 두 문장
```

## Module Design

### api/delivered_cart.py — extras 두 필드

- **책임**: v3 항목에서 화면이 쓰는 값을 확정해 extras 줄에 싣는다. FE가 요금 배열을 다시 해석하지 않게 **원화 정수 합계**를 백엔드가 낸다.
- **위치**: `examples/delivered/api/delivered_cart.py`
- **의존성**: 없음(순수 함수)
- **주요 로직**:
  - `line_total_of(item) -> float`: ① `item["total_price"]`가 리스트면 `fee_type == "TOTAL"` 행의 `cost_krw`(2026-09-14 실측 픽스처 형태) → ② dict면 `total_price`(고객 프론트 `TotalPriceT` 형태) → ③ 둘 다 없으면 `unit_price_of(item) × quantity + UNIT_PRICE가 아닌 prices[].cost_krw 합`. `cost_krw`가 None이면 0.
  - `option_rows_of(item) -> list[dict]`: v3 `options[]` → `[{"name": option_key_locale.product_option_group_name or key, "value": value}]`, `PRI_ORDER`/`PRE_ORDER` 타입은 제외(고객 프론트 `filterOptions` 관례).
  - `cart_from_v3`의 group item에 `"line_total": line_total_of(item)`, `"options": option_rows_of(item)` 추가. 기존 키는 그대로(`fees`는 유지 — 요금 줄 표시에 쓴다).

### api/delivered_backend.py — checkout_handoff

- **책임**: 체크아웃 카드가 이어질 delivered 웹 장바구니 URL을 프레임워크 훅으로 공급한다. URL은 모델에 절대 노출되지 않는다(`enrich_checkout`이 카드 페이로드에만 붙임).
- **위치**: `examples/delivered/api/delivered_backend.py`
- **의존성**: `CheckoutHandoff`(shopping_agent.types), `credential_of`
- **주요 로직**: `DELIVERED_CART_URL = os.environ.get("DELIVERED_WEB_CART_URL") or "https://www.delivered.co.kr/cart"` (고객 프론트 라우트 `app/[locale]/cart`, `localePrefix: "always"` — locale 없는 경로는 미들웨어가 방문자 언어로 리다이렉트하므로 서버는 locale을 고르지 않는다; develop에서 리다이렉트를 한 번 확인). `async def checkout_handoff(session, cart)`: 게스트면 `[]`(카드는 기존 비활성 버튼), 회원이면 `[CheckoutHandoff(url=DELIVERED_CART_URL, label="Continue on delivered")]`. 카트가 비면 `enrich_checkout`이 먼저 거절하므로 여기서 다시 검사하지 않는다.

### lib/types.ts — delivered 확장 타입

- **책임**: 페이로드 확장을 선택 필드로 선언해 리테일 공용 모양을 깨지 않는다.
- **주요 로직**: `DeliveredCartFee {fee_type: string; cost_krw: number | null; cost_usd: number}`, `DeliveredCartOption {name: string; value: string}`, `DeliveredCartLine {buy_request_id: number; product_id: string; product_url?: string | null; fees: DeliveredCartFee[]; line_total: number; options: DeliveredCartOption[]; is_expired: boolean; is_selling: boolean}`, `DeliveredCartGroup {market_sub_type: string | null; market_name: string | null; is_bundled: boolean; items: DeliveredCartLine[]}`, `CartPayload.delivered_cart?: {groups: DeliveredCartGroup[]}`.

### lib/buildCartView.ts — 순수 뷰 모델 (테스트의 중심)

- **책임**: `CartPayload` 하나를 화면이 그리기 좋은 구조로 바꾼다. 컴포넌트에는 조건 로직을 남기지 않는다.
- **위치**: `examples/delivered/storefront-web/lib/buildCartView.ts` (유틸 파일 — 주석 허용)
- **주요 로직**:
  - `lineStatus(line?: DeliveredCartLine): "expired" | "sold_out" | null` — `is_expired` 우선, 그다음 `!is_selling`.
  - `feeLabel(feeType)`: `UNIT_PRICE → "Item price"`, `DOMESTIC_SHIPPING_PRICE → "Domestic shipping"`, `HANDLING_FEE → "Handling fee"`, 그 외는 `Title Case` 변환.
  - `feeRows(item, line)`: `[{label: "Item price", amount: item.price × item.quantity}, …UNIT_PRICE가 아닌 fees의 {label: feeLabel, amount: cost_krw ?? 0}]` — 요금이 없으면 한 줄(상품가)만.
  - `buildCartView(cart)`: `delivered_cart.groups`가 있으면 그룹 순서대로 `{key, marketName, isBundled, lines: [{item, line, status, total: line.line_total}]}`(item은 `cart.items`에서 product_id로 찾음; 못 찾으면 그 줄은 건너뛰고 경고 없이 무시). 그룹에 없는 `cart.items`(게스트·리테일 픽스처처럼 `delivered_cart`가 없을 때 포함)는 `marketName: null`인 기본 그룹 하나로. 줄의 `total`은 `line?.line_total ?? item.line_total`.
  - `activeTotals(view)`: `status === null`인 줄만 세어 `{count, subtotal}`.

### components/CartLine.tsx — 항목 한 줄

- **책임**: 한 줄의 표시와 액션. `CartPanel`이 넘긴 값만 그린다(내부 상태 없음).
- **의존성**: `ProductImage`/`ProductTitle`/`DeliveryPromise`(ProductTile), `Stepper`/`RemoveLink`(web-shared), `Pill`(web-shared `ui` — 배지), `formatMoney`
- **주요 로직**: props `{ line: CartLineView; currency: string; pending: boolean; onQuantityChange(quantity); onRemove() }`.
  - 제목 → 옵션 한 줄(`line.options`가 있으면 `name: value`를 `·`로 이어 붙이고, 없으면 기존 `optionValuesLabel(item)`) → 마켓명(그룹 머리와 중복이지만 AC1 "각 항목에 마켓명") → 상태 배지(`Pill tone="warn"` "Expired" / "Sold out").
  - 요금: `feeRows` 결과를 `dl`로 (라벨 / `formatMoney(amount, currency, {whole: true})`), 마지막 줄 합계 `formatMoney(total)` 굵게.
  - 액션: 상태가 null이면 `Stepper` + `RemoveLink`, 아니면 `RemoveLink`만. `pending`이면 줄 컨테이너 `aria-busy` + `opacity-60`, 버튼은 `disabled`(Stepper/RemoveLink는 `chat.busy`로도 비활성되므로 pending 동안 `fieldset disabled`로 감싼다), 오른쪽에 "Updating…" 텍스트.
  - `product_url`이 있으면 "View on {marketName}" 외부 링크(`target="_blank" rel="noopener noreferrer"`).
  - 핸들러는 `useCallback`으로 본문에 선언(공통 컨벤션 3.5).

### components/CartPanel.tsx — 그룹과 pending

- **책임**: 뷰 모델을 그룹별 `section`으로 그리고 pending 상태를 소유한다.
- **주요 로직**:
  1. `const view = useMemo(() => buildCartView(cart), [cart])`, `const totals = activeTotals(view)`.
  2. `pendingId` 로컬 상태: `handleQuantityChange(productId, quantity)`가 `setPendingId(productId)` 후 `ask(...)`; `handleRemove(productId)` 동일. `useEffect([cart])`에서 `setPendingId(null)`; `useEffect([chat?.busy])`에서 `busy === false`이면 `setPendingId(null)`(장바구니 갱신 없이 끝난 턴).
  3. 그룹 머리: `<h3>` 마켓명(없으면 "Cart"), 항목 수, `is_bundled`면 `Pill` "Bundled shipping".
  4. 푸터: `TotalRow(label="Subtotal · N items", value=formatMoney(totals.subtotal, currency, {whole: true}), note="Fees and payment are settled on delivered")`, `CheckoutButton(disabled = totals.count === 0)`, `AskLink` 유지.
  5. `BagPanel count`는 `plural(totals.count, "item")` — 만료 줄은 세지 않는다(AC3).
  6. `key`는 `product_id`(고유).

### components/generative/CheckoutSummary.tsx — delivered 이동

- **책임**: 카드가 delivered 장바구니 요약과 이동 버튼을 보여준다.
- **주요 로직**: `buildCartView(payload.cart)`로 같은 뷰 모델을 쓴다. 항목 줄에 마켓명 소문자 라벨, 만료 줄은 흐리게 + "Expired". 기존 "Shipping international / Tax" 두 줄을 **"Domestic shipping & fees — included above · International shipping quoted on delivered"** 한 줄로 바꾸고, "Estimated total"은 `activeTotals.subtotal`. 핸드오프 버튼은 기존 `safeHandoffs` 경로 그대로 — 라벨 기본값을 "Continue on delivered"로, 안내 문구를 "Payment happens on delivered."로. 핸드오프가 없으면(게스트) 기존 비활성 버튼 유지.

### lib/showcase-fixtures.ts — delivered 형태 픽스처

- **주요 로직**: `SHOWCASE_CART`를 KRW로: 스마트스토어 그룹(옵션 항목 1 + 국내 배송비 항목 1) + 번개장터 그룹(만료 항목 1, `is_selling false`), 각 `delivered_cart.groups` 줄에 `fees`·`line_total`·`options`. `checkout` 픽스처도 같은 카트 + `handoffs: [{url: "https://www.delivered.co.kr/cart", label: "Continue on delivered"}]`. `products` 픽스처의 id·이미지 경로와 맞춘다(리테일 `AR-…` id 대신 `smart_store:…`/`bunjang:…` — 이미지 없으면 `ProductImage` 폴백).

## Error Handling

- `delivered_cart`가 없는 페이로드(게스트, 리테일 픽스처, 구버전 API) → 기본 그룹 하나로 현행과 같은 화면. 타입은 전부 선택 필드.
- 그룹 줄이 `cart.items`에 없는 product_id를 가리키면(백엔드 캐시 불일치) 그 줄은 건너뛴다 — 화면이 깨지지 않게 하고, 다음 `cart_update`에서 정리된다.
- `cost_krw`가 `null`인 요금 → 0으로 표시하지 않고 그 요금 줄을 생략(원화 없는 요금은 delivered가 결제에서 정산).
- pending이 풀리지 않는 경우(스트림 끊김) → `chat.busy`가 false로 떨어지면 해제; `busy`를 못 받는 `/showcase`(FrameContext 기본값 `chat: null`)는 pending을 만들지 않는다(`ask`가 no-op).
- `checkout_handoff` URL이 http이거나 잘못되면 `safeHandoffs`가 걸러 비활성 버튼으로 남는다 — 백엔드 테스트가 https를 보장.

## Migration / Side Effects

- DB·마이그레이션 없음. `web-shared` 변경 없음.
- `cart_from_v3` extras 키 추가는 덧붙이기만 — RBD-8277 테스트의 기존 단언(`fees`, `is_expired`…)은 그대로 통과해야 한다.
- `total_price`의 실제 형태는 8277 픽스처(`[{fee_type: "TOTAL", cost_krw}]`)와 고객 프론트 타입(`{item_total_price, total_price}`)이 다르다 — `line_total_of`가 셋을 모두 받고, develop에서 운영 `GET /v3/cart` 한 번으로 실제 형태를 확인해 픽스처를 맞춘다(읽기 전용).
- delivered 웹 장바구니 URL은 locale 없이(`/cart`) 두고 사이트 리다이렉트에 맡긴다 — develop에서 `curl -I`로 302를 확인하고, `DELIVERED_WEB_CART_URL` env로 덮어쓸 수 있게 둔다.
- 컴포넌트 테스트에서 `ask`·`chat.busy`가 필요한 케이스는 `web-shared/storefront/frame`의 `FrameContext.Provider`로 감싼다(`web-shared`는 `main: index.ts`뿐이라 깊은 경로 import가 열려 있다; vitest는 `web-shared`를 inline). `@/lib/api`의 `fetchProducts`는 `vi.mock`으로 빈 카탈로그를 돌려준다(외부 API 모킹).
- `scripts/smoke_chat.py`·`verify_all.py` 영향 없음(빌드만). `next build`에서 미사용 import(`DeliveryPromise` 등) 정리.
