"""Final saved V14 material accounting; no model, tokenizer or source mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.finance_research.contracts import digest

ROOT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v14_representation_01"
)


def entry(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    value = json.loads(raw)
    return dict(
        path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        id=value.get("id", value.get("encoding_id")),
    )


def read_ref(ref):
    raw = Path(ref["path"]).read_bytes()
    value = json.loads(raw)
    if (
        hashlib.sha256(raw).hexdigest() != ref["sha256"]
        or value.get("id", value.get("encoding_id")) != ref["id"]
    ):
        raise ValueError("saved source changed: " + ref["path"])
    return value


def summarize(root=ROOT):
    root = Path(root).resolve()
    refs = {
        name: entry(root / relative)
        for name, relative in (
            ("support", "material/support/record.json"),
            ("result", "material/result/record.json"),
            ("completion_seal", "completion_seal/record.json"),
            ("initial_encoding_audit", "encoding_cache/initial_audit/record.json"),
            ("final_authority_revision", "encoding_cache/revisions/0001/record.json"),
        )
    }
    values = {name: read_ref(ref) for name, ref in refs.items()}
    support, result, seal = (values[n] for n in ("support", "result", "completion_seal"))
    initial, revision = values["initial_encoding_audit"], values["final_authority_revision"]
    refs["final_encoding_run"] = entry(
        root / "encoding_cache/runs" / revision["id"] / "record.json"
    )
    run = read_ref(refs["final_encoding_run"])
    refs["representation_review"] = seal["representation_review"]
    review = read_ref(refs["representation_review"])
    old_run = read_ref(initial["source_run"])
    fixed_slots = set(support["candidate_slot_ids"])
    if (
        result["support"] != refs["support"]
        or result["protocol_id"] != seal["protocol_id"]
        or result["registration_id"] != seal["registration_id"]
        or run["authority_revision"] != refs["final_authority_revision"]
        or set(run["encoding_refs"]) != fixed_slots
        or not len(fixed_slots) == support["package_count"] == 2468
        or support["N"] != 744
        or run["pending_authority_slot_ids"]
        or initial["encoding_admitted_packages"] != 2465
        or initial["encoding_failed_packages"] != 0
    ):
        raise ValueError("not the fixed complete V14 encoding and material result chain")
    if any(run["encoding_refs"].get(sid) != ref for sid, ref in old_run["encoding_refs"].items()):
        raise ValueError("the prior 2465 cached authority outputs were replaced")
    added = [sid for sid in run["encoding_refs"] if sid not in old_run["encoding_refs"]]
    if len(added) != 3:
        raise ValueError("exactly the three formerly pending authorities must be appended")
    layers = Counter(initial["observed_initial_layer_target_counts"])
    supervised = initial["observed_initial_total_supervised_tokens"]
    sequences = initial["observed_initial_total_sequence_tokens"]
    rows = initial["observed_initial_response_rows"]
    maximum = initial["observed_initial_max_sequence_tokens"]
    added_rows, failures, overflow = [], [], []
    for sid in added:
        ref = run["encoding_refs"][sid]
        value = read_ref(ref)
        if value["schema"] != "v14_student_encoding.v1" or value["slot_id"] != sid:
            raise ValueError("new saved encoding identity/schema differs")
        if not value["encoding_admitted"]:
            failures.append(dict(slot_id=sid, encoding=ref, failures=value["failures"]))
        if any(f["reason"] == "untruncated_context_overflow" for f in value["failures"]):
            overflow.append(sid)
        layers.update(value["layer_target_counts"])
        supervised += value["total_supervised_tokens"]
        sequences += value["total_sequence_tokens"]
        rows += len(value["rows"])
        maximum = max(maximum, value["max_sequence_tokens"])
        added_rows.append(
            dict(
                slot_id=sid,
                task_id=value["task_id"],
                encoding=ref,
                encoding_admitted=value["encoding_admitted"],
                supervised_tokens=value["total_supervised_tokens"],
                layer_target_counts=value["layer_target_counts"],
                max_sequence_tokens=value["max_sequence_tokens"],
            )
        )
    profile, resolved = support["capability_profile"], support["task_support"]
    blockers = Counter(b["reason"] for b in profile["blockers"])
    if (
        dict(layers) != profile["supervised_tokens"]
        or sum(layers.values()) != supervised
        or sequences != profile["total_sequence_tokens"]
        or maximum != profile["maximum_sequence_tokens"]
        or profile["encoding_started_packages"] != 2468
        or len(failures) != blockers["fixed_original_encoding_unresolved"]
    ):
        raise ValueError("whole saved encoding totals differ from frozen material consumer")
    N, P = support["N"], support["package_count"]
    resolved_n = len(resolved)
    resolved_p = sum(row["n_x"] for row in resolved.values())
    states = sum(len(row["states"]) for row in resolved.values())
    degrees = states - resolved_n
    flexible = sum(len(row["states"]) > 1 for row in resolved.values())
    chi_flexible = sum(set(row["chi"].values()) == {0, 1} for row in resolved.values())
    singletons = sum(row["deterministic_singleton"] for row in resolved.values())
    missing_n, missing_p = N - resolved_n, P - resolved_p
    if missing_n != blockers["whole_task_mapping_unresolved"]:
        raise ValueError("unresolved mapping task count changed")
    known_dose = dict(plus=Fraction(0), minus=Fraction(0))
    for row in resolved.values():
        p = sum(
            (Fraction(n, row["n_x"]) for z, n in row["states"].items() if row["chi"][z] == 1),
            Fraction(0),
        )
        known_dose["plus"] += p * (1 - p) / (1 + p) / N
        known_dose["minus"] += p * (1 - p) / (2 - p) / N
    body = dict(
        schema="v14_final_support_audit.v1",
        material_root=str(root),
        source_records=refs,
        protocol_id=result["protocol_id"],
        registration_id=result["registration_id"],
        phase=result["phase"],
        fixed_population=dict(packages=P, tasks=N),
        API_matrix=dict(
            expected=seal["expected_calls"],
            actual_returns=seal["actual_returns"],
            network_unknowns=seal["network_unknowns"],
            new_projection_usable=seal["projection_usable_calls"],
            new_mapping_complete=seal["mapping_complete_calls"],
            purpose_expected=seal["purpose_expected"],
            failures=seal["failures"],
        ),
        projection=dict(
            known_authorities=run["known_authority_count"],
            pending_slot_ids=revision["pending_slot_ids"],
            original_known_authorities=2465,
            appended_authorities=len(added),
        ),
        complete_encoding=dict(
            denominator=P,
            encoding_started=profile["encoding_started_packages"],
            encoding_admitted=2465 + sum(e["encoding_admitted"] for e in added_rows),
            failed=len(failures),
            failure_slots=failures,
            context_overflow_count=len(overflow),
            context_overflow_slot_ids=overflow,
            context_limit=24576,
            maximum_sequence_tokens=maximum,
            response_rows=rows,
            total_sequence_tokens=sequences,
            full_supervised_tokens=supervised,
            full_layer_target_counts=dict(layers),
            all_public_reasoning_masked=profile["all_public_reasoning_masked"],
            reason_zero_packages=len(profile["public_content_all_masked_packages"]),
            initial_2465_encoding_refs_unchanged=True,
            appended_encoding_details=added_rows,
            retokenization_calls=0,
            verification_scope=(
                "Reuse the byte-bound 2465 initial audit, verify unchanged encoding refs, "
                "read the three appended files, and match the final material consumer totals."
            ),
        ),
        mapping=dict(
            resolved_tasks=resolved_n,
            unresolved_tasks=missing_n,
            deterministic_singletons=singletons,
            inherited_or_derived_multi_task_mappings=len(review["mapping_authority_refs"]),
            new_complete_mappings=seal["mapping_complete_calls"],
            unresolved_task_ids=[
                b["task_id"]
                for b in profile["blockers"]
                if b["reason"] == "whole_task_mapping_unresolved"
            ],
        ),
        resolved_subset_only=dict(
            tasks=resolved_n,
            packages=resolved_p,
            states=states,
            state_count_minus_task_count=degrees,
            multi_state_tasks=flexible,
            one_state_tasks=resolved_n - flexible,
            chi_contrast_tasks=chi_flexible,
            states_with_one_package=sum(
                n == 1 for row in resolved.values() for n in row["states"].values()
            ),
            chi_state_histogram=dict(
                Counter(
                    "null" if chi is None else str(chi)
                    for row in resolved.values()
                    for chi in row["chi"].values()
                )
            ),
            known_mu_weighted_Manual_TV_plus=str(known_dose["plus"]),
            known_mu_weighted_Manual_TV_minus=str(known_dose["minus"]),
            dose_mu_denominator=N,
            dose_is_partial_contribution_not_full_manual_measurement=True,
            no_subset_training=True,
        ),
        full_population_measurements=dict(
            D_pi=profile["D_pi"],
            M_flex=profile["M_flex"],
            state_count=profile["state_count"],
            chi_flexible_tasks=profile["chi_flexible_tasks"],
            chi_flexible_mass=profile["chi_flexible_mass"],
            manual_intervention_dose=profile["manual_intervention_dose"],
            null_means_incomplete_mapping_not_zero_or_proven_degeneracy=True,
        ),
        conditional_bounds_not_measurements=dict(
            assumptions=[
                "All currently resolved task partitions and chi remain unchanged.",
                "Each unresolved fixed task eventually assigns every original package "
                "exactly once to between one and n_x states.",
            ],
            unresolved_tasks=missing_n,
            unresolved_packages=missing_p,
            D_pi=dict(lower=degrees, upper=degrees + missing_p - missing_n),
            multi_state_tasks=dict(lower=flexible, upper=flexible + missing_n),
            chi_flexible_tasks=dict(lower=chi_flexible, upper=chi_flexible + missing_n),
            M_flex=dict(
                lower=str(Fraction(flexible, N)), upper=str(Fraction(flexible + missing_n, N))
            ),
            chi_flexible_mass=dict(
                lower=str(Fraction(chi_flexible, N)),
                upper=str(Fraction(chi_flexible + missing_n, N)),
            ),
            does_not_replace_null_full_population_measurements=True,
            does_not_establish_state_semantic_quality_or_statistical_power=True,
        ),
        admission=dict(
            material_complete=support["material_complete"],
            training_admitted=result["training_admitted"],
            binding_exists=(root / "material/binding/record.json").exists(),
            training_started=seal["training_started"],
            all_originals_retained=result["all_originals_retained"],
            remaining_blocker_counts=dict(blockers),
        ),
        report_only=True,
        source_files_modified=False,
        API_calls_by_report=0,
        GPU_used_by_report=False,
        audit_script=dict(
            repository_path="trusted_data_synthesis/scripts/finqa_v14_support_audit.py",
            sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ),
    )
    return body | dict(id=digest(body))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(summarize(args.root), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
