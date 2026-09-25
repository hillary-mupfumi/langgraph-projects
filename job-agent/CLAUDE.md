# Job Application Agent

LangGraph app that discovers jobs, tailors my resume and cover letter, assists with applications, and drafts outreach. See [PLAN.md](PLAN.md) for the full build plan and phases.

## Hard rules

- Never submit an application or send a message without an explicit approval step (LangGraph `interrupt()`), and keep a test proving it.
- Never state anything in a resume or cover letter that is not in `profile/profile.json`. Gaps must be stated honestly.
- No em dashes or en dashes in any generated document or message. Use commas, periods or hyphens.
- Resumes are one page and ATS-friendly (no tables, columns or images). Filenames: `Hillary_Mupfumi_{Resume|CoverLetter}_{Company}_{Tag}`.
- Do not scrape or automate LinkedIn. Only draft text for LinkedIn messages.
- Never commit secrets. Use `.env`.

## Conventions

- Python 3.11+, `uv` for dependencies, `pytest` for tests, `ruff` for lint and format.
- Type hints everywhere; graph state lives in `src/jobagent/state.py`.
- Keep side effects (sending, submitting, writing files) out of nodes that run before an `interrupt()`, because resumed nodes restart from the top.
- All agent actions are logged to the `events` table.
- Work in small commits; run tests before each commit.
- LLM calls go through the Anthropic API (`langchain-anthropic`), not OpenAI.
- Contact lookup (the plan's "Apollo API" step) goes through the Apollo MCP connector already available in this environment rather than a hand-rolled `httpx` client. If that connector isn't available in a given environment, fall back to `httpx` against Apollo's REST API and note the switch in `PLAN.md`.

## Commands

- `uv run jobagent ingest` - fetch and score new jobs
- `uv run jobagent shortlist` - print ranked shortlist
- `uv run jobagent resume <thread_id>` - resume a paused job thread
- `uv run streamlit run src/jobagent/ui/app.py` - approval queue and tracker
- `uv run pytest tests`; `uv run pytest evals/` - quality evals
