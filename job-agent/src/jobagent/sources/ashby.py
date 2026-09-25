"""Ashby job board client. Public, no-auth JSON API."""

from datetime import UTC, datetime

import httpx

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch_jobs(ats_slug: str, client: httpx.Client | None = None) -> list[dict]:
    """Fetch every listed posting for an Ashby board and normalize it to the
    jobs table shape: external_id, title, location, url, description, posted_at, raw_json.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        resp = client.get(BASE_URL.format(slug=ats_slug), params={"includeCompensation": "false"})
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if owns_client:
            client.close()

    now = datetime.now(UTC).isoformat()
    jobs = []
    for raw in payload.get("jobs", []):
        if raw.get("isListed") is False:
            continue
        jobs.append(
            {
                "external_id": str(raw["id"]),
                "title": raw.get("title", ""),
                "location": raw.get("location"),
                "url": raw.get("jobUrl"),
                "description": raw.get("descriptionPlain") or raw.get("descriptionHtml"),
                "posted_at": raw.get("publishedAt"),
                "first_seen_at": now,
                "raw_json": raw,
            }
        )
    return jobs
