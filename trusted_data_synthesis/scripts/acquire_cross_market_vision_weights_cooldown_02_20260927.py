"""One prospectively bounded slow acquisition after the preserved HTTP429 stage.

The new budget never mutates or refunds stage01. No GET or reservation is allowed
before the exact parent429 receipt time plus900 seconds. No scheduler or long
cooldown sleep exists here; the controller must explicitly run this stage later.
"""

import argparse
import subprocess
import time
import types
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import acquire_cross_market_vision_weights_20260927 as prior

base = prior.base
RAW = base.RAW / "original_evidence_revision_02" / "vision_model_acquisition_cooldown_02"
SCRIPT = (
    "trusted_data_synthesis/scripts/acquire_cross_market_vision_weights_cooldown_02_20260927.py"
)
PROTOCOL = "cross_market_vision_weight_cooldown_protocol"
COOLDOWN_SECONDS = 900
MINIMUM_HTTP_START_INTERVAL_SECONDS = 5
RATE_LIMIT_FILENAME = "added_tokens.json"
EXPECTED_429_AT = "2026-09-26T17:48:53.236132+00:00"
RATE_HEADERS = (
    "Retry-After",
    "RateLimit",
    "RateLimit-Policy",
    "RateLimit-Limit",
    "RateLimit-Remaining",
    "RateLimit-Reset",
)
RATE_LIMIT_GUIDANCE = {
    "official_source": "https://huggingface.co/docs/hub/rate-limits",
    "controller_checked_on": "2026-09-27",
    "window_seconds_documented": 300,
    "meaning": "429 is rate limiting, not the stage01 evidence of403 authorization denial. "
    "This separately frozen attempt waits at least900 seconds and spaces every GET; "
    "it is not an automatic retry or a guarantee that the limit has reset.",
}


def require(condition, reason):
    base.require(condition, "vision_cooldown." + reason)


def clone_namespace(**overrides):
    """Reuse fixed acquisition code objects without altering their module globals."""
    namespace = dict(prior.__dict__)
    namespace.update(RAW=RAW, MAX_CONCURRENT_FILES=1, **overrides)
    for name, value in prior.__dict__.items():
        if isinstance(value, types.FunctionType) and value.__module__ == prior.__name__:
            cloned = types.FunctionType(
                value.__code__, namespace, name, value.__defaults__, value.__closure__
            )
            cloned.__kwdefaults__ = value.__kwdefaults__
            namespace[name] = cloned
    return namespace


def save(path, value):
    clone_namespace()["save"](path, value)


def utc(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "explicit_UTC_timestamp")
    return parsed.astimezone(timezone.utc)


def utc_now():
    return datetime.now(timezone.utc)


def parent_references():
    return dict(
        acquisition_01_protocol=prior.reference(prior.RAW / "protocol.json"),
        acquisition_01_summary=prior.reference(prior.RAW / "summary.json"),
        acquisition_01_429_receipt=prior.reference(
            prior.RAW / "receipts" / (RATE_LIMIT_FILENAME + ".json")
        ),
    )


def read_parents(references):
    expected_paths = {
        "acquisition_01_protocol": prior.RAW / "protocol.json",
        "acquisition_01_summary": prior.RAW / "summary.json",
        "acquisition_01_429_receipt": prior.RAW / "receipts" / (RATE_LIMIT_FILENAME + ".json"),
    }
    require(set(references) == set(expected_paths), "exact_parent_reference_set")
    parents = {}
    for key, reference in references.items():
        require(
            Path(reference["path"]) == expected_paths[key]
            and prior.reference(expected_paths[key]) == reference,
            "preserved_parent_bytes",
        )
        parents[key] = base.read(reference["path"])
    plan = base.checked(parents["acquisition_01_protocol"], prior.PROTOCOL)
    done = base.checked(parents["acquisition_01_summary"], prior.SUMMARY)
    denied = base.checked(parents["acquisition_01_429_receipt"], prior.RECEIPT)
    require(
        done["protocol_id"] == denied["protocol_id"] == plan["id"]
        and denied["filename"] == RATE_LIMIT_FILENAME
        and denied["http_status"] == 429
        and denied["at"] == EXPECTED_429_AT
        and denied["status"] == "TRANSFER_FAILED_NOT_REFUNDED"
        and done["files"] == 18
        and done["verified_files"] == 0
        and done["reserved_file_attempts"] == done["reserved_physical_HTTP_requests"] == 2
        and plan["model_files"] == prior.provision.manifest(),
        "exact_completed_01_rate_limit_evidence",
    )
    row = next(r for r in plan["model_files"] if r["filename"] == RATE_LIMIT_FILENAME)
    require(denied["manifest_entry_sha256"] == base.sha(base.encode(row)), "429_manifest_binding")
    require(
        any(item.get("id") == denied["id"] for item in done["results"]),
        "429_receipt_in_parent_summary",
    )
    return plan, done, denied


