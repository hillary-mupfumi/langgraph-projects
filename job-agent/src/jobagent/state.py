from typing import Literal, TypedDict

ApplicationStatus = Literal[
    "discovered",
    "shortlisted",
    "tailoring",
    "awaiting_approval",
    "ready_to_apply",
    "applied",
    "outreach_drafted",
    "followed_up",
    "interview",
    "rejected",
    "withdrawn",
]


class Score(TypedDict):
    fit_score: int  # 0-100
    eligibility_ok: bool
    reasons: list[str]
    stretch_flag: bool


class ValidationResult(TypedDict):
    ok: bool
    errors: list[str]


class JobState(TypedDict, total=False):
    """State for a single per-job LangGraph thread (nodes: tailor onward).

    ingest/score run in a separate daily-batch graph, not per-thread.
    """

    job_id: str
    job: dict
    score: Score
    resume_variant: str
    tailored_resume: dict
    cover_letter: str
    validation: ValidationResult
    validation_attempts: int
    docs_approved: bool
    resume_path: str
    cover_letter_path: str
    application_screenshot_path: str
    manual_review: bool
    unmapped_fields: list[str]
    submit_approved: bool
    contacts: list[dict]
    outreach_drafts: list[dict]
    outreach_approved: bool
    status: ApplicationStatus
    application_id: int
    follow_up_at: str
