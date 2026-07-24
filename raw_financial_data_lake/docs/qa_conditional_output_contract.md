# Conditional QA Output Contract

## Purpose

Question completeness and output uniformity are separate concerns. Every QA must specify enough information to be graded, but not every answer should request two decimal places or use the same closing sentence.

New QA builds use `conditional_output_contract.v1`. Existing released builds retain their pinned generator and rubric contracts.

## Contract classes

| Contract type | Output rule |
|---|---|
| `monetary_numeric` | Use the requested currency/unit and deterministically select 0, 1, or 2 decimal places. |
| `percentage_numeric` | Use percent and select 1 or 2 decimal places. |
| `numeric` | Use the metric unit and select 1 or 2 decimal places. |
| `exact_integer` | Return an exact integer without a decimal-place requirement. |
| `period_and_value` | Require a compatible period format plus the value contract. |
| `entity_only` | Return only the entity name. |
| `entity_and_value` | Return the entity name and associated value. |
| `structured_table` | Return the complete table in the required order; no global decimal rule is imposed. |

Period formatting is inferred from the answer and time basis:

- full dates: `YYYY-MM-DD`;
- monthly observations: `YYYY-MM`;
- fiscal periods: fiscal-year notation;
- calendar periods: calendar-year notation.

## Determinism and diversity

Decimal precision and instruction style are selected from registered choices using the stable candidate ID. The same candidate therefore receives the same contract across thread schedules and reruns, while the full build covers multiple precision and phrasing variants.

Registered instruction styles are `direct`, `compact`, and `formal`. All retain parser-critical anchors for units, precision, table completeness, ordering, period format, and entity output.

## Shared contract across the pipeline

A single output-contract object is used by:

1. canonical question construction;
2. protected LLM rewriting;
3. standard answer-text formatting;
4. rubric construction;
5. independent question reparse;
6. final output-contract verification.

The selected contract is stored in `qa_samples.source_metadata.output_contract`.

## Tolerance policy

When decimal precision is requested, the rubric adds a display tolerance equal to half of the least significant displayed unit:

| Decimal places | Display absolute tolerance |
|---:|---:|
| 0 | 0.5 |
| 1 | 0.05 |
| 2 | 0.005 |

The rounding mode is `half_up`. Existing stricter tolerances are widened only where a rounded display answer would otherwise be rejected. Structural requirements, entity identity, period identity, ranking order, and scope completeness are unaffected.

## Profile policy

Both DeepSeek production profiles enable:

```json
{
  "version": "conditional_output_contract.v1",
  "mode": "conditional",
  "monetary_decimal_places": [0, 1, 2],
  "percentage_decimal_places": [1, 2],
  "numeric_decimal_places": [1, 2],
  "instruction_styles": ["direct", "compact", "formal"]
}
```

Fixed `decimal_places: 2` is no longer present in those profiles.
