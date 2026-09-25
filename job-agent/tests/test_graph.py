"""Proves the interrupt/resume mechanics actually work: a thread pauses at
each approve_* gate, and -- the important guarantee from CLAUDE.md -- nothing
downstream of a rejected gate ever runs. Uses fake node functions (monkeypatched
in before build_graph() wires them) and an in-memory checkpointer, so this
doesn't touch the real filesystem, LLM, or browser.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from jobagent.nodes import apply, contacts, outreach, render_docs, tailor, track, validate


class CallTracker:
    def __init__(self, return_value):
        self.return_value = return_value
        self.calls = 0

    def __call__(self, _state):
        self.calls += 1
        return self.return_value


def _build_test_graph(monkeypatch):
    fake_tailor = CallTracker({"tailored_resume": {"bullets": []}, "cover_letter": "hi"})
    fake_validate = CallTracker(
        {"validation": {"ok": True, "errors": []}, "validation_attempts": 1}
    )
    fake_render_docs = CallTracker(
        {"resume_path": "fake_resume.docx", "cover_letter_path": "fake_cl.docx"}
    )
    fake_apply = CallTracker(
        {"application_screenshot_path": "fake.png", "manual_review": False, "status": "x"}
    )
    fake_contacts = CallTracker({"contacts": []})
    fake_outreach = CallTracker({"outreach_drafts": []})
    fake_track = CallTracker(None)

    monkeypatch.setattr(tailor, "run", fake_tailor)
    monkeypatch.setattr(validate, "run", fake_validate)
    monkeypatch.setattr(render_docs, "run", fake_render_docs)
    monkeypatch.setattr(apply, "run", fake_apply)
    monkeypatch.setattr(contacts, "run", fake_contacts)
    monkeypatch.setattr(outreach, "run", fake_outreach)
    monkeypatch.setattr(track, "run", fake_track)

    from jobagent.graph import build_graph

    graph = build_graph().compile(checkpointer=MemorySaver())
    fakes = {
        "tailor": fake_tailor,
        "validate": fake_validate,
        "render_docs": fake_render_docs,
        "apply": fake_apply,
        "contacts": fake_contacts,
        "outreach": fake_outreach,
        "track": fake_track,
    }
    return graph, fakes


def test_thread_pauses_at_approve_docs(monkeypatch):
    graph, fakes = _build_test_graph(monkeypatch)
    config = {"configurable": {"thread_id": "job-1"}}

    result = graph.invoke({"job_id": "job-1", "job": {"title": "Data Analyst"}}, config)

    assert "__interrupt__" in result
    assert result["__interrupt__"][0].value["kind"] == "approve_docs"
    assert fakes["tailor"].calls == 1
    assert fakes["apply"].calls == 0  # must not have run yet


def test_rejecting_docs_stops_before_apply_ever_runs(monkeypatch):
    graph, fakes = _build_test_graph(monkeypatch)
    config = {"configurable": {"thread_id": "job-2"}}
    graph.invoke({"job_id": "job-2", "job": {"title": "Data Analyst"}}, config)

    result = graph.invoke(Command(resume=False), config)

    assert "__interrupt__" not in result
    assert fakes["apply"].calls == 0  # rejected before apply -- must never run
    state = graph.get_state(config)
    assert state.values["docs_approved"] is False


def test_approving_docs_then_rejecting_submit_stops_before_outreach(monkeypatch):
    graph, fakes = _build_test_graph(monkeypatch)
    config = {"configurable": {"thread_id": "job-3"}}
    graph.invoke({"job_id": "job-3", "job": {"title": "Data Analyst"}}, config)

    result = graph.invoke(Command(resume=True), config)  # approve docs
    assert result["__interrupt__"][0].value["kind"] == "approve_submit"
    assert fakes["apply"].calls == 1  # ran once docs were approved

    result = graph.invoke(Command(resume=False), config)  # reject submit

    assert "__interrupt__" not in result
    assert fakes["contacts"].calls == 0  # rejected before outreach -- must never run
    assert fakes["outreach"].calls == 0
    assert fakes["track"].calls == 0


def test_full_approval_chain_reaches_track(monkeypatch):
    graph, fakes = _build_test_graph(monkeypatch)
    config = {"configurable": {"thread_id": "job-4"}}
    graph.invoke({"job_id": "job-4", "job": {"title": "Data Analyst"}}, config)

    graph.invoke(Command(resume=True), config)  # approve docs
    result = graph.invoke(Command(resume=True), config)  # approve submit
    assert result["__interrupt__"][0].value["kind"] == "approve_outreach"

    result = graph.invoke(Command(resume=True), config)  # approve outreach

    assert "__interrupt__" not in result
    assert fakes["track"].calls == 1
    state = graph.get_state(config)
    assert state.values["docs_approved"] is True
    assert state.values["submit_approved"] is True
    assert state.values["outreach_approved"] is True
