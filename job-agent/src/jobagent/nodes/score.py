"""Daily batch node: embed + compare each job to the profile, then an LLM pass
produces fit_score (0-100), reasons, and a stretch flag. Hard-filter failures
from rules.yaml get eligibility_ok=false with the reason, never silently dropped
(so a rejected job is still visible on the shortlist as "filtered, reason X").
"""

import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from jobagent import profile_index
from jobagent.config import load_rules
from jobagent.state import Score
from jobagent.store.db import get_connection


class FitAssessment(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    reasons: list[str]
    stretch_flag: bool


def _check_eligibility(job: dict, rules) -> tuple[bool, list[str]]:
    reasons = []
    title = (job.get("title") or "").lower()

    if rules.target_titles and not any(t.lower() in title for t in rules.target_titles):
        reasons.append(f"title '{job.get('title')}' doesn't match any target title")

    locations = rules.locations or {}
    allow = locations.get("allow") or []
    deny = locations.get("deny") or []
    loc = (job.get("location") or "").lower()

    if deny and any(d.lower() in loc for d in deny):
        reasons.append(f"location '{job.get('location')}' is on the deny list")
    if allow and not any(a.lower() in loc for a in allow):
        reasons.append(f"location '{job.get('location')}' not on the allow list")

    return (len(reasons) == 0, reasons)


def _default_llm():
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model="claude-haiku-4-5-20251001")


def _score_with_llm(llm, job: dict, snippets: list[str]) -> FitAssessment:
    structured_llm = llm.with_structured_output(FitAssessment)
    profile_text = "\n".join(f"- {s}" for s in snippets) or "(no relevant facts found)"
    prompt = (
        "Score how well this job posting fits the candidate, using ONLY the candidate "
        "facts listed below. Never assume a fact that isn't listed.\n\n"
        f"Candidate facts:\n{profile_text}\n\n"
        f"Job title: {job.get('title')}\n"
        f"Job description:\n{job.get('description') or '(none provided)'}\n\n"
        "Give a fit_score from 0 to 100, a short list of one-line reasons for that score, "
        "and stretch_flag=true if this role is a step above the candidate's demonstrated "
        "level but still worth applying to."
    )
    return structured_llm.invoke(prompt)


def run(job: dict, retrieve=None, llm=None) -> Score:
    """Score a single job dict (as returned by a sources/* client or a jobs table row)."""
    rules = load_rules()
    eligible, reasons = _check_eligibility(job, rules)
    if not eligible:
        return Score(fit_score=0, eligibility_ok=False, reasons=reasons, stretch_flag=False)

    retrieve = retrieve or profile_index.retrieve
    llm = llm or _default_llm()

    query = job.get("description") or job.get("title") or ""
    snippets = retrieve(query, k=8)
    assessment = _score_with_llm(llm, job, snippets)

    return Score(
        fit_score=assessment.fit_score,
        eligibility_ok=True,
        reasons=assessment.reasons,
        stretch_flag=assessment.stretch_flag,
    )


def run_batch(db_path=None, retrieve=None, llm=None) -> int:
    """Score every job that doesn't have a score row yet. Returns the count scored."""
    count = 0
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE id NOT IN (SELECT job_id FROM scores)"
        ).fetchall()
        for row in rows:
            job = dict(row)
            result = run(job, retrieve=retrieve, llm=llm)
            conn.execute(
                """INSERT INTO scores
                   (job_id, fit_score, eligibility_ok, reasons, stretch_flag, scored_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    job["id"],
                    result["fit_score"],
                    int(result["eligibility_ok"]),
                    json.dumps(result["reasons"]),
                    int(result["stretch_flag"]),
                    datetime.now(UTC).isoformat(),
                ),
            )
            count += 1
    return count
