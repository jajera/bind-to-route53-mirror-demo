SYNC_TYPES: frozenset[str] = frozenset(
    {"A", "AAAA", "CNAME", "MX", "TXT", "SRV", "PTR"}
)
MAX_BATCH_SIZE: int = 1000
DEFAULT_TIMEOUT: int = 30
DEFAULT_SYNC_INTERVAL_MIN: int = 15
ZONE_ID_PATTERN = r"^Z?[A-Z0-9]{10,32}$"
