import ipaddress
import re

from zone_sync.constants import ZONE_ID_PATTERN
from zone_sync.exceptions import ValidationError
from zone_sync.models import ValidatedInput

_DOMAIN_LABEL = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")


def _valid_domain(domain: str) -> bool:
    if not domain or len(domain) > 253:
        return False
    labels = domain.rstrip(".").split(".")
    if not labels or any(not label for label in labels):
        return False
    return all(_DOMAIN_LABEL.match(label) for label in labels)


def validate_event(event: dict) -> ValidatedInput:
    if not isinstance(event, dict):
        raise ValidationError("Event must be a JSON object")

    domain = event.get("Domain")
    if not isinstance(domain, str) or not _valid_domain(domain):
        raise ValidationError(f"Invalid Domain: {domain!r}")

    master_dns = event.get("MasterDns")
    if not isinstance(master_dns, str):
        raise ValidationError(f"Invalid MasterDns: {master_dns!r}")
    try:
        ipaddress.ip_address(master_dns)
    except ValueError as exc:
        raise ValidationError(f"Invalid MasterDns: {master_dns!r}") from exc

    zone_id = event.get("ZoneId")
    if not isinstance(zone_id, str):
        raise ValidationError(f"Invalid ZoneId: {zone_id!r}")
    if zone_id.startswith("/hostedzone/"):
        zone_id = zone_id.removeprefix("/hostedzone/")
    if not re.fullmatch(ZONE_ID_PATTERN, zone_id):
        raise ValidationError(f"Invalid ZoneId: {event.get('ZoneId')!r}")

    ignore_ttl = event.get("IgnoreTTL", True)
    if isinstance(ignore_ttl, str):
        ignore_ttl = ignore_ttl.lower() in ("true", "1", "yes")
    if not isinstance(ignore_ttl, bool):
        raise ValidationError(f"Invalid IgnoreTTL: {ignore_ttl!r}")

    return ValidatedInput(
        domain=domain.rstrip("."),
        master_dns=master_dns,
        zone_id=zone_id,
        ignore_ttl=ignore_ttl,
    )
