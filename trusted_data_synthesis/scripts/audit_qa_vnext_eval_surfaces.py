"""Independent saved-base audit of wording overlays, not a new source/QA audit.

Only the standard library is used. This parser consumes original public
contracts and actual saved words; it never imports the producer guard, renderer,
private reference, financial executor, model provider or tokenizer.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SEP = "\n\nActual comparison periods (inclusive source dates):"
VERSION = "evaluation_surface_rewrite.v1"
PUBLIC_SYSTEM_PROMPT = (
    "Rewrite the protected financial question template under the supplied contract. "
    "Return only its exact JSON output schema with one or two candidates in preference order. "
    "Each candidate has only rewrite_version and question_template. Preserve every required "
    "placeholder exactly once and put the output_instruction placeholder last. Preserve the "
    "specified operation: signed current-minus-previous difference, positive-previous-base "
    "percentage change, arithmetic mean over all three comparison periods, or primary maximum "
    "selection followed by secondary lookup in that same period. Use only the permitted wording. "
    "Do not invent literal numbers, companies, metric names, period labels, source values, "
    "answers, explanations, extra operations, or alternative source definitions."
)
PARENT_ID = "manifest:90ebc575be3e1c825edb598a937677e0bd83c49cd43c29f35cfe67f543055407"
OLD_AUDIT_ID = "manifest:72c5120253e04a0d6c5c6e806b2b5b59a223f99b4789e70acc5c60eb676639af"
PUBLIC_KEYS = {
    "question",
    "period_contract",
    "source_document",
    "quantity_contract",
    "source_policy",
    "tool_contract",
}
QUOTAS = {
    "dev": {"dual_sufficient": 60, "composition_required": 60, "other_financial": 60},
    "confirm": {"dual_sufficient": 240, "composition_required": 240, "other_financial": 240},
}
METRICS = {
    "revenue": "Revenue",
    "gross_profit": "Gross Profit",
    "net_income": "Net Income",
    "operating_income": "Operating Income",
    "net_cash_provided_by_used_in_operating_activities": (
        "Net Cash Provided by Used in Operating Activities"
    ),
    "cash_and_cash_equivalents": "Cash and Cash Equivalents",
    "cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents": (
        "Cash, Cash Equivalents, Restricted Cash and Restricted Cash Equivalents"
    ),
}


def require(value, code):
    if not value:
        raise ValueError(code)


def encode(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def check_record(value):
    kind, actual = value["id"].split(":", 1)
    require(
        value["schema_version"] == "finance_qa_vnext_task_build.v1." + kind,
        "content-addressed record schema",
    )
    require(
        actual == digest(encode({key: item for key, item in value.items() if key != "id"})),
        "content-addressed record SHA",
    )


def safe(root, name):
    name = Path(name)
    require(not name.is_absolute() and ".." not in name.parts, "relative audit member")
    path = root / name
    for item in (path, *path.parents):
        if item == root:
            break
        require(not item.is_symlink(), "no symlink source or member")
    require(path.resolve().is_relative_to(root), "member inside pinned root")
    return path


class Pinned:
    def __init__(self, root, directory, expected_id=None, expected_sha=None):
        self.root = Path(root).resolve()
        self.directory = safe(self.root, directory)
        raw = safe(self.directory, "manifest.json").read_bytes()
        self.manifest_sha = digest(raw)
        self.manifest = json.loads(raw)
        check_record(self.manifest)
        require(expected_id is None or self.manifest["id"] == expected_id, "manifest identity pin")
        require(
            expected_sha is None or self.manifest_sha == expected_sha, "literal manifest SHA pin"
        )
        self.members = {row["path"]: row for row in self.manifest["members"]}
        require(len(self.members) == len(self.manifest["members"]), "unique manifest members")

    def bytes(self, name):
        require(
            digest(safe(self.directory, "manifest.json").read_bytes()) == self.manifest_sha,
            "manifest unchanged while reading",
        )
        require(name in self.members, "declared manifest member")
        value = safe(self.directory, name).read_bytes()
        require(
            len(value) == self.members[name]["bytes"]
            and digest(value) == self.members[name]["sha256"],
            "actual saved member bytes",
        )
        return value

    def read(self, name):
        return json.loads(self.bytes(name))

    def verify(self):
        for name in self.members:
            self.bytes(name)
        actual = {
            str(path.relative_to(self.directory))
            for path in self.directory.rglob("*")
            if path.is_file() and path != self.directory / "manifest.json"
        }
        require(actual == set(self.members), "complete sealed member set")


def public_object(messages):
    require(
        isinstance(messages, list)
        and len(messages) == 1
        and set(messages[0]) == {"role", "content"}
        and messages[0]["role"] == "user",
        "one actual public user message",
    )
    value = json.loads(messages[0]["content"])
    require(set(value) == PUBLIC_KEYS, "exact public field boundary")
    return value


def split(question):
    require(question.count(SEP) == 1, "one original immutable suffix")
    at = question.index(SEP)
    return question[:at], question[at:]


def public_slots(public):
    """Derive labels and all periods only from the original public contract."""
    contract, quantity = public["period_contract"], public["quantity_contract"]
    kind = contract["operation"]["kind"]
    ids = contract["metric_ids"]
    require(all(metric in METRICS for metric in ids), "registered full public metric names")
    require(re.fullmatch(r"cik:\d{10}", contract["source_cluster"]), "original public CIK")
    output = (
        "Report the result in percent, rounded to two decimal places using half away from zero."
        if kind == "relative_change"
        else (
            "Report the result in million USD, rounded to two decimal places "
            "using half away from zero."
        )
    )
    slots = {
        "entity": "the company with CIK " + contract["source_cluster"][4:],
        "output_instruction": output,
    }

    def interval(row):
        return (
            "the period " + row["start"] + " through " + row["end"]
            if row["start"] is not None
            else "the instant at " + row["end"]
        )

    if kind in {"difference", "relative_change"}:
        require(
            len(contract["periods"]) == 2
            and len(ids) == 1
            and contract["operation"]["direction"] == "current_minus_previous",
            "original forward two-period operation",
        )
        slots.update(
            metric=METRICS[ids[0]],
            previous_period=interval(contract["periods"][0]),
            current_period=interval(contract["periods"][1]),
        )
        if kind == "relative_change":
            require(
                contract["operation"]["denominator"] == "strictly_positive_previous"
                and contract["operation"]["multiplier"] == 100,
                "original percentage base and scale",
            )
    else:
        require(
            len(contract["periods"]) == 3
            and all(row["start"] is not None for row in contract["periods"]),
            "exact three complete original durations",
        )
        slots["periods"] = "[" + "; ".join(interval(row) for row in contract["periods"]) + "]"
        if kind == "arithmetic_mean":
            require(
                len(ids) == 1 and contract["operation"]["operand_count"] == 3,
                "original arithmetic mean domain",
            )
            slots["metric"] = METRICS[ids[0]]
        else:
            require(
                kind == "argmax_then_lookup"
                and len(ids) == 2
                and contract["operation"]["primary_metric_id"] == ids[0]
                and contract["operation"]["secondary_metric_id"] == ids[1]
                and contract["operation"]["candidate_count"] == 3
                and contract["operation"]["same_actual_period_required"] is True,
                "original peak metric roles",
            )
            slots.update(primary_metric=METRICS[ids[0]], secondary_metric=METRICS[ids[1]])
            slots["output_instruction"] = (
                "In the first Final, report the selected actual period_id and the secondary amount "
                "in million USD, rounded to two decimal places using half away from zero."
            )
    require(
        quantity["unit"] == ("percent" if kind == "relative_change" else "million USD")
        and quantity["decimal_places"] == 2
        and quantity["rounding"] == "half away from zero",
        "original exact output units and rounding",
    )
    return kind, slots


class Cursor:
    def __init__(self, words):
        self.words, self.at = words, 0

    def peek(self):
        return self.words[self.at] if self.at < len(self.words) else None

    def take(self, word):
        require(self.peek() == word, "positive base grammar expected " + word)
        self.at += 1

    def maybe(self, word):
        if self.peek() == word:
            self.at += 1
            return True
        return False

    def choose(self, choices):
        require(self.peek() in choices, "positive base grammar finite word choice")
        value = self.peek()
        self.at += 1
        return value

    def sequence(self, words):
        for word in words.split():
            self.take(word)


def verb(c):
    if c.maybe("what"):
        c.choose({"is", "was"})
    else:
        c.maybe("please")
        c.choose({"calculate", "compute", "determine", "report", "give", "state"})


def company(c):
    if c.maybe("reported"):
        c.take("by")
    else:
        c.take("for")
    c.take("<slot_entity>")


def period_scope(c, *, peak=False):
    c.choose({"among", "across"} if peak else {"across", "over"})
    c.choose({"all"} if peak else {"exactly", "all"})
    c.sequence("three actual")
    c.choose({"annual", "reporting"})
    c.take("periods")
    c.maybe(":")
    c.take("<slot_periods>")


def earlier_later(c):
    c.sequence("from <slot_previous_period> to <slot_current_period>")


def lookup(c):
    if c.maybe("look"):
        c.take("up")
    else:
        c.choose({"report", "give", "state"})
    c.take("<slot_secondary_metric>")
    c.choose({"for", "from", "in"})
    c.sequence("that same actual period")


def parse_positive(template, public):
    """An independent clause/role state machine, not the producer's regexes."""
    require(isinstance(template, str) and 0 < len(template) <= 6000, "bounded actual base template")
    kind, slots = public_slots(public)
    required = ["<slot_" + key + ">" for key in slots]
    found = re.findall(r"<slot_[a-z_]+>", template)
    require(
        sorted(found) == sorted(required) and len(set(found)) == len(found),
        "every role placeholder exactly once",
    )
    remainder = re.sub(r"<slot_[a-z_]+>", "", template)
    require(not re.search(r"\d|[<>]", remainder), "no unprotected numbers or unknown markup")
    require(template.rstrip().endswith("<slot_output_instruction>"), "immutable output last")
    core = template.rstrip()[: -len("<slot_output_instruction>")].strip()
    require(core[-1:] in {".", "?"}, "single complete base sentence")
    words = re.findall(r"<slot_[a-z_]+>|[a-z]+|[^\s]", core[:-1].casefold())
    c = Cursor(words)
    front_company = front_period = False
    if c.maybe("for"):
        c.take("<slot_entity>")
        c.take(",")
        front_company = True
    if kind in {"difference", "relative_change"}:
        if c.peek() == "from":
            require(not front_company, "one leading scope clause")
            earlier_later(c)
            c.take(",")
            front_period = True
        verb(c)
        c.maybe("the")
        if kind == "difference":
            c.take("signed")
            c.choose({"change", "difference"})
        else:
            if c.maybe("year"):
                c.maybe("-")
                c.take("over")
                c.maybe("-")
                c.take("year")
            c.sequence("percentage change")
        c.sequence("in <slot_metric>")
        if not front_company:
            c.sequence("for <slot_entity>")
        if not front_period:
            earlier_later(c)
        c.take(",")
        c.choose({"defined", "calculated"})
        c.take("as")
        if kind == "relative_change":
            c.take("(")
        if c.maybe("current"):
            c.sequence("minus previous")
        else:
            c.sequence("later minus earlier")
        if kind == "relative_change":
            c.take(")")
            c.sequence("divided by the strictly positive")
            c.choose({"previous", "earlier"})
            c.take("amount")
            c.maybe("and")
            c.sequence("multiplied by one hundred")
    elif kind == "arithmetic_mean":
        if c.peek() in {"across", "over"}:
            require(not front_company, "one leading mean scope")
            period_scope(c)
            c.take(",")
            front_period = True
        verb(c)
        c.maybe("the")
        c.maybe("unweighted")
        c.sequence("arithmetic mean of <slot_metric>")
        if not front_company:
            company(c)
        if not front_period:
            period_scope(c)
    elif c.maybe("which"):
        require(not front_company, "question has one company scope")
        c.take("of")
        c.maybe("the")
        c.sequence("three actual")
        c.choose({"annual", "reporting"})
        c.take("periods")
        c.maybe(":")
        c.take("<slot_periods>")
        c.choose({"had", "has"})
        c.maybe("the")
        c.choose({"highest", "largest", "maximum"})
        c.sequence("<slot_primary_metric> for <slot_entity> , and what")
        c.choose({"was", "is"})
        c.take("<slot_secondary_metric>")
        c.choose({"for", "in"})
        c.sequence("that same actual period")
    else:
        if c.peek() in {"among", "across"}:
            period_scope(c, peak=True)
            c.take(",")
            front_period = True
        require(not front_company or front_period, "company front accompanies whole peak domain")
        c.choose({"identify", "determine", "find", "select"})
        c.sequence("the actual period")
        c.choose({"with", "having"})
        c.maybe("the")
        c.choose({"highest", "largest", "maximum"})
        c.take("<slot_primary_metric>")
        if not front_company:
            company(c)
        if not front_period:
            period_scope(c, peak=True)
        c.sequence(", then")
        lookup(c)
    require(c.at == len(c.words), "no unparsed condition, operation or method route")
    return kind, slots


