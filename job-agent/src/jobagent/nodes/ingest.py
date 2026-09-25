"""Daily batch node: pull jobs from every configured source, normalize, dedupe.

Runs once per day over all companies in profile/companies.yaml, not per-thread.
One company's failure (a source API being down, an unknown ats_type) is logged
to the events table and skipped, rather than aborting the whole run.
"""

import json
from datetime import UTC, datetime

from jobagent.config import load_companies
from jobagent.sources import ashby, greenhouse, lever
from jobagent.store.db import get_connection

SOURCES = {
    "greenhouse": greenhouse.fetch_jobs,
    "lever": lever.fetch_jobs,
    "ashby": ashby.fetch_jobs,
}


def _log_event(conn, job_id, type_, detail):
    conn.execute(
        "INSERT INTO events (job_id, type, detail, at) VALUES (?, ?, ?, ?)",
        (job_id, type_, detail, datetime.now(UTC).isoformat()),
    )


def _get_or_create_company(conn, name: str, ats_type: str, ats_slug: str, notes: str | None) -> int:
    row = conn.execute(
        "SELECT id FROM companies WHERE ats_type = ? AND ats_slug = ?",
        (ats_type, ats_slug),
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO companies (name, ats_type, ats_slug, notes) VALUES (?, ?, ?, ?)",
        (name, ats_type, ats_slug, notes),
    )
    return cur.lastrowid


def _upsert_job(conn, company_id: int, job: dict) -> bool:
    """Insert a job, or update its mutable fields if already seen. Returns True if new."""
    existing = conn.execute(
        "SELECT id FROM jobs WHERE company_id = ? AND external_id = ?",
        (company_id, job["external_id"]),
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE jobs SET title = ?, location = ?, url = ?, description = ?,
               posted_at = ?, raw_json = ? WHERE id = ?""",
            (
                job["title"],
                job["location"],
                job["url"],
                job["description"],
                job["posted_at"],
                json.dumps(job["raw_json"]),
                existing["id"],
            ),
        )
        return False

    conn.execute(
        """INSERT INTO jobs
           (company_id, external_id, title, location, url, description, posted_at,
            first_seen_at, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            company_id,
            job["external_id"],
            job["title"],
            job["location"],
            job["url"],
            job["description"],
            job["posted_at"],
            job["first_seen_at"],
            json.dumps(job["raw_json"]),
        ),
    )
    return True


def run(db_path=None) -> dict:
    """Fetch every configured company's postings and upsert them. Returns a summary."""
    summary = {"companies_processed": 0, "companies_failed": 0, "jobs_seen": 0, "new_jobs": 0}

    with get_connection(db_path) as conn:
        for company in load_companies():
            ats_type = company.get("ats_type")
            fetch = SOURCES.get(ats_type)
            if fetch is None:
                _log_event(
                    conn,
                    None,
                    "ingest_skipped",
                    f"{company.get('name')}: unsupported or manual ats_type '{ats_type}'",
                )
                continue

            try:
                jobs = fetch(company["ats_slug"])
            except Exception as exc:  # noqa: BLE001 -- one bad company shouldn't stop the batch
                summary["companies_failed"] += 1
                _log_event(conn, None, "ingest_error", f"{company.get('name')}: {exc}")
                continue

            company_id = _get_or_create_company(
                conn, company["name"], ats_type, company["ats_slug"], company.get("notes")
            )
            for job in jobs:
                is_new = _upsert_job(conn, company_id, job)
                summary["jobs_seen"] += 1
                if is_new:
                    summary["new_jobs"] += 1

            summary["companies_processed"] += 1

    return summary
