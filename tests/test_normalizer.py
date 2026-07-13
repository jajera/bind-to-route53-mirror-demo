from zone_sync.constants import SYNC_TYPES
from zone_sync.models import RawRecord, RecordKey, RecordSet
from zone_sync.normalizer import normalize_fqdn, normalize_records, normalize_txt_value


def test_trailing_dot_idempotent():
    name = normalize_fqdn("app.corp.internal")
    assert name == "app.corp.internal."
    assert normalize_fqdn(name) == name


def test_txt_normalization():
    assert normalize_txt_value(['"hello" "world"']) == "helloworld"
    assert normalize_txt_value(['"hello"']) == "hello"


def test_normalize_records_skips_malformed():
    raw = [
        RawRecord(name="good.corp.internal", rtype="A", ttl=300, rdata=["10.0.0.1"]),
        RawRecord(name="", rtype="A", ttl=300, rdata=["10.0.0.2"]),
    ]
    normalized, warnings = normalize_records(raw, ignore_ttl=True, zone_origin="corp.internal")
    assert len(normalized) == 1
    assert len(warnings) == 1
    key = RecordKey(name="good.corp.internal.", rtype="A")
    assert key in normalized


def test_normalize_filters_types():
    raw = [RawRecord(name="x.corp.internal", rtype="NAPTR", ttl=300, rdata=["1"])]
    normalized, _ = normalize_records(raw, ignore_ttl=True, zone_origin="corp.internal")
    assert normalized == {}
