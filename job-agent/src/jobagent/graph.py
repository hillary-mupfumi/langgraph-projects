"""Builds and compiles the per-job LangGraph (PLAN.md section 6):

    tailor -> validate -> [tailor again, up to 3 tries] -> approve_docs
    approve_docs -> render_docs -> apply -> approve_submit
    approve_submit -> contacts -> outreach -> approve_outreach -> track

render_docs isn't in the original PLAN.md graph diagram -- added so apply.py
has an actual file to upload and track.py has an actual path to log, instead
of rendering happening nowhere.

ingest/score run in a separate daily-batch script (nodes/ingest.py, nodes/score.py),
not in this per-job thread graph. Each approve_* node is an interrupt() and the
thread resumes with Command(resume=...) once I act in the Streamlit queue -- see
nodes/approve.py and CLAUDE.md's hard rule against unattended submits/sends.
"""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from jobagent.config import DB_PATH
from jobagent.nodes import apply, approve, contacts, outreach, render_docs, tailor, track, validate
from jobagent.state import JobState

MAX_VALIDATION_ATTEMPTS = 3


def _after_validate(state: JobState) -> str:
    if state["validation"]["ok"]:
        return "approve_docs"
    if state.get("validation_attempts", 0) >= MAX_VALIDATION_ATTEMPTS:
        return "approve_docs"  # let the human see it fail rather than loop forever
    return "tailor"


def _after_approve_docs(state: JobState) -> str:
    return "render_docs" if state.get("docs_approved") else END


def _after_approve_submit(state: JobState) -> str:
    return "contacts" if state.get("submit_approved") else END


def _after_approve_outreach(state: JobState) -> str:
    return "track" if state.get("outreach_approved") else END


def build_graph():
    g = StateGraph(JobState)

    g.add_node("tailor", tailor.run)
    g.add_node("validate", validate.run)
    g.add_node("approve_docs", approve.approve_docs)
    g.add_node("render_docs", render_docs.run)
    g.add_node("apply", apply.run)
    g.add_node("approve_submit", approve.approve_submit)
    g.add_node("contacts", contacts.run)
    g.add_node("outreach", outreach.run)
    g.add_node("approve_outreach", approve.approve_outreach)
    g.add_node("track", track.run)

    g.add_edge(START, "tailor")
    g.add_edge("tailor", "validate")
    g.add_conditional_edges("validate", _after_validate)
    g.add_conditional_edges("approve_docs", _after_approve_docs)
    g.add_edge("render_docs", "apply")
    g.add_edge("apply", "approve_submit")
    g.add_conditional_edges("approve_submit", _after_approve_submit)
    g.add_edge("contacts", "outreach")
    g.add_edge("outreach", "approve_outreach")
    g.add_conditional_edges("approve_outreach", _after_approve_outreach)
    g.add_edge("track", END)

    return g


def compile_graph():
    """Compiles with a SQLite checkpointer backed by a persistent connection --
    NOT SqliteSaver.from_conn_string(), which is a context manager that closes
    its connection on exit and would leave the checkpointer unusable for a
    long-lived CLI/Streamlit process.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return build_graph().compile(checkpointer=checkpointer)
