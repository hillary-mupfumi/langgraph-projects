"""Renders the approved tailored resume/cover letter to DOCX files. Runs
between approve_docs and apply in graph.py -- apply.py needs a real file to
upload, and track.py needs a real path to log in the applications table.

Separate from apply.py so browser automation stays focused on the browser.
"""

import json
from pathlib import Path

from jobagent.config import PROFILE_DIR, ROOT
from jobagent.render.docx import render_cover_letter, render_resume
from jobagent.state import JobState

OUTPUT_DIR = ROOT / "data" / "output"
PROFILE_PATH = PROFILE_DIR / "profile.json"


def _candidate_name(profile_path: Path | None = None) -> str:
    profile_path = profile_path or PROFILE_PATH
    with open(profile_path) as f:
        return json.load(f).get("name", "Candidate")


def run(state: JobState, out_dir: Path | None = None, profile_path: Path | None = None) -> dict:
    out_dir = out_dir or OUTPUT_DIR
    job = state["job"]
    company = job.get("company_name") or job.get("company") or "Company"
    tag = state.get("resume_variant") or "v1"

    resume_path = render_resume(
        _candidate_name(profile_path), state["tailored_resume"], out_dir, company, tag
    )
    cover_letter_path = render_cover_letter(state["cover_letter"], out_dir, company, tag)

    return {
        "resume_path": str(resume_path),
        "cover_letter_path": str(cover_letter_path),
    }
