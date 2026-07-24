from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from typing import Any


CONTAMINATION_POLICY_VERSION = "finsearchcomp_contamination.v2.0"
FINGERPRINT_VERSION = "semantic_fingerprint.v1.0"
EMBEDDING_BACKEND = "local_hashed_word_char_ngram.v1"
EMBEDDING_DIMENSIONS = 8192

DEFAULT_CONTAMINATION_POLICY = {
    "embedding_review_threshold": 0.65,
    "embedding_reject_threshold": 0.85,
    "maximum_review_pairs": 500,
    "minimum_calibration_review_pairs": 50,
    "block_exact_match": True,
    "block_slot_normalized_match": True,
    "block_high_embedding_with_program_match": True,
}

_METRIC_TERMS = {
    "revenue": ("revenue", "sales", "net sales", "营收", "营业收入", "收入"),
    "profitability": (
        "net income",
        "operating income",
        "gross profit",
        "profit",
        "margin",
        "净利润",
        "营业利润",
        "毛利润",
        "利润率",
        "利润",
    ),
    "balance_sheet": (
        "total assets",
        "total liabilities",
        "assets",
        "liabilities",
        "debt",
        "equity",
        "总资产",
        "总负债",
        "资产",
        "负债",
        "债务",
        "权益",
    ),
    "cash_flow": (
        "operating cash flow",
        "cash flow",
        "capital expenditure",
        "经营现金流",
        "现金流",
        "资本开支",
    ),
    "market_price": (
        "closing price",
        "opening price",
        "stock price",
        "price",
        "收盘价",
        "开盘价",
        "股价",
        "价格",
    ),
    "market_value": ("market capitalization", "market cap", "市值"),
    "interest_rate": (
        "interest rate",
        "federal funds rate",
        "yield",
        "利率",
        "收益率",
    ),
    "macro_output": (
        "gross domestic product",
        "industrial production",
        "gdp",
        "国内生产总值",
        "工业增加值",
    ),
    "inflation": ("inflation", "cpi", "ppi", "通货膨胀", "通胀"),
    "employment": (
        "unemployment rate",
        "employment",
        "unemployment",
        "payroll",
        "失业率",
        "就业",
        "失业",
    ),
    "external_sector": (
        "external debt",
        "current account",
        "trade balance",
        "外债",
        "经常账户",
        "贸易差额",
    ),
    "money_and_credit": (
        "money supply",
        "bank credit",
        "loan",
        "货币供应",
        "信贷",
        "贷款",
    ),
    "population": ("population", "newborn", "人口", "新生儿"),
}

_OPERATION_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\b(?:highest|maximum|max|largest|peak)\b|最高|最大|峰值", "<op_argmax>"),
    (r"\b(?:lowest|minimum|min|smallest)\b|最低|最小", "<op_argmin>"),
    (r"\b(?:rank|ranking|top)\b|排名|排序|前\s*<number>", "<op_rank>"),
    (r"\b(?:filter|screen|select those)\b|筛选|过滤", "<op_filter>"),
    (
        r"\b(?:compare|comparison|versus|vs\.?|higher than|lower than)\b|比较|相比|高于|低于",
        "<op_compare>",
    ),
    (r"\b(?:difference|differ|gap)\b|差值|相差|差额", "<op_difference>"),
    (
        r"\b(?:growth|grew|increase|decrease|change)\b|增长|增速|下降|变化",
        "<op_growth>",
    ),
    (r"\b(?:average|mean)\b|平均", "<op_mean>"),
    (r"\b(?:ratio|share|percentage|percent)\b|比率|占比|比例|百分比", "<op_ratio>"),
    (r"\b(?:sum|total combined)\b|合计|总和", "<op_sum>"),
)

_NON_ENTITY_CAPITALIZED = {
    "what",
    "which",
    "when",
    "where",
    "how",
    "from",
    "among",
    "across",
    "between",
    "based",
    "according",
    "calculate",
    "report",
    "identify",
    "find",
    "compare",
    "using",
    "during",
    "in",
    "for",
}


