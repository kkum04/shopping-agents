---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: mission
completed: [mission]
plan: [blueprint, tasks, develop]
skip: []
depth: standard
base_sha: 432c401
gates:
  open_q: 0                     # Q1·Q2 2026-09-15 사용자 답으로 해소
risk:
  self: 0.2                     # base 0 + UI 티켓 Figma 없음 0.2 → < 0.4(standard) 생략
  review: skipped
difficulty:
  area: FE
  level: M
  size: 중
  signals:
    changed_files: 6
    module_count: 1
    new_api: false
    db_migration: false
    txn_concurrency_external: false
    est_md: 2.0
  computed_at: 432c401
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [장바구니, cart, CartPanel, cart_extras, delivered_cart, 마켓, 수수료, 만료, 체크아웃 핸드오프]
  modules: [examples/delivered/storefront-web/components/CartPanel.tsx, examples/delivered/storefront-web/components/generative/CheckoutSummary.tsx, examples/delivered/storefront-web/lib/types.ts, examples/delivered/api/delivered_backend.py]
acceptance:
  - id: AC1
    story: P1
    ears: "WHEN 장바구니 페이로드에 delivered_cart.groups가 둘 이상이면 THE system SHALL 패널을 마켓별 그룹으로 나누고 각 그룹 머리와 항목에 마켓명을 보여준다"
  - id: AC2
    story: P1
    ears: "WHEN 항목에 옵션 값이 있으면 THE system SHALL 제목 아래에 옵션(그룹명: 값)을 한 줄로 보여준다"
  - id: AC3
    story: P1
    ears: "WHEN 항목이 만료(is_expired)이거나 판매 종료(is_selling false)이면 THE system SHALL 그 줄을 흐리게 표시하고 상태 배지를 붙이며 수량 변경을 막고(삭제만 허용) 패널의 개수·소계에서 제외한다"
  - id: AC4
    story: P2
    ears: "WHEN 항목의 fees에 UNIT_PRICE 외 요금(국내 배송비·수수료)이 있으면 THE system SHALL 상품가(단가×수량)와 각 요금을 원화로 따로 보여준다"
  - id: AC5
    story: P2
    ears: "WHEN 항목 소계를 보여줄 때 THE system SHALL delivered 장바구니 목록의 항목 합계(total_price)와 같은 값을 원화 정수로 보여주고 패널 소계는 만료·판매 종료가 아닌 항목 합계의 합이다"
  - id: AC6
    story: P3
    ears: "WHEN 수량 변경·삭제 버튼이 어시스턴트에게 메시지를 보내면 THE system SHALL 다음 cart_update가 올 때까지 그 줄을 진행 중 상태(버튼 비활성·표시)로 보여준다"
  - id: AC7
    story: P4
    ears: "WHEN 체크아웃 카드가 그려지면 THE system SHALL 백엔드 checkout_handoff가 준 delivered 웹 장바구니 URL을 새 창으로 여는 버튼과 결제는 delivered에서 진행된다는 문구를 보여준다"
  - id: AC8
    story: P5
    ears: "WHEN /showcase 페이지가 빌드되면 THE system SHALL 마켓 그룹·수수료·만료 항목이 있는 delivered 장바구니 픽스처를 그리고 next build와 vitest가 통과한다"
sources: { read: 1, unread: 0, blocked: 0, figma: none }
---

# Mission: 장바구니 화면 — delivered 장바구니 항목·수수료·마켓 표시

> Jira: RBD-8279 | Epic: RBD-8273 [RND] delivered 쇼핑 에이전트 — 로그인·장바구니·결제 연결 | Priority: Medium

## Background

RBD-8277로 장바구니가 delivered 실제 장바구니가 되었다. 백엔드는 `GET /v3/cart`를 프레임워크의 `Cart`(항목·단가·수량)로 바꾸고, 프레임워크 줄에 자리가 없는 정보(마켓 그룹, 요금 구성, 만료·판매 종료, 원본 상품 링크)를 `cart_extras`의 `delivered_cart.groups`로 함께 실어 보낸다. 그런데 스토어프론트 패널(`CartPanel.tsx`)과 체크아웃 카드(`CheckoutSummary.tsx`)는 리테일 예제의 복사본 그대로라 상품·수량·소계만 그리고, 요금·마켓·상태는 버려진다. 체크아웃 카드는 "Continue to checkout"이 비활성 버튼으로 남아 있고 배송·세금 줄은 해외 리테일 문구다.