def render(template, slots):
    output = template
    for key, value in slots.items():
        output = output.replace("<slot_" + key + ">", value)
    return output


def inspect_base(base, original_public):
    _, slots = public_slots(original_public)
    template = base
    for key, value in sorted(slots.items(), key=lambda item: len(item[1]), reverse=True):
        require(template.count(value) == 1, "saved base exact immutable role value")
        template = template.replace(value, "<slot_" + key + ">", 1)
    kind, _ = parse_positive(template, original_public)
    require(render(template, slots) == base, "saved base exact independent role restoration")
    return {
        "quantity_kind": kind,
        "recovered_template": template,
        "base_question_sha256": digest(base),
    }


def lexical_words(value):
    return re.findall(r"<slot_[a-z_]+>|[a-z]+", value.casefold())


def public_words(value):
    return re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+", value.casefold())


def verify_one(
    original_public, final_public, category, *, canonical_template=None, selected_template=None
):
    require(set(original_public) == set(final_public) == PUBLIC_KEYS, "same six public fields")
    before, after = split(original_public["question"]), split(final_public["question"])
    require(before[1] == after[1], "original full period/operation suffix literal bytes unchanged")
    require(
        {k: v for k, v in original_public.items() if k != "question"}
        == {k: v for k, v in final_public.items() if k != "question"},
        "original sources units periods operations and tools unchanged",
    )
    if category in {"canonical_fallback", "unchanged_or_format_only"}:
        require(final_public == original_public, "fallback/unchanged exact original public")
        return {"status": "passed", "reused_original_admission": True, "base_rewritten": False}
    require(
        category == "accepted_true_rewrite" and public_words(before[0]) != public_words(after[0]),
        "real changed saved base only",
    )
    result = inspect_base(after[0], original_public)
    if selected_template is not None:
        require(
            result["recovered_template"] == selected_template,
            "saved base is actual selected model template",
        )
    if canonical_template is not None:
        parse_positive(canonical_template, original_public)
        require(
            lexical_words(result["recovered_template"]) != lexical_words(canonical_template),
            "LLM wording change not deterministic canonical preparation",
        )
    return {
        "status": "passed",
        "reused_original_admission": False,
        "base_rewritten": True,
        **result,
    }


