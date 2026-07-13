"""Property-based tests for the diff engine.

Uses Hypothesis to verify properties 5-10, 12.
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from tests.generators import record_set, record_key
from zone_sync.constants import SYNC_TYPES
from zone_sync.diff_engine import compute_diff
from zone_sync.models import DiffResult, RecordKey, RecordSet


ZONE_APEX = "example.com."


@st.composite
def record_dict(draw, min_size=0, max_size=5):
    """Generate a dict[RecordKey, RecordSet] for use as source or target."""
    records = draw(st.lists(record_set(), min_size=min_size, max_size=max_size))
    result = {}
    for rs in records:
        # Skip apex NS/SOA which are filtered out by diff
        if rs.key.rtype == "SOA":
            continue
        if rs.key.rtype == "NS" and rs.key.name.lower() == ZONE_APEX.lower():
            continue
        result[rs.key] = rs
    return result


@st.composite
def non_apex_record_set(draw):
    """Generate a RecordSet that is not apex NS or SOA."""
    rs = draw(record_set())
    assume(rs.key.rtype != "SOA")
    assume(not (rs.key.rtype == "NS" and rs.key.name.lower() == ZONE_APEX.lower()))
    return rs


# Feature: bind-to-route53-mirror-demo, Property 5: Diff creates equals source minus target
# **Validates: Requirements 4.1**
@given(record_dict(min_size=1, max_size=5), record_dict(min_size=0, max_size=5))
def test_property_diff_creates_source_minus_target(source, target):
    """CREATE = keys in source not in target (allowed types; exclude apex NS, SOA)."""
    diff = compute_diff(source, target, ZONE_APEX, ignore_ttl=True)
    create_keys = {rs.key for rs in diff.creates}
    conflict_names = {name for name, _, _ in diff.conflicts}
    for key in source:
        if key not in target:
            if key.rtype == "CNAME" and key.name in conflict_names:
                continue
            assert key in create_keys, f"{key} should be in creates"
    # All creates should be keys in source but not in target
    for rs in diff.creates:
        assert rs.key in source
        assert rs.key not in target


# Feature: bind-to-route53-mirror-demo, Property 6: Diff upserts equals changed intersection
# **Validates: Requirements 4.2**
@given(record_dict(min_size=1, max_size=5), record_dict(min_size=1, max_size=5))
def test_property_diff_upserts_changed_intersection(source, target):
    """UPSERT = keys in both with differing values/TTL per IgnoreTTL setting."""
    diff = compute_diff(source, target, ZONE_APEX, ignore_ttl=True)
    upsert_keys = {rs.key for rs in diff.upserts}
    conflict_names = {name for name, _, _ in diff.conflicts}
    for key in source:
        if key in target:
            src_rs = source[key]
            tgt_rs = target[key]
            # With ignore_ttl=True, only values matter
            if src_rs.values != tgt_rs.values:
                if key.rtype == "CNAME" and key.name in conflict_names:
                    continue
                assert key in upsert_keys, f"{key} should be in upserts"
    # All upserts must be keys in both source and target
    for rs in diff.upserts:
        assert rs.key in source
        assert rs.key in target


# Feature: bind-to-route53-mirror-demo, Property 7: Diff deletes equals target minus source
# **Validates: Requirements 4.3**
@given(record_dict(min_size=0, max_size=5), record_dict(min_size=1, max_size=5))
def test_property_diff_deletes_target_minus_source(source, target):
    """DELETE = keys in target not in source."""
    diff = compute_diff(source, target, ZONE_APEX, ignore_ttl=True)
    delete_keys = set(diff.deletes)
    for key in target:
        if key not in source:
            assert key in delete_keys, f"{key} should be in deletes"
    # All deletes should be keys in target but not source
    for key in diff.deletes:
        assert key in target
        assert key not in source


# Feature: bind-to-route53-mirror-demo, Property 8: Diff output type filtering
# **Validates: Requirements 4.4, 4.5, 4.6**
@given(record_dict(min_size=1, max_size=5), record_dict(min_size=0, max_size=5))
def test_property_diff_output_type_filtering(source, target):
    """All operations use only SYNC_TYPES; no apex NS or SOA."""
    diff = compute_diff(source, target, ZONE_APEX, ignore_ttl=True)
    for rs in diff.creates:
        assert rs.key.rtype in SYNC_TYPES
        assert not (rs.key.rtype == "NS" and rs.key.name.lower() == ZONE_APEX.lower())
        assert rs.key.rtype != "SOA"
    for rs in diff.upserts:
        assert rs.key.rtype in SYNC_TYPES
        assert not (rs.key.rtype == "NS" and rs.key.name.lower() == ZONE_APEX.lower())
        assert rs.key.rtype != "SOA"
    for key in diff.deletes:
        assert key.rtype in SYNC_TYPES
        assert not (key.rtype == "NS" and key.name.lower() == ZONE_APEX.lower())
        assert key.rtype != "SOA"


# Feature: bind-to-route53-mirror-demo, Property 9: CNAME conflict detection
# **Validates: Requirements 4.7**
@given(non_apex_record_set())
def test_property_cname_conflict_detection(base_rs):
    """CNAME in source vs different type at same name in target → conflict logged, record skipped."""
    assume(base_rs.key.rtype != "CNAME")
    # Create a CNAME source record at the same name
    cname_key = RecordKey(name=base_rs.key.name, rtype="CNAME")
    cname_rs = RecordSet(key=cname_key, ttl=300, values=frozenset({"target.example.com."}))
    source = {cname_key: cname_rs}
    target = {base_rs.key: base_rs}
    diff = compute_diff(source, target, ZONE_APEX, ignore_ttl=True)
    # CNAME should not appear in creates (it conflicts)
    create_keys = {rs.key for rs in diff.creates}
    assert cname_key not in create_keys
    # Conflict should be recorded
    assert len(diff.conflicts) >= 1
    conflict_names = [name for name, _, _ in diff.conflicts]
    assert base_rs.key.name in conflict_names


# Feature: bind-to-route53-mirror-demo, Property 10: Empty diff skips Route 53 writes
# **Validates: Requirements 4.8**
@given(record_dict(min_size=1, max_size=5))
def test_property_empty_diff_skips_writes(records):
    """Diff of identical source and target yields empty diff (no API calls needed)."""
    diff = compute_diff(records, records, ZONE_APEX, ignore_ttl=True)
    assert diff.is_empty
    assert diff.creates == []
    assert diff.upserts == []
    assert diff.deletes == []


# Feature: bind-to-route53-mirror-demo, Property 12: Diff idempotency
# **Validates: Requirements 5.5**
@given(record_dict(min_size=1, max_size=5), record_dict(min_size=0, max_size=5))
def test_property_diff_idempotency(source, target):
    """Applying the diff once and recomputing yields zero operations."""
    diff = compute_diff(source, target, ZONE_APEX, ignore_ttl=True)
    # Simulate applying the diff: start from target, apply creates/upserts, remove deletes
    new_state = dict(target)
    for rs in diff.creates:
        new_state[rs.key] = rs
    for rs in diff.upserts:
        new_state[rs.key] = rs
    for key in diff.deletes:
        new_state.pop(key, None)
    # Second diff should be empty (ignoring conflicts which are skipped records)
    second_diff = compute_diff(source, new_state, ZONE_APEX, ignore_ttl=True)
    # Creates and deletes should be zero; only possible non-empty is conflicts (already skipped)
    conflict_names = {name for name, _, _ in diff.conflicts}
    non_conflict_creates = [
        rs for rs in second_diff.creates if rs.key.name not in conflict_names
    ]
    non_conflict_upserts = [
        rs for rs in second_diff.upserts if rs.key.name not in conflict_names
    ]
    assert non_conflict_creates == [], f"Unexpected creates after idempotent apply: {non_conflict_creates}"
    assert non_conflict_upserts == [], f"Unexpected upserts after idempotent apply: {non_conflict_upserts}"
    assert second_diff.deletes == [], f"Unexpected deletes after idempotent apply: {second_diff.deletes}"
