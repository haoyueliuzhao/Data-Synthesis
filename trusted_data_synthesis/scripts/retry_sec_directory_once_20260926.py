"""One explicitly requested SEC directory retry; no downstream acquisition."""

import argparse
import subprocess
from pathlib import Path
from types import FunctionType, SimpleNamespace

import prepare_calibration_sources_compliance_20260926 as prior

c, p, original = prior.c, prior.p, prior.original
SCRIPT = "trusted_data_synthesis/scripts/retry_sec_directory_once_20260926.py"


def folder():
    return c.RAW / "sec_directory_single_retry_20260926_1054"


def evidence():
    return {
        str(path.relative_to(c.RAW)): p.sha(path)
        for base in (original.folder(), prior.previous.folder(), prior.folder())
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }


def run(root):
    parent = prior.read_plan(root)
    p.require(
        sum(
            p.read_json(base / "network/state.json")["requests"]
            for base in (original.folder(), prior.previous.folder(), prior.folder())
        )
        == 5,
        "SEC_single_retry.five_prior_requests_preserved",
    )
    with c.locked(folder() / "execution.lock", blocking=False):
        path = folder() / "plan.json"
        if path.exists():
            plan = p.checked(p.read_json(path), "SEC_directory_single_retry_plan")
            p.require(
                plan["parent_plan_id"] == parent["id"]
                and plan["old_evidence"] == evidence()
                and plan["adapter_sha256"] == p.sha(root / SCRIPT),
                "SEC_single_retry.same_frozen_authority",
            )
        else:
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            payload = (root / SCRIPT).read_bytes()
            p.require(
                payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
                "SEC_single_retry.committed_adapter",
            )
            plan = p.record(
                "SEC_directory_single_retry_plan",
                parent_plan_id=parent["id"],
                old_evidence=evidence(),
                code_commit=head,
                adapter_sha256=p.sha(payload),
                user_authorization="2026-09-26 user: 重试SEC",
                official_directory_url=parent["official_directory_url"],
                user_agent=parent["user_agent"],
                fixed_route=parent["fixed_route"],
                max_HTTP_requests=1,
                max_attempts_per_asset=1,
                minimum_request_interval_seconds=2,
                maximum_response_bytes=parent["maximum_response_bytes"],
                prior_HTTP_attempts=5,
                cumulative_HTTP_attempt_cap=6,
                companyfacts_requests=0,
                new_model_calls=0,
                new_evaluation_sessions=0,
                new_source_panel_admission=False,
                selection_rule=parent["selection_rule"],
                no_redirects_or_route_changes=True,
                at=p.now(),
            )
            c.write(path, plan)
            c.emit(dict(event="SEC_single_retry_registered", id=plan["id"], HTTP_cap=1))
        p.require(
            plan["max_HTTP_requests"] == plan["max_attempts_per_asset"] == 1
            and plan["official_directory_url"] == parent["official_directory_url"]
            and plan["fixed_route"] == parent["fixed_route"]
            and plan["user_agent"] == parent["user_agent"],
            "SEC_single_retry.only_registered_directory",
        )
        request = SimpleNamespace(
            Request=prior.urllib.request.Request,
            build_opener=lambda *handlers: prior._fixed_opener(parent, *handlers),
        )
        namespace = {
            **vars(original),
            "folder": folder,
            "urllib": SimpleNamespace(error=prior.urllib.error, request=request),
        }
        for name in ("save_response", "get_asset"):
            function = getattr(original, name)
            namespace[name] = FunctionType(
                function.__code__,
                namespace,
                function.__name__,
                function.__defaults__,
                function.__closure__,
            )
        try:
            snapshot, receipt = namespace["get_asset"](
                plan, "directory", plan["official_directory_url"]
            )
            result = dict(
                plan_id=plan["id"],
                status="DIRECTORY_RECEIVED_ONLY",
                HTTP_status=receipt["status"],
                bytes=receipt["bytes"],
                sha256=receipt["sha256"],
                snapshot=str(snapshot),
                companyfacts_requests=0,
                panel_admitted=False,
                at=p.now(),
            )
        except Exception as error:
            result = dict(plan_id=plan["id"], status="STOPPED", error=repr(error), at=p.now())
        result["old_evidence_unchanged"] = plan["old_evidence"] == evidence()
        c.write(folder() / "latest_result.json", result, immutable=False)
        c.emit(dict(event="SEC_single_retry_result", **result))
        return 0 if result["status"] == "DIRECTORY_RECEIVED_ONLY" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    raise SystemExit(run(args.root.resolve()))
