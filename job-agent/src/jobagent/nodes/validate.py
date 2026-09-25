"""Reflection pattern: deterministic checks first (free, instant), then a
critic LLM pass only if those pass (no point fact-checking a resume that's
already going back to tailor()). Fails on any claim not traceable to
profile.json, any em/en dash, or going over the page budget. On failure,
returns an error list that routes back to tailor() -- capped at 3 loops,
enforced in graph.py.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from jobagent.config import PROFILE_DIR, load_rules
from jobagent.state import JobState, ValidationResult

PROFILE_PATH = PROFILE_DIR / "profile.json"

EM_DASH = "—"
EN_DASH = "–"
WORDS_PER_PAGE = 550  # rough heuristic for a one-page resume + cover letter


class CriticVerdict(BaseModel):
    ok: bool
    issues: list[str]


def _load_known_bullets(profile_path: Path | None = None) -> dict[str, str]:
    profile_path = profile_path or PROFILE_PATH
    with open(profile_path) as f:
        profile = json.load(f)
    return {
        b["id"]: b["text"] for role in profile.get("roles", []) for b in role.get("bullets", [])
    }


def _deterministic_checks(state: JobState, known_bullets: dict[str, str]) -> list[str]:
    errors = []
    resume = state.get("tailored_resume") or {}
    cover_letter = state.get("cover_letter") or ""
    bullet_texts = [b.get("text", "") for b in resume.get("bullets", [])]

    all_text = cover_letter + " " + " ".join(bullet_texts)
    if EM_DASH in all_text or EN_DASH in all_text:
        errors.append("Found an em or en dash -- use commas, periods or hyphens instead.")

    max_pages = load_rules().style.max_pages
    word_count = len(all_text.split())
    if word_count > WORDS_PER_PAGE * max_pages:
        errors.append(
            f"Resume + cover letter is about {word_count} words, too long for {max_pages} page(s)."
        )

    for bullet in resume.get("bullets", []):
        source_id = bullet.get("source_id")
        if source_id not in known_bullets:
            errors.append(f"Bullet references source_id '{source_id}', not found in profile.json.")

    return errors


def _default_llm():
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model="claude-sonnet-5")


def _critic_check(state: JobState, known_bullets: dict[str, str], llm) -> list[str]:
    resume = state.get("tailored_resume") or {}
    cover_letter = state.get("cover_letter") or ""

    trace = "\n".join(
        f'- [{b["source_id"]}] original: "{known_bullets.get(b["source_id"], "?")}" '
        f'-> rewritten: "{b["text"]}"'
        for b in resume.get("bullets", [])
    )

    prompt = (
        "You are fact-checking a resume rewrite. For each pair below, the rewritten bullet "
        "must not claim anything (a tool, a number, a scope, an outcome) that isn't already "
        "present in the original. Flag any bullet or cover letter sentence that adds an "
        "unsupported claim.\n\n"
        f"{trace}\n\nCover letter:\n{cover_letter}\n\n"
        "Return ok=true only if every bullet and the cover letter are fully supported by the "
        "original facts."
    )
    structured_llm = llm.with_structured_output(CriticVerdict)
    verdict: CriticVerdict = structured_llm.invoke(prompt)
    return [] if verdict.ok else verdict.issues


def run(state: JobState, profile_path: Path | None = None, llm=None) -> dict:
    known_bullets = _load_known_bullets(profile_path)
    errors = _deterministic_checks(state, known_bullets)

    if not errors:
        llm = llm or _default_llm()
        errors = _critic_check(state, known_bullets, llm)

    attempts = state.get("validation_attempts", 0) + 1
    return {
        "validation": ValidationResult(ok=len(errors) == 0, errors=errors),
        "validation_attempts": attempts,
    }
