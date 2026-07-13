from zone_sync.constants import MAX_BATCH_SIZE
from zone_sync.exceptions import ApplyError
from zone_sync.models import ApplyResult, DiffResult, RecordKey, RecordSet


def batch_changes(diff: DiffResult, batch_size: int = MAX_BATCH_SIZE) -> list[list[tuple[str, RecordSet | RecordKey]]]:
    operations: list[tuple[str, RecordSet | RecordKey]] = []
    for record in diff.creates:
        operations.append(("CREATE", record))
    for record in diff.upserts:
        operations.append(("UPSERT", record))
    for key in diff.deletes:
        operations.append(("DELETE", key))

    batches: list[list[tuple[str, RecordSet | RecordKey]]] = []
    for i in range(0, len(operations), batch_size):
        batches.append(operations[i : i + batch_size])
    return batches


def _to_rrset(record: RecordSet) -> dict:
    return {
        "Name": record.key.name,
        "Type": record.key.rtype,
        "TTL": record.ttl,
        "ResourceRecords": [{"Value": value} for value in sorted(record.values)],
    }


def _delete_rrset(key: RecordKey, target: dict) -> dict:
    record = target[key]
    return _to_rrset(record)


def apply_changes(
    zone_id: str,
    diff: DiffResult,
    target: dict | None = None,
    batch_size: int = MAX_BATCH_SIZE,
    client=None,
) -> ApplyResult:
    if diff.is_empty:
        return ApplyResult()

    if client is None:
        import boto3

        client = boto3.client("route53")

    if target is None:
        target = {}

    result = ApplyResult()
    batches = batch_changes(diff, batch_size)

    for batch_index, batch in enumerate(batches):
        changes = []
        batch_creates = batch_upserts = batch_deletes = 0
        for action, item in batch:
            if action in ("CREATE", "UPSERT"):
                assert isinstance(item, RecordSet)
                changes.append({"Action": action, "ResourceRecordSet": _to_rrset(item)})
                if action == "CREATE":
                    batch_creates += 1
                else:
                    batch_upserts += 1
            else:
                assert isinstance(item, RecordKey)
                if item not in target:
                    raise ApplyError(f"Missing target record for delete: {item}")
                changes.append(
                    {"Action": "DELETE", "ResourceRecordSet": _delete_rrset(item, target)}
                )
                batch_deletes += 1
        try:
            client.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={"Changes": changes},
            )
        except Exception as exc:
            raise ApplyError(
                f"ChangeResourceRecordSets failed on batch {batch_index}: {exc}"
            ) from exc
        result.creates_applied += batch_creates
        result.upserts_applied += batch_upserts
        result.deletes_applied += batch_deletes
        result.batches_sent += 1

    return result