def contamination_policy(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = dict(DEFAULT_CONTAMINATION_POLICY)
    policy.update(overrides or {})
    policy["embedding_review_threshold"] = float(policy["embedding_review_threshold"])
    policy["embedding_reject_threshold"] = float(policy["embedding_reject_threshold"])
    if policy["embedding_review_threshold"] > policy["embedding_reject_threshold"]:
        raise ValueError("embedding review threshold cannot exceed reject threshold")
    policy["maximum_review_pairs"] = max(int(policy["maximum_review_pairs"]), 1)
    policy["minimum_calibration_review_pairs"] = max(
        int(policy["minimum_calibration_review_pairs"]), 0
    )
    return policy


def add_contamination_fingerprints(
    row: dict[str, Any], *, official: bool
) -> dict[str, Any]:
    out = dict(row)
    text = str(row.get("prompt") if official else row.get("question") or "")
    if not text and official:
        text = str(row.get("question") or "")
    skeleton = question_skeleton(text)
    operation_program = operation_program_signature(row)
    slot_signature = slot_normalized_signature(row, skeleton, operation_program)
    out.update(
        {
            "contamination_fingerprint_version": FINGERPRINT_VERSION,
            "question_skeleton": skeleton,
            "question_skeleton_sha256": _hash(skeleton),
            "slot_normalized_signature": slot_signature,
            "slot_normalized_sha256": _hash(slot_signature),
            "operation_program_signature": operation_program,
            "operation_program_sha256": _hash(operation_program),
            "embedding_text": semantic_embedding_text(row, skeleton, operation_program),
        }
    )
    return out


def contamination_report(
    official: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    policy: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    resolved = contamination_policy(policy)
    official_rows = [
        add_contamination_fingerprints(row, official=True) for row in official
    ]
    current_rows = [
        add_contamination_fingerprints(row, official=False) for row in current
    ]
    official_by_exact = _index(official_rows, "normalized_prompt_sha256")
    official_by_skeleton = _index(official_rows, "question_skeleton_sha256")
    official_by_slot = _index(official_rows, "slot_normalized_sha256")
    official_by_program = _index(official_rows, "operation_program_sha256")
    official_vectors = [
        hashed_ngram_embedding(row["embedding_text"]) for row in official_rows
    ]

    review_pairs: list[dict[str, Any]] = []
    nearest_pairs: list[dict[str, Any]] = []
    best_scores: list[float] = []
    exclusions: list[dict[str, Any]] = []
    exact_ids: set[str] = set()
    skeleton_ids: set[str] = set()
    slot_ids: set[str] = set()
    program_ids: set[str] = set()
    embedding_review_ids: set[str] = set()
    embedding_reject_ids: set[str] = set()
    status_counts: Counter[str] = Counter()

    for current_row in current_rows:
        qa_id = str(current_row.get("qa_id") or "")
        exact_matches = official_by_exact.get(
            str(current_row.get("normalized_question_sha256") or ""), []
        )
        skeleton_matches = official_by_skeleton.get(
            current_row["question_skeleton_sha256"], []
        )
        slot_matches = official_by_slot.get(current_row["slot_normalized_sha256"], [])
        program_matches = official_by_program.get(
            current_row["operation_program_sha256"], []
        )
        if exact_matches:
            exact_ids.add(qa_id)
        if skeleton_matches:
            skeleton_ids.add(qa_id)
        if slot_matches:
            slot_ids.add(qa_id)
        if program_matches:
            program_ids.add(qa_id)

        current_vector = hashed_ngram_embedding(current_row["embedding_text"])
        best_index = -1
        best_score = 0.0
        for index, official_vector in enumerate(official_vectors):
            score = cosine_similarity(current_vector, official_vector)
            if score > best_score:
                best_index = index
                best_score = score
        best_official = official_rows[best_index] if best_index >= 0 else {}
        best_program_match = bool(
            best_official
            and best_official.get("operation_program_sha256")
            == current_row.get("operation_program_sha256")
        )
        best_scores.append(best_score)
        if best_score >= resolved["embedding_review_threshold"]:
            embedding_review_ids.add(qa_id)
        if best_score >= resolved["embedding_reject_threshold"]:
            embedding_reject_ids.add(qa_id)

        reasons: list[str] = []
        if exact_matches:
            reasons.append("normalized_exact_match")
        if skeleton_matches:
            reasons.append("question_skeleton_match")
        if slot_matches:
            reasons.append("slot_normalized_match")
        if best_score >= resolved["embedding_review_threshold"]:
            reasons.append("embedding_near_duplicate")
        if best_program_match:
            reasons.append("best_pair_operation_program_match")

        blocked = bool(
            (resolved["block_exact_match"] and exact_matches)
            or (resolved["block_slot_normalized_match"] and slot_matches)
            or (
                resolved["block_high_embedding_with_program_match"]
                and best_program_match
                and best_score >= resolved["embedding_reject_threshold"]
            )
        )
        requires_review = bool(
            not blocked
            and (
                skeleton_matches or best_score >= resolved["embedding_review_threshold"]
            )
        )
        status = (
            "blocked" if blocked else "manual_review" if requires_review else "clear"
        )
        status_counts[status] += 1
        pair = {
            "qa_id": qa_id,
            "status": status,
            "reasons": reasons,
            "similarity": round(best_score, 8),
            "current_question": str(current_row.get("question") or ""),
            "official_item_id": _official_id(best_official),
            "official_prompt": str(
                best_official.get("prompt") or best_official.get("question") or ""
            ),
            "question_skeleton_sha256": current_row["question_skeleton_sha256"],
            "slot_normalized_sha256": current_row["slot_normalized_sha256"],
            "operation_program_sha256": current_row["operation_program_sha256"],
            "operation_program_signature": current_row["operation_program_signature"],
            "manual_review_status": (
                "pending" if status == "manual_review" else "not_applicable"
            ),
        }
        nearest_pairs.append(pair)
        if status != "clear":
            review_pairs.append(pair)
            if blocked:
                exclusions.append(
                    {
                        "qa_id": qa_id,
                        "reason": "benchmark_contamination",
                        "matched_official_item_id": pair["official_item_id"],
                        "signals": reasons,
                        "similarity": pair["similarity"],
                        "training_eligible": False,
                    }
                )

    review_qa_ids = {row["qa_id"] for row in review_pairs}
    nearest_pairs.sort(key=lambda row: (-row["similarity"], row["qa_id"]))
    calibration_target = min(
        resolved["minimum_calibration_review_pairs"], len(current_rows)
    )
    for nearest in nearest_pairs:
        if len(review_pairs) >= calibration_target:
            break
        if nearest["qa_id"] in review_qa_ids:
            continue
        calibration = dict(nearest)
        calibration["status"] = "calibration_review"
        calibration["reasons"] = ["top_embedding_similarity_calibration"]
        calibration["manual_review_status"] = "pending"
        review_pairs.append(calibration)
        review_qa_ids.add(calibration["qa_id"])

    review_pairs.sort(key=lambda row: (-row["similarity"], row["qa_id"]))
    review_pairs = review_pairs[: resolved["maximum_review_pairs"]]
    exclusions.sort(key=lambda row: row["qa_id"])
    training_release_gate = (
        "failed"
        if exclusions
        else "pending_manual_review"
        if review_pairs
        else "passed"
    )
    report = {
        "policy_version": CONTAMINATION_POLICY_VERSION,
        "fingerprint_version": FINGERPRINT_VERSION,
        "embedding_backend": EMBEDDING_BACKEND,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "policy": resolved,
        "official_item_count": len(official_rows),
        "current_item_count": len(current_rows),
        "exact_match_count": len(exact_ids),
        "question_skeleton_match_count": len(skeleton_ids),
        "slot_normalized_match_count": len(slot_ids),
        "operation_program_match_count": len(program_ids),
        "embedding_review_count": len(embedding_review_ids),
        "embedding_reject_threshold_count": len(embedding_reject_ids),
        "embedding_similarity_summary": _similarity_summary(best_scores),
        "blocked_qa_count": len(exclusions),
        "manual_review_qa_count": status_counts["manual_review"],
        "clear_qa_count": status_counts["clear"],
        "status_counts": dict(sorted(status_counts.items())),
        "matched_qa_ids": sorted(exact_ids),
        "blocked_qa_ids": [row["qa_id"] for row in exclusions],
        "manual_review_queue_count": sum(
            row["status"] == "manual_review" for row in review_pairs
        ),
        "calibration_review_count": sum(
            row["status"] == "calibration_review" for row in review_pairs
        ),
        "review_pair_count": len(review_pairs),
        "passed": not exclusions,
        "training_release_gate": training_release_gate,
        "training_release_ready": training_release_gate == "passed",
    }
    return report, review_pairs, exclusions


def question_skeleton(text: str) -> str:
    value = _normalize_surface(text)
    value = _mask_time(value)
    value = re.sub(
        r"\b(?:usd|cny|rmb|eur|jpy|hkd|gbp|dollar|dollars|yuan)\b|美元|人民币|欧元|日元|港元",
        " <currency> ",
        value,
        flags=re.IGNORECASE,
    )
    value = _mask_entities(value)
    value = value.casefold()
    value = _mask_metrics(value)
    value = re.sub(
        r"\b(?:usd|cny|rmb|eur|jpy|hkd|gbp|dollar|dollars|yuan)\b|美元|人民币|欧元|日元|港元",
        " <currency> ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b(?:million|billion|thousand|percent|percentage points?)\b|百万|十亿|千|亿元|万元|百分比|百分点",
        " <unit> ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"[-+]?\d+(?:\.\d+)?%?", " <number> ", value)
    for pattern, replacement in _OPERATION_REPLACEMENTS:
        value = re.sub(pattern, f" {replacement} ", value, flags=re.IGNORECASE)
    return _normalize_text(value)


def operation_program_signature(row: dict[str, Any]) -> str:
    operations = _string_list(row.get("operation_families"))
    if not operations:
        operations = ["lookup"]
    payload = {
        "operations": operations,
        "answer_type": str(row.get("answer_type") or "unknown"),
        "scope_required": bool(
            row.get("requires_scope_completeness")
            or (row.get("structural_features") or {}).get("requires_scope_completeness")
        ),
    }
    return _stable_json(payload)


def slot_normalized_signature(
    row: dict[str, Any], skeleton: str, operation_program: str
) -> str:
    payload = {
        "question_skeleton": skeleton,
        "metric_families": sorted(_string_list(row.get("metric_families"))),
        "operation_program": operation_program,
        "answer_type": str(row.get("answer_type") or "unknown"),
        "time_basis": str(row.get("time_basis") or "unknown"),
        "frequency": str(row.get("frequency") or "unknown"),
    }
    return _stable_json(payload)


def semantic_embedding_text(
    row: dict[str, Any], skeleton: str, operation_program: str
) -> str:
    structural = [
        *(
            f"metric_{value}"
            for value in sorted(_string_list(row.get("metric_families")))
        ),
        *(
            f"operation_{value}"
            for value in _string_list(row.get("operation_families"))
        ),
        f"answer_{row.get('answer_type') or 'unknown'}",
        f"time_{row.get('time_basis') or 'unknown'}",
        f"frequency_{row.get('frequency') or 'unknown'}",
        f"period_{_period_bucket(row.get('period_count'))}",
        f"program_{_hash(operation_program)}",
    ]
    return " ".join([skeleton, *structural])


def hashed_ngram_embedding(text: str) -> dict[int, float]:
    normalized = _normalize_text(text)
    tokens = re.findall(r"<[^>]+>|[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
    features: Counter[tuple[str, str]] = Counter()
    for size in (1, 2, 3):
        for index in range(max(len(tokens) - size + 1, 0)):
            features[(f"w{size}", " ".join(tokens[index : index + size]))] += 1.0
    compact = re.sub(r"\s+", "", normalized)
    for size, weight in ((3, 0.35), (4, 0.30), (5, 0.25)):
        for index in range(max(len(compact) - size + 1, 0)):
            features[(f"c{size}", compact[index : index + size])] += weight
    vector: defaultdict[int, float] = defaultdict(float)
    for (kind, feature), value in features.items():
        digest = hashlib.sha1(f"{kind}:{feature}".encode("utf-8")).hexdigest()
        vector[int(digest[:8], 16) % EMBEDDING_DIMENSIONS] += float(value)
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if not norm:
        return {}
    return {index: value / norm for index, value in vector.items()}


def cosine_similarity(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(index, 0.0) for index, value in left.items())


def _similarity_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "min": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "max": 0.0,
        }
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        index = min(round((len(ordered) - 1) * fraction), len(ordered) - 1)
        return round(float(ordered[index]), 8)

    return {
        "min": round(float(ordered[0]), 8),
        "p50": percentile(0.50),
        "p90": percentile(0.90),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
        "max": round(float(ordered[-1]), 8),
    }


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    result: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = str(row.get(key) or "")
        if value:
            result[value].append(row)
    return dict(result)


def _mask_time(value: str) -> str:
    value = re.sub(
        r"\b(?:fy|fiscal\s+year|calendar\s+year)?\s*(?:19|20)\d{2}\s*(?:q[1-4])?\b",
        " <time> ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\bq[1-4]\s*(?:19|20)?\d{0,4}\b", " <time> ", value, flags=re.IGNORECASE
    )
    value = re.sub(r"\b\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?\b", " <time> ", value)
    value = re.sub(
        r"(?:19|20)\d{2}\s*年(?:第?[一二三四1234]\s*季度)?", " <time> ", value
    )
    value = re.sub(r"第?[一二三四1234]\s*季度", " <time> ", value)
    return value


def _mask_entities(value: str) -> str:
    value = re.sub(
        r"[\u4e00-\u9fffA-Za-z0-9·]{2,30}(?:股份有限公司|有限公司|公司|集团|银行|证券|保险)",
        " <entity> ",
        value,
    )
    value = re.sub(
        r"\b(?:china|united states|u\.?s\.?a?|japan|germany|france|india|hong kong|macao|macau|taiwan)\b|中国|美国|日本|德国|法国|印度|香港|澳门|台湾",
        " <entity> ",
        value,
        flags=re.IGNORECASE,
    )

    def replace_capitalized(match: re.Match[str]) -> str:
        phrase = match.group(0)
        words = re.findall(r"[A-Za-z][A-Za-z0-9&.'-]*", phrase)
        if words and all(word.casefold() in _NON_ENTITY_CAPITALIZED for word in words):
            return phrase
        return " <entity> "

    value = re.sub(
        r"\b(?:[A-Z][A-Za-z0-9&.'-]*(?:\s+|$)){1,5}",
        replace_capitalized,
        value,
    )
    value = re.sub(r"\b[A-Z]{1,6}(?:\.[A-Z])?\b", " <entity> ", value)
    return value


def _mask_metrics(value: str) -> str:
    for terms in _METRIC_TERMS.values():
        for term in sorted(terms, key=len, reverse=True):
            value = re.sub(re.escape(term), " <metric> ", value, flags=re.IGNORECASE)
    return value


def _period_bucket(value: Any) -> str:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        count = 0
    if count <= 1:
        return "single"
    if count == 2:
        return "two_period"
    if count <= 5:
        return "short_window"
    if count <= 12:
        return "medium_window"
    return "long_window"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                import json

                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if str(item).strip()]
            except (TypeError, ValueError):
                pass
        return [stripped]
    try:
        return [str(item) for item in value if str(item).strip()]
    except TypeError:
        return [str(value)]


def _official_id(row: dict[str, Any]) -> str:
    return str(
        row.get("item_id") or row.get("official_item_id") or row.get("prompt_id") or ""
    )


def _normalize_surface(value: str) -> str:
    value = value.replace("’", "'").replace("–", "-").replace("—", "-")
    value = re.sub(r"[^\w\u4e00-\u9fff<>%+.'/-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _normalize_text(value: str) -> str:
    return _normalize_surface(value).casefold()


def _stable_json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
