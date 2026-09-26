"""Bounded legal-issuer review using only previously archived PDF page text.

This is not a claim that base-model pretraining is unexposed, that all corporate
groups are independent, or that identity evidence promotes financial facts.
The legal-name roster below is a human-reviewed transcription of saved official
report self-identification; the program verifies each asserted binding.
"""

import argparse
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

import prepare_cross_market_sources_20260926 as base

SCRIPT = "trusted_data_synthesis/scripts/cross_market_issuer_admission_20260926.py"
RAW = base.RAW / "issuer_admission_01"
AUDIT = base.RAW / "evidence_audit_01"
CN_NAMES = {
    "600067": ["冠城大通新材料股份有限公司", "冠城大通股份有限公司"],
    "600036": ["招商银行股份有限公司"],
    "001202": ["炬申物流集团股份有限公司", "广东炬申物流股份有限公司"],
    "000498": ["山东高速路桥集团股份有限公司"],
    "600816": ["建元信托股份有限公司", "安信信托股份有限公司"],
    "000978": ["桂林旅游股份有限公司"],
    "600022": ["山东钢铁股份有限公司"],
    "603860": ["中公高科养护科技股份有限公司"],
    "600371": ["万向德农股份有限公司"],
    "600170": ["上海建工集团股份有限公司"],
    "000503": ["国新健康保障服务集团股份有限公司"],
    "000151": ["中成进出口股份有限公司"],
    "002159": ["武汉三特索道集团股份有限公司"],
    "603177": ["浙江德创环保科技股份有限公司"],
    "001872": ["招商局港口集团股份有限公司"],
    "600643": ["上海爱建集团股份有限公司"],
    "600648": ["上海外高桥集团股份有限公司"],
    "002027": ["分众传媒信息技术股份有限公司"],
    "000997": ["新大陆数字技术股份有限公司"],
    "000059": ["北方华锦化学工业股份有限公司"],
    "000721": ["西安饮食股份有限公司"],
    "000068": ["深圳华控赛格股份有限公司"],
    "000429": ["广东省高速公路发展股份有限公司"],
    "000035": ["中国天楹股份有限公司"],
    "600149": ["廊坊发展股份有限公司"],
    "000507": ["珠海港股份有限公司"],
    "600373": ["中文天地出版传媒集团股份有限公司"],
    "605167": ["江苏利柏特股份有限公司"],
    "600037": ["北京歌华有线电视网络股份有限公司"],
    "600033": ["福建发展高速公路股份有限公司"],
    "600280": ["南京中央商场（集团）股份有限公司"],
    "603682": ["上海锦和商业经营管理（集团）股份有限公司", "上海锦和商业经营管理股份有限公司"],
}
SUBMISSIONS = base.LAKE / "sec/submissions"
HK_NAMES = {
    "00175": ["Geely Automobile Holdings Limited"],
    "02318": ["Ping An Insurance (Group) Company of China, Ltd."],
    "00006": ["Power Assets Holdings Limited"],
    "00016": ["Sun Hung Kai Properties Limited"],
    "00386": ["China Petroleum & Chemical Corporation"],
    "00981": ["Semiconductor Manufacturing International Corporation"],
    "01211": ["BYD Company Limited"],
    "00960": ["Longfor Group Holdings Limited"],
    "00019": ["Swire Pacific Limited"],
    "00101": ["Hang Lung Properties Limited"],
    "00288": ["WH Group Limited"],
    "03988": ["Bank of China Limited"],
    "01088": ["China Shenhua Energy Company Limited"],
    "02020": ["ANTA Sports Products Limited"],
    "00762": ["China Unicom (Hong Kong) Limited"],
    "00857": ["PetroChina Company Limited"],
    "00027": ["Galaxy Entertainment Group Limited"],
    "00012": ["Henderson Land Development Company Limited"],
    "00688": ["China Overseas Land & Investment Limited"],
    "00001": ["CK Hutchison Holdings Limited"],
    "00002": ["CLP Holdings Limited"],
    "00700": ["Tencent Holdings Limited"],
    "00939": ["China Construction Bank Corporation"],
    "01044": ["Hengan International Group Company Limited"],
    "01109": ["China Resources Land Limited"],
    "00883": ["CNOOC Limited"],
    "01398": ["Industrial and Commercial Bank of China Limited"],
    "01038": ["CK Infrastructure Holdings Limited"],
    "00017": ["New World Development Company Limited"],
    "00941": ["China Mobile Limited"],
    "00003": ["The Hong Kong and China Gas Company Limited"],
    "01810": ["Xiaomi Corporation"],
}


