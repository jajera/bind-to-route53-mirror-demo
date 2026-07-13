from zone_sync.exceptions import Route53ReadError
from zone_sync.models import RawRecord


def fetch_route53_records(zone_id: str, client=None) -> list[RawRecord]:
    if client is None:
        import boto3

        client = boto3.client("route53")

    records: list[RawRecord] = []
    paginator = client.get_paginator("list_resource_record_sets")
    try:
        for page in paginator.paginate(HostedZoneId=zone_id):
            for rrset in page.get("ResourceRecordSets", []):
                if "AliasTarget" in rrset:
                    continue
                name = rrset["Name"]
                rtype = rrset["Type"]
                ttl = int(rrset.get("TTL", 0))
                rdata = [r["Value"] for r in rrset.get("ResourceRecords", [])]
                records.append(RawRecord(name=name, rtype=rtype, ttl=ttl, rdata=rdata))
    except Exception as exc:
        raise Route53ReadError(f"ListResourceRecordSets failed for {zone_id}: {exc}") from exc
    return records
