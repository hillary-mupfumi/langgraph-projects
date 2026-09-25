import sqlite3
from contextlib import contextmanager

from jobagent.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ats_type TEXT NOT NULL,
    ats_slug TEXT NOT NULL,
    notes TEXT,
    UNIQUE (ats_type, ats_slug)
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    url TEXT,
    description TEXT,
    posted_at TEXT,
    first_seen_at TEXT NOT NULL,
    raw_json TEXT,
    UNIQUE (company_id, external_id)
);

CREATE TABLE IF NOT EXISTS scores (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
    fit_score INTEGER NOT NULL,
    eligibility_ok INTEGER NOT NULL,
    reasons TEXT,
    stretch_flag INTEGER NOT NULL DEFAULT 0,
    scored_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    status TEXT NOT NULL,
    resume_path TEXT,
    cover_letter_path TEXT,
    resume_variant TEXT,
    submitted_at TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name TEXT NOT NULL,
    title TEXT,
    source TEXT,
    url TEXT,
    relation TEXT
);

CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    channel TEXT NOT NULL,
    draft TEXT,
    status TEXT NOT NULL,
    sent_at TEXT,
    replied_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES jobs(id),
    type TEXT NOT NULL,
    detail TEXT,
    at TEXT NOT NULL
);
"""


def init_db(db_path=None) -> None:
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_connection(db_path=None):
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_job_with_company(job_id: int, db_path=None) -> dict | None:
    """A job row joined with its company's ats_type/name -- what apply.py needs
    to pick the right form filler, and what the Streamlit queue shows a human.
    """
    with get_connection(db_path) as conn:
        row = conn.execute(
            """SELECT j.*, c.name AS company_name, c.ats_type
               FROM jobs j JOIN companies c ON c.id = j.company_id
               WHERE j.id = ?""",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def list_scored_jobs(db_path=None) -> list[dict]:
    """Every job with a score, joined with company info, ranked like `shortlist`."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT j.*, c.name AS company_name, c.ats_type,
                      s.fit_score, s.eligibility_ok, s.reasons, s.stretch_flag
               FROM jobs j
               JOIN companies c ON c.id = j.company_id
               JOIN scores s ON s.job_id = j.id
               WHERE s.eligibility_ok = 1
               ORDER BY s.fit_score DESC"""
        ).fetchall()
    return [dict(r) for r in rows]
