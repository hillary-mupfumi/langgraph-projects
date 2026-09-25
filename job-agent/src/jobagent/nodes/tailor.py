"""Pick the base resume variant, retrieve the most relevant profile items, and
rewrite bullets to mirror the posting's language without adding facts. Generate
a cover letter that states gaps honestly.

No side effects here: this node can run again after a validate() failure, and
a resumed LangGraph thread restarts from the top of the node it was in. On a
retry, the previous validation errors are fed back in as instructions to fix.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from jobagent import profile_index
from jobagent.config import PROFILE_DIR, load_rules
from jobagent.state import JobState

PROFILE_PATH = PROFILE_DIR / "profile.json"


class TailoredBullet(BaseModel):
    source_id: str
    text: str


class TailoredResume(BaseModel):
    summary: str
    bullets: list[TailoredBullet]
    skills: list[str]


class TailorOutput(BaseModel):
    resume: TailoredResume
    cover_letter: str


def _load_profile(profile_path: Path | None = None) -> dict:
    profile_path = profile_path or PROFILE_PATH
    with open(profile_path) as f:
        return json.load(f)


def _default_llm():
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model="claude-sonnet-5")


def _pick_variant(job: dict, rules) -> str:
    title_words = set((job.get("title") or "").lower().split())
    for variant in rules.resume_variants:
        label_words = set(variant["label"].lower().split())
        if title_words & label_words:
            return variant["id"]
    return rules.resume_variants[0]["id"] if rules.resume_variants else "default"


def _relevant_bullets(profile: dict, relevant_texts: list[str]) -> list[dict]:
    all_bullets = {b["id"]: b for role in profile.get("roles", []) for b in role.get("bullets", [])}
    text_set = set(relevant_texts)
    matches = [b for b in all_bullets.values() if b["text"] in text_set]
    return matches or list(all_bullets.values())  # fall back to everything if no match


def run(state: JobState, retrieve=None, llm=None, profile_path: Path | None = None) -> dict:
    job = state["job"]
    rules = load_rules()
    retrieve = retrieve or profile_index.retrieve
    llm = llm or _default_llm()

    profile = _load_profile(profile_path)
    query = job.get("description") or job.get("title") or ""
    relevant_texts = retrieve(query, k=10)
    facts = _relevant_bullets(profile, relevant_texts)
    facts_block = "\n".join(f"- [{b['id']}] {b['text']}" for b in facts)

    feedback = (state.get("validation") or {}).get("errors")
    feedback_block = ""
    if feedback:
        feedback_block = (
            "\n\nThe previous attempt failed validation for these reasons. Fix them:\n"
            + "\n".join(f"- {f}" for f in feedback)
        )

    prompt = (
        "Rewrite these candidate facts into resume bullets tailored to the job below. "
        "You may ONLY rephrase the given facts to mirror the job's language -- never add "
        "a skill, tool, number or outcome that isn't already stated in the fact. Every "
        "rewritten bullet must carry the source_id of the fact it came from.\n\n"
        f"Candidate facts:\n{facts_block}\n\n"
        f"Job title: {job.get('title')}\n"
        f"Job description:\n{job.get('description') or '(none provided)'}"
        f"{feedback_block}\n\n"
        "Also write a one-paragraph cover letter body (no greeting or signature) that is "
        "honest about any gaps between the candidate's background and the role."
    )

    structured_llm = llm.with_structured_output(TailorOutput)
    result: TailorOutput = structured_llm.invoke(prompt)

    return {
        "resume_variant": _pick_variant(job, rules),
        "tailored_resume": result.resume.model_dump(),
        "cover_letter": result.cover_letter,
    }
