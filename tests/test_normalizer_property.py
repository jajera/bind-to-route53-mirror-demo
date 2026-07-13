from hypothesis import given, settings
from hypothesis import strategies as st

import pytest

from tests.generators import raw_record
from zone_sync.constants import SYNC_TYPES
from zone_sync.models import RawRecord, RecordKey, RecordSet
from zone_sync.normalizer import (
    normalize_fqdn,
    normalize_records,
    normalize_txt_value,
    records_equal,
)


# Feature: bind-to-route53-mirror-demo, Property 1: Normalization produces valid RecordSets
# **Validates: Requirements 1.2, 2.2**
@given(raw_record())
def test_property_normalization_produces_valid_record_sets(raw):
    normalized, _ = normalize_records([raw], ignore_ttl=True, zone_origin="example.com")
    for record in normalized.values():
        assert record.key.name.endswith(".")
        assert record.key.rtype in SYNC_TYPES
        assert record.ttl >= 0
        assert record.values


# Feature: bind-to-route53-mirror-demo, Property 2: Trailing dot normalization is idempotent
# **Validates: Requirements 3.1**
@given(raw_record())
def test_property_trailing_dot_idempotent(raw):
    first, _ = normalize_records([raw], ignore_ttl=True, zone_origin="example.com")
    if not first:
        return
    record = next(iter(first.values()))
    assert normalize_fqdn(record.key.name) == record.key.name


# Feature: bind-to-route53-mirror-demo, Property 3: TXT normalization round-trip consistency
# **Validates: Requirements 3.2**
@given(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_characters='"')))
def test_property_txt_normalization_round_trip(txt_content):
    """Semantically equivalent TXT strings normalize to the same value."""
    # Unquoted form
    plain = normalize_txt_value([txt_content])
    # Single-quoted form
    quoted = normalize_txt_value([f'"{txt_content}"'])
    # Multi-part quoted form (split into two chunks)
    mid = len(txt_content) // 2
    if mid > 0:
        multi_quoted = normalize_txt_value(
            [f'"{txt_content[:mid]}" "{txt_content[mid:]}"']
        )
        assert multi_quoted == plain
    assert plain == quoted


# Feature: bind-to-route53-mirror-demo, Property 4: Record equality respects IgnoreTTL setting
# **Validates: Requirements 3.3, 3.4, 3.5**
@given(
    raw_record(),
    st.integers(min_value=0, max_value=86400),
    st.integers(min_value=0, max_value=86400),
)
def test_property_record_equality_respects_ignore_ttl(raw, ttl_a, ttl_b):
    """Same name/type/data with different TTL: equal when IgnoreTTL=true, unequal when false."""
    normalized, _ = normalize_records([raw], ignore_ttl=True, zone_origin="example.com")
    if not normalized:
        return
    record = next(iter(normalized.values()))
    rec_a = RecordSet(key=record.key, ttl=ttl_a, values=record.values)
    rec_b = RecordSet(key=record.key, ttl=ttl_b, values=record.values)
    # With ignore_ttl=True, same key+values are always equal regardless of TTL
    assert records_equal(rec_a, rec_b, ignore_ttl=True)
    # With ignore_ttl=False, equality depends on TTL match
    if ttl_a == ttl_b:
        assert records_equal(rec_a, rec_b, ignore_ttl=False)
    else:
        assert not records_equal(rec_a, rec_b, ignore_ttl=False)


# Feature: bind-to-route53-mirror-demo, Property 14: Malformed record exclusion preserves valid records
# **Validates: Requirements 1.4**
@given(st.lists(raw_record(), min_size=1, max_size=10))
def test_property_malformed_record_exclusion_preserves_valid(records):
    """Malformed raw records excluded with warnings; all well-formed records retained."""
    # Add a malformed record (negative TTL)
    malformed = RawRecord(name="bad..host", rtype="A", ttl=-1, rdata=["10.0.0.1"])
    all_records = records + [malformed]
    normalized, warnings = normalize_records(
        all_records, ignore_ttl=True, zone_origin="example.com"
    )
    # The malformed record should generate a warning
    assert any(w.name == "bad..host" or w.message for w in warnings)
    # All valid records from the original set should still be normalized
    valid_normalized, _ = normalize_records(
        records, ignore_ttl=True, zone_origin="example.com"
    )
    for key, rs in valid_normalized.items():
        assert key in normalized
        assert normalized[key] == rs
