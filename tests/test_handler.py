from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws

from zone_sync.exceptions import AXFRError, ValidationError
from zone_sync.handler import lambda_handler
from zone_sync.models import RawRecord


@patch("zone_sync.handler.fetch_zone")
@patch("zone_sync.handler.fetch_route53_records")
def test_handler_happy_path(mock_r53, mock_axfr):
    mock_axfr.return_value = [
        RawRecord(name="app.corp.internal.", rtype="A", ttl=300, rdata=["10.0.0.1"])
    ]
    mock_r53.return_value = []

    with mock_aws():
        import boto3

        client = boto3.client("route53", region_name="us-east-1")
        zone = client.create_hosted_zone(
            Name="corp.internal.",
            CallerReference="test",
            HostedZoneConfig={"PrivateZone": False},
        )["HostedZone"]["Id"]

        event = {
            "Domain": "corp.internal",
            "MasterDns": "10.0.1.10",
            "ZoneId": zone,
            "IgnoreTTL": True,
        }
        result = lambda_handler(event, None)
        assert result["status"] == "success"
        assert result["creates"] == 1


@patch("zone_sync.handler.fetch_zone")
def test_handler_axfr_failure(mock_axfr):
    mock_axfr.side_effect = AXFRError("timeout")
    event = {
        "Domain": "corp.internal",
        "MasterDns": "10.0.1.10",
        "ZoneId": "Z1234567890ABC",
    }
    with pytest.raises(AXFRError, match="timeout"):
        lambda_handler(event, None)


def test_handler_validation_failure():
    with pytest.raises(ValidationError):
        lambda_handler({}, None)