def fixed_fields(denied):
    fields = clone_namespace()["fixed_fields"]()
    fields.update(
        cooldown_seconds=COOLDOWN_SECONDS,
        not_before=(utc(denied["at"]) + timedelta(seconds=COOLDOWN_SECONDS)).isoformat(),
        minimum_HTTP_start_interval_seconds=MINIMUM_HTTP_START_INTERVAL_SECONDS,
        execution_revision=2,
        same_original_file_order=True,
        previous_attempts_refunded=False,
        previous_responses_or_partials_modified=False,
        explicit_separate_budget=True,
        automatic_third_stage=False,
        proxy_or_egress_configuration_changes=0,
        IP_selection_or_rotation=False,
        actual_public_IP_not_independently_measured=True,
        rate_header_allowlist=list(RATE_HEADERS),
        maximum_rate_header_characters=512,
        rate_headers_recorded_not_automatic_retry_instructions=True,
        original_01_reserved_initial_GETs=2,
        combined_01_02_maximum_initial_GETs=20,
        original_01_reserved_HTTP_requests=2,
        combined_01_02_maximum_HTTP_requests=92,
    )
    return fields


def register(root):
    root = Path(root)
    if (RAW / "protocol.json").exists():
        return protocol(root)
    require(
        not any((RAW / "attempts").glob("*.json"))
        and not any((RAW / "HTTP_requests").glob("*/*.json"))
        and not any((RAW / "HTTP_observations").glob("*/*.json"))
        and not any((RAW / "HTTP_starts").glob("*/*.json"))
        and not any((RAW / "receipts").glob("*.json")),
        "no_unregistered_02_activity",
    )
    previous = prior.protocol(root)
    references = parent_references()
    parent, completed, denied = read_parents(references)
    require(previous == parent, "frozen_original_protocol")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    content = (root / SCRIPT).read_bytes()
    require(
        content == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "committed_cooldown_code",
    )
    sources = dict(parent["sources"], **{SCRIPT: base.sha(content)})
    plan = base.record(
        PROTOCOL,
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_references=references,
        parent_acquisition_protocol_id=parent["id"],
        parent_acquisition_summary_id=completed["id"],
        parent_429_receipt_id=denied["id"],
        official_rate_limit_guidance=RATE_LIMIT_GUIDANCE,
        authority="One separately frozen lower-rate acquisition after the preserved429, "
        "under the user's continue-experiment authority. No proxy/authentication/IP/source "
        "change and no automatic retries; controller must explicitly invoke run after not_before.",
        available_bytes_at_registration=prior.disk_guard(),
        network_requests_at_registration=0,
        **fixed_fields(denied),
    )
    save(RAW / "protocol.json", plan)
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    parent, completed, denied = read_parents(plan["parent_references"])
    require(
        plan["parent_acquisition_protocol_id"] == parent["id"]
        and plan["parent_acquisition_summary_id"] == completed["id"]
        and plan["parent_429_receipt_id"] == denied["id"],
        "parent_identity",
    )
    require(all(plan.get(k) == v for k, v in fixed_fields(denied).items()), "fixed_slow_scope")
    require(plan["official_rate_limit_guidance"] == RATE_LIMIT_GUIDANCE, "frozen_rate_guidance")
    require(set(plan["sources"]) == set(parent["sources"]) | {SCRIPT}, "complete_code_lineage")
    for name, digest in plan["sources"].items():
        require(base.sha(Path(root) / name) == digest, "frozen_code")
    return plan


def check_not_before(plan, now=None):
    current = utc_now() if now is None else now
    require(current.tzinfo is not None, "aware_current_time")
    require(
        current.astimezone(timezone.utc) >= utc(plan["not_before"]),
        "not_before_reached_no_reservation_or_GET_permitted",
    )


