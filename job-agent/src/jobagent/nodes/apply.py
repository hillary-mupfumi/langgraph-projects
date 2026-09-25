"""Playwright-driven assisted apply. Fills standard fields from profile/answers.yaml,
uploads the tailored resume, and flags anything it can't confidently map for manual
review. Always stops before the submit button -- the click only happens after
approve_submit() in graph.py, and this node never looks for or clicks submit at all.

Greenhouse's field naming is the most stable across postings, so it gets a real
filler. Lever and Ashby vary more per-company; those (and anything Greenhouse's
filler can't find) fall back to "mark manual and hand me the link and files",
per CLAUDE.md/PLAN.md.
"""

from pathlib import Path

from jobagent.config import ROOT, load_answers
from jobagent.state import JobState

SCREENSHOT_DIR = ROOT / "data" / "screenshots"

# Common Greenhouse field name/id substrings -> answers.yaml key.
GREENHOUSE_FIELD_MAP = {
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "phone": "phone",
    "location": "location",
}


def _fill_greenhouse_form(page, answers: dict, resume_path: Path | None) -> list[str]:
    """Fill what we can on a Greenhouse application page. Returns unmapped field labels."""
    unmapped: list[str] = []

    for field_key, answer_key in GREENHOUSE_FIELD_MAP.items():
        value = answers.get(answer_key)
        locator = page.locator(f"input[id*='{field_key}'], input[name*='{field_key}']")
        if locator.count() == 0:
            continue
        if not value:
            unmapped.append(field_key)
            continue
        locator.first.fill(str(value))

    file_input = page.locator("input[type='file']")
    if file_input.count() > 0:
        if resume_path is not None:
            file_input.first.set_input_files(str(resume_path))
        else:
            unmapped.append("resume_upload (no rendered resume available to attach)")

    # Anything Greenhouse renders as a free-text "custom question" we don't
    # have a mapped answer for gets flagged rather than guessed at.
    for textarea in page.locator("textarea").all():
        name = textarea.get_attribute("name") or textarea.get_attribute("id") or "unnamed question"
        if not (textarea.input_value() or "").strip():
            unmapped.append(f"custom question: {name}")

    return unmapped


FILLERS = {"greenhouse": _fill_greenhouse_form}


def run(
    state: JobState,
    browser_factory=None,
    resume_path: Path | None = None,
    answers: dict | None = None,
) -> dict:
    """browser_factory() -> a Playwright BrowserContext-like object with .new_page().
    Defaults to launching a real headed Chromium so you can watch/take over.
    resume_path defaults to state["resume_path"] (set by render_docs.py) when not
    passed explicitly -- explicit still wins, mainly for tests.
    """
    job = state["job"]
    url = job.get("url")
    ats_type = job.get("ats_type")
    if resume_path is None and state.get("resume_path"):
        resume_path = Path(state["resume_path"])

    if not url:
        return {
            "status": "applied",
            "manual_review": True,
            "unmapped_fields": ["no job url on record"],
        }

    owns_browser = browser_factory is None
    if owns_browser:
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
    else:
        context = browser_factory()

    try:
        page = context.new_page()
        page.goto(url)

        filler = FILLERS.get(ats_type)
        if filler is None:
            manual_review = True
            unmapped = [f"ats_type '{ats_type}' has no automated filler -- fill in manually"]
        else:
            answers = answers if answers is not None else load_answers()
            unmapped = filler(page, answers, resume_path)
            manual_review = len(unmapped) > 0

        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_path = SCREENSHOT_DIR / f"{job.get('id', 'job')}_pre_submit.png"
        page.screenshot(path=str(screenshot_path))
    finally:
        if owns_browser:
            context.close()
            browser.close()
            pw.stop()

    return {
        "application_screenshot_path": str(screenshot_path),
        "manual_review": manual_review,
        "unmapped_fields": unmapped,
        "status": "ready_to_apply",
    }
