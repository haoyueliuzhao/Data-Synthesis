"""Authorized truthful SEC contact declaration after cooldown; no route rotation.

Old denial evidence remains immutable. One directory GET at most; another denial
stops this revision permanently. New financial selection and builder are unchanged.
"""

import argparse
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from types import FunctionType, SimpleNamespace

import retry_direction_calibration_sources_20260926 as previous

original, c, p = previous.original, previous.c, previous.p
SCRIPT = "trusted_data_synthesis/scripts/prepare_calibration_sources_compliance_20260926.py"
CONTACT = "zxr18726189832@outlook.com"
ROUTE = {"kind": "proxy", "url": previous.PROXY}
POLICY = "https://www.sec.gov/about/webmaster-frequently-asked-questions"


def folder():
    return c.RAW / "panel_sources_compliance_revision_02"


def previous_evidence():
    return {
        str(path.relative_to(c.RAW)): p.sha(path)
        for base in (original.folder(), previous.folder())
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }


def _unblocked():
    p.require(
        not (folder() / "access_blocked.json").exists(),
        "calibration_compliance.new_denial_is_permanent_stop",
    )


def _parents(root):
    base = original.read_plan(root)
    parent = p.checked(
        p.read_json(previous.folder() / "acquisition_plan.json"),
        "direction_calibration_source_acquisition_plan",
    )
    denied = p.read_json(previous.folder() / "access_blocked.json")
    route = p.checked(
        p.read_json(previous.folder() / "route.json"), "calibration_source_transport_route"
    )
    p.require(
        parent["parent_acquisition_plan_id"] == base["id"]
        and parent["parent_evidence"] == previous.parent_evidence()
        and denied["status"] == 403
        and denied["url"] == base["official_directory_url"]
        and route["plan_id"] == parent["id"]
        and route["route"] == ROUTE
        and p.read_json(original.folder() / "network/state.json")["requests"] == 3
        and p.read_json(previous.folder() / "network/state.json")["requests"] == 1
        and not (previous.folder() / "roster.json").exists(),
        "calibration_compliance.exact_prior_four_attempts_and_denial",
    )
    for name, digest in parent["sources"].items():
        p.require(p.sha(root / name) == digest, "calibration_compliance.frozen_parent_source")
    return base, parent, denied


def _cooldown(denied_at):
    p.require(
        time.time() >= datetime.fromisoformat(denied_at).timestamp() + 600,
        "calibration_compliance.at_least600_seconds_after_denial",
    )