delivered 장바구니는 마켓별로 묶이고(`orders[].market_name`), 항목마다 `prices[]`에 상품가(UNIT_PRICE) 외에 국내 배송비(DOMESTIC_SHIPPING_PRICE)·수수료(HANDLING_FEE)가 붙으며, 항목 상태로 만료(`is_expired`)와 판매 종료(`is_selling`)가 있다. delivered 웹 장바구니는 만료·판매 종료 항목을 흐리게 그리고 결제 대상에서 뺀다. 이 화면이 그 정보를 그대로 보여줘야 고객이 어시스턴트와 웹에서 같은 장바구니를 본다.

## Goal

delivered 장바구니의 마켓 그룹·옵션·요금·상태를 스토어프론트 패널과 체크아웃 카드에 그대로 보여주고, 쓰기 동작(수량·삭제)에는 진행 중 상태를, 결제에는 delivered 웹으로 넘어가는 길을 붙인다.

## User Stories

우선순위 순으로 정렬:

### P1: 마켓별 그룹과 항목 정보

- **As a** delivered 고객
- **I want** 장바구니 패널이 마켓별로 묶여 있고 각 항목에 마켓명·옵션·상태가 보이기를
- **So that** 어느 마켓에서 무엇을 어떤 옵션으로 담았고 아직 살 수 있는지 한눈에 알 수 있다

**Acceptance Criteria:**
- [ ] AC1: 두 마켓 상품을 담으면 패널이 마켓별 두 그룹으로 보이고 그룹 머리와 각 항목에 마켓명이 있다.
- [ ] AC2: 옵션 상품 항목은 제목 아래에 옵션(예: 색상: White)이 보인다.
- [ ] AC3: 만료·판매 종료 항목은 흐리게 표시되고 상태 배지(만료 / 판매 종료)가 붙으며, 수량 변경이 막히고(삭제만 가능) 패널의 항목 개수·소계에서 빠진다.

### P2: 요금 구성과 소계

- **As a** delivered 고객
- **I want** 항목별로 상품가와 국내 배송비·수수료가 따로 원화로 보이기를
- **So that** delivered 웹 장바구니와 같은 금액을 어시스턴트 화면에서도 확인할 수 있다

**Acceptance Criteria:**
- [ ] AC4: 국내 배송비나 수수료가 있는 항목은 상품가(단가×수량)와 각 요금이 이름과 함께 따로 보인다. 요금이 없는 항목은 상품가만 보인다.
- [ ] AC5: 항목 소계는 delivered 장바구니 목록이 주는 항목 합계와 같은 원화 정수이고, 패널 소계는 만료·판매 종료가 아닌 항목 소계의 합이다.

### P3: 쓰기 동작의 진행 중 상태

- **As a** delivered 고객
- **I want** 수량을 바꾸거나 삭제를 누르면 결과가 반영될 때까지 그 줄이 진행 중으로 보이기를
- **So that** delivered가 삭제·재생성을 끝내는 동안 같은 버튼을 다시 누르지 않는다

**Acceptance Criteria:**
- [ ] AC6: 수량 변경·삭제 버튼은 지금처럼 어시스턴트에게 메시지를 보내고, 다음 `cart_update`가 올 때까지 그 줄의 버튼이 비활성화되고 진행 중 표시가 보인다. 어시스턴트 턴이 장바구니 갱신 없이 끝나면 표시가 풀린다.

### P4: delivered 결제로 넘어가기

- **As a** delivered 고객
- **I want** 체크아웃 카드와 패널의 체크아웃 버튼이 delivered 웹 장바구니로 이어지기를
- **So that** 결제(쿠폰·포인트·배송지)는 delivered 결제 페이지에서 마친다

