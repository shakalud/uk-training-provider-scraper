import re
from urllib.parse import urlsplit, urlunsplit


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_url(value: object) -> str:
    url = clean_text(value)
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url.lstrip("/")
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "", parts.query, ""))


def normalize_phone(value: object) -> str:
    phone = clean_text(value)
    return re.sub(r"[^\d+() .-]", "", phone)


def provider_key(record: dict) -> tuple[str, str]:
    name = clean_text(record.get("provider_name")).casefold()
    website = urlsplit(normalize_url(record.get("website"))).netloc.removeprefix("www.")
    return name, website


def deduplicate(records: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for record in records:
        key = provider_key(record)
        if key not in merged:
            merged[key] = record.copy()
            continue
        current = merged[key]
        for field, value in record.items():
            if not current.get(field) and value:
                current[field] = value
        locations = [clean_text(x) for x in (current.get("town_or_location", ""), record.get("town_or_location", "")) if clean_text(x)]
        current["town_or_location"] = "; ".join(dict.fromkeys(locations))
        addresses = [clean_text(x) for x in (current.get("address", ""), record.get("address", "")) if clean_text(x)]
        current["address"] = "; ".join(dict.fromkeys(addresses))
    return list(merged.values())
