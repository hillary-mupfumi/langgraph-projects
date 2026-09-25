"""Streamlit approval queue and tracker.

Run with: uv run streamlit run src/jobagent/ui/app.py

Lists every eligible scored job. Each one is its own LangGraph thread (thread_id
= job id): "Start" kicks off tailor -> validate, then the page shows whatever
the thread is paused on -- resume/cover letter, the pre-submit screenshot, or
outreach drafts -- with Approve/Reject buttons that call Command(resume=...).
Nothing here ever clicks submit or sends a message itself; approving just lets
the graph continue to the next stage, which stops at its own interrupt.
"""

import streamlit as st
from langgraph.types import Command

from jobagent.graph import compile_graph
from jobagent.store.db import list_scored_jobs

st.set_page_config(page_title="Job Application Agent", layout="wide")
st.title("Job Application Agent")

jobs = list_scored_jobs()
if not jobs:
    st.info("No scored jobs yet. Run `jobagent ingest` first.")
    st.stop()

graph = compile_graph()

for job in jobs:
    thread_id = str(job["id"])
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)

    label = f"{job['company_name']} - {job['title']} (fit {job['fit_score']})"
    with st.expander(label):
        if not state.values:
            if st.button("Start", key=f"start-{thread_id}"):
                graph.invoke({"job_id": thread_id, "job": job}, config)
                st.rerun()
            continue

        if not state.interrupts:
            st.success(f"Status: {state.values.get('status', 'done')}")
            continue

        kind = state.interrupts[0].value["kind"]

        if kind == "approve_docs":
            resume = state.values.get("tailored_resume", {})
            st.subheader("Tailored resume")
            st.write(resume.get("summary", ""))
            for bullet in resume.get("bullets", []):
                st.markdown(f"- {bullet['text']}")
            st.subheader("Cover letter")
            st.write(state.values.get("cover_letter", ""))

        elif kind == "approve_submit":
            st.write("Application form filled, stopped before submit.")
            screenshot = state.values.get("application_screenshot_path")
            if screenshot:
                st.image(screenshot)
            if state.values.get("manual_review"):
                st.warning(f"Needs manual review: {state.values.get('unmapped_fields')}")
            st.caption(
                "Approving here does NOT click submit -- it only lets you move on to "
                "outreach. Submitting the actual application is still on you, in the browser."
            )

        elif kind == "approve_outreach":
            st.subheader("Outreach drafts")
            for draft in state.values.get("outreach_drafts", []):
                st.write(draft)

        col1, col2 = st.columns(2)
        if col1.button("Approve", key=f"approve-{thread_id}"):
            graph.invoke(Command(resume=True), config)
            st.rerun()
        if col2.button("Reject", key=f"reject-{thread_id}"):
            graph.invoke(Command(resume=False), config)
            st.rerun()
