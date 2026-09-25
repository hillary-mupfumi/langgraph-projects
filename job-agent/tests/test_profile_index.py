import json

import pytest

from jobagent.profile_index import build_index, retrieve

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
                {"id": "b2", "text": "Automated ETL pipelines in Python", "tags": ["python"]},
            ],
            "tags": ["analytics"],
        }
    ],
    "projects": [
        {"id": "p1", "name": "Job tracker", "description": "A LangGraph job app", "tags": ["ai"]}
    ],
    "skills": [{"id": "s1", "name": "Python", "category": "language"}],
    "education": [],
}


@pytest.fixture
def profile_path(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(SAMPLE_PROFILE))
    return path


def test_build_index_and_retrieve(tmp_path, profile_path):
    persist_dir = tmp_path / "chroma"

    count = build_index(profile_path=profile_path, persist_dir=persist_dir)
    assert count == 4  # 2 bullets + 1 project + 1 skill

    results = retrieve("SQL dashboards and reporting", k=2, persist_dir=persist_dir)
    assert len(results) == 2
    assert any("SQL dashboards" in r for r in results)


def test_build_index_missing_profile_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_index(profile_path=tmp_path / "does-not-exist.json", persist_dir=tmp_path / "chroma")


def test_retrieve_before_build_raises(tmp_path):
    with pytest.raises(RuntimeError):
        retrieve("anything", persist_dir=tmp_path / "chroma")
