"""Unit tests for zone_sync.route53_reader — mocked boto3 paginator."""

from unittest.mock import MagicMock, patch

import pytest

from zone_sync.exceptions import Route53ReadError
from zone_sync.route53_reader import fetch_route53_records


def _make_mock_client(pages: list[dict]):
    """Create a mock boto3 client with paginator returning given pages."""
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = iter(pages)
    mock_client.get_paginator.return_value = mock_paginator
    return mock_client


def test_fetch_route53_records_single_page():
    """Single page of records is parsed correctly."""
    pages = [
        {
            "ResourceRecordSets": [
                {
                    "Name": "app.corp.internal.",
                    "Type": "A",
                    "TTL": 300,
                    "ResourceRecords": [{"Value": "10.0.0.1"}],
                },
                {
                    "Name": "mail.corp.internal.",
                    "Type": "MX",
                    "TTL": 600,
                    "ResourceRecords": [{"Value": "10 mail.corp.internal."}],
                },
            ]
        }
    ]
    client = _make_mock_client(pages)

    records = fetch_route53_records("Z1234567890ABC", client=client)
    assert len(records) == 2
    assert records[0].name == "app.corp.internal."
    assert records[0].rtype == "A"
    assert records[0].ttl == 300
    assert records[0].rdata == ["10.0.0.1"]
    assert records[1].rtype == "MX"


def test_fetch_route53_records_pagination():
    """Multiple pages are aggregated correctly."""
    pages = [
        {
            "ResourceRecordSets": [
                {
                    "Name": "a.corp.internal.",
                    "Type": "A",
                    "TTL": 300,
                    "ResourceRecords": [{"Value": "10.0.0.1"}],
                }
            ]
        },
        {
            "ResourceRecordSets": [
                {
                    "Name": "b.corp.internal.",
                    "Type": "A",
                    "TTL": 300,
                    "ResourceRecords": [{"Value": "10.0.0.2"}],
                }
            ]
        },
    ]
    client = _make_mock_client(pages)

    records = fetch_route53_records("Z1234567890ABC", client=client)
    assert len(records) == 2
    assert records[0].name == "a.corp.internal."
    assert records[1].name == "b.corp.internal."


def test_fetch_route53_records_skips_alias():
    """Alias records are skipped (no ResourceRecords)."""
    pages = [
        {
            "ResourceRecordSets": [
                {
                    "Name": "alias.corp.internal.",
                    "Type": "A",
                    "AliasTarget": {
                        "HostedZoneId": "Z111",
                        "DNSName": "elb.amazonaws.com.",
                        "EvaluateTargetHealth": False,
                    },
                },
                {
                    "Name": "real.corp.internal.",
                    "Type": "A",
                    "TTL": 300,
                    "ResourceRecords": [{"Value": "10.0.0.5"}],
                },
            ]
        }
    ]
    client = _make_mock_client(pages)

    records = fetch_route53_records("Z1234567890ABC", client=client)
    assert len(records) == 1
    assert records[0].name == "real.corp.internal."


def test_fetch_route53_records_api_error():
    """API error raises Route53ReadError."""
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.side_effect = Exception("Throttling")
    mock_client.get_paginator.return_value = mock_paginator

    with pytest.raises(Route53ReadError, match="ListResourceRecordSets failed"):
        fetch_route53_records("Z1234567890ABC", client=mock_client)
