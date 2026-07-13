from dataclasses import dataclass, field

from zone_sync.constants import SYNC_TYPES


@dataclass(frozen=True)
class RecordKey:
    name: str
    rtype: str


@dataclass(frozen=True)
class RecordSet:
    key: RecordKey
    ttl: int
    values: frozenset[str]


@dataclass
class RawRecord:
    name: str
    rtype: str
    ttl: int
    rdata: list[str]


@dataclass(frozen=True)
class ValidatedInput:
    domain: str
    master_dns: str
    zone_id: str
    ignore_ttl: bool


@dataclass
class DiffResult:
    creates: list[RecordSet] = field(default_factory=list)
    upserts: list[RecordSet] = field(default_factory=list)
    deletes: list[RecordKey] = field(default_factory=list)
    conflicts: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.creates and not self.upserts and not self.deletes


@dataclass
class ApplyResult:
    creates_applied: int = 0
    upserts_applied: int = 0
    deletes_applied: int = 0
    batches_sent: int = 0


@dataclass(frozen=True)
class NormalizeWarning:
    name: str
    rtype: str
    message: str


def record_sets_equal(a: RecordSet, b: RecordSet, ignore_ttl: bool) -> bool:
    if a.key != b.key:
        return False
    if not ignore_ttl and a.ttl != b.ttl:
        return False
    return a.values == b.values


def is_sync_type(rtype: str) -> bool:
    return rtype.upper() in SYNC_TYPES
