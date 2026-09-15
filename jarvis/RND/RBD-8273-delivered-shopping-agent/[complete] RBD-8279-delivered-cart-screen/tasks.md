---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: tasks
completed: [mission, blueprint, tasks, develop]
plan: []
skip: []
depth: standard
base_sha: 432c401
gates:
  open_q: 0
  findings_pending: 0
risk:
  self: 0.0                     # 커버리지 갭 0 · [P] 파일 충돌 0 · 태스크 14(<15) → 생략
  review: skipped
tests: included
task_count: 14
coverage:
  - ac: AC1
    tasks: [T001, T004, T005, T006, T007]
  - ac: AC2
    tasks: [T002, T003, T006, T007]
  - ac: AC3
    tasks: [T004, T005, T006, T007]
  - ac: AC4
    tasks: [T004, T005, T008]
  - ac: AC5
    tasks: [T002, T003, T004, T005, T008]
  - ac: AC6
    tasks: [T009]
  - ac: AC7
    tasks: [T002, T003, T010, T011]
  - ac: AC8
    tasks: [T012, T014]
uncovered_acs: []
parallel_conflicts: []
---

# Tasks: 장바구니 화면 — delivered 장바구니 항목·수수료·마켓 표시

> Mission: ./mission.md | Blueprint: ./blueprint.md | Jira: RBD-8279
> 실행: 웹 `cd examples/delivered/storefront-web && npm test` · `npm run build` / 백엔드 `.venv/bin/python -m pytest -q -p no:cacheprovider examples/delivered` · 린트 `.venv/bin/ruff check examples/delivered && .venv/bin/ruff format --check examples/delivered`

## Implementation Strategy

- **실행 모드**: 일괄 흐름 — 스토어프론트 한 모듈 + 백엔드 extras·핸드오프 소폭, PR 하나.
- **MVP 경계**: Phase 1~3(타입·extras·뷰 모델·마켓 그룹/상태 표시)까지가 MVP. 요금(US2)·pending(US3)·핸드오프(US4)는 그 위에 얹는다.
- **병렬 실행 예시**: T002(백엔드 L1, `tests/test_delivered_*.py`)와 T004(뷰 모델 L1, `lib/buildCartView.test.ts`)는 파일이 달라 동시 작성 가능.
- **실측 계획**: 새 아웃바운드 호출 없음. T014에서 운영 `GET /v3/cart` 읽기 1회로 `total_price` 실제 형태를 확인해 픽스처를 맞추고, delivered 웹 `/cart` 리다이렉트를 `curl -I`로 확인한다(모두 읽기 전용).

## Phase 1: Setup — 타입

- [X] T001 `CartPayload` delivered 확장 타입 추가 — `DeliveredCartFee`·`DeliveredCartOption`·`DeliveredCartLine`·`DeliveredCartGroup`, `CartPayload.delivered_cart?: {groups}` (전부 선택 필드, 기존 필드 불변) (`examples/delivered/storefront-web/lib/types.ts`)

## Phase 2: Foundational — extras 값과 뷰 모델

- [X] T002 [P] [L1] 백엔드 테스트 작성 (Red) — `line_total_of` 3경로(`total_price` 리스트 `TOTAL`/dict `total_price`/없음 → 단가×수량+기타 요금, `cost_krw` None → 0), `option_rows_of`(`option_key_locale` 그룹명 우선·`PRI_ORDER`/`PRE_ORDER` 제외), `cart_from_v3` extras 줄에 `line_total`·`options`가 실리고 기존 키 유지; `checkout_handoff`: 회원 → `[CheckoutHandoff(url=https://www.delivered.co.kr/cart, label)]`, 게스트 → `[]`, `DELIVERED_WEB_CART_URL` env 반영 (`examples/delivered/api/tests/test_delivered_cart.py`, `examples/delivered/api/tests/test_delivered_backend.py`)
- [X] T003 백엔드 구현 (Green) — `line_total_of`·`option_rows_of` + `cart_from_v3` extras 두 키, `DELIVERED_CART_URL` 상수 + `DeliveredStorefront.checkout_handoff` (`examples/delivered/api/delivered_cart.py`, `examples/delivered/api/delivered_backend.py`)
- [X] T004 [P] [L1] `buildCartView` 단위 테스트 작성 (Red) — 그룹 결합(product_id 매칭·그룹 순서·그룹에 없는 줄 무시), `delivered_cart` 없으면 기본 그룹 하나, `lineStatus`(expired 우선 → sold_out → null), `feeLabel` 3종 + Title Case 폴백, `feeRows`(상품가 = 단가×수량, `cost_krw` null 요금 생략), `activeTotals`(만료·판매 종료 제외) (`examples/delivered/storefront-web/lib/buildCartView.test.ts`)
- [X] T005 `buildCartView.ts` 구현 (Green) — `buildCartView`·`lineStatus`·`feeLabel`·`feeRows`·`activeTotals`, 뷰 모델 인터페이스(`CartGroupView`, `CartLineView`, `FeeRow`) (`examples/delivered/storefront-web/lib/buildCartView.ts`)

