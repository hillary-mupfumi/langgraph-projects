from types import SimpleNamespace

import jobagent.store.db as db
from jobagent import cli
from jobagent.store.db import get_connection, init_db


def _seed(db_path):
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO companies (name, ats_type, ats_slug) VALUES ('Acme', 'greenhouse', 'acme')"
        )
        conn.execute(
            """INSERT INTO jobs (company_id, external_id, title, first_seen_at)
               VALUES (1, '1', 'Data Analyst', '2026-01-01')"""
        )
        conn.execute(
            """INSERT INTO applications (job_id, status, submitted_at)
               VALUES (1, 'applied', '2026-09-21T00:00:00+00:00')"""
        )
        conn.execute(
            """INSERT INTO contacts (company_id, name, title)
               VALUES (1, 'Alex Recruiter', 'Recruiter')"""
        )
        conn.execute(
            """INSERT INTO outreach (application_id, contact_id, channel, draft, status)
               VALUES (1, 1, 'linkedin', 'hi', 'drafted')"""
        )


def test_mark_sent_sets_sent_at_and_status(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed(db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)

    cli.cmd_mark_sent(SimpleNamespace(outreach_id=1))

    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM outreach WHERE id = 1").fetchone()
    assert row["status"] == "sent"
    assert row["sent_at"] is not None


def test_mark_replied_sets_replied_at_and_status(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed(db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)

    cli.cmd_mark_sent(SimpleNamespace(outreach_id=1))
    cli.cmd_mark_replied(SimpleNamespace(outreach_id=1))

    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM outreach WHERE id = 1").fetchone()
    assert row["status"] == "replied"
    assert row["replied_at"] is not None


def test_metrics_prints_week_and_response_rate(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed(db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    cli.cmd_mark_sent(SimpleNamespace(outreach_id=1))

    cli.cmd_metrics(SimpleNamespace())

    out = capsys.readouterr().out
    assert "Applications per week" in out
    assert "2026-W39" in out  # 2026-09-21 falls in ISO week 39
    assert "linkedin: 0/1 replied" in out


def test_daily_writes_shortlist_log_and_skips_email_when_unconfigured(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr("jobagent.config.ROOT", tmp_path)

    import jobagent.nodes.ingest as ingest_mod
    import jobagent.nodes.score as score_mod

    monkeypatch.setattr(
        ingest_mod,
        "run",
        lambda: {"companies_processed": 0, "companies_failed": 0, "jobs_seen": 0, "new_jobs": 0},
    )
    monkeypatch.setattr(score_mod, "run_batch", lambda: 0)
    for var in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_EMAIL_TO"]:
        monkeypatch.delenv(var, raising=False)

    cli.cmd_daily(SimpleNamespace())

    from datetime import date

    log_path = tmp_path / "data" / "shortlists" / f"{date.today().isoformat()}.txt"
    assert log_path.exists()
