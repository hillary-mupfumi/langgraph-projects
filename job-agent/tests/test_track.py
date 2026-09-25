from jobagent.nodes import track
from jobagent.store.db import get_connection, init_db


def _seed_job(db_path):
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO companies (name, ats_type, ats_slug) VALUES ('Acme', 'greenhouse', 'acme')"
        )
        conn.execute(
            """INSERT INTO jobs (company_id, external_id, title, first_seen_at)
               VALUES (1, '1', 'Data Analyst', '2026-01-01')"""
        )
    return {"id": 1, "company_id": 1, "title": "Data Analyst"}


def test_run_writes_application_with_no_outreach(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    job = _seed_job(db_path)

    state = {
        "job": job,
        "resume_path": "resume.docx",
        "cover_letter_path": "cl.docx",
        "resume_variant": "data-analytics",
        "contacts": [],
        "outreach_drafts": [],
    }

    result = track.run(state, db_path=db_path)

    assert result["status"] == "applied"
    assert result["follow_up_at"]

    with get_connection(db_path) as conn:
        apps = conn.execute("SELECT * FROM applications").fetchall()
        assert len(apps) == 1
        assert apps[0]["status"] == "applied"
        assert apps[0]["resume_path"] == "resume.docx"

        events = {e["type"] for e in conn.execute("SELECT * FROM events").fetchall()}
        assert "application_tracked" in events
        assert "follow_up_scheduled" in events


def test_run_writes_contacts_and_outreach(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    job = _seed_job(db_path)

    state = {
        "job": job,
        "contacts": [
            {
                "name": "Alex Recruiter",
                "title": "Recruiter",
                "source": "apollo",
                "url": "u",
                "relation": None,
            }
        ],
        "outreach_drafts": [
            {
                "contact_name": "Alex Recruiter",
                "channel": "linkedin",
                "connection_note": "Hi Alex...",
            }
        ],
    }

    result = track.run(state, db_path=db_path)
    assert result["status"] == "outreach_drafted"

    with get_connection(db_path) as conn:
        contacts_rows = conn.execute("SELECT * FROM contacts").fetchall()
        assert len(contacts_rows) == 1
        assert contacts_rows[0]["name"] == "Alex Recruiter"

        outreach_rows = conn.execute("SELECT * FROM outreach").fetchall()
        assert len(outreach_rows) == 1
        assert outreach_rows[0]["draft"] == "Hi Alex..."
        assert outreach_rows[0]["status"] == "drafted"


def test_run_skips_outreach_for_unmatched_contact_name(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    job = _seed_job(db_path)

    state = {
        "job": job,
        "contacts": [{"name": "Alex Recruiter", "title": "Recruiter"}],
        "outreach_drafts": [{"contact_name": "Someone Else", "connection_note": "..."}],
    }

    track.run(state, db_path=db_path)

    with get_connection(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM outreach").fetchone()["c"] == 0
