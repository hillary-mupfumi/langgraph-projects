"""Phase 2 acceptance (PLAN.md section 7): style rules (no em/en dash, one
page, every claim traceable to profile.json) must actually be caught. Unlike
evals/test_scoring_agreement.py and test_tailoring_truthfulness.py, this one
runs for free and needs no golden data -- validate.py's deterministic checks
don't call an LLM, so there's nothing to skip.
"""

import json

import pytest

from jobagent.nodes.validate import _deterministic_checks


@pytest.fixture
def known_bullets():
    return {"b1": "Built SQL dashboards"}


def test_catches_em_dash(known_bullets):
    state = {
        "tailored_resume": {"bullets": [{"source_id": "b1", "text": "Built SQL—dashboards"}]},
        "cover_letter": "",
    }
    errors = _deterministic_checks(state, known_bullets)
    assert any("em or en dash" in e for e in errors)


def test_catches_en_dash(known_bullets):
    state = {
        "tailored_resume": {"bullets": [{"source_id": "b1", "text": "Built SQL–dashboards"}]},
        "cover_letter": "",
    }
    errors = _deterministic_checks(state, known_bullets)
    assert any("em or en dash" in e for e in errors)


def test_catches_unsourced_bullet(known_bullets):
    state = {
        "tailored_resume": {"bullets": [{"source_id": "does-not-exist", "text": "Invented fact"}]},
        "cover_letter": "",
    }
    errors = _deterministic_checks(state, known_bullets)
    assert any("does-not-exist" in e for e in errors)


def test_catches_over_length(known_bullets):
    state = {
        "tailored_resume": {"bullets": [{"source_id": "b1", "text": "word " * 600}]},
        "cover_letter": "",
    }
    errors = _deterministic_checks(state, known_bullets)
    assert any("too long" in e for e in errors)


def test_clean_resume_passes(known_bullets):
    state = {
        "tailored_resume": {"bullets": [{"source_id": "b1", "text": "Built SQL dashboards"}]},
        "cover_letter": "A short, clean cover letter.",
    }
    assert _deterministic_checks(state, known_bullets) == []


def test_profile_schema_is_valid_json():
    from jobagent.config import PROFILE_DIR

    with open(PROFILE_DIR / "profile.schema.json") as f:
        schema = json.load(f)
    assert schema["type"] == "object"
    assert "roles" in schema["properties"]
