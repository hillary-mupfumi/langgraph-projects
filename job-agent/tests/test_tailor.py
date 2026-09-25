import json

import pytest

from jobagent.nodes import tailor
from jobagent.nodes.tailor import TailoredBullet, TailoredResume, TailorOutput

SAMPLE_PROFILE = {
    "name": "Test Candidate",
    "roles": [
        {
            "id": "role-1",
            "title": "Data Analyst",
            "company": "Acme",
            "start": "2023-01",
            "bullets": [
                {"id": "b1", "text": "Built SQL dashboards for sales reporting", "tags": ["sql"]},
            ],
            "tags": [],
        }
    ],
    "projects": [],
    "skills": [],
    "education": [],
}


class FakeLLM:
    def __init__(self, output: TailorOutput):
        self._output = output
        self.last_prompt = None

    def with_structured_output(self, _model_cls):
        return self

    def invoke(self, prompt):
        self.last_prompt = prompt
        return self._output


@pytest.fixture
def profile_path(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(SAMPLE_PROFILE))
    return path


def _fake_retrieve(_query, k=10):
    return ["Built SQL dashboards for sales reporting"]


def test_run_returns_resume_and_cover_letter(profile_path):
    output = TailorOutput(
        resume=TailoredResume(
            summary="Data analyst with SQL experience.",
            bullets=[TailoredBullet(source_id="b1", text="Built SQL dashboards for reporting")],
            skills=["SQL"],
        ),
        cover_letter="I would be a strong fit for this role.",
    )
    fake_llm = FakeLLM(output)

    state = {"job": {"title": "Data Analyst", "description": "Looking for a SQL expert"}}
    result = tailor.run(state, retrieve=_fake_retrieve, llm=fake_llm, profile_path=profile_path)

    assert result["tailored_resume"]["bullets"][0]["source_id"] == "b1"
    assert result["cover_letter"] == "I would be a strong fit for this role."
    assert result["resume_variant"]  # some variant chosen


def test_run_includes_prior_validation_feedback_in_prompt(profile_path):
    output = TailorOutput(resume=TailoredResume(summary="", bullets=[], skills=[]), cover_letter="")
    fake_llm = FakeLLM(output)

    state = {
        "job": {"title": "Data Analyst", "description": "..."},
        "validation": {"ok": False, "errors": ["Found an em dash"]},
    }
    tailor.run(state, retrieve=_fake_retrieve, llm=fake_llm, profile_path=profile_path)

    assert "Found an em dash" in fake_llm.last_prompt


def test_variant_selection_matches_job_title():
    from jobagent.config import Rules, StyleRules

    rules = Rules(
        resume_variants=[
            {"id": "data-analytics", "label": "Data Analytics"},
            {"id": "sap-abap", "label": "SAP ABAP"},
        ],
        style=StyleRules(),
    )

    variant = tailor._pick_variant({"title": "SAP ABAP Developer"}, rules)
    assert variant == "sap-abap"

    variant = tailor._pick_variant({"title": "Data Analyst"}, rules)
    assert variant == "data-analytics"
