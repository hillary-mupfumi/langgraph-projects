"""Entry point for `uv run jobagent <command>` (see pyproject.toml [project.scripts]).

Phase 1 wires up `ingest` and `shortlist`. Phase 3 adds `start` (kick off a
per-job LangGraph thread) and `resume` (act on a paused approval gate).
"""

import argparse
import json

from jobagent.store.db import get_connection, get_job_with_company, init_db


def cmd_ingest(_args) -> None:
    from jobagent.nodes import ingest, score

    summary = ingest.run()
    print(
        f"Processed {summary['companies_processed']} companies "
        f"({summary['companies_failed']} failed), "
        f"saw {summary['jobs_seen']} jobs ({summary['new_jobs']} new)."
    )
    scored = score.run_batch()
    print(f"Scored {scored} jobs.")


def _shortlist_rows():
    with get_connection() as conn:
        return conn.execute(
            """SELECT j.title, c.name AS company, j.location,
                      s.fit_score, s.eligibility_ok, s.reasons, s.stretch_flag
               FROM jobs j
               JOIN companies c ON c.id = j.company_id
               LEFT JOIN scores s ON s.job_id = j.id
               ORDER BY COALESCE(s.eligibility_ok, -1) DESC, COALESCE(s.fit_score, -1) DESC"""
        ).fetchall()


def _format_shortlist(rows) -> str:
    if not rows:
        return "No jobs yet. Run `jobagent ingest` first."

    lines = []
    for row in rows:
        if row["fit_score"] is None:
            status = "not yet scored"
        elif not row["eligibility_ok"]:
            reasons = ", ".join(json.loads(row["reasons"] or "[]"))
            status = f"filtered: {reasons}"
        else:
            stretch = " (stretch)" if row["stretch_flag"] else ""
            status = f"fit {row['fit_score']}{stretch}"
        lines.append(f"{row['company']:<20} {row['title']:<40} {status}")
    return "\n".join(lines)


def cmd_shortlist(_args) -> None:
    print(_format_shortlist(_shortlist_rows()))


def _print_interrupt_or_done(result: dict) -> None:
    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        print(f"Paused, waiting on: {payload['kind']} (job_id={payload['job_id']})")
        print("Resume with: uv run jobagent resume <thread_id> --approve|--reject")
    else:
        print("Thread finished (or ran to the next interrupt with nothing pending).")


def cmd_start(args) -> None:
    from jobagent.graph import compile_graph

    job = get_job_with_company(args.job_id)
    if job is None:
        print(f"No job with id {args.job_id}. Run `jobagent shortlist` to see what's available.")
        return

    thread_id = str(args.job_id)
    config = {"configurable": {"thread_id": thread_id}}
    graph = compile_graph()
    result = graph.invoke({"job_id": thread_id, "job": job}, config)
    print(f"Started thread {thread_id} for '{job['title']}' at {job['company_name']}.")
    _print_interrupt_or_done(result)


def cmd_resume(args) -> None:
    from langgraph.types import Command

    from jobagent.graph import compile_graph

    config = {"configurable": {"thread_id": args.thread_id}}
    graph = compile_graph()
    result = graph.invoke(Command(resume=args.approve), config)
    _print_interrupt_or_done(result)


def cmd_status(args) -> None:
    from jobagent.graph import compile_graph

    config = {"configurable": {"thread_id": args.thread_id}}
    state = compile_graph().get_state(config)
    if not state.values:
        print(f"No thread with id {args.thread_id}.")
        return
    for key, value in state.values.items():
        print(f"{key}: {value}")
    if state.interrupts:
        print(f"\nPaused, waiting on: {state.interrupts[0].value['kind']}")


def cmd_init_db(_args) -> None:
    init_db()
    print("Initialized database schema.")


