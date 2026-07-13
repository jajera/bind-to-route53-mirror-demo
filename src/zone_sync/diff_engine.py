from zone_sync.constants import SYNC_TYPES
from zone_sync.models import DiffResult, RecordKey, RecordSet, record_sets_equal


def _apex(name: str, zone_apex: str) -> bool:
    apex = zone_apex if zone_apex.endswith(".") else f"{zone_apex}."
    return name.lower() == apex.lower()


def _skip_record(key: RecordKey, zone_apex: str) -> bool:
    if key.rtype == "SOA":
        return True
    if key.rtype == "NS" and _apex(key.name, zone_apex):
        return True
    if key.rtype not in SYNC_TYPES:
        return True
    return False


def _types_at_name(target: dict[RecordKey, RecordSet], name: str) -> set[str]:
    return {k.rtype for k in target if k.name == name}


def compute_diff(
    source: dict[RecordKey, RecordSet],
    target: dict[RecordKey, RecordSet],
    zone_apex: str,
    ignore_ttl: bool = True,
) -> DiffResult:
    diff = DiffResult()
    source_keys = {k for k in source if not _skip_record(k, zone_apex)}
    target_keys = {k for k in target if not _skip_record(k, zone_apex)}

    for key in sorted(source_keys, key=lambda k: (k.name, k.rtype)):
        record = source[key]
        if key not in target_keys:
            if record.key.rtype == "CNAME":
                existing = _types_at_name(target, key.name)
                if existing:
                    for t in existing:
                        diff.conflicts.append((key.name, "CNAME", t))
                    continue
            diff.creates.append(record)
            continue
        if not record_sets_equal(record, target[key], ignore_ttl):
            if record.key.rtype == "CNAME":
                existing = _types_at_name(target, key.name) - {key.rtype}
                if existing:
                    for t in existing:
                        diff.conflicts.append((key.name, "CNAME", t))
                    continue
            diff.upserts.append(record)

    for key in sorted(target_keys - source_keys, key=lambda k: (k.name, k.rtype)):
        diff.deletes.append(key)

    return diff
