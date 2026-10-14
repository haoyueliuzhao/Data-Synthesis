"""Narrow execution adapter for the sealed V32 measurement/recovery worker.

Only the stage labels, removal of its one diagnostic profile, and dependency
injection change. Numerical replay, comparisons, timing and actual response16
recovery remain inherited. The source transformer is pinned and fail-closed.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import finqa_v33_bounded_controller as control

EXPECTED_ADAPTATIONS = dict(
    controller_import=1,
    stage_allowlist=1,
    cohort_variant=1,
    disable_profile=1,
    zero_profile_count=1,
)


def adapt_source(source):
    tree = ast.parse(source)
    counts = dict.fromkeys(EXPECTED_ADAPTATIONS, 0)

    class Adapter(ast.NodeTransformer):
        function = None

        def visit_FunctionDef(self, node):
            previous = self.function
            self.function = node.name
            node = self.generic_visit(node)
            self.function = previous
            return node

        def visit_Import(self, node):
            if len(node.names) == 1 and node.names[0].name == "finqa_v32_performance_controller":
                control.require(node.names[0].asname == "control", "controller import changed")
                counts["controller_import"] += 1
                return ast.copy_location(ast.Pass(), node)
            return node

        def visit_Set(self, node):
            if self.function == "run" and ast.literal_eval(node) == {
                "micro_R0",
                "micro_R1",
                "micro_R2",
                "cohort_first",
                "cohort_resume",
            }:
                counts["stage_allowlist"] += 1
                return ast.copy_location(
                    ast.Set(elts=[ast.Constant(value=v) for v in control.STAGES]), node
                )
            return self.generic_visit(node)

        def visit_Tuple(self, node):
            if (
                self.function == "execute_cohort"
                and all(isinstance(value, ast.Constant) for value in node.elts)
                and ast.literal_eval(node) == ("R1", "R2")
            ):
                counts["cohort_variant"] += 1
                return ast.copy_location(
                    ast.Tuple(elts=[ast.Constant(value="R3")], ctx=node.ctx), node
                )
            return self.generic_visit(node)

        def visit_If(self, node):
            if self.function == "execute_micro" and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "run_profile"
                for statement in node.body
                for child in ast.walk(statement)
            ):
                control.require(
                    ast.dump(node.test) == ast.dump(ast.parse('variant == "R0"', mode="eval").body),
                    "diagnostic profile condition changed",
                )
                counts["disable_profile"] += 1
                node.test = ast.copy_location(ast.Constant(value=False), node.test)
            return self.generic_visit(node)

        def visit_keyword(self, node):
            if self.function == "execute_micro" and node.arg == "profile_responses":
                control.require(
                    ast.dump(node.value)
                    == ast.dump(ast.parse('int(variant == "R0")', mode="eval").body),
                    "diagnostic profile counter changed",
                )
                counts["zero_profile_count"] += 1
                node.value = ast.copy_location(ast.Constant(value=0), node.value)
            return self.generic_visit(node)

    tree = ast.fix_missing_locations(Adapter().visit(tree))
    control.require(counts == EXPECTED_ADAPTATIONS, "sealed worker adaptation contract changed")
    return tree, counts


def inherited_worker():
    manifest = control._sealed_body(
        control.V32_ROOT / "implementation/record.json", control.V32_IMPLEMENTATION_ID
    )
    source = Path(__file__).resolve().parent / "finqa_v32_performance_worker.py"
    if Path(__file__).resolve().parent.name != "implementation":
        source = control.V32_ROOT / "implementation" / source.name
    control.require(
        control.sha(source) == manifest["sha256"][source.name], "V32 worker bytes changed"
    )
    tree, counts = adapt_source(source.read_text())
    namespace = dict(__name__=__name__ + "_inherited", __file__=__file__, control=control)
    exec(compile(tree, str(source), "exec"), namespace)
    return namespace, dict(source=control.file_ref(source), adaptations=counts)


def dependencies():
    # Bind the original V25 loader before importing the frozen V19/V32 modules.
    training = control.frozen_training_module()
    rt = training.load_runtime()
    guard = importlib.import_module("finqa_v32_same_point_guard")
    backend = importlib.import_module("finqa_v33_activation_residency")
    control.require(backend.BACKEND_VERSION == control.BACKEND_VERSION, "R3 version changed")
    parent = backend.v32

    def session(model, theta, *, variant, **kwargs):
        control.require(variant == "R3", "only registered R3 candidate permitted")
        return backend.R3Session(
            model, theta, activation_resident_budget_bytes=16 * 1024**3, **kwargs
        )

    # Only checkpoint metadata uses this global. Accumulation bytecode and all
    # its numerical/state helpers are identical to the sealed V32 function.
    feedback = backend.optimized.bind_dependencies(
        parent.feedback_gradient, BACKEND_VERSION=backend.BACKEND_VERSION
    )
    variants = SimpleNamespace(
        __file__=backend.__file__,
        BACKEND_VERSION=backend.BACKEND_VERSION,
        optimized=backend.optimized,
        ReplaySession=session,
        feedback_gradient=feedback,
        PauseRequest=parent.PauseRequest,
        ReplayPaused=parent.ReplayPaused,
    )
    mechanism = importlib.import_module("trusted_synthesis.finance_research.v9_mechanism_execution")
    immutable = importlib.import_module("trusted_synthesis.core.immutable_artifacts")
    return training, rt, guard, variants, mechanism, immutable


_namespace, ADAPTER_RECEIPT = inherited_worker()
_micro = _namespace["execute_micro"]
_cohort = _namespace["execute_cohort"]


def execute_micro(*args, **kwargs):
    result = _micro(*args, **kwargs)
    control.require(
        result["profile_responses"] == 0 and result["diagnostic_profile"] is None,
        "V33 does not authorize a new diagnostic profile",
    )
    return dict(result, active_variant=result["variant"], execution_adapter=ADAPTER_RECEIPT)


def execute_cohort(*args, **kwargs):
    result = _cohort(*args, **kwargs)
    control.require(result["selected_variant"] == "R3", "cohort candidate drift")
    return dict(result, active_variant="R3", execution_adapter=ADAPTER_RECEIPT)


_namespace.update(
    dependencies=dependencies, execute_micro=execute_micro, execute_cohort=execute_cohort
)
run = _namespace["run"]


def __getattr__(name):
    try:
        return _namespace[name]
    except KeyError as exc:
        raise AttributeError(name) from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    args = parser.parse_args()
    result = run(args.root, args.stage, args.gpu_index)
    print(json.dumps(dict(status=result["status"], id=result["id"]), ensure_ascii=False))
