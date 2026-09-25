"""Find hiring manager, recruiter and peer contacts at the company via the
Apollo REST API.

CLAUDE.md's original amendment assumed the Apollo MCP connector available in
a Claude Code session would also be reachable at runtime by this standalone
script -- it isn't; MCP connectors only exist inside an MCP client/host
conversation, not in a plain Python process. This is the httpx fallback
CLAUDE.md already anticipated for that case.

Verified live against the real API (2026-09-23): the request shape here is
correct -- Apollo returned a structured 403 (API_INACCESSIBLE) because the
configured key is on a Free plan that doesn't include people search, not
because the request was malformed. Upgrading the Apollo plan, not this code,
is what would make it return real contacts.
"""

import json
import os
from pathlib import Path

import httpx

from jobagent.config import PROFILE_DIR
from jobagent.state import JobState

APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"
PROFILE_PATH = PROFILE_DIR / "profile.json"

DEFAULT_TITLES = ["hiring manager", "recruiter", "talent acquisition"]


class ApolloAccessError(Exception):
    """Apollo was reachable but rejected the request (bad key, plan limits, rate limit)."""


def _search_apollo(company_name: str, titles: list[str], api_key: str, client=None) -> list[dict]:
    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        resp = client.post(
            APOLLO_SEARCH_URL,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            json={
                "q_organization_name": company_name,
                "person_titles": titles,
                "page": 1,
                "per_page": 10,
            },
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("error", resp.text)
            except ValueError:
                detail = resp.text
            raise ApolloAccessError(f"Apollo returned {resp.status_code}: {detail}")
        return resp.json().get("people", [])
    finally:
        if owns_client:
            client.close()


def _warm_path_relation(raw: dict, profile: dict) -> str | None:
    """Flags a shared past employer between this contact and the candidate, per
    PLAN.md's "prefer warm paths" guidance. Apollo's people-search response
    doesn't include education history, so shared schools aren't checked here.
    """
    my_companies = {r.get("company", "").lower() for r in profile.get("roles", [])}
    their_employers = {
        (e.get("organization_name") or "").lower() for e in (raw.get("employment_history") or [])
    }
    shared = my_companies & their_employers - {""}
    return f"shared employer: {next(iter(shared))}" if shared else None


def _normalize(raw: dict, profile: dict) -> dict:
    return {
        "name": raw.get("name"),
        "title": raw.get("title"),
        "source": "apollo",
        "url": raw.get("linkedin_url"),
        "relation": _warm_path_relation(raw, profile),
    }


def _load_profile(profile_path: Path | None = None) -> dict:
    profile_path = profile_path or PROFILE_PATH
    if not profile_path.exists():
        return {}
    with open(profile_path) as f:
        return json.load(f)


def run(
    state: JobState,
    api_key: str | None = None,
    search=None,
    profile_path: Path | None = None,
) -> dict:
    job = state["job"]
    company_name = job.get("company_name") or job.get("company")
    api_key = api_key or os.environ.get("APOLLO_API_KEY")

    if not company_name:
        return {
            "contacts": [],
            "manual_review": True,
            "unmapped_fields": ["no company name on record for contact lookup"],
        }
    if not api_key:
        return {
            "contacts": [],
            "manual_review": True,
            "unmapped_fields": ["no APOLLO_API_KEY configured"],
        }

    search = search or _search_apollo
    titles = DEFAULT_TITLES + ([job["title"]] if job.get("title") else [])

    try:
        raw_people = search(company_name, titles, api_key)
    except ApolloAccessError as exc:
        return {"contacts": [], "manual_review": True, "unmapped_fields": [str(exc)]}

    profile = _load_profile(profile_path)
    contacts = [_normalize(p, profile) for p in raw_people]

    return {"contacts": contacts}
