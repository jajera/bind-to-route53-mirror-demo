from hypothesis import given, settings
from hypothesis import strategies as st

from zone_sync.applicator import batch_changes
from zone_sync.constants import MAX_BATCH_SIZE
from zone_sync.diff_engine import compute_diff
from zone_sync.models import DiffResult, RecordKey, RecordSet

from tests.generators import record_set


def _rs(name: str, rtype: str, value: str) -> RecordSet:
    key = RecordKey(name=name, rtype=rtype)
    return RecordSet(key=key, ttl=300, values=frozenset({value}))


def test_batch_size_limit():
    diff = DiffResult(
        creates=[
            _rs(f"h{i}.corp.internal.", "A", f"10.0.0.{i % 255}") for i in range(1001)
        ]
    )
    batches = batch_changes(diff, batch_size=1000)
    assert len(batches) == 2
    assert len(batches[0]) == 1000
    assert len(batches[1]) == 1


def test_empty_diff_no_batches():
    assert batch_changes(DiffResult()) == []


# Feature: bind-to-route53-mirror-demo, Property 11: Change batch size limit
# **Validates: Requirements 5.1**
@given(
    st.lists(record_set(), min_size=0, max_size=20),
    st.lists(record_set(), min_size=0, max_size=20),
    st.integers(min_value=1, max_value=10),
)
def test_property_batch_size_limit(creates_list, upserts_list, batch_size):
    """Batching produces ≤batch_size changes per batch; union of batches equals full change set."""
    # Deduplicate by key to form valid diff
    creates_dict = {rs.key: rs for rs in creates_list}
    upserts_dict = {rs.key: rs for rs in upserts_list if rs.key not in creates_dict}
    diff = DiffResult(
        creates=list(creates_dict.values()),
        upserts=list(upserts_dict.values()),
    )
    batches = batch_changes(diff, batch_size=batch_size)
    if diff.is_empty:
        assert batches == []
        return
    # Each batch should be <= batch_size
    for batch in batches:
        assert len(batch) <= batch_size
    # Union of all batches should equal all operations
    all_ops = []
    for batch in batches:
        all_ops.extend(batch)
    total_expected = len(diff.creates) + len(diff.upserts) + len(diff.deletes)
    assert len(all_ops) == total_expected
