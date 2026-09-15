---
# 🤖 AI용 — 기계 전용 (사람은 아래 본문만 읽으면 된다). navigation.md 「문서 2계층 규약」참조.
stage: mission
completed: [mission]
plan: [blueprint, tasks, develop]
skip: []
depth: standard
base_sha: 7b13529
gates:
  open_q: 0
risk:
  self: 0.2                     # base 0.2(외부 연동) + 품질 신호 0 → < 0.4(standard) 생략
  review: skipped
difficulty:
  area: BE
  level: M
  size: 중
  signals:
    changed_files: 5
    module_count: 1
    new_api: false
    db_migration: false
    txn_concurrency_external: true
    est_md: 2.5
  computed_at: 7b13529
domain_cache:
  squad: RND
  epic_folder: RBD-8273-delivered-shopping-agent
  keywords: [옵션, option-groups, options, variant, family, 구매요청, 스마트스토어]
  modules: [examples/delivered/api/delivered_backend.py, examples/delivered/api/delivered_cart.py]
acceptance:
  - id: AC1
    story: P1
    ears: "WHEN 옵션 그룹이 있는 스마트스토어 상품의 get_product_details가 호출되면 THE system SHALL option-groups·options를 함께 읽어 options(그룹 → 값 목록)와 variants(옵션 조합별 id·가격·재고)를 채운 family를 돌려준다"
  - id: AC2
    story: P1
    ears: "WHEN family id로 add_to_cart가 호출되면 THE system SHALL 프레임워크 옵션 게이트가 variants를 가리키며 보류하고 delivered에 아무것도 만들지 않는다"
  - id: AC3
    story: P2
    ears: "WHEN variant id({market}:{pid}#{optionId})로 add_to_cart가 호출되면 THE system SHALL 구매요청 본문 options에 그 optionId를 실어 delivered 장바구니에 옵션이 표시되게 한다"
  - id: AC4
    story: P2
    ears: "WHEN 품절(stockQuantity 0) variant로 add_to_cart가 호출되면 THE system SHALL Unavailable(재고 있는 형제 variant id 목록)을 내고 delivered에 아무것도 만들지 않는다"
  - id: AC5
    story: P3
    ears: "WHEN 옵션 조합이 60개를 넘으면 THE system SHALL 첫 옵션 그룹 값 기준으로 family를 나눠 각 family가 60개 이하의 variants를 갖게 한다"
  - id: AC6
    story: P1
    ears: "WHEN 테스트가 실행되면 THE system SHALL 녹화된 option-groups·options 응답으로 family/variant 매핑·variant id 역매핑·옵션 전달·품절 처리를 검증하고 네트워크에 닿지 않는다"
  - id: AC7
    story: P2
    ears: "WHEN 장바구니 조회(v3/cart)가 옵션 있는 라인을 돌려주면 THE system SHALL 그 라인의 product_id를 variant id로 복원해 수량 변경·삭제가 같은 variant로 이어지게 한다"
  - id: AC8
    story: P2
    ears: "WHEN TEXT 옵션 그룹이 있는 상품(family 또는 그 variant)으로 add_to_cart가 호출되면 THE system SHALL 문구 입력이 필요해 delivered 웹에서 담아 달라는 CartRejected를 내고 delivered에 호출하지 않는다"
sources: { read: 1, unread: 0, blocked: 0, figma: none }
---

# Mission: 옵션 상품 매핑 — option-groups/options를 family/variant로, 구매요청에 옵션 전달

> Jira: RBD-8278 | Epic: RBD-8273 [RND] delivered 쇼핑 에이전트 — 로그인·장바구니·결제 연결 | Priority: Medium

## Background

색상·사이즈처럼 옵션이 있는 상품은 옵션을 고르지 않으면 구매요청을 만들 수 없다. 프레임워크는 옵션 상품을 **family**(옵션 목록을 가진 상품 — 장바구니가 거부) + **variant**(옵션 조합별 구매 단위 — `option_values`·`variant_of`, 장바구니가 받는 id) 구조로 다루고(`docs/backends.md` Step 4), 상세 조회 결과의 `variants`가 세션 provenance에 함께 들어가 에이전트가 "블랙 L로 담아줘"를 variant id로 바꾼다.

delivered 스마트스토어 상세에는 옵션 API가 따로 있다 — `GET …/stores/smartstore/{pid}/option-groups`(그룹: `productOptionGroupId`, `productOptionGroupType` SIMPLE|COMBINATION|TEXT, 이름 ko/en)와 `GET …/{pid}/options`(옵션: `optionId`, 그룹별 `productOptionName`, `optionPriceKrw`(그 조합의 전체 가격), `stockQuantity`). 2026-09-14 운영 게스트 API 실측: 옵션 있는 상품 58개 중 56개가 COMBINATION만, 2개가 COMBINATION+TEXT(각인 문구 입력). RBD-8277(완료)이 만든 구매요청 본문은 `options: number[]`·`text_options: [{product_option_group_id, value}]`를 이미 갖고 있어(지금은 빈 배열) 옵션 ID만 실어 보내면 된다.

