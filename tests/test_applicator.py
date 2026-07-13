"""Unit tests for zone_sync.applicator — batching and apply logic."""

from unittest.mock import MagicMock, patch

import pytest

from zone_sync.applicator import apply_changes, batch_changes
from zone_sync.exceptions import ApplyError
from zone_sync.models import ApplyResult, DiffResult, RecordKey, RecordSet


def _rs(name: str, rtype: str, value: str, ttl: int = 300) -> RecordSet:
    key = RecordKey(name=name, rtype=rtype)
    return RecordSet(key=key, ttl=ttl, values=frozenset({value}))


def test_apply_changes_batching():
    """Changes are batched and applied via Route 53 API."""
    diff = DiffResult(
        creates=[_rs("a.corp.internal.", "A", "10.0.0.1")],
        upserts=[_rs("b.corp.internal.", "A", "10.0.0.2")],
    )
    mock_client = MagicMock()

    result = apply_changes("Z1234567890ABC", diff, client=mock_client)

    assert result.creates_applied == 1
    assert result.upserts_applied == 1
    assert result.deletes_applied == 0
    assert result.batches_sent == 1
    mock_client.change_resource_record_sets.assert_called_once()


def test_apply_changes_empty_diff_skip():
    """Empty diff does not call Route 53 API."""
    diff = DiffResult()
    mock_client = MagicMock()

    result = apply_changes("Z1234567890ABC", diff, client=mock_client)

    assert result == ApplyResult()
    assert result.batches_sent == 0
    mock_client.change_resource_record_sets.assert_not_called()


def test_apply_changes_mid_batch_failure():
    """API failure mid-batch raises ApplyError."""
    diff = DiffResult(
        creates=[
            _rs(f"h{i}.corp.internal.", "A", f"10.0.0.{i % 255}")
            for i in range(5)
        ],
    )
    mock_client = MagicMock()
    mock_client.change_resource_record_sets.side_effect = Exception("Throttled")

    with pytest.raises(ApplyError, match="ChangeResourceRecordSets failed"):
        apply_changes("Z1234567890ABC", diff, client=mock_client)


def test_apply_changes_with_deletes():
    """Deletes use target record data for the API call."""
    key = RecordKey(name="old.corp.internal.", rtype="A")
    target_record = RecordSet(key=key, ttl=300, values=frozenset({"10.0.0.99"}))
    target_map = {key: target_record}

    diff = DiffResult(deletes=[key])
    mock_client = MagicMock()

    result = apply_changes(
        "Z1234567890ABC", diff, target=target_map, client=mock_client
    )

    assert result.deletes_applied == 1
    assert result.batches_sent == 1
    call_args = mock_client.change_resource_record_sets.call_args
    changes = call_args[1]["ChangeBatch"]["Changes"]
    assert changes[0]["Action"] == "DELETE"
    assert changes[0]["ResourceRecordSet"]["Name"] == "old.corp.internal."


def test_apply_changes_delete_missing_target_raises():
    """Delete without target record raises ApplyError."""
    key = RecordKey(name="missing.corp.internal.", rtype="A")
    diff = DiffResult(deletes=[key])
    mock_client = MagicMock()

    with pytest.raises(ApplyError, match="Missing target record"):
        apply_changes("Z1234567890ABC", diff, target={}, client=mock_client)
