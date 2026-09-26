"""One authorized finite SEC acquisition revision; frozen old evidence is read-only.

Two TLS-only diagnostic connections at most, then one persistently pinned route.
No SEC HTTP probe, certificate bypass, proxy rotation or scientific-rule change.
"""

import argparse
import errno
import http.client
import socket
import ssl
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from types import FunctionType, SimpleNamespace
from urllib.parse import urlsplit

import prepare_direction_calibration_panel_20260926 as original

c, p = original.c, original.p
SCRIPT = "trusted_data_synthesis/scripts/retry_direction_calibration_sources_20260926.py"
PROXY = "http://127.0.0.1:7897"
ROUTES = ({"kind": "proxy", "url": PROXY}, {"kind": "direct"})


def folder():
    return c.RAW / "panel_sources_retry_revision_01"


def parent_evidence():
    return {
        str(path.relative_to(original.folder())): p.sha(path)
        for path in sorted(original.folder().rglob("*"))
        if path.is_file()
    }


def _unblocked():
    p.require(
        not (original.folder() / "access_blocked.json").exists()
        and not (folder() / "access_blocked.json").exists(),
        "calibration_retry.no_inherited_or_new_access_denial",
    )


def register(root):
    destination = folder() / "acquisition_plan.json"
    if destination.exists():
        return read_plan(root)
    parent = original.read_plan(root)
    _unblocked()
    # This approval applies to the three TLS failures, not a previously denied source.
    expected_intents = [f"{i:04d}.json" for i in (1, 2, 3)]
    p.require(
        p.read_json(original.folder() / "network/state.json")["requests"] == 3
        and sorted(x.name for x in (original.folder() / "network/directory").glob("*.json"))
        == expected_intents
        and not (original.folder() / "roster.json").exists()
        and not (original.folder() / "snapshots").exists()
        and not (original.folder() / "terminal_failures").exists(),
        "calibration_retry.only_original_three_failed_directory_attempts",
    )
    for number in (1, 2, 3):
        error = p.read_json(original.folder() / "failures/directory" / f"{number:04d}.json")
        p.require(
            error["attempt"] == number
            and error["url"] == parent["official_directory_url"]
            and "SSLEOFError" in error["error"]
            and "status" not in error,
            "calibration_retry.original_TLS_EOF_not_HTTP_denial",
        )
    # Inspect configuration without exporting proxy credentials or unrelated environment.
    p.require(
        urllib.request.getproxies().get("https") == PROXY
        and not urllib.request.proxy_bypass("www.sec.gov"),
        "calibration_retry.observed_existing_local_proxy",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    payload = (root / SCRIPT).read_bytes()
    p.require(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "calibration_retry.committed_adapter",
    )
    inherited = {key: value for key, value in parent.items() if key not in ("id", "schema_version")}
    inherited.update(
        code_commit=head,
        sources={**parent["sources"], SCRIPT: p.sha(payload)},
        at=p.now(),
        execution_revision="retry_revision_01",
        user_authorization="2026-09-26 同意：排查连接后另行登记一轮有限来源采集重试",
        parent_acquisition_plan_id=parent["id"],
        parent_evidence=parent_evidence(),
        previous_HTTP_attempts=3,
        cumulative_HTTP_attempt_cap=198,
        maximum_TLS_diagnostic_connections=2,
        diagnostic_routes=list(ROUTES),
        diagnostic_host="www.sec.gov",
        diagnostic_timeout_seconds=20,
        diagnostic_HTTP_to_SEC=0,
        diagnostic_proxy_CONNECT_is_separate_network_work=True,
        direct_fallback_only="explicit network EOF/timeout/reset/refused/DNS/unreachable",
        HTTP_route="first successful TLS route, persist once; never switch after HTTP begins",
        certificate_verification="default trust store and original hostname, never disabled",
        scientific_rules_changed=False,
        all_old_failure_and_budget_evidence_preserved=True,
    )
    plan = p.record("direction_calibration_source_acquisition_plan", **inherited)
    c.write(destination, plan)
    return plan


def read_plan(root):
    parent = original.read_plan(root)
    _unblocked()
    plan = p.checked(
        p.read_json(folder() / "acquisition_plan.json"),
        "direction_calibration_source_acquisition_plan",
    )
    p.require(
        plan["parent_acquisition_plan_id"] == parent["id"]
        and plan["parent_evidence"] == parent_evidence()
        and plan["execution_revision"] == "retry_revision_01"
        and plan["diagnostic_routes"] == list(ROUTES)
        and plan["diagnostic_host"] == "www.sec.gov"
        and plan["diagnostic_timeout_seconds"] == 20
        and plan["maximum_TLS_diagnostic_connections"] == 2
        and plan["previous_HTTP_attempts"] == 3
        and plan["cumulative_HTTP_attempt_cap"] == 198,
        "calibration_retry.frozen_parent_evidence_and_finite_revision",
    )
    for key, value in parent.items():
        if key not in ("id", "schema_version", "at", "code_commit", "sources"):
            p.require(plan[key] == value, "calibration_retry.unchanged_contract:" + key)
    for name, expected in plan["sources"].items():
        p.require(p.sha(root / name) == expected, "calibration_retry.frozen_code:" + name)
    return plan


def _tls_probe(route, host, timeout=20):
    context = ssl.create_default_context()
    if route["kind"] == "proxy":
        proxy = urlsplit(route["url"])
        connection = http.client.HTTPSConnection(
            proxy.hostname, proxy.port, timeout=timeout, context=context
        )
        connection.set_tunnel(host, 443)
    else:
        connection = http.client.HTTPSConnection(host, 443, timeout=timeout, context=context)
    try:
        # CONNECT to the registered local proxy when needed; no SEC GET/HEAD is sent.
        connection.connect()
        return dict(tls_version=connection.sock.version(), cipher=list(connection.sock.cipher()))
    finally:
        connection.close()


def _network_failure(error):
    if isinstance(error, ssl.SSLCertVerificationError):
        return False
    if isinstance(error, (ssl.SSLEOFError, TimeoutError, ConnectionError, socket.gaierror)):
        return True
    return isinstance(error, OSError) and error.errno in (
        errno.ECONNRESET,
        errno.ECONNREFUSED,
        errno.ECONNABORTED,
        errno.ETIMEDOUT,
        errno.ENETUNREACH,
        errno.EHOSTUNREACH,
    )


def _selected(plan):
    selected = p.checked(p.read_json(folder() / "route.json"), "calibration_source_transport_route")
    p.require(
        selected["plan_id"] == plan["id"] and selected["route"] in plan["diagnostic_routes"],
        "calibration_retry.same_persisted_route",
    )
    number = plan["diagnostic_routes"].index(selected["route"]) + 1
    result = p.read_json(folder() / "diagnostics" / f"{number:02d}.json")
    p.require(
        result["success"] is True
        and result["plan_id"] == plan["id"]
        and result["route"] == selected["route"],
        "calibration_retry.route_has_verified_TLS",
    )
    return selected["route"]


def diagnose(root):
    plan = read_plan(root)
    with c.locked(folder() / "diagnostics.lock", blocking=False):
        _unblocked()
        if (folder() / "route.json").exists():
            return _selected(plan)
        p.require(
            not (folder() / "diagnostic_terminal.json").exists(),
            "calibration_retry.diagnostic_terminal_no_new_route",
        )
        for number, route in enumerate(plan["diagnostic_routes"], 1):
            destination = folder() / "diagnostics" / f"{number:02d}.json"
            intent = folder() / "diagnostic_intents" / f"{number:02d}.json"
            if destination.exists():
                result = p.read_json(destination)
                p.require(
                    result["plan_id"] == plan["id"] and result["route"] == route,
                    "calibration_retry.diagnostic_result_identity",
                )
            else:
                # An unresolved intent may have seen denial before a crash: no repeat/fallback.
                p.require(not intent.exists(), "calibration_retry.unresolved_diagnostic_intent")
                c.write(intent, dict(plan_id=plan["id"], route=route, at=p.now(), attempt=number))
                result = dict(plan_id=plan["id"], route=route, attempt=number, at=p.now())
                try:
                    result.update(success=True, TLS=_tls_probe(route, plan["diagnostic_host"], 20))
                except Exception as error:
                    result.update(
                        success=False,
                        error=repr(error),
                        retryable_network_failure=_network_failure(error),
                    )
                    if not result["retryable_network_failure"]:
                        # Includes every non-2xx proxy CONNECT and certificate verification failure.
                        c.write(folder() / "diagnostic_terminal.json", result)
                        if "Tunnel connection failed:" in str(error) or (
                            isinstance(error, urllib.error.HTTPError)
                            and error.code in (403, 429, 407)
                        ):
                            c.write(folder() / "access_blocked.json", result)
                c.write(destination, result)
            if result["success"]:
                c.write(
                    folder() / "route.json",
                    p.record(
                        "calibration_source_transport_route",
                        plan_id=plan["id"],
                        route=route,
                        at=p.now(),
                    ),
                )
                c.emit(
                    dict(event="calibration_retry_route_selected", route=route, plan_id=plan["id"])
                )
                return route
            p.require(
                result["retryable_network_failure"], "calibration_retry.terminal_diagnostic_failure"
            )
        raise RuntimeError("calibration_retry.TLS_diagnostic_budget_exhausted")


class FixedProxy(urllib.request.ProxyHandler):
    """Use the registered existing proxy even when ambient NO_PROXY later changes."""

    def proxy_open(self, req, proxy, type):
        p.require(type == "https" and proxy == PROXY, "calibration_retry.only_pinned_HTTPS_proxy")
        req.set_proxy(urlsplit(proxy).netloc, "http")
        return None


def _fixed_opener(plan, route, *handlers):
    _unblocked()
    p.require(route in plan["diagnostic_routes"], "calibration_retry.registered_route_only")
    proxy = (
        FixedProxy({"https": route["url"]})
        if route["kind"] == "proxy"
        else urllib.request.ProxyHandler({})
    )
    return urllib.request.build_opener(
        proxy,
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        *handlers,
    )


def _collector(plan, route):
    # All functions share one private namespace; original modules and paths remain untouched.
    request = SimpleNamespace(
        Request=urllib.request.Request,
        build_opener=lambda *handlers: _fixed_opener(plan, route, *handlers),
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
        # Reject inherited denial even before reserving a new HTTP intent.
        _unblocked()
        return legacy_get_asset(plan, key, url)

    namespace["get_asset"] = checked_get_asset
    return SimpleNamespace(**{name: namespace[name] for name in ("get_asset", "acquire")})


def acquire(root):
    plan = read_plan(root)
    route = diagnose(root)
    return _collector(plan, route).acquire(root)


def run(root):
    with c.locked(folder() / "revision.lock", blocking=False):
        try:
            # Also prevent simultaneous old acquisition; lock has no scientific contents.
            with c.locked(original.folder() / "acquisition.lock", blocking=False):
                sources = acquire(root)
                output = folder() / "calibration_panel"
                admission = output / "admission.json"
                if admission.exists():
                    value = p.checked(p.read_json(admission), "calibration_panel_admission")
                else:
                    value = original.panel.build(root, sources, output)["admission"]
                p.require(
                    value["source_registration_id"] == sources["id"],
                    "calibration_retry.panel_bound_to_this_source_registration",
                )
                completion = dict(
                    source_registration_id=sources["id"],
                    panel_admission_id=value["id"],
                    passed=value["passed"],
                    new_model_calls=0,
                    at=p.now(),
                )
                if (folder() / "completion.json").exists():
                    previous = p.read_json(folder() / "completion.json")
                    p.require(
                        all(previous[key] == completion[key] for key in completion if key != "at"),
                        "calibration_retry.same_completed_panel",
                    )
                else:
                    c.write(folder() / "completion.json", completion)
                c.emit(dict(event="calibration_retry_panel_admission", **completion))
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
    parser.add_argument("--mode", choices=("register", "diagnose", "run"), required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "register":
        value = register(root)
        c.emit(dict(event="calibration_retry_registered", id=value["id"], HTTP_cap=195, TLS_cap=2))
    elif args.mode == "diagnose":
        diagnose(root)
    else:
        raise SystemExit(run(root))
