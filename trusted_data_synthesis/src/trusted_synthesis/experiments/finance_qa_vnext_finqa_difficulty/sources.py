"""Uniform numeric indexing of the original closed text/table; no gold-role labels."""

from __future__ import annotations

import re
from fractions import Fraction

from .census import NUMBER


def numeric_spans(text):
    result = []
    previous = None
    for match in NUMBER.finditer(text):
        token = match.group()
        value = Fraction(token.rstrip("%").replace(",", ""))
        if token.endswith("%"):
            value /= 100
        # FinQA normalizes accounting negatives as '-6.3 ( 6.3 )'.
        # The parenthesized repeat is not a second positive financial quantity.
        if previous and previous["value"].startswith("-") and value == -Fraction(previous["value"]):
            between = text[previous["end"] : match.start()]
            if re.fullmatch(r"\s*\(\s*", between) and re.match(r"\s*\)", text[match.end() :]):
                continue
        item = {
            "index": len(result),
            "start": match.start(),
            "end": match.end(),
            "token": token,
            "value": str(value),
        }
        result.append(item)
        previous = item
    return result


def catalog(entry):
    segments, facts = {}, {}
    for row_index, row in enumerate(entry["table"]):
        for col_index, cell in enumerate(row):
            key = f"t{row_index}c{col_index}"
            segments[key] = {
                "locator": ["table", row_index, col_index],
                "text": cell,
                "row_label": row[0],
                "column_label": entry["table"][0][col_index]
                if col_index < len(entry["table"][0])
                else None,
            }
    for field, prefix in (("pre_text", "p"), ("post_text", "q")):
        for index, text in enumerate(entry[field]):
            segments[f"{prefix}{index}"] = {"locator": [field, index], "text": text}
    for key, segment in segments.items():
        for span in numeric_spans(segment["text"]):
            fact_id = f"source:{key}n{span['index']}"
            facts[fact_id] = {"id": fact_id, "segment": key, **span}
    return segments, facts


def select(facts, segment, token):
    matches = [
        key for key, fact in facts.items() if fact["segment"] == segment and fact["token"] == token
    ]
    if len(matches) != 1:
        raise ValueError(f"Ambiguous/missing independently reviewed binding: {segment} {token}")
    return matches[0]


def view(entry, selected, condition):
    segments, facts = catalog(entry)
    if condition == "F":
        return {
            "original_source": {key: entry[key] for key in ("table", "pre_text", "post_text")},
            "numeric_catalog": list(facts.values()),
            "indexing": (
                "source:tROWcCOLUMNnNUMBER, source:pPRE_PARAGRAPHnNUMBER, "
                "source:qPOST_PARAGRAPHnNUMBER; zero based. All numeric spans are "
                "uniformly indexed, including years and OCR artifacts. Indexing does not "
                "certify relevance or units."
            ),
        }
    if condition != "E":
        raise ValueError("unknown condition")
    return {
        "related_source_fragments": {
            key: segments[key] for key in sorted({facts[k]["segment"] for k in selected})
        },
        "numeric_catalog": [facts[key] for key in sorted(selected)],
        "indexing": (
            "Prelocated relevant numeric evidence with original offsets and necessary "
            "source context; no arithmetic plan. Same numeric IDs and values as the "
            "complete source."
        ),
    }
