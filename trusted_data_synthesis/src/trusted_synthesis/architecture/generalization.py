from __future__ import annotations

import ast
from collections import Counter
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.hashing import canonical_hash

GENERALIZATION_CONTRACT_VERSION = "generalization_contract.v1.1"
_CONCRETE_DOMAINS = frozenset({"finance", "legal", "science"})
_DOMAIN_INTERPRETATION_FIELDS = frozenset(
    {
        "currency",
        "fiscal_year",
        "fiscal_quarter",
        "seasonal_adjustment",
        "vintage_policy",
        "jurisdiction",
        "authority_level",
        "confidence_interval",
        "population",
        "protocol",
    }
)


class GeneralizationViolation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    violation_type: str
    path: str
    line: int
    symbol: str
    message: str


class GeneralizationAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str
    scanned_file_count: int
    core_domain_import_count: int
    core_domain_branch_count: int
    core_domain_field_access_count: int
    violations: tuple[GeneralizationViolation, ...]
    violation_counts: dict[str, int]
    audit_hash: str

    @property
    def passed(self) -> bool:
        return not self.violations


def audit_generalization_contract(source_root: Path) -> GeneralizationAudit:
    """Audit the Core dependency direction and domain-neutral interpretation boundary."""

    core_root = source_root / "trusted_synthesis" / "core"
    violations: list[GeneralizationViolation] = []
    paths = tuple(sorted(core_root.rglob("*.py")))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = str(path.relative_to(source_root))
        for node in ast.walk(tree):
            violations.extend(_import_violations(node, relative))
            violations.extend(_branch_violations(node, relative))
            violations.extend(_field_access_violations(node, relative))
    ordered = tuple(
        sorted(
            violations,
            key=lambda item: (item.path, item.line, item.violation_type, item.symbol),
        )
    )
    counts = Counter(item.violation_type for item in ordered)
    identity = {
        "contract_version": GENERALIZATION_CONTRACT_VERSION,
        "rules": {
            "concrete_domains": sorted(_CONCRETE_DOMAINS),
            "protected_domain_fields": sorted(_DOMAIN_INTERPRETATION_FIELDS),
            "branch_node_types": ["If", "IfExp", "Match", "comprehension"],
        },
        "files": [
            {
                "path": str(path.relative_to(source_root)),
                "sha256": sha256(path.read_bytes()).hexdigest(),
            }
            for path in paths
        ],
        "violations": [item.model_dump(mode="json") for item in ordered],
    }
    return GeneralizationAudit(
        contract_version=GENERALIZATION_CONTRACT_VERSION,
        scanned_file_count=len(paths),
        core_domain_import_count=counts["domain_import"],
        core_domain_branch_count=counts["domain_branch"],
        core_domain_field_access_count=counts["domain_field_access"],
        violations=ordered,
        violation_counts=dict(sorted(counts.items())),
        audit_hash=canonical_hash(identity, prefix="generalization_audit:"),
    )


def assert_generalization_contract(source_root: Path) -> GeneralizationAudit:
    report = audit_generalization_contract(source_root)
    if report.violations:
        details = "; ".join(
            f"{item.path}:{item.line}:{item.violation_type}:{item.symbol}"
            for item in report.violations
        )
        raise AssertionError(f"generalization contract failed: {details}")
    return report


def _import_violations(node: ast.AST, path: str) -> tuple[GeneralizationViolation, ...]:
    names: tuple[str, ...] = ()
    if isinstance(node, ast.Import):
        names = tuple(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        names = (node.module,)
    return tuple(
        _violation(
            "domain_import",
            path,
            node,
            name,
            "Core must depend on plugin protocols, never a concrete domain package.",
        )
        for name in names
        if name == "trusted_synthesis.domains" or name.startswith("trusted_synthesis.domains.")
    )


def _branch_violations(node: ast.AST, path: str) -> tuple[GeneralizationViolation, ...]:
    if not isinstance(node, (ast.If, ast.IfExp, ast.Match, ast.comprehension)):
        return ()
    concrete = sorted(
        {
            value
            for expression in _branch_expressions(node)
            for value in _string_constants(expression)
        }
        & _CONCRETE_DOMAINS
    )
    return tuple(
        _violation(
            "domain_branch",
            path,
            node,
            domain,
            "Core cannot select behavior by a concrete domain label.",
        )
        for domain in concrete
    )


def _branch_expressions(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, (ast.If, ast.IfExp)):
        return (node.test,)
    if isinstance(node, ast.Match):
        return (
            node.subject,
            *(case.pattern for case in node.cases),
            *(case.guard for case in node.cases if case.guard is not None),
        )
    if isinstance(node, ast.comprehension):
        return tuple(node.ifs)
    return ()


def _field_access_violations(node: ast.AST, path: str) -> tuple[GeneralizationViolation, ...]:
    if not isinstance(node, ast.Attribute) or node.attr not in _DOMAIN_INTERPRETATION_FIELDS:
        return ()
    return (
        _violation(
            "domain_field_access",
            path,
            node,
            node.attr,
            "Core may transport domain context but cannot interpret a domain-specific field.",
        ),
    )


def _string_constants(node: ast.AST) -> set[str]:
    return {
        child.value.casefold()
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


def _violation(
    violation_type: str,
    path: str,
    node: ast.AST,
    symbol: str,
    message: str,
) -> GeneralizationViolation:
    return GeneralizationViolation(
        violation_type=violation_type,
        path=path,
        line=getattr(node, "lineno", 0),
        symbol=symbol,
        message=message,
    )
