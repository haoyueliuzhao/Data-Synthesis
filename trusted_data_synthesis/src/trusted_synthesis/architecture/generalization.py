from __future__ import annotations

import ast
from collections import Counter
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.hashing import canonical_hash

GENERALIZATION_CONTRACT_VERSION = "generalization_contract.v1.2"
_COMMON_PACKAGES = ("core", "runtime", "architecture")
_AUDIT_EXEMPT_PATHS = frozenset({"trusted_synthesis/architecture/generalization.py"})
_DOMAIN_INTERPRETATION_FIELDS = frozenset(
    {
        "currency",
        "accounting_standard",
        "financial_scope",
        "fiscal_period",
        "fiscal_year",
        "fiscal_quarter",
        "seasonal_adjustment",
        "vintage_policy",
        "jurisdiction",
        "authority_level",
        "authority_priority",
        "legal_effect",
        "confidence_interval",
        "confidence_level",
        "uncertainty",
        "population",
        "protocol",
        "sample_size",
        "study_design",
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
    scanned_packages: tuple[str, ...]
    discovered_domains: tuple[str, ...]
    exempted_files: tuple[str, ...]
    core_domain_import_count: int
    core_domain_branch_count: int
    core_domain_field_access_count: int
    dynamic_domain_import_count: int
    domain_dispatch_count: int
    violations: tuple[GeneralizationViolation, ...]
    violation_counts: dict[str, int]
    audit_hash: str

    @property
    def passed(self) -> bool:
        return not self.violations


def audit_generalization_contract(source_root: Path) -> GeneralizationAudit:
    """Audit every package declared domain-neutral by the architecture contract."""

    package_root = source_root / "trusted_synthesis"
    concrete_domains = _discover_domains(package_root / "domains")
    paths = tuple(
        sorted(
            path for package in _COMMON_PACKAGES for path in (package_root / package).rglob("*.py")
        )
    )
    violations: list[GeneralizationViolation] = []
    exempted: list[str] = []
    for path in paths:
        relative = str(path.relative_to(source_root))
        if relative in _AUDIT_EXEMPT_PATHS:
            exempted.append(relative)
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        constants = _module_constants(tree)
        module_name = _module_name(path, source_root)
        for node in ast.walk(tree):
            violations.extend(
                _import_violations(
                    node,
                    relative,
                    module_name,
                    constants,
                    concrete_domains,
                )
            )
            violations.extend(_branch_violations(node, relative, constants, concrete_domains))
            violations.extend(_field_access_violations(node, relative, constants))
            violations.extend(_dispatch_violations(node, relative, constants, concrete_domains))
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
            "common_packages": _COMMON_PACKAGES,
            "concrete_domains": concrete_domains,
            "protected_domain_fields": sorted(_DOMAIN_INTERPRETATION_FIELDS),
            "audit_exempt_paths": sorted(_AUDIT_EXEMPT_PATHS),
            "branch_node_types": ["If", "IfExp", "Match", "comprehension"],
            "dynamic_imports": ["importlib.import_module", "__import__"],
            "dispatch_node_types": ["Dict"],
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
        scanned_packages=_COMMON_PACKAGES,
        discovered_domains=concrete_domains,
        exempted_files=tuple(sorted(exempted)),
        core_domain_import_count=counts["domain_import"] + counts["dynamic_domain_import"],
        core_domain_branch_count=counts["domain_branch"] + counts["domain_dispatch"],
        core_domain_field_access_count=counts["domain_field_access"],
        dynamic_domain_import_count=counts["dynamic_domain_import"],
        domain_dispatch_count=counts["domain_dispatch"],
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


def _discover_domains(domains_root: Path) -> tuple[str, ...]:
    if not domains_root.exists():
        return ()
    return tuple(
        sorted(
            path.name.casefold()
            for path in domains_root.iterdir()
            if path.is_dir() and not path.name.startswith(("_", "."))
        )
    )


def _module_name(path: Path, source_root: Path) -> str:
    return ".".join(path.relative_to(source_root).with_suffix("").parts)


def _module_constants(tree: ast.Module) -> dict[str, frozenset[str]]:
    constants: dict[str, frozenset[str]] = {}
    assignments: dict[str, ast.AST] = {}
    for node in tree.body:
        name: str | None = None
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                name, value = target.id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name, value = node.target.id, node.value
        if name and value is not None:
            assignments[name] = value
    for _ in range(len(assignments) + 1):
        changed = False
        for name, value in assignments.items():
            resolved = frozenset(_resolved_strings(value, constants))
            if resolved and resolved != constants.get(name):
                constants[name] = resolved
                changed = True
        if not changed:
            break
    return constants


def _resolved_strings(node: ast.AST, constants: dict[str, frozenset[str]]) -> set[str]:
    values: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.add(child.value.casefold())
        elif isinstance(child, ast.Name):
            values.update(constants.get(child.id, ()))
    return values


def _import_violations(
    node: ast.AST,
    path: str,
    module_name: str,
    constants: dict[str, frozenset[str]],
    concrete_domains: tuple[str, ...],
) -> tuple[GeneralizationViolation, ...]:
    names = _imported_modules(node, module_name)
    direct = tuple(
        _violation(
            "domain_import",
            path,
            node,
            name,
            "Domain-neutral packages must depend on plugin protocols, not domain packages.",
        )
        for name in names
        if _is_domain_module(name)
    )
    if not isinstance(node, ast.Call) or not _is_dynamic_import_call(node.func):
        return direct
    dynamic_names = _resolved_strings(node.args[0], constants) if node.args else set()
    dynamic = tuple(
        _violation(
            "dynamic_domain_import",
            path,
            node,
            name,
            "Dynamic import cannot bypass the domain-plugin dependency boundary.",
        )
        for name in sorted(dynamic_names)
        if _is_domain_module(name)
    )
    return (*direct, *dynamic)


def _imported_modules(node: ast.AST, module_name: str) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if not isinstance(node, ast.ImportFrom):
        return ()
    module = node.module or ""
    if node.level:
        package = module_name.split(".")
        if package and package[-1] != "__init__":
            package = package[:-1]
        remove = max(node.level - 1, 0)
        if remove:
            package = package[:-remove]
        base = ".".join((*package, *module.split("."))) if module else ".".join(package)
    else:
        base = module
    if module:
        return (base,)
    return tuple(f"{base}.{alias.name}" if base else alias.name for alias in node.names)


def _is_dynamic_import_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Name)
        and node.id == "__import__"
        or isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "importlib"
        and node.attr == "import_module"
    )