## Phase 3: US1 — 마켓별 그룹과 항목 정보 (P1)

**목표**: 패널이 마켓별 그룹으로 나뉘고 각 항목에 마켓명·옵션·상태가 보인다.
**독립 테스트 기준**: 두 그룹 픽스처를 넘기면 그룹 머리 2개(마켓명)와 항목마다 마켓명이 보이고, 옵션 항목은 `색상: White`, 만료 항목은 "Expired" 배지 + Stepper 없음 + Remove만, 헤더 개수는 활성 항목 수.

- [X] T006 [US1] `CartPanel` 컴포넌트 테스트 작성 (Red) — `FrameContext` 기본값(showcase 경로)으로 렌더, `@/lib/api` `fetchProducts` 모킹; 그룹 머리·항목 마켓명·옵션 줄·만료/판매 종료 배지·Stepper 유무·`plural(count)` 활성 개수·`delivered_cart` 없는 카트는 현행처럼 한 목록 (`examples/delivered/storefront-web/components/CartPanel.test.tsx`)
- [X] T007 [US1] `CartLine.tsx` 신규 + `CartPanel.tsx` 그룹 렌더링 (Green) — `CartLine` props `{line, currency, pending, onQuantityChange, onRemove}`(옵션 줄·마켓명·`Pill` 배지·원본 링크·상태별 액션), `CartPanel`이 `useMemo(buildCartView)`로 `section`/`h3` 그룹 머리(`is_bundled` 배지)와 `CartLine` 목록을 그림, 핸들러는 `useCallback` (`examples/delivered/storefront-web/components/CartLine.tsx`, `examples/delivered/storefront-web/components/CartPanel.tsx`)

## Phase 4: US2 — 요금 구성과 소계 (P2)

**목표**: 항목마다 상품가와 요금이 따로 원화로 보이고 소계는 활성 항목 합계다.
**독립 테스트 기준**: 국내 배송비 3,000원이 있는 항목에 "Item price ₩60,000"·"Domestic shipping ₩3,000"·합계 ₩63,000이 보이고, 만료 항목 45,000원은 패널 소계에서 빠진다.

- [X] T008 [US2] 요금·소계 테스트 추가(Red) 후 구현(Green) — `CartPanel.test.tsx`에 요금 줄·항목 합계·활성 소계 케이스; `CartLine`에 `feeRows` `dl`(라벨/`formatMoney(…, {whole: true})`)과 합계, `CartPanel` 푸터 `TotalRow`를 `activeTotals.subtotal`로, `note` "Fees and payment are settled on delivered" (`examples/delivered/storefront-web/components/CartPanel.test.tsx`, `examples/delivered/storefront-web/components/CartLine.tsx`, `examples/delivered/storefront-web/components/CartPanel.tsx`)

## Phase 5: US3 — 쓰기 동작의 진행 중 상태 (P3)

**목표**: 수량·삭제를 누르면 그 줄이 다음 갱신까지 진행 중으로 보인다.
**독립 테스트 기준**: `FrameContext.Provider`(`ask` spy, `chat.busy`)로 감싸 Stepper `+`를 누르면 `ask("Change the … quantity to 2.")`가 불리고 그 줄이 `aria-busy` + 버튼 비활성 + "Updating…"; `cart` prop을 바꾸거나 `busy`가 false가 되면 풀린다. 다른 줄은 영향 없음.

- [X] T009 [US3] pending 테스트 추가(Red) 후 구현(Green) — `CartPanel.test.tsx`에 pending 3케이스(진입·cart 변경 해제·busy false 해제); `CartPanel`의 `pendingId` 상태 + `handleQuantityChange`/`handleRemove` + `useEffect([cart])`/`useEffect([chat?.busy])`; `CartLine`의 `pending` 표시(`aria-busy`, `fieldset disabled`, "Updating…") (`examples/delivered/storefront-web/components/CartPanel.test.tsx`, `examples/delivered/storefront-web/components/CartPanel.tsx`, `examples/delivered/storefront-web/components/CartLine.tsx`)

## Phase 6: US4 — delivered 결제로 넘어가기 (P4)

