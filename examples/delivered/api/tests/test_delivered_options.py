# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""delivered's option groups and options as the framework's family and variants. The
recorded answers are the production guest API's (2026-09-14): a two-colour racket set
(one COMBINATION group) and a pouch with a colour and size COMBINATION plus a TEXT
group for an engraving."""

from __future__ import annotations

import json
from pathlib import Path

from delivered.api.delivered_cart import split_product_id
from delivered.api.delivered_options import (
    MAX_VARIANTS,
    family_with_variants,
    group_names,
    split_families,
    split_variant_id,
    sub_family_index,
    text_option_groups,
    variant_for_option_values,
    variant_id_of,
)
from shopping_agent import ProductDetails

FIXTURES = Path(__file__).parent / "fixtures"
RACKET = "11314403854"
POUCH = "10631022673"


def recorded(name: str, pid: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())[pid]["data"]


def detail(pid: str, title: str = "상품", price: float = 10000.0) -> ProductDetails:
    return ProductDetails.model_validate(
        {
            "product_id": f"smart_store:{pid}",
            "title": title,
            "price": price,
            "currency": "KRW",
            "image_url": "https://img.test/x.jpg",
            "attributes": {
                "market": "스마트스토어",
                "product_url": f"https://smartstore.naver.com/main/products/{pid}",
            },
            "specs": {"판매 페이지": "https://x"},
        }
    )


def test_variant_ids_round_trip_and_the_market_id_helper_ignores_the_suffix():
    assert variant_id_of("smart_store:1", 137750) == "smart_store:1#137750"
    assert split_variant_id("smart_store:1#137750") == ("smart_store:1", "137750")
    assert split_variant_id("smart_store:1") == ("smart_store:1", None)
    assert split_variant_id("smart_store:1#g2") == ("smart_store:1", None)
    assert sub_family_index("smart_store:1#g2") == 2
    assert sub_family_index("smart_store:1#137750") is None
    assert split_product_id("smart_store:1#137750") == ("SMART_STORE", "1")


def test_group_names_keep_choice_groups_and_name_text_groups_apart():
    groups = recorded("smartstore-option-groups.json", POUCH)
    assert group_names(groups) == {
        17745: "색상(각인 x 선택시 기본제품으로 발송됩니다)",
        17746: "사이즈",
    }
    assert text_option_groups(groups) == ["각인X:없음 / 각인O:TEXT를 입력"]
    assert text_option_groups(recorded("smartstore-option-groups.json", RACKET)) == []


def test_a_one_group_product_becomes_a_family_with_one_variant_per_row():
    family = family_with_variants(
        detail(RACKET, "라켓 세트", 22200.0),
        recorded("smartstore-option-groups.json", RACKET),
        recorded("smartstore-options.json", RACKET),
    )
    assert family.options == {"색상": ["레드블랙", "화이트"]}
    assert family.has_options and family.in_stock and family.price == 22200.0
    assert [v.product_id for v in family.variants] == [
        f"smart_store:{RACKET}#137750",
        f"smart_store:{RACKET}#137751",
    ]
    red = family.variants[0]
    assert red.option_values == {"색상": "레드블랙"}
    assert red.variant_of == family.product_id
    assert red.price == 22200.0 and red.in_stock is True
    assert red.title == "라켓 세트" and red.image_url == family.image_url
    assert red.attributes["option_id"] == "137750"
    assert "text_options" not in family.attributes


def test_a_text_group_is_kept_as_an_attribute_and_never_a_variant_key():
    family = family_with_variants(
        detail(POUCH, "파우치", 26000.0),
        recorded("smartstore-option-groups.json", POUCH),
        recorded("smartstore-options.json", POUCH),
    )
    assert set(family.options) == {"색상(각인 x 선택시 기본제품으로 발송됩니다)", "사이즈"}
    assert family.attributes["text_options"] == "각인X:없음 / 각인O:TEXT를 입력"
    assert len(family.variants) == 12
    small = next(v for v in family.variants if v.option_values.get("사이즈") == "S")
    assert set(small.option_values) == set(family.options)
    assert small.price == 18900.0
    assert family.price == min(v.price for v in family.variants if v.in_stock)


def test_sold_out_rows_are_variants_out_of_stock_and_drive_the_family_price():
    options = recorded("smartstore-options.json", RACKET)
    options[0] = {**options[0], "stockQuantity": 0, "optionPriceKrw": 1000.0}
    family = family_with_variants(
        detail(RACKET), recorded("smartstore-option-groups.json", RACKET), options
    )
    assert family.variants[0].in_stock is False
    assert family.price == 22200.0 and family.in_stock is True
    options[1] = {**options[1], "stockQuantity": 0}
    family = family_with_variants(
        detail(RACKET), recorded("smartstore-option-groups.json", RACKET), options
    )
    assert family.in_stock is False and family.price == 1000.0


def test_no_rows_or_unknown_groups_leave_the_product_plain():
    plain = family_with_variants(detail(RACKET), [], [])
    assert not plain.has_options and plain.variants == []
    stray = [
        {
            "optionId": 1,
            "productOptionName": [{"productOptionGroupId": 999, "productOptionName": "x"}],
            "optionPriceKrw": 1,
            "stockQuantity": 1,
        }
    ]
    plain = family_with_variants(
        detail(RACKET), recorded("smartstore-option-groups.json", RACKET), stray
    )
    assert not plain.has_options and plain.variants == []


def test_variants_are_found_by_group_id_and_korean_or_english_values():
    options = recorded("smartstore-options.json", POUCH)
    groups = recorded("smartstore-option-groups.json", POUCH)
    assert (
        variant_for_option_values(groups, options, [(17745, "레드(각인 x)"), (17746, " M ")])
        == 134496
    )
    assert (
        variant_for_option_values(groups, options, [(None, "레드(각인 x)"), (None, "M")]) == 134496
    )
    assert (
        variant_for_option_values(groups, options, [(17745, "Red (with engraving)"), (17746, "M")])
        == 134496
    )
    assert variant_for_option_values(groups, options, [(None, "M")]) is None
    assert variant_for_option_values(groups, options, [(17745, "없는색"), (17746, "M")]) is None
    assert variant_for_option_values(groups, options, []) is None


def synthetic(rows: int) -> tuple[list[dict], list[dict]]:
    groups = [
        {
            "productOptionGroupId": 1,
            "productOptionGroupType": "COMBINATION",
            "productOptionGroupName": {
                "productOptionGroupName": "색상",
                "productOptionGroupNameEn": "Color",
            },
        },
        {
            "productOptionGroupId": 2,
            "productOptionGroupType": "COMBINATION",
            "productOptionGroupName": {
                "productOptionGroupName": "사이즈",
                "productOptionGroupNameEn": "Size",
            },
        },
    ]
    options = []
    for index in range(rows):
        colour, size = f"C{index % 7}", f"S{index // 7}"
        options.append(
            {
                "optionId": 1000 + index,
                "productOptionName": [
                    {
                        "productOptionGroupId": 1,
                        "productOptionName": colour,
                        "productOptionNameEn": colour,
                    },
                    {
                        "productOptionGroupId": 2,
                        "productOptionName": size,
                        "productOptionNameEn": size,
                    },
                ],
                "optionPriceKrw": 5000.0 + index,
                "stockQuantity": 3,
            }
        )
    return groups, options


def test_small_families_are_left_whole():
    groups, options = synthetic(MAX_VARIANTS)
    family = family_with_variants(detail("1"), groups, options)
    assert split_families(family) == [family]


def test_large_families_split_by_the_first_group_value():
    groups, options = synthetic(MAX_VARIANTS + 3)
    family = family_with_variants(detail("1"), groups, options)
    pieces = split_families(family)
    parent, subs = pieces[0], pieces[1:]
    assert parent.product_id == "smart_store:1" and parent.variants == [] and parent.has_options
    assert "smart_store:1#g1" in parent.attributes["variant_families"]
    assert [s.product_id for s in subs] == [f"smart_store:1#g{n}" for n in range(1, 8)]
    first = subs[0]
    assert (
        first.attributes["색상"] == "C0"
        and "색상" not in first.options
        and "사이즈" in first.options
    )
    assert all(len(s.variants) <= MAX_VARIANTS for s in subs)
    assert sum(len(s.variants) for s in subs) == MAX_VARIANTS + 3
    assert all(v.variant_of == "smart_store:1" for s in subs for v in s.variants)