**Acceptance Criteria:**
- [ ] AC7: 체크아웃 카드에는 백엔드 `checkout_handoff`가 준 delivered 웹 장바구니 URL을 새 창으로 여는 버튼과 "결제는 delivered에서 진행된다"는 문구가 있고, 해외 배송·세금 줄 대신 delivered 요금 안내가 있다. 패널의 체크아웃 버튼 문구도 같은 뜻으로 바뀐다.

### P5: 쇼케이스와 빌드

- **As a** 이 예제를 보는 개발자
- **I want** `/showcase`에서 delivered 장바구니 형태를 볼 수 있기를
- **So that** 로그인 없이도 화면을 검토할 수 있다

**Acceptance Criteria:**
- [ ] AC8: `/showcase` 픽스처가 마켓 그룹 2개·요금 있는 항목·만료 항목·옵션 항목을 담고, `next build`와 vitest가 통과한다.

## UI/Design Requirements

> Figma 없음 — delivered 웹 장바구니(고객 프론트 `src/containers/cart/`)와 기존 패널 구조를 따른다.

### 화면 구성
- 도킹 패널(`BagPanel`): 그룹 머리(마켓명, 항목 수) → 항목 줄 → 푸터(소계, 체크아웃 버튼, 물어보기 링크).
- 체크아웃 카드(`CheckoutSummary`): 항목 요약(마켓명 포함) → 소계 → delivered 요금 안내 → delivered로 이동 버튼.

### 컴포넌트
- 그룹 머리: 마켓명(`market_name`), 묶음 배송(`is_bundled`)이면 표시.
- 항목 줄: 썸네일·제목·옵션 한 줄·마켓명·상태 배지·요금 줄(상품가 / 국내 배송비 / 수수료)·항목 소계·Stepper·삭제·원본 상품 링크(`product_url`).
- 진행 중 표시: 줄 전체 반투명 + 버튼 비활성 + 작은 스피너 또는 "Updating…" 텍스트.

### 인터랙션
- 수량 변경·삭제 → 어시스턴트 메시지(현행) → 줄 진행 중 → `cart_update` 수신 시 해제. 만료·판매 종료 줄은 Stepper 없이 삭제만.
- 체크아웃 버튼(패널)과 카드 버튼 → delivered 웹 장바구니 URL 새 창.
- 화면 문구는 스토어프론트 나머지(AccountBar 등)와 같이 영문, 데이터(마켓명·옵션·제목)는 delivered가 준 그대로.

### 데이터 요구사항 (from Design)
- `CartPayload.delivered_cart.groups[]`: `market_sub_type`, `market_name`, `is_bundled`, `items[]{buy_request_id, product_id, product_url, fees[{fee_type, cost_krw, cost_usd}], is_expired, is_selling}` — RBD-8277이 이미 싣는 값.
- 추가로 필요한 값(백엔드 `cart_from_v3`에 한 줄씩): 항목 합계 `total_price{item_total_price, total_price}`, 항목 옵션 `options[]{key, value, option_key_locale}` (v3 목록에 있음).
- 요금 이름: `UNIT_PRICE`(상품가) / `DOMESTIC_SHIPPING_PRICE`(국내 배송비) / `HANDLING_FEE`(수수료) — 고객 프론트 `BUY_REQUEST_FEE_TYPE`. 그 외 이름은 그대로 표시.
- 통화: `cart.currency`(KRW)를 `formatMoney(value, currency, {whole: true})`로.

## Non-Functional Requirements

- **성능**: 그룹·요금 계산은 페이로드 한 번 순회로; 카탈로그 조회(`useCatalogIndex`)는 현행 유지.
- **보안**: delivered URL은 백엔드 `checkout_handoff`가 채우고 모델·화면은 조립하지 않는다; 새 창 링크는 `rel="noopener noreferrer"`.
- **호환성**: 기존 `CartPayload` 필드는 그대로(리테일 공용 타입 유지), delivered 확장 필드는 선택 필드로 두어 다른 예제가 깨지지 않는다. vitest(RTL)로 컴포넌트 테스트, 네트워크 없음.

