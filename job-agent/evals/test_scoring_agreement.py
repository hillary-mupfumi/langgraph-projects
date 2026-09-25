"""Phase 1 acceptance (PLAN.md section 7): on hand-labeled jobs, the score
node's judgment should agree with my good/bad-fit label at least 80% of the
time. Needs evals/golden_jobs/labels.json -- see evals/README.md. Skips
(doesn't fail) when that file doesn't exist yet, since no one has labeled
anything. This eval calls the real Anthropic API once per labeled job, so
it costs a little money each run -- that's deliberate, not a bug.
"""

import json
from pathlib import Path

import pytest

from jobagent.nodes import score

LABELS_PATH = Path(__file__).parent / "golden_jobs" / "labels.json"


def _load_labels() -> list[dict]:
    if not LABELS_PATH.exists():
        pytest.skip(f"No golden jobs yet -- add {LABELS_PATH} (see evals/README.md)")
    with open(LABELS_PATH) as f:
        return json.load(f)


def test_scoring_agrees_with_my_labels_at_least_80_percent():
    labels = _load_labels()
    agreements = 0
    disagreements = []

    for item in labels:
        result = score.run({"title": item["title"], "description": item["description"]})
        predicted_good = result["eligibility_ok"] and result["fit_score"] >= 60
        actual_good = item["label"] == "good"
        if predicted_good == actual_good:
            agreements += 1
        else:
            disagreements.append(item["title"])

    rate = agreements / len(labels)
    assert rate >= 0.8, (
        f"Scoring agreed with my labels {rate:.0%} of the time (need >= 80%). "
        f"Disagreed on: {disagreements}"
    )
