import json

import pytest

from jobagent.nodes import validate
from jobagent.nodes.validate import CriticVerdict

SAMPLE_PROFILE = {
    "name": "Test Candidate",
    "roles": [
        {
            "id": "role-1",
            "title": "Data Analyst",
            "company": "Acme",
            "start": "2023-01",
            "bullets": [
                {"id": "b1", "text": "Built SQL dashboards for sales reporting", "tags": []},
            ],
            "tags": [],
        }
    ],
    "projects": [],
    "skills": [],
    "education": [],
}


class FakeLLM:
    def __init__(self, verdict: CriticVerdict):
        self._verdict = verdict

    def with_structured_output(self, _model_cls):
        return self

    def invoke(self, _prompt):
        return self._verdict


def _boom_llm(*_a, **_k):
    raise AssertionError("critic LLM should not be called when deterministic checks fail")


@pytest.fixture
def profile_path(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(SAMPLE_PROFILE))
    return path


def test_em_dash_fails_without_calling_llm(profile_path):
    state = {
        "tailored_resume": {"bullets": [{"source_id": "b1", "text": "Built dashboards—fast"}]},
        "cover_letter": "",
    }

    result = validate.run(state, profile_path=profile_path, llm=_boom_llm)

    assert result["validation"]["ok"] is False
    assert any("em or en dash" in e for e in result["validation"]["errors"])
    assert result["validation_attempts"] == 1


def test_unknown_source_id_fails_without_calling_llm(profile_path):
    state = {
        "tailored_resume": {"bullets": [{"source_id": "does-not-exist", "text": "Something"}]},
        "cover_letter": "",
    }

    result = validate.run(state, profile_path=profile_path, llm=_boom_llm)

    assert result["validation"]["ok"] is False
    assert any("does-not-exist" in e for e in result["validation"]["errors"])


def test_too_long_fails_without_calling_llm(profile_path):
    long_text = "word " * 600
    state = {
        "tailored_resume": {"bullets": [{"source_id": "b1", "text": long_text}]},
        "cover_letter": "",
    }

    result = validate.run(state, profile_path=profile_path, llm=_boom_llm)

    assert result["validation"]["ok"] is False
    assert any("too long" in e for e in result["validation"]["errors"])


def test_clean_resume_passes_deterministic_and_calls_critic(profile_path):
    state = {
        "tailored_resume": {
            "bullets": [{"source_id": "b1", "text": "Built SQL dashboards for reporting"}]
        },
        "cover_letter": "I am excited to apply.",
    }
    fake_llm = FakeLLM(CriticVerdict(ok=True, issues=[]))

    result = validate.run(state, profile_path=profile_path, llm=fake_llm)

    assert result["validation"]["ok"] is True
    assert result["validation"]["errors"] == []


def test_critic_can_still_fail_a_deterministically_clean_resume(profile_path):
    state = {
        "tailored_resume": {
            "bullets": [{"source_id": "b1", "text": "Built SQL dashboards for reporting"}]
        },
        "cover_letter": "I led a team of 50 engineers.",
    }
    fake_llm = FakeLLM(CriticVerdict(ok=False, issues=["'team of 50' isn't in the original facts"]))

    result = validate.run(state, profile_path=profile_path, llm=fake_llm)

    assert result["validation"]["ok"] is False
    assert "team of 50" in result["validation"]["errors"][0]


def test_validation_attempts_increments_across_calls(profile_path):
    state = {"tailored_resume": {"bullets": []}, "cover_letter": ""}
    fake_llm = FakeLLM(CriticVerdict(ok=True, issues=[]))

    result1 = validate.run(state, profile_path=profile_path, llm=fake_llm)
    assert result1["validation_attempts"] == 1

    state.update(result1)
    result2 = validate.run(state, profile_path=profile_path, llm=fake_llm)
    assert result2["validation_attempts"] == 2
