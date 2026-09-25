import respx
from httpx import Response

from jobagent.sources.ashby import fetch_jobs

SAMPLE_RESPONSE = {
    "jobs": [
        {
            "id": "job-1",
            "title": "Data Analyst",
            "location": "Remote",
            "jobUrl": "https://jobs.ashbyhq.com/examplecorp/job-1",
            "descriptionPlain": "Job description here.",
            "publishedAt": "2026-01-01T00:00:00.000Z",
            "isListed": True,
        },
        {
            "id": "job-2",
            "title": "Unlisted role",
            "isListed": False,
        },
    ]
}


@respx.mock
def test_fetch_jobs_normalizes_and_skips_unlisted():
    respx.get("https://api.ashbyhq.com/posting-api/job-board/examplecorp").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    jobs = fetch_jobs("examplecorp")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["external_id"] == "job-1"
    assert job["title"] == "Data Analyst"
    assert job["location"] == "Remote"
    assert job["url"] == "https://jobs.ashbyhq.com/examplecorp/job-1"
    assert job["description"] == "Job description here."
    assert job["posted_at"] == "2026-01-01T00:00:00.000Z"
