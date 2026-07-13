from zone_sync.diff_engine import compute_diff
from zone_sync.models import RecordKey, RecordSet


def _rs(name: str, rtype: str, ttl: int, value: str) -> RecordSet:
    key = RecordKey(name=name, rtype=rtype)
    return RecordSet(key=key, ttl=ttl, values=frozenset({value}))


def test_diff_create_delete_upsert():
    source = {
        RecordKey("app.corp.internal.", "A"): _rs(
            "app.corp.internal.", "A", 300, "10.0.0.1"
        ),
        RecordKey("new.corp.internal.", "A"): _rs(
            "new.corp.internal.", "A", 300, "10.0.0.2"
        ),
    }
    target = {
        RecordKey("app.corp.internal.", "A"): _rs(
            "app.corp.internal.", "A", 300, "10.0.0.9"
        ),
        RecordKey("old.corp.internal.", "A"): _rs(
            "old.corp.internal.", "A", 300, "10.0.0.3"
        ),
    }
    diff = compute_diff(source, target, "corp.internal.", ignore_ttl=True)
    assert len(diff.creates) == 1
    assert diff.creates[0].key.name == "new.corp.internal."
    assert len(diff.deletes) == 1
    assert diff.deletes[0].name == "old.corp.internal."
    assert len(diff.upserts) == 1


def test_diff_excludes_soa_and_apex_ns():
    source = {
        RecordKey("corp.internal.", "SOA"): _rs("corp.internal.", "SOA", 300, "x"),
        RecordKey("corp.internal.", "NS"): _rs("corp.internal.", "NS", 300, "ns1."),
    }
    diff = compute_diff(source, {}, "corp.internal.")
    assert diff.is_empty


def test_cname_conflict_skipped():
    source = {
        RecordKey("www.corp.internal.", "CNAME"): _rs(
            "www.corp.internal.", "CNAME", 300, "app.corp.internal."
        )
    }
    target = {
        RecordKey("www.corp.internal.", "A"): _rs(
            "www.corp.internal.", "A", 300, "10.0.0.1"
        )
    }
    diff = compute_diff(source, target, "corp.internal.")
    assert diff.creates == []
    assert len(diff.conflicts) == 1


def test_diff_idempotent():
    source = {
        RecordKey("app.corp.internal.", "A"): _rs(
            "app.corp.internal.", "A", 300, "10.0.0.1"
        )
    }
    diff = compute_diff(source, source, "corp.internal.")
    assert diff.is_empty
