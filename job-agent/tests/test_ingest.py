import jobagent.nodes.ingest as ingest
from jobagent.store.db import get_connection, init_db


def _fake_greenhouse(slug):
    return [
        {
            "external_id": "1",
            "title": "Data Analyst",
            "location": "Remote",
            "url": "https://example.com/1",
            "description": "desc",
            "posted_at": "2026-01-01T00:00:00Z",
            "first_seen_at": "2026-01-02T00:00:00Z",
            "raw_json": {"id": 1},
        }
    ]


def test_run_ingests_and_dedupes(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    monkeypatch.setattr(
        ingest,
        "load_companies",
        lambda: [{"name": "Example Corp", "ats_type": "greenhouse", "ats_slug": "examplecorp"}],
    )
    monkeypatch.setitem(ingest.SOURCES, "greenhouse", _fake_greenhouse)

    summary = ingest.run(db_path=db_path)

    assert summary == {
        "companies_processed": 1,
        "companies_failed": 0,
        "jobs_seen": 1,
        "new_jobs": 1,
    }

    with get_connection(db_path) as conn:
        jobs = conn.execute("SELECT * FROM jobs").fetchall()
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Data Analyst"

    # Running again should update, not duplicate.
    summary2 = ingest.run(db_path=db_path)
    assert summary2["new_jobs"] == 0
    assert summary2["jobs_seen"] == 1
    with get_connection(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"] == 1


def test_run_skips_unsupported_ats_type(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    monkeypatch.setattr(
        ingest,
        "load_companies",
        lambda: [{"name": "Manual Co", "ats_type": "manual", "ats_slug": "n/a"}],
    )

    summary = ingest.run(db_path=db_path)

    assert summary["companies_processed"] == 0
    with get_connection(db_path) as conn:
        events = conn.execute("SELECT * FROM events WHERE type='ingest_skipped'").fetchall()
        assert len(events) == 1


def test_run_continues_after_one_company_fails(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    monkeypatch.setattr(
        ingest,
        "load_companies",
        lambda: [
            {"name": "Broken Co", "ats_type": "greenhouse", "ats_slug": "broken"},
            {"name": "Example Corp", "ats_type": "greenhouse", "ats_slug": "examplecorp"},
        ],
    )

    def flaky(slug):
        if slug == "broken":
            raise RuntimeError("boom")
        return _fake_greenhouse(slug)

    monkeypatch.setitem(ingest.SOURCES, "greenhouse", flaky)

    summary = ingest.run(db_path=db_path)

    assert summary["companies_failed"] == 1
    assert summary["companies_processed"] == 1
    assert summary["new_jobs"] == 1
