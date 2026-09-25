"""Lever job board client. Public, no-auth JSON API."""

from datetime import UTC, datetime

import httpx

BASE_URL = "https://api.lever.co/v0/postings/{slug}"


def fetch_jobs(ats_slug: str, client: httpx.Client | None = None) -> list[dict]:
    """Fetch every open posting for a Lever site and normalize it to the
    jobs table shape: external_id, title, location, url, description, posted_at, raw_json.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        resp = client.get(BASE_URL.format(slug=ats_slug), params={"mode": "json"})
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if owns_client:
            client.close()

    now = datetime.now(UTC).isoformat()
    jobs = []
    for raw in payload:
        created_at_ms = raw.get("createdAt")
        posted_at = (
            datetime.fromtimestamp(created_at_ms / 1000, tz=UTC).isoformat()
            if created_at_ms
            else None
        )
        categories = raw.get("categories") or {}
        jobs.append(
            {
                "external_id": str(raw["id"]),
                "title": raw.get("text", ""),
                "location": categories.get("location"),
                "url": raw.get("hostedUrl"),
                "description": raw.get("descriptionPlain") or raw.get("description"),
                "posted_at": posted_at,
                "first_seen_at": now,
                "raw_json": raw,
            }
        )
    return jobs
