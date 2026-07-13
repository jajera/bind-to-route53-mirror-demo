import pytest

from zone_sync.exceptions import ValidationError
from zone_sync.models import ValidatedInput
from zone_sync.validator import validate_event


def test_validate_event_success():
    event = {
        "Domain": "corp.internal",
        "MasterDns": "10.0.1.10",
        "ZoneId": "Z1234567890ABC",
        "IgnoreTTL": True,
    }
    result = validate_event(event)
    assert isinstance(result, ValidatedInput)
    assert result.domain == "corp.internal"
    assert result.ignore_ttl is True


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"Domain": "", "MasterDns": "10.0.0.1", "ZoneId": "Z1234567890ABC"},
        {"Domain": "corp.internal", "MasterDns": "not-an-ip", "ZoneId": "Z1234567890ABC"},
        {"Domain": "corp.internal", "MasterDns": "10.0.0.1", "ZoneId": "bad"},
    ],
)
def test_validate_event_rejects_invalid(event):
    with pytest.raises(ValidationError):
        validate_event(event)


def test_validate_event_ipv6():
    event = {
        "Domain": "corp.internal",
        "MasterDns": "2001:db8::1",
        "ZoneId": "Z1234567890ABC",
    }
    assert validate_event(event).master_dns == "2001:db8::1"
