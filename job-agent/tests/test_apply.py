from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from jobagent.nodes import apply

FIXTURE_URL = (Path(__file__).parent / "fixtures" / "fake_greenhouse_form.html").as_uri()

ANSWERS = {
    "first_name": "Jordan",
    "last_name": "Rivera",
    "email": "jordan.rivera.dummy@example.com",
    "phone": "555-000-1234",
}


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    p = context.new_page()
    p.goto(FIXTURE_URL)
    yield p
    context.close()


def test_fill_greenhouse_form_fills_known_fields_and_flags_unknown(page, tmp_path):
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 fake resume")

    unmapped = apply._fill_greenhouse_form(page, ANSWERS, resume_path)

    assert page.locator("#first_name").input_value() == "Jordan"
    assert page.locator("#last_name").input_value() == "Rivera"
    assert page.locator("#email").input_value() == "jordan.rivera.dummy@example.com"
    assert page.locator("#phone").input_value() == "555-000-1234"

    assert any("why_interested" in item for item in unmapped)


def test_fill_greenhouse_form_flags_missing_answers(page, tmp_path):
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 fake resume")

    unmapped = apply._fill_greenhouse_form(page, {"first_name": "Jordan"}, resume_path)

    assert "last_name" in unmapped
    assert "email" in unmapped
    assert page.locator("#first_name").input_value() == "Jordan"


def test_run_never_clicks_submit_and_takes_a_screenshot(browser, tmp_path, monkeypatch):
    monkeypatch.setattr(apply, "SCREENSHOT_DIR", tmp_path)

    context = browser.new_context()
    state = {
        "job": {"id": 1, "url": FIXTURE_URL, "ats_type": "greenhouse"},
    }
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 fake resume")

    result = apply.run(
        state,
        browser_factory=lambda: context,
        resume_path=resume_path,
        answers=ANSWERS,
    )
    context.close()

    assert result["status"] == "ready_to_apply"
    assert result["manual_review"] is True  # the custom question is still unmapped
    assert Path(result["application_screenshot_path"]).exists()


def test_run_marks_manual_when_url_missing():
    result = apply.run({"job": {"id": 1}})
    assert result["manual_review"] is True
    assert result["status"] == "applied"


def test_run_marks_manual_for_unsupported_ats_type(browser, tmp_path, monkeypatch):
    monkeypatch.setattr(apply, "SCREENSHOT_DIR", tmp_path)

    context = browser.new_context()
    state = {"job": {"id": 2, "url": FIXTURE_URL, "ats_type": "lever"}}
    result = apply.run(state, browser_factory=lambda: context)
    context.close()

    assert result["manual_review"] is True
    assert any("lever" in item for item in result["unmapped_fields"])
