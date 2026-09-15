# Findings: 옵션 상품 매핑 — option-groups/options를 family/variant로, 구매요청에 옵션 전달

> Jira: RBD-8278 | Mission: ./mission.md | Blueprint: ./blueprint.md · ./blueprint-integration.md
>
> 📌 `/jarvis:develop` 실행 중 발견한 명세 갭/판단/편차/트레이드오프/미결 질문을 4개 카테고리로 누적합니다.
> 노트 ID: 설계 결정=D###, 편차=DV###, 트레이드오프=T###, 미결 질문=Q###.

## 미결 질문 ❓

(없음)

## 편차 ⚠️

### DV001 — sub-family attributes 키가 `option_group_1`이 아니라 그룹명

- **태스크**: T010
- **파일**: `examples/delivered/api/delivered_options.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**명세**: blueprint.md split_families: "첫 그룹 값별로 sub-family(… `attributes[\"option_group_1\"] = 값`, id `#g{n}`)"

**실제**: `family.attributes | {첫 그룹명: 값}` — 키가 고정 이름이 아니라 그룹명(예: `색상`)이다. 테스트도 `attributes["색상"]`을 단언한다.

**판단**: 그룹명을 키로 두면 상세 화면에 「색상: 화이트」로 그대로 읽혀 고정 키보다 낫다고 봤다. agent_config는 `variant_families`만 안내하므로 프롬프트 영향 없음.

**여파**: blueprint.md Module Design(split_families) 문구 갱신

---
### DV002 — `variant_families` 값이 `#g1 값A`가 아니라 전체 id

- **태스크**: T010
- **파일**: `examples/delivered/api/delivered_options.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**명세**: blueprint.md: "원 family는 `variants=[]`·`attributes[\"variant_families\"] = \"#g1 값A, #g2 값B, …\"`"

**실제**: `"smart_store:1#g1 C0, smart_store:1#g2 C1, …"` — 전체 product id를 싣는다.

**판단**: agent_config의 안내가 「listed sub-family id로 get_product_details를 호출」이므로 에이전트가 id를 조립하지 않도록 전체 id를 실었다.

**여파**: blueprint.md Module Design(split_families) 형식 문구 갱신

---
### DV003 — 옵션 API 4xx가 경고 없이 빈 옵션으로 처리됨 → develop에서 수정

- **태스크**: T005
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 19:45
- **상태**: ✅ resolved (코드 수정)

**명세**: mission NFR: "옵션 API 실패는 상세를 막지 않는다(옵션 없는 상품으로 두고 경고 로그)"; blueprint Error Handling: "4xx/5xx/전송 오류 → 옵션 없는 상품 + 경고(경로·상태만)"

**실제**: `_call`이 4xx 본문을 그대로 돌려주고 `_answer_rows`가 `result` falsy를 로그 없이 `[]`로 처리했다(테스트는 503만 주입).

**판단**: 격리 평가 직후 `_answer_rows`에 경고(경로·pid·code)를 추가하고 404 주입 테스트를 더해 명세대로 맞췄다.

**여파**: -

---
### DV004 — 역매핑 함수·입력이 blueprint 서술과 다름(`variant_for_option_values`, option-groups 동반 조회, 장바구니 라인 옵션 우선)

- **태스크**: T009 · T012
- **파일**: `examples/delivered/api/delivered_options.py, examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**명세**: blueprint.md: "`variant_for_option_names(options, names: dict[str, str]) -> int | None`: `{그룹명: 값}`이 전부 일치하는 optionId", "`_resolve_product_id`: 상세 응답의 `options`가 비어 있지 않고 SMART_STORE면 `client.smartstore_options(pid)`로 대조"; coverage AC7도 옛 이름을 가리킨다.

**실제**: T012 운영 실측에서 `v3/cart` 라인은 값이 영문+그룹 id(`option_key_locale`), `v2/cart/{id}`는 한글 값만이라 그룹명 dict 대조가 성립하지 않았다. `variant_for_option_values(groups, options, chosen: [(group_id|None, value)])`로 바꾸고 option-groups·options를 함께 읽으며, 라인 옵션을 먼저 쓰고 상세 옵션으로 폴백한다. 미해석 옵션 라인당 게스트 호출 +2.

**판단**: 실측 데이터 형태에 맞춘 재결정. tasks.md Develop Notes와 blueprint-integration.md에는 기록했으나 blueprint.md 본문은 develop 범위 밖이라 두었다.

**여파**: blueprint.md Module Design(delivered_options·_resolve_product_id)·Migration(호출 수)·coverage AC7 문구 갱신

---
### DV005 — option-groups 성공·options 실패 시 `text_options` 표식이 남은 상세

- **태스크**: T005
- **파일**: `examples/delivered/api/delivered_options.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**명세**: blueprint.md get_product_details: "옵션 둘 중 하나라도 예외/빈 응답이면 옵션 없는 상세(현행)"

**실제**: `family_with_variants`는 variants가 없어도 TEXT 표식을 attributes에 남긴 사본을 돌려주므로, 그 상태로 담으면 `CartRejected`(웹 안내)가 난다.

**판단**: TEXT 그룹이 확인된 상품은 옵션 조회 실패 중에도 담기지 않는 편이 AC8과 맞다고 봐서 그대로 두었다.

**여파**: blueprint.md Error Handling 문구에 예외 명시

---
### DV006 — `split_product_id`도 수정됨(`#` 절단)

- **태스크**: T007
- **파일**: `examples/delivered/api/delivered_cart.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**명세**: blueprint.md id 형식: "split_product_id는 # 앞까지가 마켓:pid이므로 … 그대로 동작한다"; Directory Structure는 delivered_cart.py 변경을 buy_request_body로 한정.

**실제**: `raw_id.partition("#")[0]`을 추가해야 variant id의 pid가 나왔다.

**판단**: 결과는 명세 의도와 같고 변경 범위만 한 줄 넓다.

**여파**: blueprint.md Directory Structure(delivered_cart.py 변경 범위)

---

## 설계 결정 📘

### D001 — 선택 그룹을 전부 채운 옵션 행만 variant로 채택

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_options.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**맥락**: 명세는 "알려진 그룹을 가리키지 않으면 그 행은 건너뛴다"만 말하고, 일부 그룹이 빠진 행은 침묵.

**판단**: `_row_values`는 어느 한 그룹이라도 빠진 행도 버린다. 그런 상품은 variants가 비어 옵션 없는 상품으로 취급된다.

**근거**: 실측 58개 상품 모두 행마다 전 그룹을 채웠다. 부분 행을 variant로 세우면 option_values가 불완전해 매칭이 흔들린다.

**여파**: -

---
### D002 — 그룹 한글명이 비면 영문명으로 대체

- **태스크**: T003
- **파일**: `examples/delivered/api/delivered_options.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**맥락**: 명세는 그룹명 = productOptionGroupName(ko)만 명시.

**판단**: `_group_name`이 ko가 비면 `productOptionGroupNameEn`을 쓴다.

**근거**: 픽스처에 사례는 없으나 빈 키가 options dict에 들어가는 것을 막기 위함.

**여파**: -

---
### D003 — 분할은 첫 그룹 값별 1회만 — 한 값이 60행을 넘으면 그 sub-family는 60을 넘김

- **태스크**: T010
- **파일**: `examples/delivered/api/delivered_options.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**맥락**: AC5 "각 family가 60개 이하의 variants"; blueprint도 첫 그룹 분할만 기술.

**판단**: 잔여 초과 가드를 두지 않았다.

**근거**: 실측 최대 12행. 2단 분할은 id 형식(`#g{n}`)을 늘려야 해 명세 공백을 develop에서 메우지 않았다.

**여파**: mission.md AC5 보장 범위 명시 후보

---
### D004 — 선택 그룹이 하나뿐인 61행+ family의 sub-family는 옵션 없는 family 모양 → add_to_cart가 sub-family id를 거절하도록 보강

- **태스크**: T010
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 19:45
- **상태**: ✅ resolved (코드 수정)

**맥락**: blueprint "sub-family(options는 나머지 그룹만)"이 남는 그룹이 없는 경우를 침묵. 그때 `…#g1`은 `has_options`가 False라 family 게이트를 통과하고 `options: []`로 POST될 수 있었다.

**판단**: 격리 평가 직후 `add_to_cart`가 `sub_family_index(product_id)`가 있는 id를 family와 같이 `KeyError`로 거절하도록 고치고 테스트를 더했다. sub-family 자체의 모양(옵션 없음)은 그대로다.

**근거**: AC2 「family id로 담으면 delivered에 아무것도 만들지 않는다」.

**여파**: blueprint.md add_to_cart 규칙에 sub-family 거절 한 줄

---
### D005 — 분할된 family의 품절 variant 메시지에는 재고 형제가 나오지 않음

- **태스크**: T010
- **파일**: `examples/delivered/api/delivered_backend.py`
- **시각**: 2026-09-14 19:45
- **상태**: 📌 역류 대기

**맥락**: blueprint "형제 재고 목록은 family(product(variant.variant_of))의 variants에서" + "원 family는 variants=[]"의 결합.

**판단**: variant의 `variant_of`가 부모 id라 분할 후에는 형제 목록이 비어 「none」으로 나온다.

**근거**: 실측 데이터에는 분할 대상이 없어 명세 두 문장의 귀결대로 두었다.

**여파**: mission.md AC4 범위(분할 family 제외) 명시 후보

---

## 트레이드오프 🔀

(없음)
