"""Synthetic cooldown/spacing/namespace controls; no real register or GET."""

import threading
import urllib.error
from copy import deepcopy
from datetime import timedelta

import acquire_cross_market_vision_weights_cooldown_02_20260927 as m
import pytest
from test_cross_market_vision_weights_acquisition import Response, artifact


class Clock:
    def __init__(self, at):
        self.seconds = 0.0
        self.at = at
        self.waited = []

    def monotonic(self):
        return self.seconds

    def wallclock(self):
        return self.at + timedelta(seconds=self.seconds)

    def wait(self, stop, seconds):
        assert 0 < seconds <= 5
        self.waited.append(seconds)
        self.seconds += seconds
        return stop.is_set()


@pytest.fixture
def tiny(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "new-cooldown-02")
    row = artifact()
    not_before = m.utc(m.EXPECTED_429_AT) + timedelta(seconds=900)
    plan = dict(id="synthetic-cooldown", model_files=[row], not_before=not_before.isoformat())
    return dict(plan=plan, row=row, not_before=not_before, payload=b"pinned original bytes")


def paced(tiny, sender):
    clock = Clock(tiny["not_before"])
    pacer = m.PacedSender(
        tiny["plan"],
        sender=sender,
        clock=clock.monotonic,
        wallclock=clock.wallclock,
        wait=clock.wait,
    )
    return clock, m.execution_namespace(tiny["plan"], pacer)


def test_scope_has_exact900s_floor_single_thread_and_original18_90_budget():
    fields = m.fixed_fields(dict(at=m.EXPECTED_429_AT))
    assert fields["not_before"] == "2026-09-26T18:03:53.236132+00:00"
    assert fields["maximum_concurrent_files"] == 1
    assert fields["maximum_initial_GETs"] == 18 and fields["maximum_physical_HTTP_requests"] == 90
    assert fields["maximum_initial_GETs_per_file"] == 1
    assert fields["maximum_redirects_per_file"] == 4
    assert fields["model_files"] == m.prior.provision.manifest()
    assert fields["combined_01_02_maximum_initial_GETs"] == 20
    assert fields["combined_01_02_maximum_HTTP_requests"] == 92
    assert fields["previous_attempts_refunded"] is False
    assert fields["authentication"] is False and fields["direct_connection"] is True
    assert fields["IP_selection_or_rotation"] is False


def test_early_run_rejects_before_any_lock_reservation_or_GET(tiny, monkeypatch):
    monkeypatch.setattr(m, "protocol", lambda _: tiny["plan"])
    monkeypatch.setattr(m, "utc_now", lambda: tiny["not_before"] - timedelta(microseconds=1))
    monkeypatch.setattr(
        m, "execution_namespace", lambda *_: pytest.fail("must reject before execution")
    )
    with pytest.raises(ValueError, match="not_before_reached"):
        m.run(m.RAW.parent)
    assert not m.RAW.exists()


def test_exact_not_before_boundary_allowed_without_long_sleep(tiny):
    m.check_not_before(tiny["plan"], tiny["not_before"])
    with pytest.raises(ValueError, match="aware_current_time"):
        m.check_not_before(tiny["plan"], tiny["not_before"].replace(tzinfo=None))


def test_each_redirect_and_next_file_start_spaced5s_and_old_namespace_unchanged(tiny):
    calls = []
    old = (m.prior.RAW, m.prior.MAX_CONCURRENT_FILES, m.prior.open_once, m.prior.download_file)

    def sender(url, timeout):
        calls.append((clock.seconds, url))
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                url,
                302,
                "redirect",
                {
                    "Location": "https://cas-bridge.xethub.hf.co/item?signature=notlogged",
                    "RateLimit": '"resolvers";r=499; t=300',
                },
                None,
            )
        return Response(tiny["payload"], {"RateLimit-Policy": '"fixed window";q=500;w=300'})

    other = artifact(filename="second.json")
    tiny["plan"]["model_files"].append(other)
    clock, namespace = paced(tiny, sender)
    stop = threading.Event()
    first = namespace["download_file"](tiny["plan"], tiny["row"], stop=stop)
    second = namespace["download_file"](tiny["plan"], other, stop=stop)
    assert first["status"] in m.prior.VERIFIED and second["status"] in m.prior.VERIFIED
    assert [at for at, _ in calls] == [5.0, 10.0, 15.0]
    assert len(list((m.RAW / "HTTP_starts").glob("*/*.json"))) == 3
    observations = [m.base.read(p) for p in (m.RAW / "HTTP_observations").glob("*/*.json")]
    assert {r["HTTP_status"] for r in observations} == {200, 302}
    assert any("RateLimit" in r["rate_headers"] for r in observations)
    assert all(not r["automatic_retry_scheduled"] for r in observations)
    assert old == (
        m.prior.RAW,
        m.prior.MAX_CONCURRENT_FILES,
        m.prior.open_once,
        m.prior.download_file,
    )
    assert namespace["MAX_CONCURRENT_FILES"] == 1
    assert "signature=notlogged" not in "".join(
        p.read_text() for p in m.RAW.rglob("*.json") if p.is_file()
    )


