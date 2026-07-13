import pytest
from hypothesis import given

from tests.generators import domain_name, ipv4_address, zone_id
from zone_sync.exceptions import ValidationError
from zone_sync.validator import validate_event


@given(domain_name, ipv4_address(), zone_id())
def test_property_valid_inputs_accepted(domain, ip, zid):
    event = {"Domain": domain, "MasterDns": ip, "ZoneId": zid, "IgnoreTTL": True}
    result = validate_event(event)
    assert result.domain == domain.rstrip(".")


@given(domain_name)
def test_property_invalid_ip_rejected(domain):
    event = {"Domain": domain, "MasterDns": "999.999.999.999", "ZoneId": "Z1234567890ABC"}
    with pytest.raises(ValidationError):
        validate_event(event)
