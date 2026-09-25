"""Final node: writes the application (and any outreach) to SQLite, schedules
a follow-up reminder 5-7 days out, and logs both as events. Every agent action
is logged to the events table (CLAUDE.md hard rule) -- this is the node that
makes that true for the whole per-job run, not just this step.
"""

from datetime import UTC, datetime, timedelta

from jobagent.state import JobState
from jobagent.store.db import get_connection

FOLLOW_UP_DAYS = 6  # middle of PLAN.md's "5 to 7 days" window


def _log_event(conn, job_id, type_, detail) -> None:
    conn.execute(
        "INSERT INTO events (job_id, type, detail, at) VALUES (?, ?, ?, ?)",
        (job_id, type_, detail, datetime.now(UTC).isoformat()),
    )


def run(state: JobState, db_path=None) -> dict:
    job = state["job"]
    job_id = job["id"]
    now = datetime.now(UTC)
    outreach_drafts = state.get("outreach_drafts") or []
    status = "outreach_drafted" if outreach_drafts else "applied"

    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO applications
               (job_id, status, resume_path, cover_letter_path, resume_variant, submitted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                status,
                state.get("resume_path"),
                state.get("cover_letter_path"),
                state.get("resume_variant"),
                now.isoformat(),
            ),
        )
        application_id = cur.lastrowid

        contact_ids: dict[str, int] = {}
        for contact in state.get("contacts") or []:
            cur = conn.execute(
                """INSERT INTO contacts (company_id, name, title, source, url, relation)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    job["company_id"],
                    contact.get("name"),
                    contact.get("title"),
                    contact.get("source"),
                    contact.get("url"),
                    contact.get("relation"),
                ),
            )
            contact_ids[contact.get("name")] = cur.lastrowid

        for draft in outreach_drafts:
            contact_id = contact_ids.get(draft.get("contact_name"))
            if contact_id is None:
                continue
            conn.execute(
                """INSERT INTO outreach (application_id, contact_id, channel, draft, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    application_id,
                    contact_id,
                    draft.get("channel", "linkedin"),
                    draft.get("connection_note"),
                    "drafted",
                ),
            )

        _log_event(conn, job_id, "application_tracked", f"status={status}")
        follow_up_at = (now + timedelta(days=FOLLOW_UP_DAYS)).date().isoformat()
        _log_event(conn, job_id, "follow_up_scheduled", follow_up_at)

    return {"status": status, "application_id": application_id, "follow_up_at": follow_up_at}