@pytest.mark.parametrize("status", [403, 429])
def test_new_denial_stops_stage_without_new_reset_retry(tiny, status):
    calls = []

    def sender(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(
            url,
            status,
            "limited",
            {
                "Retry-After": "300",
                "RateLimit": '"resolvers";r=0;t=300',
                "RateLimit-Policy": '"fixed window";q=500;w=300',
                "Authorization": "must never persist",
                "Set-Cookie": "must never persist",
            },
            None,
        )

    clock, namespace = paced(tiny, sender)
    stop = threading.Event()
    result = namespace["download_file"](tiny["plan"], tiny["row"], stop=stop)
    assert result["http_status"] == status and stop.is_set()
    assert result["status"] == "TRANSFER_FAILED_NOT_REFUNDED"
    assert namespace["download_file"](tiny["plan"], tiny["row"], stop=stop) == result
    other = artifact(filename="unstarted.json")
    tiny["plan"]["model_files"].append(other)
    assert (
        namespace["download_file"](tiny["plan"], other, stop=stop)["status"]
        == "NOT_STARTED_INTERRUPTED"
    )
    assert len(calls) == 1 and clock.waited == [5]
    observation = m.base.read(next((m.RAW / "HTTP_observations").glob("*/*.json")))
    assert observation["rate_headers"]["Retry-After"]["value"] == "300"
    assert "must never persist" not in str(observation)
    assert observation["automatic_retry_scheduled"] is False


def test_bad_header_values_are_hash_only_no_control_or_URL_content():
    headers = {
        "Retry-After": "300\r\nAuthorization:secret",
        "RateLimit": "https://example.invalid/?secret",
        "RateLimit-Policy": "x" * 513,
        "Set-Cookie": "private",
    }
    result = m.safe_rate_headers(headers)
    assert set(result) == {"Retry-After", "RateLimit", "RateLimit-Policy"}
    assert all(row["value_withheld"] for row in result.values())
    assert "Authorization" not in str(result) and "example.invalid" not in str(result)


def test_HTTP_date_retry_after_is_diagnostic_only():
    value = "Sat, 26 Sep 2026 18:10:00 GMT"
    result = m.safe_rate_headers({"Retry-After": value})
    assert result["Retry-After"] == {"value": value, "diagnostic_only": True}


def test_interrupt_during5s_spacing_sends_no_GET_and_keeps_attempt(tiny):
    stop = threading.Event()
    clock = Clock(tiny["not_before"])

    def wait(event, seconds):
        event.set()
        return True

    pacer = m.PacedSender(
        tiny["plan"],
        sender=lambda *_: pytest.fail("no GET after stop"),
        clock=clock.monotonic,
        wallclock=clock.wallclock,
        wait=wait,
    )
    namespace = m.execution_namespace(tiny["plan"], pacer)
    result = namespace["download_file"](tiny["plan"], tiny["row"], stop=stop)
    assert result["status"] == "TRANSFER_INTERRUPTED_NOT_REFUNDED"
    assert len(list((m.RAW / "attempts").glob("*.json"))) == 1
    assert len(list((m.RAW / "HTTP_requests").glob("*/*.json"))) == 1
    assert not list((m.RAW / "HTTP_starts").glob("*/*.json"))


def test_unsettled_02_file_not_replayed_by_new_pacer(tiny):
    namespace = m.clone_namespace()
    row, plan = tiny["row"], tiny["plan"]
    paths = namespace["file_paths"](row)
    namespace["save"](
        paths["attempt"],
        m.base.record(
            m.prior.ATTEMPT,
            protocol_id=plan["id"],
            filename=row["filename"],
            manifest_entry_sha256=m.base.sha(m.base.encode(row)),
        ),
    )
    clock, execution = paced(tiny, lambda *_: pytest.fail("no replay"))
    result = execution["download_file"](plan, row, stop=threading.Event())
    assert result["status"] == "UNSETTLED_OR_PARTIAL_NOT_REPLAYED"
    assert not clock.waited


def test_protocol_fixed_fields_do_not_mutate_frozen01(tiny):
    before = deepcopy(m.prior.fixed_fields())
    fields = m.fixed_fields(dict(at=m.EXPECTED_429_AT))
    assert m.prior.fixed_fields() == before
    assert fields["model_files"] == before["model_files"]
    assert fields["model_directory"] != before["model_directory"]
    assert before["maximum_concurrent_files"] == 2
    assert fields["maximum_concurrent_files"] == 1


def test_register_rejects_unregistered_HTTP_before_parent_work(tiny, monkeypatch):
    m.save(m.RAW / "HTTP_requests" / "config.json" / "0.json", {"synthetic": True})
    monkeypatch.setattr(m.prior, "protocol", lambda _: pytest.fail("must reject before parent"))
    with pytest.raises(ValueError, match="unregistered_02_activity"):
        m.register(m.RAW.parent)