def candidates(content):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate response JSON field")
            result[key] = value
        return result

    try:
        value = json.loads(content, object_pairs_hook=unique)
        require(
            isinstance(value, dict) and set(value) == {"rewrites"},
            "closed returned candidate wrapper",
        )
        rows = value["rewrites"]
        require(
            isinstance(rows, list) and 1 <= len(rows) <= 2, "one/two actual returned candidates"
        )
        require(
            all(
                isinstance(row, dict)
                and set(row) == {"rewrite_version", "question_template"}
                and row["rewrite_version"] == VERSION
                and isinstance(row["question_template"], str)
                and row["question_template"].strip()
                for row in rows
            ),
            "closed returned candidate schema",
        )
        return rows
    except (TypeError, ValueError, KeyError):
        return []


def check_public_request(request, model_contract):
    body, reason = request["body"], request["repair_reason"]
    system = PUBLIC_SYSTEM_PROMPT
    if reason is not None:
        require(
            isinstance(reason, list)
            and 1 <= len(reason) <= 32
            and all(
                isinstance(code, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}", code)
                for code in reason
            ),
            "bounded repair error codes only",
        )
        system += (
            "\nThe prior returned candidate violated these contract checks; correct them: "
            + encode(reason).decode()
        )
    require(
        set(body) == {"model", "messages", "thinking", "response_format", "max_tokens", "stream"}
        and body["model"] == "deepseek-flash"
        and body["thinking"] == {"type": "disabled"}
        and body["response_format"] == {"type": "json_object"}
        and body["max_tokens"] == 1536
        and body["stream"] is False
        and body["messages"]
        == [
            {"role": "system", "content": system},
            {"role": "user", "content": encode(model_contract).decode()},
        ],
        "only fixed system prompt and frozen public model contract supplied",
    )


