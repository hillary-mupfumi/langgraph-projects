import respx
from httpx import Response

from jobagent.sources.greenhouse import fetch_jobs

SAMPLE_RESPONSE = {
    "jobs": [
        {
            "id": 12345,
            "title": "Data Analyst",
            "updated_at": "2026-09-01T12:00:00-04:00",
            "location": {"name": "Remote"},
            "absolute_url": "https://boards.greenhouse.io/examplecorp/jobs/12345",
            "content": "<p>Job description here.</p>",
        },
        {
            "id": 67890,
            "title": "Business Analyst",
            "updated_at": "2026-09-02T12:00:00-04:00",
            "location": {"name": "New York, NY"},
            "absolute_url": "https://boards.greenhouse.io/examplecorp/jobs/67890",
            "content": "<p>Another job.</p>",
        },
    ]
}


@respx.mock
def test_fetch_jobs_normalizes_greenhouse_response():
    respx.get("https://boards-api.greenhouse.io/v1/boards/examplecorp/jobs").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    jobs = fetch_jobs("examplecorp")

    assert len(jobs) == 2
    first = jobs[0]
    assert first["external_id"] == "12345"
    assert first["title"] == "Data Analyst"
    assert first["location"] == "Remote"
    assert first["url"] == "https://boards.greenhouse.io/examplecorp/jobs/12345"
    assert first["description"] == "<p>Job description here.</p>"
    assert first["posted_at"] == "2026-09-01T12:00:00-04:00"
    assert "first_seen_at" in first
    assert first["raw_json"]["id"] == 12345


@respx.mock
def test_fetch_jobs_handles_missing_location():
    respx.get("https://boards-api.greenhouse.io/v1/boards/examplecorp/jobs").mock(
        return_value=Response(200, json={"jobs": [{"id": 1, "title": "No location"}]})
    )

    jobs = fetch_jobs("examplecorp")

    assert jobs[0]["location"] is None