지금 `get_product_details`는 상세 한 번만 읽어 옵션 없는 상품으로 만들고, 옵션 상품은 `has_options`가 비어 있어 담기가 "옵션 선택" 안내 없이 진행된다(실제로는 delivered가 옵션 누락으로 거절할 수 있다).

## Goal

옵션 있는 스마트스토어 상품을 에이전트가 family/variant로 보고, 손님이 고른 옵션 조합의 variant id로 담으면 그 옵션 ID가 delivered 구매요청에 실려 웹 장바구니에 옵션이 표시되게 한다.

## User Stories

우선순위 순으로 정렬:

### P1: 옵션 상품 상세를 family/variant로

- **As a** 손님
- **I want** 옵션 있는 상품을 물으면 에이전트가 고를 수 있는 옵션(색상·사이즈)과 각 조합의 가격·재고를 알려주기를
- **So that** 어떤 조합으로 담을지 바로 정할 수 있다

**Acceptance Criteria:**
- [ ] AC1: 옵션 그룹이 있는 스마트스토어 상품의 상세 조회가 option-groups·options를 함께 읽어 `options`(그룹명 → 값 목록)와 `variants`(조합별 id·가격·재고·`option_values`)를 채운 family를 돌려준다.
- [ ] AC2: family id로 담으면 프레임워크 옵션 게이트가 variants를 가리키며 보류하고 delivered에 아무것도 만들지 않는다.
- [ ] AC6: 녹화된 option-groups·options 응답으로 매핑·역매핑·옵션 전달·품절 처리 테스트가 통과하며 네트워크에 닿지 않는다.

### P2: variant로 담기 — 옵션 ID를 구매요청에 전달

- **As a** 손님
- **I want** "블랙 L로 담아줘"가 그 조합으로 delivered 장바구니에 들어가기를
- **So that** 웹에서 옵션을 다시 고르지 않아도 된다

**Acceptance Criteria:**
- [ ] AC3: variant id(`{market}:{pid}#{optionId}`)로 담으면 구매요청 본문 `options`에 그 optionId가 실리고 delivered 웹 장바구니에 옵션이 표시된다.
- [ ] AC4: 품절 variant로 담으면 재고 있는 형제 variant id 목록을 담은 `Unavailable`로 끝나고 delivered에 아무것도 만들지 않는다.
- [ ] AC7: `v3/cart`의 옵션 있는 라인은 `product_id`가 variant id로 복원되어 수량 변경·삭제가 같은 variant로 이어진다.
- [ ] AC8: TEXT 옵션 그룹(각인 문구 등)이 있는 상품은 family든 variant든 담기가 "문구 입력이 필요해 delivered 웹에서 담아 주세요"로 거절되고 delivered 호출이 없다(Q1).

### P3: 큰 옵션 조합의 분할

- **As a** 에이전트
- **I want** 조합이 많은 상품도 프레임워크 상한 안에서 다루기를
- **So that** 상세 결과가 잘리지 않는다

**Acceptance Criteria:**
- [ ] AC5: 옵션 조합이 60개를 넘으면 첫 옵션 그룹 값 기준으로 family를 나눠 각 family가 60개 이하의 variants를 갖는다(분할 family id `{market}:{pid}#g{optionId…}` 등 역매핑 가능한 형식).

## UI/Design Requirements

> 백엔드 티켓 — 화면 변경 없음. 스토어프론트 카드·장바구니 패널은 기존 `option_values`·`variant_of`를 이미 읽는다(`optionValuesLabel`).

### 데이터 요구사항 (from Design)
- family: `product_id = {market}:{pid}`, `options = {그룹명: [값…]}`(COMBINATION 그룹만), `price` = 재고 있는 variant 최저가, `in_stock` = 재고 있는 variant가 하나라도 있으면 true.
- variant: `product_id = {market}:{pid}#{optionId}`, `option_values = {그룹명: 값}`, `price = optionPriceKrw`, `in_stock = stockQuantity > 0`, `variant_of = family id`, 제목·이미지는 family 상속.
- 구매요청: `options: [optionId]`, `text_options`는 항상 빈 배열 — TEXT 그룹 상품은 담기 전에 거절(Q1).
- 장바구니 라인 역매핑: `v3/cart` 항목의 `options[]`(있으면) 또는 상세 `GET /v2/cart/{id}`의 `options[]`에서 optionId를 읽어 variant id로.

## Non-Functional Requirements