def cmd_followups(_args) -> None:
    """Jobs with a scheduled follow-up that's due (PLAN.md: 5-7 days after applying)."""
    from datetime import date

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT j.title, c.name AS company, e.detail AS follow_up_at
               FROM events e
               JOIN jobs j ON j.id = e.job_id
               JOIN companies c ON c.id = j.company_id
               WHERE e.type = 'follow_up_scheduled'"""
        ).fetchall()

    today = date.today().isoformat()
    due = [r for r in rows if r["follow_up_at"] <= today]

    if not due:
        print("No follow-ups due.")
        return
    for row in due:
        print(f"{row['company']:<20} {row['title']:<40} due {row['follow_up_at']}")


def cmd_daily(_args) -> None:
    """Phase 5 (PLAN.md section 7): the daily scheduled run -- ingest, score,
    log the shortlist, and email it if SMTP is configured. Register this with
    Windows Task Scheduler yourself (see README) -- nothing here auto-registers
    a recurring OS-level job.
    """
    from datetime import date

    from jobagent.config import ROOT
    from jobagent.nodes import ingest, score
    from jobagent.notify import send_shortlist_email

    summary = ingest.run()
    scored = score.run_batch()
    print(
        f"Processed {summary['companies_processed']} companies "
        f"({summary['companies_failed']} failed), saw {summary['jobs_seen']} jobs "
        f"({summary['new_jobs']} new). Scored {scored}."
    )

    body = _format_shortlist(_shortlist_rows())
    log_dir = ROOT / "data" / "shortlists"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{date.today().isoformat()}.txt"
    log_path.write_text(body, encoding="utf-8")
    print(f"Shortlist saved to {log_path}")

    if send_shortlist_email(body):
        print("Emailed shortlist.")
    else:
        print("SMTP not configured -- skipped email (see .env.example).")


def cmd_mark_sent(args) -> None:
    from datetime import UTC, datetime

    with get_connection() as conn:
        conn.execute(
            "UPDATE outreach SET sent_at = ?, status = 'sent' WHERE id = ?",
            (datetime.now(UTC).isoformat(), args.outreach_id),
        )
    print(f"Marked outreach {args.outreach_id} as sent.")


def cmd_mark_replied(args) -> None:
    from datetime import UTC, datetime

    with get_connection() as conn:
        conn.execute(
            "UPDATE outreach SET replied_at = ?, status = 'replied' WHERE id = ?",
            (datetime.now(UTC).isoformat(), args.outreach_id),
        )
    print(f"Marked outreach {args.outreach_id} as replied.")


def cmd_metrics(_args) -> None:
    from collections import defaultdict
    from datetime import datetime

    with get_connection() as conn:
        apps = conn.execute(
            "SELECT submitted_at FROM applications WHERE submitted_at IS NOT NULL"
        ).fetchall()
        outreach_rows = conn.execute("SELECT channel, sent_at, replied_at FROM outreach").fetchall()

    per_week = defaultdict(int)
    for row in apps:
        week = datetime.fromisoformat(row["submitted_at"]).strftime("%G-W%V")
        per_week[week] += 1

    print("Applications per week:")
    if not per_week:
        print("  (none yet)")
    for week in sorted(per_week):
        print(f"  {week}: {per_week[week]}")

    by_channel = defaultdict(lambda: {"sent": 0, "replied": 0})
    for row in outreach_rows:
        channel = row["channel"] or "unknown"
        if row["sent_at"]:
            by_channel[channel]["sent"] += 1
        if row["replied_at"]:
            by_channel[channel]["replied"] += 1

    print("\nOutreach response rate by channel:")
    if not by_channel:
        print("  (none yet)")
    for channel, stats in by_channel.items():
        rate = stats["replied"] / stats["sent"] if stats["sent"] else 0
        print(f"  {channel}: {stats['replied']}/{stats['sent']} replied ({rate:.0%})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="jobagent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="fetch and score new jobs").set_defaults(func=cmd_ingest)
    sub.add_parser("shortlist", help="print ranked shortlist").set_defaults(func=cmd_shortlist)
    sub.add_parser("init-db", help="create the SQLite schema").set_defaults(func=cmd_init_db)

    start_parser = sub.add_parser("start", help="start the per-job pipeline for a job id")
    start_parser.add_argument("job_id", type=int)
    start_parser.set_defaults(func=cmd_start)

    resume_parser = sub.add_parser("resume", help="act on a paused approval gate")
    resume_parser.add_argument("thread_id")
    approve_group = resume_parser.add_mutually_exclusive_group(required=True)
    approve_group.add_argument("--approve", action="store_true", dest="approve")
    approve_group.add_argument("--reject", action="store_false", dest="approve")
    resume_parser.set_defaults(func=cmd_resume)

    status_parser = sub.add_parser("status", help="show a thread's current state")
    status_parser.add_argument("thread_id")
    status_parser.set_defaults(func=cmd_status)

    sub.add_parser("followups", help="list applications with a due follow-up").set_defaults(
        func=cmd_followups
    )

    sub.add_parser(
        "daily", help="ingest, score, log the shortlist, and email it if configured"
    ).set_defaults(func=cmd_daily)

    mark_sent_parser = sub.add_parser("mark-sent", help="mark an outreach message as sent")
    mark_sent_parser.add_argument("outreach_id", type=int)
    mark_sent_parser.set_defaults(func=cmd_mark_sent)

    mark_replied_parser = sub.add_parser(
        "mark-replied", help="mark an outreach message as having gotten a reply"
    )
    mark_replied_parser.add_argument("outreach_id", type=int)
    mark_replied_parser.set_defaults(func=cmd_mark_replied)

    sub.add_parser("metrics", help="applications per week and outreach response rate").set_defaults(
        func=cmd_metrics
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
