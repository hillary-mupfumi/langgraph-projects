from jobagent.nodes import outreach
from jobagent.nodes.outreach import OutreachDraft


class FakeLLM:
    def __init__(self, draft: OutreachDraft):
        self._draft = draft
        self.prompts = []

    def with_structured_output(self, _model_cls):
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self._draft


def test_run_returns_empty_when_no_contacts():
    def boom_llm(*_a, **_k):
        raise AssertionError("LLM should not be called with no contacts")

    result = outreach.run({"job": {}, "contacts": []}, llm=boom_llm)
    assert result == {"outreach_drafts": []}


def test_run_drafts_one_message_per_contact():
    fake_llm = FakeLLM(
        OutreachDraft(connection_note="Hi Alex, loved your work on...", email="Dear Alex, ...")
    )
    state = {
        "job": {"title": "Data Analyst", "company_name": "Acme"},
        "tailored_resume": {"summary": "Data analyst with SQL and dashboarding experience."},
        "contacts": [
            {"name": "Alex Recruiter", "title": "Recruiter", "relation": "shared employer: acme"},
            {"name": "Sam Manager", "title": "Hiring Manager", "relation": None},
        ],
    }

    result = outreach.run(state, llm=fake_llm)

    assert len(result["outreach_drafts"]) == 2
    first = result["outreach_drafts"][0]
    assert first["contact_name"] == "Alex Recruiter"
    assert first["connection_note"] == "Hi Alex, loved your work on..."
    assert first["warm_path"] == "shared employer: acme"
    assert "shared employer: acme" in fake_llm.prompts[0]
