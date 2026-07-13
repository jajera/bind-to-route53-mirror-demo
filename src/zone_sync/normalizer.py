import re

from zone_sync.constants import SYNC_TYPES
from zone_sync.models import NormalizeWarning, RawRecord, RecordKey, RecordSet


def normalize_fqdn(name: str, origin: str | None = None) -> str:
    text = name.strip()
    if not text:
        raise ValueError("empty name")
    if not text.endswith("."):
        if origin and not text.endswith(origin.rstrip(".")):
            text = f"{text}.{origin.rstrip('.')}"
        text = f"{text}."
    if text.count(".") == 1 and text == ".":
        raise ValueError("invalid name")
    return text.lower()


def normalize_txt_value(parts: list[str]) -> str:
    joined = " ".join(parts)
    chunks = re.findall(r'"([^"]*)"', joined)
    if chunks:
        return "".join(chunks)
    if joined.startswith('"') and joined.endswith('"'):
        return joined[1:-1]
    return joined.replace('"', "")


def normalize_rdata(rtype: str, rdata: list[str]) -> frozenset[str]:
    rtype = rtype.upper()
    if not rdata:
        raise ValueError("empty rdata")
    if rtype == "TXT":
        return frozenset({normalize_txt_value(rdata)})
    if rtype == "CNAME":
        return frozenset({normalize_fqdn(rdata[0])})
    if rtype in ("A", "AAAA", "PTR"):
        return frozenset({part.strip() for part in rdata})
    if rtype == "MX":
        normalized = []
        for part in rdata:
            tokens = part.split(None, 1)
            if len(tokens) == 2:
                priority, host = tokens
                normalized.append(f"{priority} {normalize_fqdn(host)}")
            else:
                normalized.append(part.strip())
        return frozenset(normalized)
    if rtype == "SRV":
        normalized = []
        for part in rdata:
            tokens = part.split()
            if len(tokens) == 4:
                priority, weight, port, target = tokens
                normalized.append(
                    f"{priority} {weight} {port} {normalize_fqdn(target)}"
                )
            else:
                normalized.append(part.strip())
        return frozenset(normalized)
    return frozenset({part.strip() for part in rdata})


def normalize_records(
    raw_records: list[RawRecord],
    ignore_ttl: bool,
    allowed_types: set[str] | frozenset[str] = SYNC_TYPES,
    zone_origin: str | None = None,
) -> tuple[dict[RecordKey, RecordSet], list[NormalizeWarning]]:
    del ignore_ttl  # comparison happens in diff, not normalization
    result: dict[RecordKey, RecordSet] = {}
    warnings: list[NormalizeWarning] = []

    for raw in raw_records:
        rtype = raw.rtype.upper()
        if rtype not in allowed_types:
            continue
        try:
            name = normalize_fqdn(raw.name, zone_origin)
            values = normalize_rdata(rtype, raw.rdata)
            if raw.ttl < 0:
                raise ValueError("negative ttl")
            key = RecordKey(name=name, rtype=rtype)
            result[key] = RecordSet(key=key, ttl=raw.ttl, values=values)
        except (ValueError, IndexError) as exc:
            warnings.append(
                NormalizeWarning(
                    name=raw.name,
                    rtype=raw.rtype,
                    message=str(exc),
                )
            )
    return result, warnings


def records_equal(a: RecordSet, b: RecordSet, ignore_ttl: bool) -> bool:
    if a.key != b.key or a.values != b.values:
        return False
    if ignore_ttl:
        return True
    return a.ttl == b.ttl
