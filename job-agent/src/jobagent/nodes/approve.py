"""Human approval gates. Each of the three gates in graph.py calls interrupt()
here, which pauses the thread until I resume it with Command(resume=...) from
the Streamlit queue. Whatever value comes back from Command(resume=...) becomes
the node's *input*, not its output -- the node still has to return a proper
state-update dict, or the decision never reaches _after_approve_docs() etc. in
graph.py and the gate silently does nothing.

CLAUDE.md hard rule: no submit and no outreach send without one of these.
"""

from langgraph.types import interrupt

from jobagent.state import JobState


def approve_docs(state: JobState) -> dict:
    decision = interrupt({"kind": "approve_docs", "job_id": state.get("job_id")})
    return {"docs_approved": bool(decision)}


def approve_submit(state: JobState) -> dict:
    decision = interrupt({"kind": "approve_submit", "job_id": state.get("job_id")})
    return {"submit_approved": bool(decision)}


def approve_outreach(state: JobState) -> dict:
    decision = interrupt({"kind": "approve_outreach", "job_id": state.get("job_id")})
    return {"outreach_approved": bool(decision)}
