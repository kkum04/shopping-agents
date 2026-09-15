# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""delivered's option groups and options as the framework's family and variants. A
Smart Store product with options answers two extra routes: the option groups (a colour,
a size, or a free-text field such as an engraving) and the options, one row per
purchasable combination with its own price and stock. Each row becomes a variant whose
id is the family's id plus ``#`` and the option id; a free-text group is kept on the
family as an attribute, since the cart cannot carry the text. The functions here are
pure; ``DeliveredStorefront`` fetches and remembers."""

from __future__ import annotations

from typing import Any

from shopping_agent import Product, ProductDetails

MAX_VARIANTS = 60
VARIANT_SEPARATOR = "#"
SUB_FAMILY_PREFIX = "g"
CHOICE_GROUP_TYPES = frozenset({"COMBINATION", "SIMPLE"})
TEXT_GROUP_TYPE = "TEXT"
TEXT_OPTIONS_ATTRIBUTE = "text_options"
OPTION_ID_ATTRIBUTE = "option_id"
VARIANT_FAMILIES_ATTRIBUTE = "variant_families"

_VARIANT_DROPS = {"variants", "specs", "long_description", "review_highlights"}


def variant_id_of(family_id: str, option_id: int | str) -> str:
    return f"{family_id}{VARIANT_SEPARATOR}{option_id}"


def split_variant_id(product_id: str) -> tuple[str, str | None]:
    """``("smart_store:1", "137750")`` for a variant id; the option id is None for a
    family or a sub-family id."""
    base, _, suffix = product_id.partition(VARIANT_SEPARATOR)
    return base, (suffix if suffix.isdigit() else None)


def sub_family_index(product_id: str) -> int | None:
    _, _, suffix = product_id.partition(VARIANT_SEPARATOR)
    if suffix.startswith(SUB_FAMILY_PREFIX) and suffix[len(SUB_FAMILY_PREFIX) :].isdigit():
        return int(suffix[len(SUB_FAMILY_PREFIX) :])
    return None


def _group_name(group: dict[str, Any]) -> str:
    names = group.get("productOptionGroupName") or {}
    return str(names.get("productOptionGroupName") or names.get("productOptionGroupNameEn") or "")


def group_names(groups: list[dict[str, Any]]) -> dict[int, str]:
    """Group id to Korean name for the groups a row can name; text groups are left out."""
    return {
        int(group["productOptionGroupId"]): _group_name(group)
        for group in groups
        if group.get("productOptionGroupType") in CHOICE_GROUP_TYPES and _group_name(group)
    }


def text_option_groups(groups: list[dict[str, Any]]) -> list[str]:
    return [
        _group_name(group)
        for group in groups
        if group.get("productOptionGroupType") == TEXT_GROUP_TYPE and _group_name(group)
    ]


def _row_values(row: dict[str, Any], names: dict[int, str]) -> dict[str, str] | None:
    values: dict[str, str] = {}
    for entry in row.get("productOptionName") or []:
        group_id = entry.get("productOptionGroupId")
        if group_id not in names:
            return None
        values[names[group_id]] = str(entry.get("productOptionName") or "").strip()
    return values if values and len(values) == len(names) else None


def _normalized(value: str) -> str:
    return " ".join(value.split())


def family_with_variants(
    detail: ProductDetails, groups: list[dict[str, Any]], options: list[dict[str, Any]]
) -> ProductDetails:
    """The detail record as a family with one variant per option row; plain when the
    rows name no known group."""
    names = group_names(groups)
    text_groups = text_option_groups(groups)
    attributes = dict(detail.attributes)
    if text_groups:
        attributes[TEXT_OPTIONS_ATTRIBUTE] = ", ".join(text_groups)
    base = detail.model_dump(exclude=_VARIANT_DROPS)
    values_by_group: dict[str, list[str]] = {name: [] for name in names.values()}
    variants: list[Product] = []
    for row in options:
        values = _row_values(row, names)
        option_id = row.get("optionId")
        if values is None or option_id is None:
            continue
        for group, value in values.items():
            if value not in values_by_group[group]:
                values_by_group[group].append(value)
        price = row.get("optionPriceKrw")
        stock = row.get("stockQuantity")
        variants.append(
            Product.model_validate(
                base
                | {
                    "product_id": variant_id_of(detail.product_id, option_id),
                    "price": float(price) if isinstance(price, (int, float)) else detail.price,
                    "in_stock": isinstance(stock, (int, float)) and stock > 0,
                    "options": {},
                    "option_values": values,
                    "variant_of": detail.product_id,
                    "attributes": attributes | {OPTION_ID_ATTRIBUTE: str(option_id)},
                }
            )
        )
    if not variants:
        return detail.model_copy(update={"attributes": attributes})
    return detail.model_copy(
        update={
            "options": {group: values for group, values in values_by_group.items() if values},
            "variants": variants,
            "attributes": attributes,
            **_family_figures(variants),
        }
    )


def _family_figures(variants: list[Product]) -> dict[str, Any]:
    in_stock = [variant for variant in variants if variant.in_stock]
    priced = in_stock or variants
    return {"price": min(variant.price for variant in priced), "in_stock": bool(in_stock)}


def variant_for_option_values(
    groups: list[dict[str, Any]],
    options: list[dict[str, Any]],
    chosen: list[tuple[int | None, str]],
) -> int | None:
    """The option id of the row whose entries carry exactly these ``(group id, value)``
    pairs; a value matches the Korean or the English name, and a missing group id
    matches any group. Cart lines name their choices this way."""
    known = group_names(groups)
    wanted = [(group_id, _normalized(value)) for group_id, value in chosen if value]
    if not wanted:
        return None
    for row in options:
        entries = [
            entry
            for entry in row.get("productOptionName") or []
            if entry.get("productOptionGroupId") in known
        ]
        if len(entries) != len(wanted):
            continue
        if all(_entry_matches(entries, group_id, value) for group_id, value in wanted):
            option_id = row.get("optionId")
            return int(option_id) if option_id is not None else None
    return None


def _entry_matches(entries: list[dict[str, Any]], group_id: int | None, value: str) -> bool:
    for entry in entries:
        if group_id is not None and entry.get("productOptionGroupId") != group_id:
            continue
        names = {
            _normalized(str(entry.get(key) or ""))
            for key in ("productOptionName", "productOptionNameEn")
        }
        if value in names:
            return True
    return False


def split_families(family: ProductDetails) -> list[ProductDetails]:
    """A family with more rows than ``MAX_VARIANTS`` becomes a parent that lists its
    sub-families plus one sub-family per value of the first group; a small family is
    returned as it is."""
    if len(family.variants) <= MAX_VARIANTS or not family.options:
        return [family]
    first_group, first_values = next(iter(family.options.items()))
    rest = {group: values for group, values in family.options.items() if group != first_group}
    pieces: list[ProductDetails] = []
    labels: list[str] = []
    for index, value in enumerate(first_values, start=1):
        members = [v for v in family.variants if v.option_values.get(first_group) == value]
        if not members:
            continue
        sub_id = f"{family.product_id}{VARIANT_SEPARATOR}{SUB_FAMILY_PREFIX}{index}"
        labels.append(f"{sub_id} {value}")
        pieces.append(
            family.model_copy(
                update={
                    "product_id": sub_id,
                    "options": {
                        group: [
                            x
                            for x in values
                            if any(m.option_values.get(group) == x for m in members)
                        ]
                        for group, values in rest.items()
                    },
                    "variants": members,
                    "attributes": family.attributes | {first_group: value},
                    **_family_figures(members),
                }
            )
        )
    parent = family.model_copy(
        update={
            "variants": [],
            "attributes": family.attributes | {VARIANT_FAMILIES_ATTRIBUTE: ", ".join(labels)},
        }
    )
    return [parent, *pieces]
