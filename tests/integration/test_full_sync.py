from unittest.mock import patch

from moto import mock_aws

from zone_sync.handler import lambda_handler
from zone_sync.models import RawRecord


@mock_aws
@patch("zone_sync.handler.fetch_zone")
def test_full_sync_idempotent(mock_axfr):
    import boto3

    client = boto3.client("route53", region_name="us-east-1")
    zone_id = client.create_hosted_zone(
        Name="corp.internal.",
        CallerReference="integration-1",
    )["HostedZone"]["Id"]

    client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "stale.corp.internal.",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "10.0.0.99"}],
                    },
                }
            ]
        },
    )

    mock_axfr.return_value = [
        RawRecord(name="app.corp.internal.", rtype="A", ttl=300, rdata=["10.0.0.1"]),
    ]

    event = {
        "Domain": "corp.internal",
        "MasterDns": "10.0.1.10",
        "ZoneId": zone_id,
        "IgnoreTTL": True,
    }
    first = lambda_handler(event, None)
    assert first["status"] == "success"
    assert first["creates"] == 1
    assert first["deletes"] == 1

    second = lambda_handler(event, None)
    assert second["status"] == "success"
    assert second["creates"] == 0
    assert second["upserts"] == 0
    assert second["deletes"] == 0


@mock_aws
@patch("zone_sync.handler.fetch_zone")
def test_upsert_on_changed_ip(mock_axfr):
    """AXFR returns changed IP for an existing record → UPSERT applied, then idempotent."""
    import boto3

    client = boto3.client("route53", region_name="us-east-1")
    zone_id = client.create_hosted_zone(
        Name="corp.internal.",
        CallerReference="integration-upsert",
    )["HostedZone"]["Id"]

    # Pre-populate Route 53 with app.corp.internal. pointing to old IP
    client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "app.corp.internal.",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "10.0.0.1"}],
                    },
                }
            ]
        },
    )

    # AXFR source now has a different IP for the same record
    mock_axfr.return_value = [
        RawRecord(name="app.corp.internal.", rtype="A", ttl=300, rdata=["10.0.0.2"]),
    ]

    event = {
        "Domain": "corp.internal",
        "MasterDns": "10.0.1.10",
        "ZoneId": zone_id,
        "IgnoreTTL": True,
    }

    # First run: detects changed rdata → UPSERT
    first = lambda_handler(event, None)
    assert first["status"] == "success"
    assert first["creates"] == 0
    assert first["upserts"] == 1
    assert first["deletes"] == 0

    # Verify Route 53 now has the new IP
    rrsets = client.list_resource_record_sets(HostedZoneId=zone_id)[
        "ResourceRecordSets"
    ]
    app_records = [
        r for r in rrsets
        if r["Name"] == "app.corp.internal." and r["Type"] == "A"
    ]
    assert len(app_records) == 1
    assert app_records[0]["ResourceRecords"] == [{"Value": "10.0.0.2"}]

    # Second run: idempotent (no changes)
    second = lambda_handler(event, None)
    assert second["status"] == "success"
    assert second["creates"] == 0
    assert second["upserts"] == 0
    assert second["deletes"] == 0


@mock_aws
@patch("zone_sync.handler.fetch_zone")
def test_cname_conflict_skipped(mock_axfr):
    """CNAME in AXFR source vs A record at same name in Route 53 → conflict skipped."""
    import boto3

    client = boto3.client("route53", region_name="us-east-1")
    zone_id = client.create_hosted_zone(
        Name="corp.internal.",
        CallerReference="integration-cname",
    )["HostedZone"]["Id"]

    # Pre-populate Route 53 with an A record at web.corp.internal.
    client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "web.corp.internal.",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "10.0.0.5"}],
                    },
                }
            ]
        },
    )

    # AXFR source has a CNAME at the same name (web.corp.internal.)
    # plus a non-conflicting record that should still sync
    mock_axfr.return_value = [
        RawRecord(
            name="web.corp.internal.",
            rtype="CNAME",
            ttl=300,
            rdata=["alias.corp.internal."],
        ),
        RawRecord(name="api.corp.internal.", rtype="A", ttl=300, rdata=["10.0.0.10"]),
    ]

    event = {
        "Domain": "corp.internal",
        "MasterDns": "10.0.1.10",
        "ZoneId": zone_id,
        "IgnoreTTL": True,
    }

    result = lambda_handler(event, None)
    assert result["status"] == "success"

    # The CNAME conflict is skipped — the A record at web.corp.internal. stays as a
    # delete candidate (present in target, absent as A in source), and the CNAME is
    # not created.
    # api.corp.internal. A should be created normally.
    assert result["creates"] == 1  # api.corp.internal. A
    # web.corp.internal. A is deleted because it's in target but not in source
    assert result["deletes"] == 1

    # Verify CNAME was NOT created — Route 53 should not have the CNAME
    rrsets = client.list_resource_record_sets(HostedZoneId=zone_id)[
        "ResourceRecordSets"
    ]
    cname_records = [
        r for r in rrsets
        if r["Name"] == "web.corp.internal." and r["Type"] == "CNAME"
    ]
    assert len(cname_records) == 0

    # Verify the non-conflicting record was created
    api_records = [
        r for r in rrsets
        if r["Name"] == "api.corp.internal." and r["Type"] == "A"
    ]
    assert len(api_records) == 1
    assert api_records[0]["ResourceRecords"] == [{"Value": "10.0.0.10"}]
