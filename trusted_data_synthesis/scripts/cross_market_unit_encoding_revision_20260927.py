"""Unit-only cache representation repair after the preserved phase04 run.

Do not change header selection, semantic guards, years, signs or original words.
Explicit scale evidence outranks currency-only declarations, not explicit 元.
No files, PDF, parser, network, API, model or qualification execution here.
"""

import re
import types

import cross_market_header_binding_revision_20260926 as header

SCRIPT = "trusted_data_synthesis/scripts/cross_market_unit_encoding_revision_20260927.py"
VERSION = "cross_market_unit_encoding_revision_05.v1"
CURRENCY = r"(?:rmb|cny|hkd|usd|hk\$|us\$)"
DECLARATION = r"(?:(?:allamounts)?in|expressedin)"
CHINESE_CURRENCY = r"(?:人民币|人民幣|港币|港幣|美元)"
CHINESE_UNIT = re.compile(
    r"(?:单位|單位)[:：]?(?:" + CHINESE_CURRENCY + r")?"
    r"(?P<unit>百万元|百萬元|万元|萬元|千元|元)"
    r"[,，;；]?(?:币种|幣種)[:：]?" + CHINESE_CURRENCY
)
CHINESE_SCALES = {
    "元": 1,
    "千元": 1000,
    "万元": 10000,
    "萬元": 10000,
    "百万元": 1000000,
    "百萬元": 1000000,
}
EXPLICIT_ENGLISH = re.compile(
    r"(?:" + DECLARATION + r")?" + CURRENCY + r"'?(?P<unit>millions?|thousands?|m|mn)"
)
CURRENCY_ONLY = re.compile(DECLARATION + CURRENCY)


def unit_token(text):
    return header.compact(text).strip("()（）,:：")


def currency_only_scale(text):
    """Retain original base-unit convention only as a conditional fallback."""
    return 1 if CURRENCY_ONLY.fullmatch(unit_token(text)) else None


def explicit_unit_scale(text):
    token = unit_token(text)
    # Crucially, old 'in RMB' is currency evidence, not an explicit scale 1
    # competing with a separately printed thousand/million amount unit.
    if CURRENCY_ONLY.fullmatch(token):
        return None
    chinese = CHINESE_UNIT.fullmatch(token)
    if chinese:
        return CHINESE_SCALES[chinese.group("unit")]
    english = EXPLICIT_ENGLISH.fullmatch(token)
    if english:
        return 1000000 if english.group("unit") in {"m", "mn", "million", "millions"} else 1000
    return header.unit_scale(text)


def clone_word_collector(decoder):
    """Reuse exact six-word/12pt code with private globals, never mutate header."""
    source = header.unit_witnesses
    private = dict(source.__globals__)
    private["unit_scale"] = decoder
    clone = types.FunctionType(
        source.__code__, private, source.__name__, source.__defaults__, source.__closure__
    )
    clone.__kwdefaults__ = source.__kwdefaults__
    return clone


explicit_witnesses = clone_word_collector(explicit_unit_scale)
currency_only_witnesses = clone_word_collector(currency_only_scale)


def unit_certificate(candidate, lines):
    text = "\n".join(line["text"] for line in lines)
    normalized = header.compact(text)
    currencies = {
        currency for currency, regex in header.core.CURRENCY.items() if regex.search(normalized)
    }
    header.core.fail(len(currencies) == 1, "geometry_currency_missing_or_multiple")
    explicit = [w for line in lines for w in explicit_witnesses(line)]
    fallback = [w for line in lines for w in currency_only_witnesses(line)]
    witnesses = explicit if explicit else fallback
    scales = {w["scale"] for w in witnesses}
    header.core.fail(len(scales) == 1, "geometry_native_scale_unresolved")
    header.core.fail(
        not header.core.previous.COMPLEX_SUBCOLUMNS.search(normalized),
        "geometry_group_company_or_semantic_subcolumns_unresolved",
    )
    return dict(
        currency=next(iter(currencies)),
        scale=next(iter(scales)),
        original_header=text,
        source="original_header_unit_encoding_revision_05",
        unit_token_witnesses=witnesses,
        above_title_units_used=False,
        unit_encoding_revision_evidence=dict(
            version=VERSION,
            explicit_unit_witnesses=explicit,
            currency_only_declaration_witnesses=fallback,
            currency_only_base_fallback_used=bool(fallback) and not explicit,
            currency_only_base_fallback_suppressed=bool(fallback) and bool(explicit),
            explicit_base_unit_is_not_suppressed=True,
            exact_whole_compound_Chinese_grammar=True,
            maximum_original_words_per_witness=header.MAX_UNIT_WORDS,
            maximum_adjacent_word_gap_points=header.MAX_UNIT_GAP,
            original_words_positions_currency_sign_period_unchanged=True,
        ),
    )


def install_unit_namespace(namespace):
    header.core.fail(
        namespace["unit_certificate"].__code__ is header.unit_certificate.__code__
        and header.MAX_UNIT_WORDS == 6
        and header.MAX_UNIT_GAP == 12,
        "unit05_exact_frozen_header_unit_parent",
    )
    namespace["unit_certificate"] = unit_certificate
    return namespace