def norm(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


def identity_key(text):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", text)).casefold()


def reference(path):
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def evidence(page, start, end, method, **fields):
    text = page["text"]
    return dict(
        page=page["page"],
        page_text_sha256=base.sha(text),
        excerpt=text[max(0, start - 120) : min(len(text), end + 220)],
        method=method,
        **fields,
    )


def identity_evidence(pages, names, source):
    """Require report-self context, never any arbitrary body mention."""
    for name in names:
        for page in pages:
            text = page["text"]
            normalized = norm(text)
            if norm(name) not in normalized:
                continue
            if source == "cninfo_announcements":
                for m in re.finditer(
                    r"(?:公司的中文名称|法定中文名称|公司中文名称|编制单位)\s*[:：]?\s*([^\n]+)",
                    text,
                ):
                    if norm(name) in norm(m.group(1)):
                        return evidence(
                            page, m.start(), m.end(), "explicit_issuer_name_field", legal_name=name
                        )
            else:
                # Auditor's formal addressee identifies the issuer, not a supplier.
                for m in re.finditer(r"(?:to\s+the\s+)?(?:members|shareholders)\s+of", text, re.I):
                    end = min(len(text), m.end() + 240)
                    if norm(name) in norm(text[m.end() : end]):
                        return evidence(page, m.start(), end, "auditor_addressee", legal_name=name)
                if page["page"] <= 40:
                    # Manually reviewed exact issuer name in the report title/header.
                    for m in re.finditer(r"(?m)^.*$", text):
                        line = norm(m.group())
                        target = norm(name)
                        if line == target or (line.startswith(target) and "annualreport" in line):
                            return evidence(
                                page,
                                m.start(),
                                m.end(),
                                "reviewed_report_self_header",
                                legal_name=name,
                            )
    return None


def code_evidence(pages, code):
    patterns = (
        r"(?:stock\s*(?:short\s*names\s*and\s*)?codes?|HKEX|SEHK\s*stock\s*code)\s*[:：]?",
        r"(?:股票|股份|证券|公司)(?:代[碼码號号])\s*[:：]?",
    )
    expected = int(code)
    for page in pages:
        if page["page"] > 40 and page["page"] < len(pages) - 10:
            continue
        for pattern in patterns:
            for m in re.finditer(pattern, page["text"], re.I):
                tail = page["text"][m.end() : m.end() + 200]
                for token in re.finditer(r"(?<!\d)\d{1,6}(?!\d)", tail):
                    if int(token.group()) == expected:
                        return evidence(
                            page,
                            m.start(),
                            m.end() + token.end(),
                            "own_stock_code_locator",
                            security_code=code,
                            code_field_text=page["text"][m.start() : m.end() + 200],
                        )
    return None


def foreign_name_evidence(pages):
    """Read the issuer's explicit foreign-name field, not a supplied translation."""
    result = []
    for page in pages:
        if page["page"] > 40:
            continue
        for match in re.finditer(
            r"(?:外文|英文)名称(?!缩写)(?:[（(]\s*如\s*有\s*[)）])?\s*[:：]?\s*"
            r"([A-Za-z][A-Za-z0-9 ,.&'()/\-\n\t　（）]+)",
            page["text"],
        ):
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            value = re.sub(r"\s*\d+(?:\.\d+)+\s*$", "", value).strip()
            if len(value) >= 8:
                result.append(
                    evidence(
                        page,
                        match.start(),
                        match.end(),
                        "explicit_foreign_name_field",
                        legal_name=value,
                    )
                )
    return result


def rename_evidence(documents, names):
    if len(names) == 1:
        return []
    result = []
    for old in names[1:]:
        hit = None
        for doc, saved in documents:
            for page in saved["pages"]:
                text = page["text"]
                for m in re.finditer(r"更名|变更|原名|原安信|原广东|原上海", text):
                    start, end = max(0, m.start() - 300), min(len(text), m.end() + 500)
                    window = norm(text[start:end])
                    if norm(names[0]) in window and norm(old) in window:
                        hit = dict(
                            raw_object_id=doc["raw_object_id"],
                            **evidence(
                                page,
                                start,
                                end,
                                "explicit_name_change",
                                old_name=old,
                                new_name=names[0],
                            ),
                        )
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            result.append(hit)
    return result


def register(root):
    path = RAW / "protocol.json"
    if path.exists():
        plan = base.checked(base.read(path), "cross_market_issuer_admission_protocol")
        base.require(plan["script_sha256"] == base.sha(root / SCRIPT), "issuer_frozen_code")
        base.require(plan["base_script_sha256"] == base.sha(root / base.SCRIPT), "issuer_base_code")
        return plan
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for filename in (SCRIPT, base.SCRIPT):
        base.require(
            (root / filename).read_bytes()
            == subprocess.check_output(["git", "show", head + ":" + filename], cwd=root),
            "issuer_committed_code",
        )
    audit = base.read(AUDIT / "protocol.json")
    roster = base.read(base.RAW / "protocol.json")
    history = base.read(audit["historical_source_metadata"]["path"])
    submissions = []
    for row in history["rows"]:
        cik = row["entity"]["cik"]
        paths = sorted((SUBMISSIONS / ("cik=" + cik)).glob("snapshot_date=*.json"))
        base.require(paths, "issuer_history_submissions_missing:" + cik)
        submissions.extend(dict(cik=cik, **reference(p)) for p in paths)
    docs = [d for s in roster["metadata_inventory"]["roster"] for d in s["documents"]]
    refs = []
    for doc in docs:
        key = base.sha(doc["raw_object_id"])[:24]
        refs.append(
            dict(
                raw_object_id=doc["raw_object_id"],
                **reference(AUDIT / "page_text" / (key + ".json")),
            )
        )
    plan = base.record(
        "cross_market_issuer_admission_protocol",
        at=base.now(),
        code_commit=head,
        script_sha256=base.sha(root / SCRIPT),
        base_script_sha256=base.sha(root / base.SCRIPT),
        parent=reference(base.RAW / "protocol.json"),
        evidence_completion=reference(AUDIT / "summary.json"),
        history=audit["historical_source_metadata"],
        historical_submissions_identity_only=submissions,
        maximum_historical_identity_snapshots=len(submissions),
        page_text=refs,
        source_roster_unchanged=True,
        maximum_saved_documents=440,
        new_PDF_reads=0,
        financial_parser_calls=0,
        network_requests=0,
        model_calls=0,
        GPU_processes=0,
        scoring_calls=0,
        registration_scope="Saved-text identity and exposure review only; "
        "no financial admission or evaluation permit",
        names_reviewed_before_registration=True,
        model_outcomes_consulted=False,
        rule="Exact reviewed legal name in explicit self field/auditor addressee/report header "
        "plus own stock-code evidence; explicit rename proof; no body-name merge",
        exposure_rule="Compare positively evidenced issuer identities with frozen historical "
        "registry and original local submissions names/formerNames/registration fields; "
        "absence of string match alone never certifies no exposure",
        independence_limit="Legal issuer != independent economic group; listed parents, "
        "subsidiaries and associates remain potentially correlated",
    )
    base.write(path, plan)
    return plan


def execute(root):
    plan = register(root)
    completed = RAW / "admission.json"
    if completed.exists():
        result = base.checked(base.read(completed), "cross_market_issuer_admission")
        base.require(result["protocol_id"] == plan["id"], "issuer_existing_parent")
        return result
    for r in (plan["parent"], plan["history"], plan["evidence_completion"]):
        base.require(base.sha(Path(r["path"])) == r["sha256"], "issuer_frozen_input")
    roster = base.read(Path(plan["parent"]["path"]))["metadata_inventory"]["roster"]
    history = base.read(Path(plan["history"]["path"]))
    historical_identities = {}
    for ref in plan["historical_submissions_identity_only"]:
        base.require(base.sha(Path(ref["path"])) == ref["sha256"], "issuer_historical_snapshot")
        payload = base.read(Path(ref["path"]))
        cik = str(payload["cik"]).zfill(10)
        base.require(cik == ref["cik"], "issuer_historical_CIK")
        row = historical_identities.setdefault(cik, dict(cik=cik, names=[], snapshots=[]))
        row["names"] = sorted(
            set(row["names"])
            | {payload["name"]}
            | {former["name"] for former in payload.get("formerNames", [])}
        )
        row["snapshots"].append(
            dict(
                reference=ref,
                name=payload["name"],
                former_names=payload.get("formerNames", []),
                state_of_incorporation=payload.get("stateOfIncorporation"),
                state_of_incorporation_description=payload.get("stateOfIncorporationDescription"),
                business_address=payload.get("addresses", {}).get("business"),
                tickers=payload.get("tickers", []),
            )
        )
    text_refs = {r["raw_object_id"]: r for r in plan["page_text"]}
    rows = []
    for security in roster:
        source, code = security["security_id"].split(":")
        names = (CN_NAMES if source == "cninfo_announcements" else HK_NAMES)[code]
        docs = []
        bindings = []
        foreign_names = []
        for doc in security["documents"]:
            ref = text_refs[doc["raw_object_id"]]
            base.require(base.sha(Path(ref["path"])) == ref["sha256"], "issuer_frozen_page_text")
            saved = base.checked(
                base.read(Path(ref["path"])), "cross_market_original_PDF_page_text"
            )
            base.require(
                saved["raw_object_id"] == doc["raw_object_id"]
                and saved["raw_sha256"] == doc["sha256"],
                "issuer_original_binding",
            )
            docs.append((doc, saved))
            identity = identity_evidence(saved["pages"], names, source)
            code_ref = code_evidence(saved["pages"], code)
            if source == "cninfo_announcements":
                foreign_names.extend(
                    dict(raw_object_id=doc["raw_object_id"], **e)
                    for e in foreign_name_evidence(saved["pages"])
                )
            bindings.append(
                dict(
                    raw_object_id=doc["raw_object_id"],
                    raw_sha256=doc["sha256"],
                    original_url=doc["original_url"],
                    manifest_year=doc["year"],
                    saved_text=ref,
                    identity_evidence=identity,
                    code_evidence=code_ref,
                    admitted=bool(identity and code_ref),
                    unresolved_reasons=([] if identity else ["NO_VERIFIED_SELF_NAME_LOCATOR"])
                    + ([] if code_ref else ["NO_VERIFIED_OWN_CODE_LOCATOR"]),
                )
            )
        rename = rename_evidence(docs, names)
        renames_passed = len(rename) == len(names) - 1
        # Project history contains legal issuer identities, not an exhaustive model
        # exposure ledger. The following screen does not make a novelty claim.
        comparison_names = names + [e["legal_name"] for e in foreign_names]
        matches = [
            "cik:" + cik
            for cik, r in historical_identities.items()
            if {identity_key(n) for n in r["names"]} & {identity_key(n) for n in comparison_names}
        ]
        reasons = [] if renames_passed else ["RENAME_CONTINUITY_NOT_EVIDENCED"]
        admitted = renames_passed and any(b["admitted"] for b in bindings) and not matches
        rows.append(
            dict(
                security_id=security["security_id"],
                issuer_cluster_id="issuer:" + base.sha(norm(names[0])),
                legal_name=names[0],
                legal_aliases=names,
                foreign_name_evidence=foreign_names,
                identity_comparison_aliases=sorted(set(comparison_names)),
                admitted=admitted,
                status="LEGAL_ISSUER_MAPPING_ADMITTED_EXPOSURE_SEPARATE"
                if admitted
                else "UNRESOLVED_NOT_ADMITTED",
                document_bindings=bindings,
                rename_evidence=rename,
                exposure=dict(
                    archived_registry_matches=matches,
                    archived_registry_id=history["id"],
                    archived_registry_issuer_count=len(history["rows"]),
                    original_submissions_snapshot_count=len(
                        plan["historical_submissions_identity_only"]
                    ),
                    former_names_screened=True,
                    project_source_identity_screen_passed=bool(
                        admitted and (foreign_names or source == "hkex_disclosures")
                    ),
                    status="EXACT_LEGAL_IDENTITY_MATCH"
                    if matches
                    else "NO_EXACT_IDENTITY_MATCH_NOT_NONEXPOSURE_PROOF",
                    no_exposure_certified=False,
                    base_model_pretraining="UNKNOWN",
                    scope_limit="No name-absence assertion, no automatic subsidiary-to-parent "
                    "equivalence, no claim historical registry covers all model exposure",
                ),
                unresolved_reasons=reasons + (["HISTORICAL_IDENTITY_MATCH"] if matches else []),
            )
        )
    crosslisting = []
    bilingual_alias_collisions = []
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            shared = {identity_key(n) for n in left["identity_comparison_aliases"]} & {
                identity_key(n) for n in right["identity_comparison_aliases"]
            }
            if shared:
                bilingual_alias_collisions.append(
                    dict(
                        security_ids=[left["security_id"], right["security_id"]],
                        shared_alias_keys=sorted(shared),
                        status="UNRESOLVED_REQUIRES_POSITIVE_ALIAS_ADJUDICATION",
                    )
                )
                left["admitted"] = right["admitted"] = False
                left["unresolved_reasons"].append("CROSSLISTING_ALIAS_COLLISION")
                right["unresolved_reasons"].append("CROSSLISTING_ALIAS_COLLISION")
    for row in rows:
        assertions = []
        for binding in row["document_bindings"]:
            code_ref = binding["code_evidence"]
            if code_ref:
                # Literal printed code strings, not inferred six/five digit aliases.
                # Store locators; only full-width codes can be mechanically joined
                # across the fixed CN/HK roster. Short HK codes need manual review.
                codes = sorted(
                    set(re.findall(r"(?<!\d)\d{5,6}(?!\d)", code_ref["code_field_text"]))
                )
                targets = [
                    other["security_id"]
                    for other in rows
                    if other["security_id"] != row["security_id"]
                    and other["security_id"].split(":")[1] in codes
                ]
                if targets:
                    row["admitted"] = False
                    row["unresolved_reasons"].append("OTHER_SELECTED_SECURITY_IN_OWN_LISTING_FIELD")
                assertions.append(
                    dict(
                        raw_object_id=binding["raw_object_id"],
                        code_field=code_ref,
                        printed_full_width_code_tokens=codes,
                        other_roster_code_alerts=targets,
                    )
                )
        crosslisting.append(
            dict(
                security_id=row["security_id"],
                evidence=assertions,
                status="SELF_LISTING_FIELDS_RECORDED_NOT_AUTOMATIC_ALIAS_MERGE",
            )
        )
    for row in rows:
        if not row["admitted"]:
            row["status"] = "UNRESOLVED_NOT_ADMITTED"
            row["exposure"]["project_source_identity_screen_passed"] = False
    result = base.record(
        "cross_market_issuer_admission",
        at=base.now(),
        protocol_id=plan["id"],
        complete=True,
        rows=rows,
        securities=len(rows),
        admitted_securities=sum(r["admitted"] for r in rows),
        admitted_document_bindings=sum(
            b["admitted"] and r["admitted"] for r in rows for b in r["document_bindings"]
        ),
        issuer_clusters=len({r["issuer_cluster_id"] for r in rows if r["admitted"]}),
        status_counts=dict(Counter(r["status"] for r in rows)),
        historical_identities=list(historical_identities.values()),
        crosslisting_field_audit=crosslisting,
        bilingual_alias_collisions=bilingual_alias_collisions,
        all_exposure_clear=False,
        project_source_identity_screen_passed=all(
            r["admitted"] and r["exposure"]["project_source_identity_screen_passed"] for r in rows
        ),
        financial_facts_admitted=False,
        panel_ready=False,
        eligible_mapping={r["security_id"]: r["issuer_cluster_id"] for r in rows if r["admitted"]},
        limitations=[
            "Legal issuer clusters do not imply economically independent issuers",
            "Absence of archived identity match does not certify absence of any model exposure",
            "All document bindings require per-task joins; unresolved documents are ineligible",
        ],
    )
    base.write(completed, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("register", "run"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = register(args.root) if args.command == "register" else execute(args.root)
    base.emit(
        {
            k: result[k]
            for k in (
                "id",
                "securities",
                "admitted_securities",
                "admitted_document_bindings",
                "issuer_clusters",
            )
            if k in result
        }
    )


if __name__ == "__main__":
    main()