def safe_rate_headers(headers):
    kept = {}
    for name in RATE_HEADERS:
        value = headers.get(name) if headers is not None else None
        if value is None:
            continue
        value = str(value)
        if (
            len(value) <= 512
            and all(32 <= ord(c) < 127 for c in value)
            and not any(marker in value.lower() for marker in ("http://", "https://", "bearer "))
        ):
            kept[name] = dict(value=value, diagnostic_only=True)
        else:
            kept[name] = dict(
                value_withheld=True,
                sha256=base.sha(value),
                characters=len(value),
                reason="Not bounded printable rate-limit metadata",
            )
    return kept


class PacedSender:
    """One stage-wide clock spaces starts, including redirect hops, at least5s."""

    def __init__(
        self, plan, *, sender=prior.open_once, clock=time.monotonic, wallclock=utc_now, wait=None
    ):
        self.plan, self.sender, self.clock, self.wallclock = plan, sender, clock, wallclock
        self.wait = wait if wait is not None else lambda stop, seconds: stop.wait(seconds)
        # Also wait5s at each new controller invocation: a previous interrupted
        # process cannot cause a near-immediate fresh-file request after restart.
        self.last_start = clock()

    def send(self, row, url, timeout, stop):
        check_not_before(self.plan, self.wallclock())
        while True:
            require(not stop.is_set(), "slow_transfer_interrupted")
            remaining = MINIMUM_HTTP_START_INTERVAL_SECONDS - (self.clock() - self.last_start)
            if remaining <= 0:
                break
            self.wait(stop, min(remaining, MINIMUM_HTTP_START_INTERVAL_SECONDS))
        require(not stop.is_set(), "slow_transfer_interrupted")
        check_not_before(self.plan, self.wallclock())
        requests = sorted((RAW / "HTTP_requests" / row["filename"]).glob("*.json"))
        require(bool(requests), "HTTP_reserved_before_paced_send")
        reservation = base.checked(base.read(requests[-1]), prior.REQUEST)
        require(
            reservation["protocol_id"] == self.plan["id"]
            and reservation["filename"] == row["filename"]
            and reservation["destination"]["full_URL_sha256"] == base.sha(url),
            "exact_paced_request_binding",
        )
        hop = reservation["hop"]
        start_path = RAW / "HTTP_starts" / row["filename"] / f"{hop}.json"
        require(not start_path.exists(), "paced_start_cannot_replay")
        started = base.record(
            "cross_market_vision_paced_HTTP_start",
            protocol_id=self.plan["id"],
            reservation_id=reservation["id"],
            filename=row["filename"],
            hop=hop,
            at=self.wallclock().isoformat(),
            destination=prior.safe_url(url),
            minimum_start_interval_seconds=MINIMUM_HTTP_START_INTERVAL_SECONDS,
        )
        save(start_path, started)
        self.last_start = self.clock()

        def observe(status, headers, error_type=None):
            save(
                RAW / "HTTP_observations" / row["filename"] / f"{hop}.json",
                base.record(
                    "cross_market_vision_rate_limit_observation",
                    protocol_id=self.plan["id"],
                    reservation_id=reservation["id"],
                    start_record_id=started["id"],
                    filename=row["filename"],
                    hop=hop,
                    at=self.wallclock().isoformat(),
                    HTTP_status=status,
                    rate_headers=safe_rate_headers(headers),
                    error_type=error_type,
                    automatic_retry_scheduled=False,
                ),
            )

        try:
            response = self.sender(url, timeout)
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                stop.set()
            observe(error.code, error.headers, type(error).__name__)
            self.last_start = self.clock()
            raise
        except BaseException as error:
            observe(None, None, type(error).__name__)
            self.last_start = self.clock()
            raise
        observe(response.status, response.headers)
        self.last_start = self.clock()
        return response


def execution_namespace(plan, pacer):
    namespace = clone_namespace()
    original_download = namespace["download_file"]

    def download_file(execution_plan, row, *, stop):
        return original_download(
            execution_plan,
            row,
            stop=stop,
            sender=lambda url, timeout: pacer.send(row, url, timeout, stop),
        )

    namespace["protocol"] = lambda _: plan
    namespace["download_file"] = download_file
    return namespace


def run(root):
    plan = protocol(root)
    check_not_before(plan)  # Before controller lock, fileattempt, HTTP reservation, or GET.
    namespace = execution_namespace(plan, PacedSender(plan))
    return namespace["run"](root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "status", "run"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    value = {"register": register, "status": protocol, "run": run}[args.action](args.root)
    if args.action != "run":
        base.emit(value)


if __name__ == "__main__":
    main()