def check_finalization(finalization, budget, frozen, public_catalog, registry):
    """Reconcile durable purpose closure with the exact completed public task set."""
    check_record(finalization)
    task_ids = sorted(row["task_id"] for row in registry["tasks"])
    requests = budget["eval_reservations"]
    require(
        finalization["id"].startswith("evaluation_rewrite_finalization:")
        and finalization == budget["evaluation_finalization"]
        and finalization["eval_freeze_id"] == frozen["id"]
        and finalization["owner_stage_id"] == frozen["owner_freeze_id"]
        and finalization["public_catalog_id"] == public_catalog["id"]
        and finalization["registry_sha256"]
        == frozen["evaluation_registry_sha256"]
        == digest(encode(registry["tasks"])),
        "finalization saved identity and same atomic snapshot",
    )
    require(
        finalization["outcome_task_ids"] == task_ids
        and finalization["outcome_task_ids_sha256"] == digest(encode(task_ids))
        and finalization["registered_task_count"]
        == finalization["completed_task_count"]
        == len(task_ids)
        == len(set(task_ids))
        and set(task_ids) == {row["task_id"] for row in public_catalog["tasks"]},
        "finalization exactly all original registered task outcomes",
    )
    require(
        finalization["remaining_evaluation_attempts_permanently_closed"] is True
        and finalization["unknown_charges_released"] is False
        and finalization["other_purposes_closed"] is False
        and finalization["no_inflight_requests"] is True
        and budget["persisted_study_stop"] is None
        and all(row["state"] in {"settled", "usage_unknown"} for row in requests),
        "finalization permanently closes only evaluation without inflight or fatal state",
    )
    require(
        finalization["terminal_request_count"] == len(requests)
        and finalization["terminal_unknown_count"]
        == sum(row["state"] == "usage_unknown" for row in requests)
        and finalization["retained_conservative_debit"]
        == budget["eval_conservative_charged_tokens"]
        == sum(row["charged_tokens"] for row in requests)
        and all(
            row["charged_tokens"] >= row["reserved_tokens"]
            for row in requests
            if row["state"] == "usage_unknown"
        ),
        "finalization retains all actual and unknown evaluation charges",
    )