- **성능**: 상세 조회 시 옵션 API 2개를 상세와 **병렬**로 부른다(`asyncio.gather`). 옵션 API 실패는 상세를 막지 않는다(옵션 없는 상품으로 두고 경고 로그).
- **크기**: 상세 결과는 `max_fenced_chars`(12,000자) 안 — variant 한 줄 70~120자, 60개 상한(AC5).
- **호환성**: 프레임워크 코어·`demo_common` 수정 없음. 옵션 없는 상품의 기존 흐름(RBD-8277)은 그대로.
- **보안**: 기존 게스트 API 호출 경로(`DeliveredClient._call`) 사용, 로그에 본문 없음.

## Out of Scope

- 옵션 없는 상품(기존 흐름), 옵션 이미지 표시(티켓 명시).
- 스마트스토어 외 마켓의 옵션(번개장터·다른 RPA 마켓은 우리 카탈로그에 상세 경로가 없다 — 통합검색 결과로만 존재).
- `SIMPLE` 그룹 타입 — 실측에서 관측되지 않아 COMBINATION과 같은 규칙으로 처리하되 별도 검증은 하지 않는다.
- 장바구니 화면에서 옵션명 표기 개선(기존 `option_values` 표시 그대로).

## Open Questions

- [x] Q1: `TEXT` 옵션 그룹(각인 문구 등 자유 입력)이 있는 상품은 어떻게 다룰까 — (a) TEXT는 비워 두고 COMBINATION 옵션만으로 담기(대부분 "각인 없음"에 해당), (b) TEXT 그룹이 있으면 담기를 거부하고 웹으로 안내, (c) 별도 처리 없이 지금처럼(옵션 없는 상품 취급)?
  → 확정: **(b) 담기 거부** (2026-09-14, 사용자). family에 `attributes.text_options = 그룹명`을 남겨 에이전트가 미리 안내할 수 있게 하고, 담기는 `CartRejected`로 웹 안내(AC8).
- [x] Q2: 운영 계정으로 옵션 상품을 실제로 담아 delivered 웹 장바구니의 옵션 표시를 확인해도 되는가(실측 후 삭제 — RBD-8277과 같은 방식)?
  → 확정: **된다** (2026-09-14, 사용자). develop에서 optionId를 실은 구매요청을 만들어 `v3/cart`의 `options[]` 표시를 확인하고 삭제한다.

> 모든 Open Questions가 해소되어야(`- [x]`) blueprint 단계로 진행할 수 있습니다. (frontmatter `gates.open_q` 와 동기)

---

## 🤖 소스 추적 (기계용 — 사람은 읽지 않아도 됨)

### Sources

| 소스 | 상태 | 비고 |
|------|------|------|
| Jira 티켓 | ✅ 확인 | RBD-8278 (`/jarvis:draft` 산출물 — 품질 검증 통과, 선행 RBD-8277 개발 완료) |
| PM 티켓 (에픽 링크) | ⚠️ 없음 | 기획 티켓 없음 — 에픽 RBD-8273 링크·첨부 0건 |
| Figma 디자인 | ⏭️ 없음 | 백엔드 티켓 |
| 운영 게스트 API 실측 | ✅ 확인 | 2026-09-14 option-groups/options 응답 형태·그룹 타입 분포·가격 관계 |

### PM 티켓 관련 링크 (전수)

| 제목 | kind | source | 상태 | URL |
|------|------|--------|------|-----|
| (없음) | — | — | — | — |

### Reference Code

| 프로젝트 | 파일 경로 | 참조 목적 |
|---------|---------|---------|
| 현재 프로젝트 | `examples/delivered/api/delivered_backend.py` | `get_product_details`·`detail_to_product_details`(옵션 병합 지점), `add_to_cart`(variant id) |
| 현재 프로젝트 | `examples/delivered/api/delivered_cart.py` | `buy_request_body`(`options`/`text_options`), `CartIndex`, `cart_from_v3` |
| 현재 프로젝트 | `shopping-agent/core/shopping_agent/types.py`, `gates.py`, `executor.py:149`, `docs/backends.md` Step 4 | family/variant 규칙, 옵션 게이트, variants의 provenance 등록 |
| 현재 프로젝트 | `examples/demo_common/storefront_fixtures.py`(`load_catalog`), `examples/retail/api/mock_retail.py` | family 파생(최저가·재고)·variant 해석 예 |
| deliveredkorea-customer-frontend | `src/types/api/store/storeApiDto.ts:66-93`, `src/features/constants/endPoints.ts:157-160`, `src/containers/stores/store/detail/_components/ProductInfoSection/_components/PurchaseAction/_hooks/usePurchaseAction.ts` | 옵션 API 타입·경로, `options`/`text_options` 구성 관례 |
