"""Draft connection notes (under 300 characters) and longer recruiter emails,
personalized per contact using only the tailored resume's own summary --
never a claim beyond what's already been fact-checked in validate.py. Warm
paths (shared past employer) come pre-flagged from contacts.py and get worked
into the note. Never sends on LinkedIn or anywhere else -- only drafts text;
I copy or approve each message via approve_outreach() in graph.py.
"""

from pydantic import BaseModel, Field

from jobagent.state import JobState


class OutreachDraft(BaseModel):
    connection_note: str = Field(max_length=300)
    email: str


def _default_llm():
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model="claude-sonnet-5")


def _draft_for_contact(llm, contact: dict, job: dict, tailored_resume: dict) -> OutreachDraft:
    warm_path_note = f"\n\nWarm path: {contact['relation']}." if contact.get("relation") else ""
    company = job.get("company_name") or job.get("company") or "the company"
    prompt = (
        f"Draft outreach to {contact.get('name')} ({contact.get('title')}) at {company} "
        f"about the {job.get('title')} role I'm applying to.\n\n"
        f"My relevant background: {tailored_resume.get('summary', '')}"
        f"{warm_path_note}\n\n"
        "Write two things:\n"
        "1. connection_note: a LinkedIn-style connection request note, under 300 characters, "
        "warm and specific, no generic flattery.\n"
        "2. email: a slightly longer email version suitable for a recruiter, still short "
        "(3-4 sentences), professional, mentioning the specific role.\n"
        "Never claim anything about my background beyond what's stated above."
    )
    structured_llm = llm.with_structured_output(OutreachDraft)
    return structured_llm.invoke(prompt)


def run(state: JobState, llm=None) -> dict:
    contacts = state.get("contacts") or []
    if not contacts:
        return {"outreach_drafts": []}

    llm = llm or _default_llm()
    job = state["job"]
    tailored_resume = state.get("tailored_resume") or {}

    drafts = []
    for contact in contacts:
        draft = _draft_for_contact(llm, contact, job, tailored_resume)
        drafts.append(
            {
                "contact_name": contact.get("name"),
                "contact_title": contact.get("title"),
                "channel": "linkedin",
                "connection_note": draft.connection_note,
                "email": draft.email,
                "warm_path": contact.get("relation"),
            }
        )

    return {"outreach_drafts": drafts}