## Out of Scope

- 쿠폰·포인트·배송지·결제 자체(delivered 결제 페이지 담당).
- 디자인 시스템 교체, 한국어 UI 전환.
- 백엔드 장바구니 로직(구매요청 생성·삭제·재생성, 만료 항목 자동 정리)과 옵션 매핑 — RBD-8277·RBD-8278.
- 수량 변경·삭제의 직접 REST 경로 추가(Q1에서 제외).

## Open Questions

- [x] Q1: 수량 변경·삭제 버튼의 쓰기 경로 — **확정: 어시스턴트 메시지 유지 + 줄 단위 진행 중 표시** (출처: 사용자 2026-09-15). 직접 REST 경로는 추가하지 않는다.
- [x] Q2: 체크아웃의 "delivered 결제 페이지로 넘어간다"의 수준 — **확정: 백엔드 `checkout_handoff`가 delivered 웹 장바구니 URL을 돌려주고 카드·패널 버튼이 새 창으로 연다** (출처: 사용자 2026-09-15).

> 모든 Open Questions가 해소되어야(`- [x]`) blueprint 단계로 진행할 수 있습니다. (frontmatter `gates.open_q` 와 동기)

---

## 🤖 소스 추적 (기계용 — 사람은 읽지 않아도 됨)

> 추적성 메타. "모두 확인"의 보장이자 frontmatter `sources` 카운트의 원장. 사람용 본문에는 넣지 않는다.

### Sources

| 소스 | 상태 | 비고 |
|------|------|------|
| Jira 티켓 | ✅ 확인 | RBD-8279 (`/jarvis:draft` 산출물 — 품질 검증 통과, 선행 RBD-8277·8278 개발 완료) |
| PM 티켓 (에픽 링크) | ⚠️ 없음 | 기획 티켓 없음 — 에픽 RBD-8273 링크·첨부 0건(선행 티켓에서 확인) |
| Figma 디자인 | ⏭️ 없음 | delivered 웹 장바구니 화면(고객 프론트 코드)을 참고 |
| 운영 API 실측 (RBD-8277·8278) | ✅ 확인 | `v3/cart` 항목 형태: `prices[]{fee_type, cost_krw, cost_usd}`, `total_price`, `options[]`, `is_expired`, `is_selling`, `market_info` |

### PM 티켓 관련 링크 (전수)

| 제목 | kind | source | 상태 | URL |
|------|------|--------|------|-----|
| (없음) | — | — | — | — |

### Reference Code

| 프로젝트 | 파일 경로 | 참조 목적 |
|---------|---------|---------|
| 현재 프로젝트 | `examples/delivered/storefront-web/components/CartPanel.tsx`, `components/generative/CheckoutSummary.tsx`, `app/page.tsx` | 현행 패널·카드 구조, `cart_update` 수신과 `fetchCart` 갱신 지점 |
| 현재 프로젝트 | `examples/delivered/storefront-web/lib/types.ts`, `lib/showcase-fixtures.ts` | `CartPayload` 확장 지점, 쇼케이스 픽스처 |
| 현재 프로젝트 | `examples/web-shared/storefront/bag.tsx`, `web-shared/format.ts` | `BagPanel`·`Stepper`·`RemoveLink`·`TotalRow`·`CheckoutButton`, `formatMoney(whole)` |
| 현재 프로젝트 | `examples/delivered/api/delivered_cart.py`(`cart_from_v3`), `delivered_backend.py`(`cart_extras_for`), `shopping-agent/core/shopping_agent/backend.py:120`(`checkout_handoff`) | extras 조립, 핸드오프 URL 공급 지점 |
| deliveredkorea-customer-frontend | `src/types/api/cart/cartApiDto.ts`, `src/libs/enums/_common.ts`(`BUY_REQUEST_FEE_TYPE`), `src/containers/cart/_shared/ProductCardList/ProductCardItem/_libs/utils.ts`, `_hooks/useProductCardItem.ts` | 요금 이름·단가 추출·만료/판매 종료 처리 관례 |
