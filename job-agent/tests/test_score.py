import json

from jobagent.nodes import score
from jobagent.nodes.score import FitAssessment
from jobagent.store.db import get_connection, init_db


class FakeLLM:
    def __init__(self, assessment: FitAssessment):
        self._assessment = assessment

    def with_structured_output(self, _model_cls):
        return self

    def invoke(self, _prompt):
        return self._assessment


def _fake_retrieve(_query, k=8):
    return ["Built SQL dashboards for sales reporting"]


def test_ineligible_job_never_calls_llm():
    def boom_llm(*_a, **_k):
        raise AssertionError("LLM should not be called for an ineligible job")

    result = score.run(
        {"title": "Software Engineer", "location": "Remote"},
        retrieve=_fake_retrieve,
        llm=boom_llm,
    )

    assert result["eligibility_ok"] is False
    assert result["fit_score"] == 0
    assert any("target title" in r for r in result["reasons"])


def test_eligible_job_uses_llm_assessment():
    fake_llm = FakeLLM(
        FitAssessment(fit_score=82, reasons=["Strong SQL match"], stretch_flag=False)
    )

    result = score.run(
        {"title": "Data Analyst", "location": "Remote", "description": "SQL, dashboards"},
        retrieve=_fake_retrieve,
        llm=fake_llm,
    )

    assert result["eligibility_ok"] is True
    assert result["fit_score"] == 82
    assert result["reasons"] == ["Strong SQL match"]
    assert result["stretch_flag"] is False


def test_run_batch_scores_unscored_jobs_only(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO companies (name, ats_type, ats_slug)
               VALUES ('Acme', 'greenhouse', 'acme')"""
        )
        conn.execute(
            """INSERT INTO jobs (company_id, external_id, title, location, first_seen_at)
               VALUES (1, '1', 'Data Analyst', 'Remote', '2026-01-01')"""
        )
        conn.execute(
            """INSERT INTO jobs (company_id, external_id, title, location, first_seen_at)
               VALUES (1, '2', 'Software Engineer', 'Remote', '2026-01-01')"""
        )

    fake_llm = FakeLLM(FitAssessment(fit_score=90, reasons=["Great fit"], stretch_flag=True))

    scored = score.run_batch(db_path=db_path, retrieve=_fake_retrieve, llm=fake_llm)
    assert scored == 2

    with get_connection(db_path) as conn:
        rows = {r["job_id"]: dict(r) for r in conn.execute("SELECT * FROM scores").fetchall()}

    assert rows[1]["eligibility_ok"] == 1
    assert rows[1]["fit_score"] == 90
    assert json.loads(rows[1]["reasons"]) == ["Great fit"]
    assert rows[2]["eligibility_ok"] == 0
    assert rows[2]["fit_score"] == 0

    # Re-running should not rescore already-scored jobs.
    scored_again = score.run_batch(db_path=db_path, retrieve=_fake_retrieve, llm=fake_llm)
    assert scored_again == 0
