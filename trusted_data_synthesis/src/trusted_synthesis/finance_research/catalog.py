"""Declared dataset roles, not automatic permission to train or tune on a benchmark."""

from __future__ import annotations

from .contracts import Role

DATASETS = {
    "finqa": {
        "role": "main_training_and_same_family_test",
        "source": "https://github.com/czyssrs/FinQA",
        "revision": "0f16e2867befa6840783e58be38c9efb9229d742",
        "counts": {"train": 6251, "dev": 883, "test": 1147},
        "license": "MIT (upstream repository)",
        "caveat": "test is public test; private_test has no local reference",
    },
    "tatqa": {
        "role": "external_test_until_separate_training_protocol",
        "source": "https://github.com/NExTplusplus/TAT-QA",
        "revision": "870accc41953dcde885aabeb963d94aabdc0fbc3",
        "counts": {"train": 13215, "dev": 1668, "test": 1669},
        "counts_basis": "upstream advertised counts; blind test snapshot",
        "available_labelled_snapshot_counts": {"train": 13215, "dev": 1668, "test": 1663},
        "test_snapshot_caveat": (
            "at this commit test_gold has 1663 questions/277 contexts, unlike blind test "
            "1669/278; question IDs were changed; no automatic alignment or completion"
        ),
        "license": "CC BY 4.0 dataset; MIT scorer",
        "caveat": "context groups are not known report/company groups",
    },
    "financemath": {
        "role": "external_evaluation_only",
        "source": "https://huggingface.co/datasets/yale-nlp/FinanceMath",
        "counts": {"validation": 200, "test": 1000},
        "access": "user-provided lawful local snapshot; no automated gated download",
        "caveat": "acceptance of upstream access conditions is not inferred",
    },
    "multihiertt": {
        "role": "blocked_pending_parent_overlap_audit",
        "source": "https://github.com/psunlpgroup/MultiHiertt",
        "caveat": "2119 inherited FinQA questions require parent-role audit",
    },
    "openenv290": {
        "role": "evaluation_only",
        "caveat": (
            "Snorkel AI/OpenEnv FinQABenchmark evaluation suite; not the original "
            "6251-question FinQA training dataset and no parent-task lineage inferred; "
            "never SFT or feedback material"
        ),
    },
}

_ALIASES = {
    "finqa": "finqa",
    "tatqa": "tatqa",
    "tat-qa": "tatqa",
    "financemath": "financemath",
    "finance_math": "financemath",
    "multihiertt": "multihiertt",
    "openenv290": "openenv290",
    "openenv_finqa290": "openenv290",
    "openenv-finqa-290": "openenv290",
}


def canonical_dataset(dataset: str) -> str:
    try:
        return _ALIASES[dataset.lower()]
    except KeyError as exc:
        raise ValueError(f"unregistered dataset: {dataset}") from exc


def validate_dataset_role(
    dataset: str, split: str, role: Role, *, separate_training: bool = False
) -> None:
    """Fail closed on role drift; this does not replace a cross-source leakage audit.

    ``separate_training`` is a new TAT-QA experiment declaration, not a switch that
    keeps calling its test a cross-dataset transfer test after TAT-QA training.
    """
    dataset = canonical_dataset(dataset)
    split = split.lower()
    training_roles = {"sft", "feedback", "calibration", "reserve"}
    if dataset == "multihiertt":
        raise ValueError("MultiHiertt blocked pending FinQA parent/role overlap audit")
    if dataset == "openenv290":
        allowed = {"test"}
    elif dataset == "financemath":
        allowed = (
            {"test"} if split == "test" else ({"development"} if split == "validation" else set())
        )
    elif dataset == "tatqa" and not separate_training:
        allowed = {"test"} if split in {"test", "test_gold"} else set()
    elif split == "train":
        allowed = training_roles
    elif split in {"dev", "validation"}:
        allowed = {"development"}
    elif split in {"test", "public_test", "publictest", "test_gold"}:
        allowed = {"test"}
    else:
        allowed = set()
    if role not in allowed:
        raise ValueError(f"role {role!r} is forbidden for {dataset}/{split}")