def _is_domain_module(name: str) -> bool:
    folded = name.casefold()
    if folded == "trusted_synthesis.domains" or folded.startswith("trusted_synthesis.domains."):
        return True
    return False


def _branch_violations(
    node: ast.AST,
    path: str,
    constants: dict[str, frozenset[str]],
    concrete_domains: tuple[str, ...],
) -> tuple[GeneralizationViolation, ...]:
    if not isinstance(node, (ast.If, ast.IfExp, ast.Match, ast.comprehension)):
        return ()
    concrete = sorted(
        {
            value
            for expression in _branch_expressions(node)
            for value in _resolved_strings(expression, constants)
        }
        & set(concrete_domains)
    )
    return tuple(
        _violation(
            "domain_branch",
            path,
            node,
            domain,
            "Domain-neutral packages cannot branch on a concrete domain label.",
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


def _field_access_violations(
    node: ast.AST,
    path: str,
    constants: dict[str, frozenset[str]],
) -> tuple[GeneralizationViolation, ...]:
    fields: set[str] = set()
    if isinstance(node, ast.Attribute):
        fields.add(node.attr)
    elif isinstance(node, ast.Subscript):
        fields.update(_resolved_strings(node.slice, constants))
    return tuple(
        _violation(
            "domain_field_access",
            path,
            node,
            field,
            "Core may transport domain context but cannot interpret a domain-specific field.",
        )
        for field in sorted(fields & _DOMAIN_INTERPRETATION_FIELDS)
    )


def _dispatch_violations(
    node: ast.AST,
    path: str,
    constants: dict[str, frozenset[str]],
    concrete_domains: tuple[str, ...],
) -> tuple[GeneralizationViolation, ...]:
    if not isinstance(node, ast.Dict):
        return ()
    domains = sorted(
        {
            value
            for key in node.keys
            if key is not None
            for value in _resolved_strings(key, constants)
        }
        & set(concrete_domains)
    )
    return tuple(
        _violation(
            "domain_dispatch",
            path,
            node,
            domain,
            "Dictionary dispatch cannot select implementation by concrete domain.",
        )
        for domain in domains
    )


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