def register(root):
    target = folder() / "acquisition_plan.json"
    if target.exists():
        return read_plan(root)
    base, parent, denied = _parents(root)
    _unblocked()
    _cooldown(denied["at"])
    p.require(
        "@" in CONTACT and "\n" not in CONTACT and "\r" not in CONTACT,
        "calibration_compliance.truthful_confirmed_contact",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    payload = (root / SCRIPT).read_bytes()
    p.require(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "calibration_compliance.committed_adapter",
    )
    fields = {key: value for key, value in base.items() if key not in ("id", "schema_version")}
    fields.update(
        code_commit=head,
        at=p.now(),
        sources={**parent["sources"], SCRIPT: p.sha(payload)},
        execution_revision="truthful_contact_revision_02",
        parent_acquisition_plan_id=parent["id"],
        original_acquisition_plan_id=base["id"],
        previous_evidence=previous_evidence(),
        user_authorization="2026-09-26 排查原因，恢复实验；沿用该邮箱；DeepSeek API key 正常",
        contact_email=CONTACT,
        user_agent=f"Data-Synthesis academic research {CONTACT} https://github.com/haoyueliuzhao/Data-Synthesis",
        policy_basis=POLICY,
        identity_purpose="truthful project administrator contact, not browser impersonation",
        old_denial_at=denied["at"],
        minimum_denial_cooldown_seconds=600,
        fixed_route=ROUTE,
        additional_TLS_diagnostics=0,
        direct_connections=0,
        directory_attempt_cap=1,
        max_HTTP_requests=193,
        previous_HTTP_attempts=4,
        cumulative_HTTP_attempt_cap=197,
        minimum_request_interval_seconds=2,
        scientific_rules_changed=False,
        same_source_selection_no_results_consulted=True,
        retry_after_another_403_or_429=False,
    )
    plan = p.record("direction_calibration_source_acquisition_plan", **fields)
    c.write(target, plan)
    return plan


def read_plan(root):
    base, parent, denied = _parents(root)
    _unblocked()
    plan = p.checked(
        p.read_json(folder() / "acquisition_plan.json"),
        "direction_calibration_source_acquisition_plan",
    )
    _cooldown(plan["old_denial_at"])
    p.require(
        plan["parent_acquisition_plan_id"] == parent["id"]
        and plan["original_acquisition_plan_id"] == base["id"]
        and plan["previous_evidence"] == previous_evidence()
        and plan["old_denial_at"] == denied["at"]
        and plan["fixed_route"] == ROUTE
        and plan["contact_email"] == CONTACT
        and plan["directory_attempt_cap"] == 1
        and plan["max_HTTP_requests"] == 193
        and plan["previous_HTTP_attempts"] == 4
        and plan["cumulative_HTTP_attempt_cap"] == 197
        and plan["minimum_request_interval_seconds"] == 2
        and plan["additional_TLS_diagnostics"] == plan["direct_connections"] == 0
        and plan["user_agent"]
        == f"Data-Synthesis academic research {CONTACT} https://github.com/haoyueliuzhao/Data-Synthesis",
        "calibration_compliance.frozen_revision_and_previous_evidence",
    )
    changed = {
        "id",
        "schema_version",
        "at",
        "code_commit",
        "sources",
        "user_agent",
        "max_HTTP_requests",
        "minimum_request_interval_seconds",
    }
    for key, value in base.items():
        if key not in changed:
            p.require(
                plan[key] == value, "calibration_compliance.unchanged_scientific_contract:" + key
            )
    for name, digest in plan["sources"].items():
        p.require(p.sha(root / name) == digest, "calibration_compliance.frozen_source:" + name)
    return plan


def _fixed_opener(plan, *handlers):
    _unblocked()
    p.require(plan["fixed_route"] == ROUTE, "calibration_compliance.original_local_proxy_only")
    return urllib.request.build_opener(
        previous.FixedProxy({"https": ROUTE["url"]}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        *handlers,
    )


def _collector(plan):
    request = SimpleNamespace(
        Request=urllib.request.Request,
        build_opener=lambda *handlers: _fixed_opener(plan, *handlers),
    )
    namespace = {
        **vars(original),
        "folder": folder,
        "read_plan": read_plan,
        "urllib": SimpleNamespace(error=urllib.error, request=request),
    }
    for name in ("save_response", "get_asset", "acquire"):
        source = getattr(original, name)
        namespace[name] = FunctionType(
            source.__code__, namespace, source.__name__, source.__defaults__, source.__closure__
        )
        namespace[name].__kwdefaults__ = source.__kwdefaults__
    legacy_get_asset = namespace["get_asset"]

    def checked_get_asset(plan, key, url):
        _unblocked()
        _cooldown(plan["old_denial_at"])
        # A stricter execution view of the same registered contract; never a larger budget.
        execution = {**plan, "max_attempts_per_asset": 1} if key == "directory" else plan
        return legacy_get_asset(execution, key, url)

    namespace["get_asset"] = checked_get_asset
    return SimpleNamespace(get_asset=checked_get_asset, acquire=namespace["acquire"])


def acquire(root):
    plan = read_plan(root)
    return _collector(plan).acquire(root)


def run(root):
    with c.locked(folder() / "revision.lock", blocking=False):
        try:
            sources = acquire(root)
            output = folder() / "calibration_panel"
            admission = output / "admission.json"
            value = (
                p.checked(p.read_json(admission), "calibration_panel_admission")
                if admission.exists()
                else original.panel.build(root, sources, output)["admission"]
            )
            p.require(
                value["source_registration_id"] == sources["id"],
                "calibration_compliance.panel_bound_to_new_sources",
            )
            completion = dict(
                source_registration_id=sources["id"],
                panel_admission_id=value["id"],
                passed=value["passed"],
                new_model_calls=0,
                at=p.now(),
            )
            path = folder() / "completion.json"
            if path.exists():
                prior = p.read_json(path)
                p.require(
                    all(prior[k] == v for k, v in completion.items() if k != "at"),
                    "calibration_compliance.same_completion",
                )
            else:
                c.write(path, completion)
            c.emit(dict(event="calibration_compliance_panel_admission", **completion))
            return 0 if value["passed"] else 1
        except Exception as error:
            c.write(
                folder() / "needs_attention.json",
                dict(error=repr(error), at=p.now()),
                immutable=False,
            )
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("register", "run"), required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "register":
        value = register(root)
        c.emit(dict(event="calibration_compliance_registered", id=value["id"], HTTP_cap=193))
    else:
        raise SystemExit(run(root))
