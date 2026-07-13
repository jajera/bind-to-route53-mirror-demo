"""Hypothesis strategies for DNS record testing."""

import ipaddress
import string

from hypothesis import strategies as st

from zone_sync.constants import SYNC_TYPES
from zone_sync.models import RawRecord, RecordKey, RecordSet

label = st.from_regex(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", fullmatch=True)
domain_name = st.lists(label, min_size=1, max_size=4).map(".".join)
fqdn = domain_name.map(lambda d: f"{d}.")


@st.composite
def ipv4_address(draw):
    return str(ipaddress.IPv4Address(draw(st.integers(min_value=0, max_value=2**32 - 1))))


@st.composite
def zone_id(draw):
    suffix = draw(st.text(alphabet=string.ascii_uppercase + string.digits, min_size=10, max_size=20))
    return f"Z{suffix}"


@st.composite
def raw_record(draw, rtype=None):
    name = draw(domain_name)
    rtype = rtype or draw(st.sampled_from(sorted(SYNC_TYPES)))
    ttl = draw(st.integers(min_value=0, max_value=86400))
    if rtype == "A":
        rdata = [draw(ipv4_address())]
    elif rtype == "TXT":
        rdata = [draw(st.text(min_size=1, max_size=20))]
    elif rtype == "CNAME":
        rdata = [draw(domain_name)]
    else:
        rdata = [draw(st.text(min_size=1, max_size=30))]
    return RawRecord(name=name, rtype=rtype, ttl=ttl, rdata=rdata)


@st.composite
def record_set(draw, rtype=None):
    raw = draw(raw_record(rtype=rtype))
    from zone_sync.normalizer import normalize_records

    normalized, _ = normalize_records([raw], ignore_ttl=True, zone_origin="example.com")
    if not normalized:
        return draw(record_set(rtype=rtype))
    return next(iter(normalized.values()))


@st.composite
def record_key(draw):
    rs = draw(record_set())
    return rs.key
