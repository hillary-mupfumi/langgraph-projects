"""Phase 2 acceptance (PLAN.md section 7): on the golden set, zero unsupported
claims should make it past validate.py, across repeated runs. Needs
evals/golden_jobs/postings.json (job postings to tailor against, using the
real profile/profile.json) -- see evals/README.md. Skips when that file
doesn't exist. Calls the real Anthropic API multiple times per posting (the
retry loop), so this costs money each run -- deliberate, not a bug.
"""

import json
from pathlib import Path

import pytest

from jobagent.nodes import tailor, validate

POSTINGS_PATH = Path(__file__).parent / "golden_jobs" / "postings.json"
MAX_ATTEMPTS = 3


def _load_postings() -> list[dict]:
    if not POSTINGS_PATH.exists():
        pytest.skip(f"No golden postings yet -- add {POSTINGS_PATH} (see evals/README.md)")
    with open(POSTINGS_PATH) as f:
        return json.load(f)


def test_tailoring_eventually_passes_validation_with_no_fabricated_claims():
    postings = _load_postings()
    failures = []

    for posting in postings:
        state = {"job": posting}
        for _attempt in range(MAX_ATTEMPTS):
            state.update(tailor.run(state))
            state.update(validate.run(state))
            if state["validation"]["ok"]:
                break
        if not state["validation"]["ok"]:
            failures.append({"title": posting["title"], "errors": state["validation"]["errors"]})

    assert not failures, f"{len(failures)}/{len(postings)} postings never passed: {failures}"
