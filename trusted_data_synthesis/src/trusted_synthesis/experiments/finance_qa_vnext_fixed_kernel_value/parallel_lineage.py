"""Exact execution identities for one parallel A tail and untouched originals."""

from . import protocol as p

TAIL = ("A", "minus", 47)
BINDING_FIELDS = {
    "study_freeze_id",
    "surface_manifest_id",
    "kernel_id",
    "training_configuration_id",
    "decoder_config_id",
}
PHYSICAL_FIELDS = (
    "model",
    "base_dtype",
    "adapter_dtype",
    "lora_rank",
    "lora_alpha",
    "lora_dropout",
    "target_modules",
    "bias_training",
    "embedding_or_lm_head_training",
    "maximum_sequence_length",
)


def _base_training_config():
    from .trajectory_training import training_config

    return training_config()


def _tail_training_config():
    from .parallel_training import training_config

    return training_config()


def _run(pool, arm, seed):
    p.require(
        pool in p.POOLS and arm in p.ARMS and type(seed) is int and seed in p.SEEDS,
        "parallel_lineage.exact_registered_run",
    )
    return pool, arm, seed


def expected_training_config(pool, arm, seed):
    key = _run(pool, arm, seed)
    base = _base_training_config()
    if key != TAIL:
        return base
    actual = _tail_training_config()
    p.require(
        actual["id"] != base["id"]
        and all(actual.get(field) == base[field] for field in PHYSICAL_FIELDS if field in base),
        "parallel_lineage.same_physical_decoder_distinct_execution_identity",
    )
    return actual


def configuration_ids():
    """Prospective table; the unchanged selection gate still restricts B runs."""
    return {
        "_".join(map(str, (pool, arm, seed))): expected_training_config(pool, arm, seed)["id"]
        for pool in p.POOLS
        for arm in p.ARMS
        for seed in p.SEEDS
    }


def validate_binding(value, binding, *, pool=None, arm=None, seed=None):
    """Check common fields plus exact actual configuration, without rewriting."""
    p.require(
        isinstance(value, dict)
        and isinstance(binding, dict)
        and set(binding) <= BINDING_FIELDS
        and "training_configuration_id" in binding,
        "parallel_lineage.closed_common_binding",
    )
    base = _base_training_config()
    p.require(
        binding["training_configuration_id"] == base["id"],
        "parallel_lineage.aggregate_uses_base_scientific_configuration",
    )
    explicit = any(item is not None for item in (pool, arm, seed))
    keys = ("pool", "arm", "seed")
    if explicit:
        key = _run(pool, arm, seed)
        p.require(
            tuple(value.get(name) for name in keys) == key,
            "parallel_lineage.report_matches_explicit_run",
        )
    elif any(name in value for name in keys):
        key = _run(*(value.get(name) for name in keys))
    else:
        key = None
    configuration_id = expected_training_config(*key)["id"] if key is not None else base["id"]
    p.require(
        all(
            value.get(name)
            == (configuration_id if name == "training_configuration_id" else expected)
            for name, expected in binding.items()
        ),
        "parallel_lineage.exact_actual_configuration_and_common_binding",
    )
    return value


def execution_lineage(reports=None):
    """Small backend/config lineage; raw reports are not re-checked here."""
    base, tail = _base_training_config(), expected_training_config(*TAIL)
    actual = []
    if reports is not None:
        seen = set()
        for report in reports:
            key = _run(report["pool"], report["arm"], report["seed"])
            expected = expected_training_config(*key)
            p.require(
                key not in seen and report["training_configuration_id"] == expected["id"],
                "parallel_lineage.unique_actual_report_configurations",
            )
            seen.add(key)
            actual.append(
                {
                    "pool": key[0],
                    "arm": key[1],
                    "seed": key[2],
                    "training_report_id": report["id"],
                    "training_configuration_id": report["training_configuration_id"],
                    "execution_design": expected.get("execution_design"),
                    "parallel_tail": key == TAIL,
                }
            )
        actual.sort(key=lambda row: (row["pool"], row["arm"], row["seed"]))
    return p.record(
        "heterogeneous_execution_lineage",
        scientific_training_configuration_id=base["id"],
        single_gpu_training_configuration_id=base["id"],
        parallel_tail_training_configuration_id=tail["id"],
        parallel_tail={"pool": TAIL[0], "arm": TAIL[1], "seed": TAIL[2]},
        actual_training_reports=actual,
        heterogeneous_execution=True,
        old_training_report_bytes_rewritten=False,
        actual_configuration_ids_relabelled_as_common=False,
        tail_dropout_stream_claims_require_actual_runtime_receipts=True,
        bitwise_gradient_or_optimizer_equivalence_claimed=False,
        all_B_runs_keep_single_gpu_trajectory_configuration=True,
        statistical_selection_and_bootstrap_rules_changed=False,
    )