def verify(root, directory):
    phase = Pinned(root, directory)
    phase.verify()
    public_catalog, offline = (
        phase.read("public_surface_catalog.json"),
        phase.read("offline_surface_catalog.json"),
    )
    frozen, registry = phase.read("stage_freeze.json"), phase.read("evaluation_registry.json")
    for value in (public_catalog, offline, frozen, registry):
        check_record(value)
    require(
        public_catalog["freeze_id"] == offline["freeze_id"] == frozen["id"]
        and registry["freeze_id"] == frozen["id"]
        and offline["public_catalog_id"] == public_catalog["id"],
        "new frozen surface catalog identity",
    )
    require(
        digest(encode(registry["tasks"])) == frozen["evaluation_registry_sha256"],
        "registry is exactly the pre-output frozen public registry",
    )
    rows = {row["task_id"]: row for row in offline["tasks"]}
    pub = {row["task_id"]: row for row in public_catalog["tasks"]}
    registered = {row["task_id"]: row for row in registry["tasks"]}
    require(
        len(rows)
        == len(offline["tasks"])
        == len(pub)
        == len(public_catalog["tasks"])
        == len(registered)
        == len(registry["tasks"])
        == sum(sum(groups.values()) for groups in QUOTAS.values())
        and set(rows) == set(pub) == set(registered),
        "one unchanged selected 900-task set",
    )
    first = next(iter(rows.values()))["original_bundle_reference"]
    original = Pinned(root, first["parent_directory"], PARENT_ID, first["parent_manifest_sha256"])
    old_audits = Pinned(root, first["parent_directory"] + "_audits", OLD_AUDIT_ID)
    inherited_audit = old_audits.read("panels.json")
    check_record(inherited_audit)
    require(
        inherited_audit["status"] == "PASS_AS_SCOPED"
        and inherited_audit["stage_manifest_id"] == PARENT_ID,
        "actual passed original 900 source audit inherited",
    )
    expected = {}
    for split_name in QUOTAS:
        catalog = original.read(f"panels/{split_name}/catalog.json")
        check_record(catalog)
        for row in catalog["tasks"]:
            expected[row["task_id"]] = (split_name, row)
    require(set(expected) == set(rows), "no task drop replacement or compiled overflow admitted")
    require(
        {
            split_name: dict(
                Counter(row["family"] for row in rows.values() if row["split"] == split_name)
            )
            for split_name in QUOTAS
        }
        == QUOTAS,
        "unchanged dev180 confirm720 three groups",
    )
    budget = phase.read("budget_final.json")
    finalization = phase.read("evaluation_finalization.json")
    check_finalization(finalization, budget, frozen, public_catalog, registry)
    request_rows = {row["request_id"]: row for row in budget["eval_reservations"]}
    require(
        len(request_rows) == len(budget["eval_reservations"]) <= 1800
        and budget["eval_request_reservations"] == len(request_rows),
        "actual evaluation request cap",
    )
    charged = sum(row["charged_tokens"] for row in request_rows.values())
    require(
        charged == budget["eval_conservative_charged_tokens"] <= 17510400,
        "actual evaluation token subcap",
    )
    total = (
        budget["previous_registered_debit"]
        + charged
        + sum(row["charged_tokens"] for row in budget["reservations"])
        + sum(row["charged_tokens"] for row in budget["teacher_reservations"])
    )
    require(
        total == budget["cumulative_conservative_debit"] <= 1000000000
        and budget["previous_registered_debit"] >= 221538,
        "one common allowance with prior UNP Teacher and evaluation charges",
    )
    inspected, all_requests = [], set()
    for task_id, entry in rows.items():
        split_name, prior = expected[task_id]
        require(
            entry["split"] == split_name
            and entry["family"] == prior["family"]
            and pub[task_id]
            == {key: value for key, value in entry.items() if key != "original_bundle_reference"},
            "public/offline catalog and original split roles",
        )
        reference = entry["original_bundle_reference"]
        require(
            reference
            == {
                "parent_directory": first["parent_directory"],
                "parent_manifest_id": PARENT_ID,
                "parent_manifest_sha256": original.manifest_sha,
                "bundle_member": f"panels/{split_name}/" + prior["path"],
                "bundle_id": prior["bundle_id"],
                "public_member": f"panels/{split_name}/" + prior["public_path"],
                "original_surface_version_id": prior["surface_version_id"],
                "original_public_messages_sha256": prior["public_messages_sha256"],
                "qa_id": prior["qa_id"],
                "qa_build_id": prior["qa_build_id"],
            },
            "exact original private and QA references without rewriting",
        )
        require(
            reference["bundle_member"] in original.members,
            "original scientific bundle declared, not regenerated",
        )
        before_raw, after_raw = (
            original.bytes(reference["public_member"]),
            phase.bytes(entry["public_path"]),
        )
        before_messages, after_messages = json.loads(before_raw), json.loads(after_raw)
        before, after = public_object(before_messages), public_object(after_messages)
        require(
            encode(before_messages) == before_raw
            and encode(after_messages) == after_raw
            and digest(before_raw) == prior["public_messages_sha256"]
            and digest(after_raw) == entry["public_messages_sha256"],
            "literal public serialization and SHA",
        )
        surface, spec = phase.read(entry["surface_path"]), phase.read(f"specs/{task_id}.json")
        check_record(surface)
        check_record(spec)
        identity = {
            key: prior[key]
            for key in ("task_id", "family", "surface_version_id", "public_messages_sha256")
        }
        identity["parent_manifest_id"] = PARENT_ID
        require(
            surface["id"] == entry["surface_version_id"]
            and surface["task_id"] == task_id
            and surface["freeze_id"] == frozen["id"]
            and surface["original_identity"] == identity,
            "new surface and original task identity",
        )
        require(
            registered[task_id]["identity"] == identity
            and registered[task_id]["split"] == split_name
            and registered[task_id]["spec_sha256"] == digest(encode(spec)),
            "frozen original registry and full public spec",
        )
        require(
            frozen["public_spec_sha256"][task_id] == digest(encode(spec)),
            "spec is exactly the pre-output frozen public spec",
        )
        kind, slots = public_slots(before)
        require(
            spec["original_public"] == before
            and spec["identity"] == identity
            and spec["quantity_kind"] == kind
            and spec["slot_values"] == slots,
            "spec comes exclusively from original public values and roles",
        )
        require(
            spec["immutable_suffix"] == split(before["question"])[1]
            and spec["original_base"] == split(before["question"])[0],
            "spec exact original question and suffix",
        )
        canonical = spec["canonical_template"]
        parse_positive(canonical, before)
        require(
            spec["canonical_base"] == render(canonical, slots)
            and spec["canonical_preparation_changed_original"]
            == (spec["canonical_base"] != spec["original_base"]),
            "local canonical preparation identified separately",
        )
        history = surface["evidence"]["requests"]
        require(len(history) <= 2, "per-task initial and one repair only")
        selected = selected_index = None
        for attempt, observed in enumerate(history, 1):
            identifier = observed["request_id"]
            require(
                identifier not in all_requests and identifier in request_rows,
                "one actual request per evidence reference",
            )
            all_requests.add(identifier)
            row = request_rows[identifier]
            require(
                row["task_id"] == task_id
                and row["attempt"] == observed["attempt"] == attempt
                and row["reserved_tokens"] == 9728,
                "actual request task and attempt",
            )
            prefix = "evaluation_requests/" + identifier + "/"
            request = phase.read(prefix + "request.json")
            check_record(request)
            require(
                request["task_identity"] == identity
                and request["spec_sha256"] == digest(encode(spec))
                and request["attempt"] == attempt
                and request["request_id"] == identifier
                and request["live_HTTP_sender"] is True,
                "actual original public request not mock",
            )
            body = request["body"]
            require(
                json.loads(request["body_json"]) == body
                and digest(request["body_json"]) == request["body_sha256"]
                and len(request["body_json"].encode()) == request["serialized_body_bytes"]
                and len(request["body_json"].encode()) + 1024
                == request["admitted_input_bound"]
                <= 8192,
                "exact wire request and input reservation",
            )
            check_public_request(request, spec["model_contract"])
            require(selected is None, "no request after first semantically valid candidate")
            if prefix + "receipt.json" not in phase.members:
                failure = phase.read(prefix + "failure.json")
                check_record(failure)
                require(
                    attempt == len(history)
                    and row["state"] in {"reserved", "usage_unknown", "settled", "budget_breach"}
                    and failure["request_id"] == identifier
                    and failure["request_record_id"] == request["id"]
                    and observed["receipt_id"] == failure["id"]
                    and observed["receipt"] == failure
                    and observed["receipt_path"]
                    == str((phase.directory / (prefix + "failure.json")).relative_to(phase.root)),
                    "failed transport never retried",
                )
                if row["state"] in {"reserved", "usage_unknown"}:
                    require(row["charged_tokens"] == 9728, "unknown usage never releases lease")
                continue
            response, receipt = (
                phase.read(prefix + "public_response.json"),
                phase.read(prefix + "receipt.json"),
            )
            check_record(response)
            check_record(receipt)
            require(
                receipt["request_id"] == response["request_id"] == identifier
                and receipt["request_record_id"] == request["id"]
                and receipt["response_record_id"] == response["id"]
                and observed["receipt_id"] == receipt["id"]
                and observed["receipt"] == receipt
                and observed["receipt_path"]
                == str((phase.directory / (prefix + "receipt.json")).relative_to(phase.root)),
                "actual request response receipt join",
            )
            require(
                response["response_model"] == row["response_model"] == "deepseek-flash"
                and row["http_success"] == 1
                and row["state"] == "settled",
                "settled exact model public response",
            )
            usage = response["usage"]
            require(
                usage["prompt_tokens"] == row["prompt_tokens"]
                and usage["completion_tokens"] == row["completion_tokens"]
                and usage["total_tokens"]
                == row["charged_tokens"]
                == usage["prompt_tokens"] + usage["completion_tokens"],
                "actual usage associated with same response",
            )
            content = response["raw_public_content"]
            require(
                response["original_public_content_sha256"]
                == (digest(content) if isinstance(content, str) else None)
                and not response["credential_echo_redacted"],
                "original returned public text",
            )
            returned_candidates = candidates(content)
            require(
                receipt["candidate_count"] == len(returned_candidates)
                and bool(receipt["structure_errors"]) == (not returned_candidates)
                and receipt["outcome"]
                == ("response_received" if returned_candidates else "rewrite_structure_failure")
                and receipt["settlement"]["request_id"] == identifier
                and receipt["settlement"]["charged_tokens"] == row["charged_tokens"]
                and receipt["settlement"]["state"] == row["state"],
                "saved candidate structure and settlement independently reconciled",
            )
            for index, candidate in enumerate(returned_candidates):
                try:
                    parse_positive(candidate["question_template"], before)
                except (ValueError, KeyError, IndexError):
                    continue
                selected, selected_index = candidate["question_template"], index
                break
            if selected is not None:
                require(attempt == len(history), "first valid response terminates request history")
        if selected is None:
            category = "canonical_fallback"
        else:
            category = (
                "accepted_true_rewrite"
                if lexical_words(selected) != lexical_words(canonical)
                and public_words(render(selected, slots))
                != public_words(split(before["question"])[0])
                else "unchanged_or_format_only"
            )
        require(
            surface["category"] == entry["category"] == category
            and surface["selected_variant_index"] == selected_index,
            "category and first valid candidate independently recomputed",
        )
        require(
            surface["selected_candidate_applied_to_final"] == (category == "accepted_true_rewrite")
            and surface["qa_build_created"] is False
            and surface["qa_sample_created"] is False,
            "surface-only application no invented QA build",
        )
        checked = verify_one(
            before, after, category, canonical_template=canonical, selected_template=selected
        )
        if category != "accepted_true_rewrite":
            require(before_raw == after_raw, "literal original fallback/unchanged messages")
        old_base, suffix = split(before["question"])
        new_base, _ = split(after["question"])
        require(
            surface["original_base_sha256"] == digest(old_base)
            and surface["new_base_sha256"] == digest(new_base)
            and surface["immutable_suffix_sha256"] == digest(suffix),
            "actual saved base and suffix hashes",
        )
        inspected.append(
            {
                "task_id": task_id,
                "split": split_name,
                "category": category,
                "public_messages_sha256": digest(after_raw),
                "check": checked,
            }
        )
    require(all_requests == set(request_rows), "no unreported evaluation requests")
    return {
        "schema_version": "independent_evaluation_surface_audit.v1",
        "status": "passed",
        "failures": [],
        "surface_manifest_id": phase.manifest["id"],
        "tasks": inspected,
        "task_count": len(inspected),
        "counts": dict(Counter(row["category"] for row in inspected)),
        "requests": len(all_requests),
        "evaluation_charged_tokens": charged,
        "evaluation_finalization_id": finalization["id"],
        "remaining_evaluation_attempts_permanently_closed": True,
        "cumulative_charged_tokens": total,
        "inherited_source_audit_id": inherited_audit["id"],
        "inherited_source_audit_sha256": old_audits.members["panels.json"]["sha256"],
        "source_audit_rerun": False,
        "private_reference_or_answer_files_opened": 0,
        "auditor_sha256": digest(Path(__file__).read_bytes()),
        "new_model_calls": 0,
        "limitation": (
            "finite protected English base grammar, not unrestricted natural-language equivalence"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.directory)
    if args.output:
        destination = args.output.resolve()
        require(
            not destination.is_relative_to((args.root / args.directory).resolve()),
            "audit report outside sealed surface phase",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "tasks"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