**목표**: 체크아웃 카드가 delivered 웹 장바구니 링크와 안내 문구를 보여준다.
**독립 테스트 기준**: `handoffs: [{url: https://www.delivered.co.kr/cart}]`가 있는 페이로드로 "Continue on delivered" 링크(`target=_blank`, `rel=noopener noreferrer`)가 그 URL을 가리키고, 없으면 비활성 버튼; 항목 줄에 마켓명, 만료 줄 "Expired", "Estimated total"은 활성 합계, 해외 배송·세금 줄 없음.

- [X] T010 [US4] `CheckoutSummary` 컴포넌트 테스트 작성 (Red) — 핸드오프 링크·라벨 기본값·비활성 폴백·마켓 라벨·활성 합계·요금 안내 한 줄·"Payment happens on delivered." 문구 (`examples/delivered/storefront-web/components/generative/CheckoutSummary.test.tsx`)
- [X] T011 [US4] `CheckoutSummary.tsx` 갱신 + `CartPanel` 체크아웃 문구 (Green) — `buildCartView` 재사용, 배송/세금 두 줄 → delivered 요금 안내 한 줄, 라벨 기본값 "Continue on delivered", 안내 문구; `CartPanel` 푸터 note 확인 (`examples/delivered/storefront-web/components/generative/CheckoutSummary.tsx`, `examples/delivered/storefront-web/components/CartPanel.tsx`)

## Phase 7: US5 — 쇼케이스와 빌드 (P5)

- [X] T012 [US5] 쇼케이스 픽스처를 delivered 형태로 — `SHOWCASE_CART`(KRW, 스마트스토어 그룹: 옵션 항목 + 국내 배송비 항목 / 번개장터 그룹: 만료·판매 종료 항목, 각 줄 `fees`·`line_total`·`options`)와 `checkout` 픽스처(같은 카트 + `handoffs`), `products` 픽스처 id와 정합; `/showcase` 페이지가 그대로 그려지는지 확인 (`examples/delivered/storefront-web/lib/showcase-fixtures.ts`, `examples/delivered/storefront-web/app/showcase/page.tsx`)

## Final Phase: Polish & 검증

- [X] T013 README Cart 절에 화면이 쓰는 extras 필드(`line_total`·`options`)와 체크아웃 핸드오프(`DELIVERED_WEB_CART_URL`) 두 문장 (`examples/delivered/README.md`)
- [X] T014 검증·실측 — `ruff`·`pytest examples/delivered` 전체, `npm test`, `npm run build`(미사용 import 정리), `scripts/check.py`; 운영 계정으로 `GET /v3/cart` 1회 읽어 `total_price` 실제 형태를 픽스처(`V3_ITEM`)에 반영; `curl -I https://www.delivered.co.kr/cart`로 locale 리다이렉트 확인; 데모(:8004, :3004) 재기동 후 장바구니 패널·체크아웃 카드 화면 확인(선택) (`examples/delivered/api/tests/test_delivered_cart.py`, `examples/delivered/storefront-web/`)

## Dependencies

- T001 → T004, T006 · T002 → T003 · T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014
- T002/T003(백엔드)은 T004~T009와 독립 — T011(CheckoutSummary 핸드오프 표시)은 T003의 `checkout_handoff` 없이도 픽스처로 테스트 가능하나, 데모 확인(T014)은 T003이 필요.
- [P] 표시 태스크(T002, T004)는 서로 다른 파일만 만진다.

## Develop Notes

- T014 `curl -I https://www.delivered.co.kr/cart` → `302 location: /en/cart` — locale 없는 경로가 방문자 언어로 리다이렉트됨을 확인. `checkout_handoff`는 locale 없이 `/cart`를 준다.
- T014 운영 `GET /v3/cart` 실측은 실행하지 못했다 — 운영 로그인 시도가 401(원인 미확인, 재시도하지 않음). `line_total_of`는 `total_price`의 세 형태(`TOTAL` 행 리스트 / `{total_price}` 객체 / 없음 → 단가×수량+요금)를 모두 받으므로 화면은 어느 형태에서도 합계를 낸다. 실제 형태는 다음 로그인 가능 시점에 `GET /v3/cart` 한 번으로 확인해 `V3_ITEM` 픽스처를 맞추면 된다.
- T014 데모(:8004/:3004) 재기동 e2e는 실행하지 않았다 — 같은 경로를 `CartPanel.test.tsx`·`CheckoutSummary.test.tsx`(가짜 프레임·픽스처)와 `next build`가 덮는다.
- 격리 findings 평가 후 보강: 대화 없는 프레임(/showcase)에서는 pending을 만들지 않음(DV001, 테스트 1건 추가) · 셸 헤더 bag 배지도 활성 개수·합계 사용(D003, `app/page.tsx`).
- 검증: `ruff check/format` · `pytest examples/delivered` 124 passed · `npm test` 50 passed(8 파일) · `npm run build` 통과(TypeScript 포함).
