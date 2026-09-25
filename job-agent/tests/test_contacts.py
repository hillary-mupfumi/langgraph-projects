import json

import pytest
import respx
from httpx import Response

from jobagent.nodes import contacts

SAMPLE_PEOPLE = [
    {
        "name": "Alex Recruiter",
        "title": "Technical Recruiter",
        "linkedin_url": "https://linkedin.com/in/alexrecruiter",
        "employment_history": [{"organization_name": "Acme"}],
    },
    {
        "name": "Sam Manager",
        "title": "Data Analytics Manager",
        "linkedin_url": "https://linkedin.com/in/sammanager",
        "employment_history": [{"organization_name": "Some Other Co"}],
    },
]

SAMPLE_PROFILE = {"roles": [{"company": "Acme"}]}


@pytest.fixture
def profile_path(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(SAMPLE_PROFILE))
    return path


@respx.mock
def test_run_returns_normalized_contacts_with_warm_path_flagged(profile_path):
    respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
        return_value=Response(200, json={"people": SAMPLE_PEOPLE})
    )

    state = {"job": {"company_name": "Acme", "title": "Data Analyst"}}
    result = contacts.run(state, api_key="fake-key", profile_path=profile_path)

    assert len(result["contacts"]) == 2
    assert result["contacts"][0]["name"] == "Alex Recruiter"
    assert result["contacts"][0]["relation"] == "shared employer: acme"
    assert result["contacts"][1]["relation"] is None


@respx.mock
def test_run_marks_manual_review_on_apollo_403():
    respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
        return_value=Response(
            403, json={"error": "not included in your Free plan", "error_code": "API_INACCESSIBLE"}
        )
    )

    state = {"job": {"company_name": "Acme"}}
    result = contacts.run(state, api_key="fake-key")

    assert result["contacts"] == []
    assert result["manual_review"] is True
    assert any("403" in item for item in result["unmapped_fields"])


def test_run_marks_manual_review_when_no_api_key(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    state = {"job": {"company_name": "Acme"}}
    result = contacts.run(
        state, api_key=None, search=lambda *a: (_ for _ in ()).throw(AssertionError)
    )

    assert result["manual_review"] is True
    assert "APOLLO_API_KEY" in result["unmapped_fields"][0]


def test_run_marks_manual_review_when_no_company_name():
    state = {"job": {}}
    result = contacts.run(state, api_key="fake-key")

    assert result["manual_review"] is True
    assert "company name" in result["unmapped_fields"][0]
