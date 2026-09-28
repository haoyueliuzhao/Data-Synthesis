"""Independent Probe monetary ledger: reserve before HTTP, settle actual token usage.

All money is integer micro-CNY, rounded upward per request using a frozen official
tariff. Each frozen run cap covers settled cost plus all pending/unknown reservations.
Historical defaults remain 800 CNY / 700 CNY warning / 256000 requests; a new
purpose must explicitly register its own limits rather than inherit prior spend.
This is tariff accounting from actual usage, not a fabricated provider invoice.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from urllib.parse import urlparse

from .contracts import digest, invocation_identity

HARD_CAP_MICROCNY = 800_000_000
WARNING_MICROCNY = 700_000_000
REQUEST_CAP = 256_000
PURPOSE = "finqa_fixed_probe_inventory_v1"
V6_PURPOSE = "finqa_v6_generation_and_semantic_review_v1"
V6_REVIEW_AMENDMENT_PAUSE = "user_authorized_review_capacity_audit"
V6_REVIEW_AMENDMENT_ACTION = "v6_review_capacity_amended"


def validated_budget_limits(
    *,
    hard_cap_microcny=HARD_CAP_MICROCNY,
    warning_microcny=WARNING_MICROCNY,
    request_cap=REQUEST_CAP,
):
    """Return explicit immutable-registration values, never floats or booleans."""
    values = {
        "hard_cap_microcny": hard_cap_microcny,
        "warning_microcny": warning_microcny,
        "request_cap": request_cap,
    }
    if any(type(value) is not int or not 0 < value <= 2**63 - 1 for value in values.values()):
        raise ValueError("budget limits must be positive SQLite-range integers")
    if warning_microcny > hard_cap_microcny:
        raise ValueError("budget warning threshold cannot exceed the hard cap")
    return values


def _json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


class BudgetUnavailable(RuntimeError):
    """No request was sent; the cap or a recorded unknown forbids new work."""


class DuplicateInvocation(RuntimeError):
    """A persisted invocation must never be sent for a second time."""


class InvalidUsage(ValueError):
    """The response does not establish complete tariff-accountable token usage."""


class BudgetAmendmentError(ValueError):
    """An explicit review-capacity amendment cannot change this ledger safely."""


def _review_output_limits(value, *, official_max_output_tokens):
    if (
        not isinstance(value, (list, tuple))
        or any(
            type(item) is not int or not 0 < item <= official_max_output_tokens for item in value
        )
        or len(value) != len(set(value))
        or not {2048, 16384} <= set(value)
        or any(item not in {2048, 16384} and item <= 16384 for item in value)
    ):
        raise BudgetAmendmentError(
            "explicit distinct review limits must retain 2048/16384 "
            "and only add larger official caps"
        )
    return tuple(sorted(value))


@dataclass(frozen=True)
class ProbePriceSheet:
    input_hit_cny_per_million: str
    input_miss_cny_per_million: str
    output_cny_per_million: str
    context_input_token_ceiling: int
    official_max_output_tokens: int
    source_url: str
    checked_at_utc: str
    source_sha256: str
    model: str = "deepseek-flash"
    currency: str = "CNY"
    pricing_policy: str = "conservative_peak_upper_bound_all_hours"

    def __post_init__(self):
        rates = (
            self.input_hit_cny_per_million,
            self.input_miss_cny_per_million,
            self.output_cny_per_million,
        )
        if any(
            not isinstance(value, str) or not Decimal(value).is_finite() or Decimal(value) < 0
            for value in rates
        ):
            raise ValueError("tariff rates must be finite nonnegative Decimal strings")
        if Decimal(rates[0]) > Decimal(rates[1]):
            raise ValueError("cache-hit price exceeds the miss-price reservation bound")
        if (
            self.model != "deepseek-flash"
            or self.currency != "CNY"
            or self.pricing_policy != "conservative_peak_upper_bound_all_hours"
        ):
            raise ValueError("Probe tariff must bind deepseek-flash and CNY")
        if any(
            type(v) is not int or v <= 0
            for v in (self.context_input_token_ceiling, self.official_max_output_tokens)
        ):
            raise ValueError("official token ceilings must be positive integers")
        if urlparse(self.source_url).hostname not in {
            "api-docs.deepseek.com",
            "platform.deepseek.com",
            "www.deepseek.com",
            "deepseek.com",
        }:
            raise ValueError("an official DeepSeek tariff source is required")
        if (
            not self.checked_at_utc
            or len(self.source_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.source_sha256)
        ):
            raise ValueError("the retrieved official tariff evidence must be hash-bound")

    @property
    def id(self):
        return "probe_price_sheet:" + digest(asdict(self))

    def cost_microcny(self, *, hit: int, miss: int, output: int) -> int:
        if any(type(value) is not int or value < 0 for value in (hit, miss, output)):
            raise InvalidUsage("usage counts must be nonnegative integers")
        # CNY / 1e6 tokens times 1e6 micro-CNY / CNY cancels exactly.
        amount = (
            Decimal(self.input_hit_cny_per_million) * hit
            + Decimal(self.input_miss_cny_per_million) * miss
            + Decimal(self.output_cny_per_million) * output
        )
        return int(amount.to_integral_value(rounding=ROUND_CEILING))

    def usage(self, value, *, output_limit):
        if not isinstance(value, dict):
            raise InvalidUsage("API usage is missing")
        names = (
            "prompt_tokens",
            "completion_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        )
        if any(type(value.get(name)) is not int or value[name] < 0 for name in names):
            raise InvalidUsage(
                "complete integer prompt/output/cache-hit/cache-miss counters required"
            )
        if (
            value["prompt_cache_hit_tokens"] + value["prompt_cache_miss_tokens"]
            != value["prompt_tokens"]
        ):
            raise InvalidUsage("cache counters do not sum to actual prompt tokens")
        if (
            type(value.get("total_tokens")) is not int
            or value["total_tokens"] != value["prompt_tokens"] + value["completion_tokens"]
        ):
            raise InvalidUsage("total token count disagrees with prompt plus completion")
        details = value.get("prompt_tokens_details")
        if details is not None and (
            not isinstance(details, dict)
            or (
                "cached_tokens" in details
                and (
                    type(details["cached_tokens"]) is not int
                    or details["cached_tokens"] != value["prompt_cache_hit_tokens"]
                )
            )
        ):
            raise InvalidUsage("optional cached_tokens differs from cache-hit usage")
        completion_details = value.get("completion_tokens_details")
        if completion_details is not None and (
            not isinstance(completion_details, dict)
            or (
                "reasoning_tokens" in completion_details
                and (
                    type(completion_details["reasoning_tokens"]) is not int
                    or not 0 <= completion_details["reasoning_tokens"] <= value["completion_tokens"]
                )
            )
        ):
            raise InvalidUsage("invalid optional reasoning token accounting")
        if (
            value["prompt_tokens"] > self.context_input_token_ceiling
            or value["completion_tokens"] > output_limit
        ):
            raise InvalidUsage(
                "returned usage exceeds the registered official reservation envelope"
            )
        return {name: value[name] for name in names}


def apply_v6_review_amendment(
    path,
    *,
    expected_run_id,
    expected_config_sha256,
    amendment_id,
    allowed_review_output_limits,
    evidence,
):
    """Atomically extend an existing paused V6 ledger; never reset or reconstruct spend.

    The output limits are the complete explicitly authorized set, including the
    original 2048-generation and 16384-review caps. No request, counter, price,
    monetary limit, or request ceiling is rewritten. Only the specific authorized
    audit pause may be cleared, after every paid request has settled.
    """
    path = Path(path)
    if not path.is_file():
        raise BudgetAmendmentError("original paid database is missing; amendment never creates one")
    if (
        not isinstance(expected_run_id, str)
        or not expected_run_id
        or not isinstance(expected_config_sha256, str)
        or len(expected_config_sha256) != 64
        or not isinstance(amendment_id, str)
        or not amendment_id.strip()
        or not isinstance(evidence, dict)
        or not evidence
    ):
        raise BudgetAmendmentError(
            "explicit run, old configuration hash, amendment ID and evidence required"
        )
    evidence = json.loads(_json(evidence))  # Freeze the caller's authorization evidence.
    connection = sqlite3.connect(
        path.resolve().as_uri() + "?mode=rw", uri=True, timeout=30, isolation_level=None
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
        if row is None:
            raise BudgetAmendmentError("original paid configuration is absent")
        old = json.loads(row[0])
        if (
            digest(old) != expected_config_sha256
            or old.get("run_id") != expected_run_id
            or old.get("purpose") != V6_PURPOSE
            or old.get("schema") != "probe_budget.v2"
            or old.get("hard_cap_microcny") != HARD_CAP_MICROCNY
            or old.get("warning_microcny") != WARNING_MICROCNY
            or old.get("joint_generation_and_review_cap") is not True
            or old.get("variable_reservation_bound_to_each_actual_request") is not True
        ):
            raise BudgetAmendmentError("original V6 run/configuration or 800/700 CNY limits differ")
        limits = validated_budget_limits(
            **{name: old[name] for name in ("hard_cap_microcny", "warning_microcny", "request_cap")}
        )
        sheet = ProbePriceSheet(**old["price_sheet"])
        previous = _review_output_limits(
            old.get("allowed_output_limits"),
            official_max_output_tokens=sheet.official_max_output_tokens,
        )
        allowed = _review_output_limits(
            allowed_review_output_limits,
            official_max_output_tokens=sheet.official_max_output_tokens,
        )
        if (
            old.get("price_sheet_id") != sheet.id
            or old.get("max_output_tokens") != max(previous)
            or old.get("reservation_microcny_per_request")
            != sheet.cost_microcny(
                hit=0, miss=sheet.context_input_token_ceiling, output=max(previous)
            )
            or not set(previous) < set(allowed)
        ):
            raise BudgetAmendmentError(
                "amendment must extend, never replace, the frozen original caps/tariff"
            )
        event_key = "v6_review_amendment:" + amendment_id
        if connection.execute("SELECT 1 FROM metadata WHERE key=?", (event_key,)).fetchone():
            raise BudgetAmendmentError(
                "amendment ID already recorded; no overwrite or second application"
            )
        halt = connection.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        if halt is None or json.loads(halt[0]).get("reason") != V6_REVIEW_AMENDMENT_PAUSE:
            raise BudgetAmendmentError(
                "only the explicit user-authorized review audit pause may clear"
            )
        pause_event = connection.execute(
            "SELECT sequence FROM events WHERE action='halt' AND payload_json=? "
            "ORDER BY sequence DESC LIMIT 1",
            (halt[0],),
        ).fetchone()
        if pause_event is None or any(
            json.loads(event[0]).get("reason") != V6_REVIEW_AMENDMENT_PAUSE
            for event in connection.execute(
                "SELECT payload_json FROM events WHERE action='halt' AND sequence>?",
                (pause_event[0],),
            )
        ):
            # INSERT OR IGNORE preserves the first halt in metadata. A later
            # in-flight service failure must not disappear behind that pause.
            raise BudgetAmendmentError(
                "another halt occurred during the audit pause; cannot clear it"
            )
        unsettled = connection.execute(
            "SELECT COUNT(*) FROM requests WHERE state!='SETTLED'"
        ).fetchone()[0]
        counters = connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
        aggregate = connection.execute(
            "SELECT COUNT(*) AS requests,COALESCE(SUM(settled_microcny),0) AS spent,"
            "SUM(CASE WHEN settled_microcny IS NULL OR settled_microcny<0 "
            "OR dispatched_at IS NULL THEN 1 ELSE 0 END) AS invalid FROM requests"
        ).fetchone()
        if (
            unsettled
            or counters is None
            or any(counters[name] != 0 for name in ("pending", "held", "unknown"))
            or counters["requests"] != aggregate["requests"]
            or counters["dispatched"] != aggregate["requests"]
            or counters["spent"] != aggregate["spent"]
            or aggregate["invalid"]
            or not 0 <= counters["spent"] <= limits["hard_cap_microcny"]
            or not 0 <= counters["requests"] <= limits["request_cap"]
        ):
            raise BudgetAmendmentError(
                "all original requests/costs must settle and conserve before amendment"
            )
        new = {
            **old,
            "amendment_id": amendment_id,
            "allowed_output_limits": list(allowed),
            "max_output_tokens": max(allowed),
            "reservation_microcny_per_request": sheet.cost_microcny(
                hit=0, miss=sheet.context_input_token_ceiling, output=max(allowed)
            ),
        }
        record = dict(
            schema="v6_review_capacity_amendment.v1",
            amendment_id=amendment_id,
            run_id=expected_run_id,
            old_config=old,
            new_config=new,
            old_config_sha256=digest(old),
            new_config_sha256=digest(new),
            cleared_halt=json.loads(halt[0]),
            authorization_evidence=evidence,
            preserved_counters=dict(counters),
            all_original_requests_settled=True,
            monetary_and_request_caps_unchanged=True,
            old_request_limits_unchanged=True,
            at_unix=time.time(),
        )
        connection.execute(
            "INSERT INTO metadata(key,value) VALUES (?,?)", (event_key, _json(record))
        )
        connection.execute("UPDATE metadata SET value=? WHERE key='config'", (_json(new),))
        deleted = connection.execute(
            "DELETE FROM metadata WHERE key='halt' AND value=?", (halt[0],)
        )
        if deleted.rowcount != 1:
            raise BudgetAmendmentError("authorized pause identity changed during amendment")
        connection.execute(
            "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
            (amendment_id, V6_REVIEW_AMENDMENT_ACTION, _json(record), record["at_unix"]),
        )
        connection.commit()
        return record
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


class ProbeBudget:
    """One SQLite database per registered inventory, safe across worker processes."""

    def __init__(
        self,
        path,
        *,
        run_id,
        price_sheet,
        max_output_tokens,
        purpose=PURPOSE,
        hard_cap_microcny=HARD_CAP_MICROCNY,
        warning_microcny=WARNING_MICROCNY,
        request_cap=REQUEST_CAP,
        amendment_id=None,
        allowed_output_limits=None,
    ):
        limits = validated_budget_limits(
            hard_cap_microcny=hard_cap_microcny,
            warning_microcny=warning_microcny,
            request_cap=request_cap,
        )
        self.hard_cap_microcny = limits["hard_cap_microcny"]
        self.warning_microcny = limits["warning_microcny"]
        self.request_cap = limits["request_cap"]
        self.path = Path(path)
        self._require_existing = amendment_id is not None or allowed_output_limits is not None
        if self._require_existing:
            if (
                purpose != V6_PURPOSE
                or not isinstance(amendment_id, str)
                or not amendment_id.strip()
                or allowed_output_limits is None
            ):
                raise BudgetAmendmentError(
                    "amended V6 open requires explicit amendment ID and output limits"
                )
            if not self.path.is_file():
                raise BudgetAmendmentError(
                    "original amended database is missing; never recreate the ledger"
                )
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id, self.price_sheet = (
            run_id,
            price_sheet
            if isinstance(price_sheet, ProbePriceSheet)
            else ProbePriceSheet(**price_sheet),
        )
        self.max_output_tokens = max_output_tokens
        self.purpose = purpose
        self.allowed_output_limits = (
            _review_output_limits(
                allowed_output_limits,
                official_max_output_tokens=self.price_sheet.official_max_output_tokens,
            )
            if self._require_existing
            else (2048, 16384)
            if purpose == V6_PURPOSE
            else (max_output_tokens,)
        )
        if not isinstance(run_id, str) or not run_id or purpose not in {PURPOSE, V6_PURPOSE}:
            raise ValueError("a dedicated registered Probe run and purpose are required")
        if (
            type(max_output_tokens) is not int
            or max_output_tokens
            not in (
                (max(self.allowed_output_limits),)
                if self._require_existing
                else (16384,)
                if purpose == V6_PURPOSE
                else (2048, 4096)
            )
            or max_output_tokens > self.price_sheet.official_max_output_tokens
        ):
            raise ValueError(
                "Probe output cap must be frozen at 2048 or 4096 within the official limit"
            )
        self.reservation_microcny = self.price_sheet.cost_microcny(
            hit=0, miss=self.price_sheet.context_input_token_ceiling, output=max_output_tokens
        )
        config = {
            "schema": "probe_budget.v1",
            "run_id": run_id,
            "purpose": purpose,
            "price_sheet": asdict(self.price_sheet),
            "price_sheet_id": self.price_sheet.id,
            "max_output_tokens": max_output_tokens,
            **limits,
            "reservation_microcny_per_request": self.reservation_microcny,
            "reservation_input_policy": "official_entire_context_at_cache_miss_price",
            "currency_scale": "1 CNY = 1000000 micro-CNY",
        }
        if purpose == V6_PURPOSE:
            config.update(
                schema="probe_budget.v2",
                allowed_output_limits=list(self.allowed_output_limits),
                joint_generation_and_review_cap=True,
                variable_reservation_bound_to_each_actual_request=True,
            )
        if self._require_existing:
            config["amendment_id"] = amendment_id
        self.config = config
        if not self._require_existing:
            with closing(self._connect()) as connection:
                connection.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (
                    invocation_id TEXT PRIMARY KEY,
                    coordinates_json TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    request_body BLOB NOT NULL,
                    state TEXT NOT NULL,
                    reserved_microcny INTEGER NOT NULL,
                    settled_microcny INTEGER,
                    created_at REAL NOT NULL,
                    dispatched_at REAL,
                    settled_at REAL,
                    http_status INTEGER,
                    response_classification TEXT,
                    response_body BLOB,
                    response_sha256 TEXT,
                    usage_json TEXT,
                    evidence_json TEXT
                );
                CREATE TABLE IF NOT EXISTS counters (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    requests INTEGER NOT NULL DEFAULT 0,
                    dispatched INTEGER NOT NULL DEFAULT 0,
                    spent INTEGER NOT NULL DEFAULT 0,
                    held INTEGER NOT NULL DEFAULT 0,
                    unknown INTEGER NOT NULL DEFAULT 0,
                    pending INTEGER NOT NULL DEFAULT 0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    hit_tokens INTEGER NOT NULL DEFAULT 0,
                    miss_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO counters(singleton) VALUES (1);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    invocation_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    at_unix REAL NOT NULL
                );
                """)
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT value FROM metadata WHERE key='config'"
            ).fetchone()
            if existing is not None and json.loads(existing[0]) != config:
                raise ValueError(
                    "budget database belongs to a different run, purpose, tariff, "
                    "output or budget limit"
                )
            if self._require_existing:
                amendment = connection.execute(
                    "SELECT value FROM metadata WHERE key=?",
                    ("v6_review_amendment:" + amendment_id,),
                ).fetchone()
                if existing is None or amendment is None:
                    raise BudgetAmendmentError("explicit capacity amendment evidence is absent")
                record = json.loads(amendment[0])
                if record.get("new_config") != config or record.get("new_config_sha256") != digest(
                    config
                ):
                    raise BudgetAmendmentError(
                        "amended configuration differs from its durable authorization"
                    )
            connection.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('config',?)", (_json(config),)
            )

    def _connect(self):
        connection = (
            sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=rw",
                uri=True,
                timeout=30,
                isolation_level=None,
            )
            if self._require_existing
            else sqlite3.connect(self.path, timeout=30, isolation_level=None)
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            stored = connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
            if stored is not None and json.loads(stored[0]) != self.config:
                raise ValueError(
                    "different or stale budget configuration; reopen with explicit frozen amendment"
                )
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _snapshot(self, connection):
        row = connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
        halt = connection.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        spent, held = row["spent"], row["held"]
        return {
            "run_id": self.run_id,
            "purpose": self.purpose,
            "requests_reserved": row["requests"],
            "requests_dispatched": row["dispatched"],
            "settled_tariff_microcny": spent,
            "held_microcny": held,
            "exposure_microcny": spent + held,
            "remaining_exposure_microcny": self.hard_cap_microcny - spent - held,
            "hard_cap_microcny": self.hard_cap_microcny,
            "warning_microcny": self.warning_microcny,
            "request_cap": self.request_cap,
            "warning_reached": spent >= self.warning_microcny,
            "exposure_warning_reached": spent + held >= self.warning_microcny,
            "unknown_requests": row["unknown"],
            "pending_requests": row["pending"],
            "actual_prompt_tokens_settled": row["prompt_tokens"],
            "actual_cache_hit_tokens_settled": row["hit_tokens"],
            "actual_cache_miss_tokens_settled": row["miss_tokens"],
            "actual_completion_tokens_settled": row["completion_tokens"],
            "halt": json.loads(halt[0]) if halt else None,
            "price_sheet_id": self.price_sheet.id,
            "cost_semantics": (
                "upward-rounded peak-tariff upper bound applied to actual usage; "
                "not a provider invoice"
            ),
        }

    def snapshot(self):
        connection = self._connect()
        try:
            return self._snapshot(connection)
        finally:
            connection.close()

    def reserve(self, invocation_id, *, coordinates, request, request_body):
        if (
            coordinates.get("run_id") != self.run_id
            or coordinates.get("invocation_id") != invocation_id
        ):
            raise ValueError("invocation coordinates do not belong to this budget run")
        if (
            not isinstance(coordinates.get("episode_id"), str)
            or not coordinates["episode_id"]
            or type(coordinates.get("turn_index")) is not int
            or not 0 <= coordinates["turn_index"] < 32
        ):
            raise ValueError("Probe invocation must identify one of the 32 bounded episode turns")
        if invocation_identity(coordinates, turn_index=coordinates["turn_index"]) != coordinates:
            raise ValueError(
                "invocation ID must be derived from the actual run/episode/attempt/turn"
            )
        if (
            request.get("model") != "deepseek-flash"
            or type(request.get("max_tokens")) is not int
            or request["max_tokens"] not in self.allowed_output_limits
            or request.get("thinking") != {"type": "disabled"}
        ):
            raise ValueError("request differs from the frozen Probe model/output/thinking contract")
        if not isinstance(request_body, bytes) or json.loads(request_body) != request:
            raise ValueError("retained public request bytes differ from the actual HTTP body")
        reservation = self.price_sheet.cost_microcny(
            hit=0, miss=self.price_sheet.context_input_token_ceiling, output=request["max_tokens"]
        )
        with self._transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone():
                raise DuplicateInvocation("invocation already persisted; no duplicate API send")
            state = self._snapshot(connection)
            if state["halt"] or state["unknown_requests"]:
                raise BudgetUnavailable("unknown or halted Probe ledger forbids new requests")
            if state["requests_reserved"] >= self.request_cap:
                raise BudgetUnavailable(f"{self.request_cap}-request Probe cap exhausted")
            if state["exposure_microcny"] + reservation > self.hard_cap_microcny:
                raise BudgetUnavailable(
                    "next full official-context reservation exceeds the frozen "
                    f"{self.hard_cap_microcny} micro-CNY cap"
                )
            connection.execute(
                """INSERT INTO requests
                (invocation_id,coordinates_json,request_sha256,request_body,state,reserved_microcny,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    invocation_id,
                    _json(coordinates),
                    digest(request),
                    request_body,
                    "RESERVED",
                    reservation,
                    time.time(),
                ),
            )
            connection.execute(
                "UPDATE counters SET requests=requests+1,pending=pending+1,held=held+? "
                "WHERE singleton=1",
                (reservation,),
            )
            self._event(
                connection,
                invocation_id,
                "reserved",
                {
                    "request_sha256": digest(request),
                    "reservation_microcny": reservation,
                },
            )
        return reservation

    def mark_dispatched(self, invocation_id):
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone()
            if row is None or row[0] != "RESERVED":
                raise DuplicateInvocation("only a fresh unsent reservation can be dispatched")
            if self._snapshot(connection)["halt"]:
                raise BudgetUnavailable("ledger halted before dispatch; request not sent")
            connection.execute(
                "UPDATE requests SET state='DISPATCHED',dispatched_at=? WHERE invocation_id=?",
                (time.time(), invocation_id),
            )
            connection.execute("UPDATE counters SET dispatched=dispatched+1 WHERE singleton=1")
            self._event(connection, invocation_id, "dispatched", {})

    def _event(self, connection, invocation_id, action, payload):
        connection.execute(
            "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
            (invocation_id, action, _json(payload), time.time()),
        )

    def _halt(self, connection, reason, invocation_id, evidence):
        value = {
            "reason": reason,
            "invocation_id": invocation_id,
            "evidence": evidence,
            "at_unix": time.time(),
        }
        connection.execute("INSERT OR IGNORE INTO metadata VALUES ('halt',?)", (_json(value),))
        self._event(connection, invocation_id, "halt", value)

    def unknown(
        self,
        invocation_id,
        *,
        reason,
        http_status=None,
        response_classification="unknown",
        response_body=None,
        evidence=None,
    ):
        import hashlib

        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone()
            if row is None or row[0] not in {"RESERVED", "DISPATCHED"}:
                raise ValueError("only a pending request can become unknown")
            connection.execute(
                """UPDATE requests SET state='UNKNOWN',http_status=?,response_classification=?,
                response_body=?,response_sha256=?,evidence_json=? WHERE invocation_id=?""",
                (
                    http_status,
                    response_classification,
                    response_body,
                    hashlib.sha256(response_body).hexdigest()
                    if response_body is not None
                    else None,
                    _json(evidence or {}),
                    invocation_id,
                ),
            )
            connection.execute(
                "UPDATE counters SET unknown=unknown+1,pending=pending-1 WHERE singleton=1"
            )
            self._event(
                connection,
                invocation_id,
                "unknown",
                {
                    "reason": reason,
                    "http_status": http_status,
                    "response_classification": response_classification,
                },
            )
            self._halt(connection, reason, invocation_id, evidence or {})

    def settle(
        self,
        invocation_id,
        *,
        usage,
        http_status,
        response_classification,
        response_body,
        evidence=None,
    ):
        import hashlib

        counters = self.price_sheet.usage(usage, output_limit=self.max_output_tokens)
        amount = self.price_sheet.cost_microcny(
            hit=counters["prompt_cache_hit_tokens"],
            miss=counters["prompt_cache_miss_tokens"],
            output=counters["completion_tokens"],
        )
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state,reserved_microcny,request_body FROM requests WHERE invocation_id=?",
                (invocation_id,),
            ).fetchone()
            if row is None or row[0] != "DISPATCHED":
                raise ValueError(
                    "settlement requires one dispatched, not previously settled request"
                )
            self.price_sheet.usage(usage, output_limit=json.loads(row[2])["max_tokens"])
            if amount > row[1]:
                raise InvalidUsage(
                    "actual tariff cost exceeds the official upper-bound reservation"
                )
            connection.execute(
                """UPDATE requests SET state='SETTLED',settled_microcny=?,settled_at=?,
                http_status=?,response_classification=?,response_body=?,response_sha256=?,
                usage_json=?,evidence_json=? WHERE invocation_id=?""",
                (
                    amount,
                    time.time(),
                    http_status,
                    response_classification,
                    response_body,
                    hashlib.sha256(response_body).hexdigest(),
                    _json(usage),
                    _json(evidence or {}),
                    invocation_id,
                ),
            )
            connection.execute(
                """UPDATE counters SET pending=pending-1,spent=spent+?,held=held-?,
                prompt_tokens=prompt_tokens+?,hit_tokens=hit_tokens+?,miss_tokens=miss_tokens+?,
                completion_tokens=completion_tokens+? WHERE singleton=1""",
                (
                    amount,
                    row[1],
                    counters["prompt_tokens"],
                    counters["prompt_cache_hit_tokens"],
                    counters["prompt_cache_miss_tokens"],
                    counters["completion_tokens"],
                ),
            )
            self._event(
                connection,
                invocation_id,
                "settled",
                {
                    "peak_tariff_upper_bound_microcny": amount,
                    "usage": usage,
                    "response_classification": response_classification,
                },
            )
            if response_classification != "model_response":
                self._halt(connection, response_classification, invocation_id, evidence or {})
        return amount

    def halt(self, *, reason, invocation_id, evidence=None):
        with self._transaction() as connection:
            self._halt(connection, reason, invocation_id, evidence or {})

    def request_record(self, invocation_id):
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def unsettled(self):
        connection = self._connect()
        try:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT invocation_id,state,coordinates_json FROM requests "
                    "WHERE state IN ('RESERVED','DISPATCHED','UNKNOWN') ORDER BY created_at"
                )
            ]
        finally:
            connection.close()
