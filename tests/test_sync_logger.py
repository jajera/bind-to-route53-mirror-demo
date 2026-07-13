"""Unit tests for zone_sync.sync_logger — structured log output."""

import json
import logging

import pytest

from zone_sync.models import DiffResult, RecordKey, RecordSet, ValidatedInput
from zone_sync.sync_logger import (
    log_apply_batch,
    log_axfr_result,
    log_diff_summary,
    log_error,
    log_start,
    log_success,
    log_synchronized,
    log_warning,
)


@pytest.fixture
def capture_logs(caplog):
    """Capture zone_sync logger output."""
    with caplog.at_level(logging.INFO, logger="zone_sync"):
        yield caplog


def _parse_log(caplog) -> dict:
    """Parse the last JSON log record."""
    assert caplog.records, "No log records captured"
    return json.loads(caplog.records[-1].message)


def test_log_start(capture_logs):
    params = ValidatedInput(
        domain="corp.internal",
        master_dns="10.0.1.10",
        zone_id="Z1234567890ABC",
        ignore_ttl=True,
    )
    log_start(params)
    payload = _parse_log(capture_logs)
    assert payload["event"] == "sync_start"
    assert payload["domain"] == "corp.internal"
    assert payload["master_dns"] == "10.0.1.10"
    assert payload["zone_id"] == "Z1234567890ABC"
    assert payload["ignore_ttl"] is True


def test_log_axfr_result(capture_logs):
    log_axfr_result(record_count=42, duration_ms=1500)
    payload = _parse_log(capture_logs)
    assert payload["event"] == "axfr_complete"
    assert payload["record_count"] == 42
    assert payload["duration_ms"] == 1500


def test_log_diff_summary(capture_logs):
    diff = DiffResult(
        creates=[
            RecordSet(
                key=RecordKey("a.corp.internal.", "A"),
                ttl=300,
                values=frozenset({"10.0.0.1"}),
            )
        ],
        upserts=[],
        deletes=[RecordKey("b.corp.internal.", "A")],
        conflicts=[("c.corp.internal.", "CNAME", "A")],
    )
    log_diff_summary(diff)
    payload = _parse_log(capture_logs)
    assert payload["event"] == "diff_summary"
    assert payload["creates"] == 1
    assert payload["upserts"] == 0
    assert payload["deletes"] == 1
    assert payload["conflicts"] == 1


def test_log_apply_batch(capture_logs):
    log_apply_batch(batch_index=0, creates=5, upserts=3, deletes=2)
    payload = _parse_log(capture_logs)
    assert payload["event"] == "apply_batch"
    assert payload["batch_index"] == 0
    assert payload["creates"] == 5
    assert payload["upserts"] == 3
    assert payload["deletes"] == 2


def test_log_success(capture_logs):
    log_success(total_duration_ms=4500, axfr_count=100)
    payload = _parse_log(capture_logs)
    assert payload["event"] == "sync_success"
    assert payload["total_duration_ms"] == 4500
    assert payload["axfr_count"] == 100


def test_log_synchronized(capture_logs):
    log_synchronized()
    payload = _parse_log(capture_logs)
    assert payload["event"] == "zone_synchronized"


def test_log_warning(capture_logs):
    log_warning(
        message="Malformed record skipped",
        record_name="bad.corp.internal.",
        record_type="A",
    )
    payload = _parse_log(capture_logs)
    assert payload["event"] == "sync_warning"
    assert payload["message"] == "Malformed record skipped"
    assert payload["record_name"] == "bad.corp.internal."
    assert payload["record_type"] == "A"


def test_log_error(capture_logs):
    log_error(stage="axfr", error=Exception("Connection refused"))
    payload = _parse_log(capture_logs)
    assert payload["event"] == "sync_error"
    assert payload["stage"] == "axfr"
    assert "Connection refused" in payload["error"]
