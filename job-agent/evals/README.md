# Evals

Quality checks, distinct from `tests/` (which checks code correctness). Run with `uv run pytest evals`.

- **`test_style_rules.py`** -- runs now, no setup needed. Free (no LLM calls); checks the deterministic parts of `validate.py` (dashes, length, unsourced claims) against synthetic examples.
- **`test_scoring_agreement.py`** -- skipped until `golden_jobs/labels.json` exists. Calls the real Anthropic API once per labeled job.
- **`test_tailoring_truthfulness.py`** -- skipped until `golden_jobs/postings.json` exists, and uses the real `profile/profile.json`. Calls the real Anthropic API multiple times per posting (the retry loop).

Both golden-data evals cost real API usage each run -- that's why they're opt-in via the presence of the data files, not run unconditionally.

## `golden_jobs/labels.json`

20 real past postings I've hand-labeled as a good or bad fit (PLAN.md section 9), used to check the `score` node agrees with me at least 80% of the time (Phase 1 acceptance):

```json
[
  { "title": "Data Analyst", "description": "...", "label": "good" },
  { "title": "Senior Backend Engineer", "description": "...", "label": "bad" }
]
```

## `golden_jobs/postings.json`

Real postings to run through `tailor` + `validate` against the real profile, used to check zero unsupported claims make it through (Phase 2 acceptance):

```json
[{ "title": "Data Analyst", "description": "..." }]
```
