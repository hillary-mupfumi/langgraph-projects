import respx
from httpx import Response

from jobagent.sources.lever import fetch_jobs

SAMPLE_RESPONSE = [
    {
        "id": "abc-123",
        "text": "Data Analyst",
        "categories": {"location": "Remote", "team": "Data", "commitment": "Full-time"},
        "hostedUrl": "https://jobs.lever.co/sampleinc/abc-123",
        "descriptionPlain": "Job description here.",
        "createdAt": 1767225600000,  # 2026-01-01T00:00:00Z
    }
]


@respx.mock
def test_fetch_jobs_normalizes_lever_response():
    respx.get("https://api.lever.co/v0/postings/sampleinc").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    jobs = fetch_jobs("sampleinc")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["external_id"] == "abc-123"
    assert job["title"] == "Data Analyst"
    assert job["location"] == "Remote"
    assert job["url"] == "https://jobs.lever.co/sampleinc/abc-123"
    assert job["description"] == "Job description here."
    assert job["posted_at"].startswith("2026-01-01")
    assert job["raw_json"]["id"] == "abc-123"


@respx.mock
def test_fetch_jobs_handles_missing_categories():
    respx.get("https://api.lever.co/v0/postings/sampleinc").mock(
        return_value=Response(200, json=[{"id": "1", "text": "No categories"}])
    )

    jobs = fetch_jobs("sampleinc")

    assert jobs[0]["location"] is None
    assert jobs[0]["posted_at"] is None
