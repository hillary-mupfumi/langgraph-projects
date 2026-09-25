import sqlite3

from jobagent.store.db import get_connection, get_job_with_company, init_db, list_scored_jobs

EXPECTED_TABLES = {
    "companies",
    "jobs",
    "scores",
    "applications",
    "contacts",
    "outreach",
    "events",
}


def test_init_db_creates_expected_tables(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {row["name"] for row in rows}

    assert EXPECTED_TABLES <= table_names


def test_events_row_requires_type(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    with get_connection(db_path) as conn:
        try:
            conn.execute("INSERT INTO events (job_id, at) VALUES (NULL, '2026-01-01')")
            conn.commit()
            raised = False
        except sqlite3.IntegrityError:
            raised = True

    assert raised


def _seed_job_and_score(db_path, eligible=True):
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO companies (name, ats_type, ats_slug) VALUES ('Acme', 'greenhouse', 'acme')"
        )
        conn.execute(
            """INSERT INTO jobs (company_id, external_id, title, url, first_seen_at)
               VALUES (1, '1', 'Data Analyst', 'https://example.com/1', '2026-01-01')"""
        )
        conn.execute(
            """INSERT INTO scores
               (job_id, fit_score, eligibility_ok, reasons, stretch_flag, scored_at)
               VALUES (1, 90, ?, '[]', 0, '2026-01-01')""",
            (1 if eligible else 0,),
        )


def test_get_job_with_company_joins_ats_type(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_job_and_score(db_path)

    job = get_job_with_company(1, db_path=db_path)

    assert job["title"] == "Data Analyst"
    assert job["ats_type"] == "greenhouse"
    assert job["company_name"] == "Acme"


def test_get_job_with_company_returns_none_for_missing_job(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    assert get_job_with_company(999, db_path=db_path) is None


def test_list_scored_jobs_excludes_ineligible(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_job_and_score(db_path, eligible=False)

    assert list_scored_jobs(db_path=db_path) == []
