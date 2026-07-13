from zone_sync.constants import DEFAULT_TIMEOUT, SYNC_TYPES
from zone_sync.exceptions import AXFRError
from zone_sync.models import RawRecord


def fetch_zone(master_ip: str, domain: str, timeout: int = DEFAULT_TIMEOUT) -> list[RawRecord]:
    try:
        import dns.query
        import dns.name
        import dns.rdatatype
        import dns.zone
    except ImportError as exc:
        raise AXFRError("dnspython is required for AXFR") from exc

    zone_name = dns.name.from_text(domain)
    try:
        xfr = dns.query.xfr(where=master_ip, zone=zone_name, timeout=timeout)
        zone = dns.zone.from_xfr(xfr)
    except Exception as exc:
        raise AXFRError(
            f"AXFR failed for {domain} at {master_ip}: {exc}"
        ) from exc

    records: list[RawRecord] = []
    for name, node in zone.nodes.items():
        fqdn = name.derelativize(zone_name).to_text()
        for rdataset in node.rdatasets:
            rtype = dns.rdatatype.to_text(rdataset.rdtype)
            if rtype not in SYNC_TYPES and rtype not in ("NS", "SOA"):
                continue
            ttl = int(rdataset.ttl)
            rdata = [rr.to_text() for rr in rdataset]
            records.append(RawRecord(name=fqdn, rtype=rtype, ttl=ttl, rdata=rdata))
    return records
