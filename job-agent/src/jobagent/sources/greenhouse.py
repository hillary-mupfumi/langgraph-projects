"""Greenhouse job board client. Public, no-auth JSON API."""

from datetime import UTC, datetime

import httpx

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def fetch_jobs(ats_slug: str, client: httpx.Client | None = None) -> list[dict]:
    """Fetch every open posting for a Greenhouse board and normalize it to the
    jobs table shape: external_id, title, location, url, description, posted_at, raw_json.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        resp = client.get(BASE_URL.format(slug=ats_slug), params={"content": "true"})
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if owns_client:
            client.close()

    now = datetime.now(UTC).isoformat()
    jobs = []
    for raw in payload.get("jobs", []):
        jobs.append(
            {
                "external_id": str(raw["id"]),
                "title": raw.get("title", ""),
                "location": (raw.get("location") or {}).get("name"),
                "url": raw.get("absolute_url"),
                "description": raw.get("content"),
                "posted_at": raw.get("updated_at"),
                "first_seen_at": now,
                "raw_json": raw,
            }
        )
    return jobs
