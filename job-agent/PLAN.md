# Job Application Agent: Build Plan

A LangGraph application that finds jobs matching my resume, tailors my resume and cover letter, helps me apply, and drafts outreach to hiring managers. Every irreversible action (submit an application, send a message) needs my explicit approval.

1. Goals and non-goals
2. Guardrails (apply to every phase)
3. Stack
4. Repository layout
5. Data model (SQLite)
6. Graph design
7. Phases
8. Risks and mitigations
9. What I need to provide
10. First session prompt for Claude Code
11. Amendments log

## 1. Goals and non-goals

### Goals

- Daily ranked shortlist of jobs that fit my profile, with a one-line reason per job.
- Tailored resume (DOCX and PDF) and cover letter per approved job, using only facts from my profile.
- Assisted application: form pre-filled in a browser, stopped before submit.
- Outreach drafts for hiring managers, recruiters and peers, sent only after I approve.
- One tracker showing every job, resume version, contact, status and follow-up date.

### Non-goals

- No blind mass-applying.
- No scraping or automating LinkedIn (its terms prohibit it). LinkedIn stays a manual channel; the agent only drafts the note text.
- No invented experience, ever.

## 2. Guardrails (apply to every phase)

- Truthfulness: every claim in a resume or letter must trace to an entry in `profile/profile.json`. A validator node enforces this.
- Human approval gates before: submitting any application, and sending any outreach message.
- Style rules for all generated documents: no em dashes or en dashes, single page, ATS-friendly (no tables or columns in the DOCX), filename pattern `Hillary_Mupfumi_{Resume|CoverLetter}_{Company}_{Tag}`.
- Eligibility filters are configurable in `rules.yaml` (target titles, locations, salary floor, graduation-date requirements, sponsorship). Jobs failing a hard filter are shown as "filtered, reason X" rather than silently dropped.
- Secrets in `.env`, never committed.

## 3. Stack

- Python 3.11+, managed with `uv`
- LangGraph with a SQLite checkpointer (swap to Postgres if deployed)
- Anthropic API for LLM calls
- Chroma for a retrieval index over profile entries (projects, roles, skills)
- `httpx` for job source APIs
- Playwright for assisted form filling
- `python-docx` for resume output, plus a PDF conversion step
- SQLite for the tracker
- Streamlit for the approval queue and tracker view
- `pytest` for tests, plus an `evals/` folder for quality checks
- Contact lookup via the Apollo MCP connector already available in this environment, instead of a hand-rolled Apollo REST client (see Amendments log)

## 4. Repository layout

```
job-agent/
  CLAUDE.md
  PLAN.md
  pyproject.toml
  .env.example
  profile/
    profile.json        # source of truth for all claims
    rules.yaml           # filters, style rules, target companies
    companies.yaml        # ATS type + slug per target company
  src/jobagent/
    config.py
    state.py              # graph state (TypedDict)
    graph.py               # builds and compiles the graph
    store/db.py             # SQLite schema and access
    profile_index.py         # Chroma indexing and retrieval
    sources/                  # greenhouse.py, lever.py, ashby.py
    nodes/
      ingest.py score.py tailor.py validate.py approve.py
      apply.py contacts.py outreach.py track.py
    render/                    # docx.py, pdf.py
    ui/app.py                   # Streamlit
    cli.py                       # run, resume, list commands
  tests/
  evals/
    golden_jobs/                 # past postings + my known good resumes
```

## 5. Data model (SQLite)

- `companies(id, name, ats_type, ats_slug, notes)`
- `jobs(id, company_id, external_id, title, location, url, description, posted_at, first_seen_at, raw_json)`
- `scores(job_id, fit_score, eligibility_ok, reasons, stretch_flag, scored_at)`
- `applications(id, job_id, status, resume_path, cover_letter_path, resume_variant, submitted_at)`
- `contacts(id, company_id, name, title, source, url, relation)`
- `outreach(id, application_id, contact_id, channel, draft, status, sent_at, replied_at)`
- `events(id, job_id, type, detail, at)` for an audit log of everything the agent did

Status values for an application: `discovered`, `shortlisted`, `tailoring`, `awaiting_approval`, `ready_to_apply`, `applied`, `outreach_drafted`, `followed_up`, `interview`, `rejected`, `withdrawn`.

## 6. Graph design

State carries: job, score, chosen base resume, tailored resume, cover letter, validation result, approval decisions, contacts, outreach drafts.

Nodes and edges:

```
ingest -> score -> (shortlist filter) -> tailor -> validate
validate -> tailor (if claims fail, with the error list, max 3 loops)
validate -> approve_docs (interrupt: I review resume and letter)
approve_docs -> apply (if approved)
apply -> approve_submit (interrupt: form filled, I press submit)
approve_submit -> contacts -> outreach -> approve_outreach (interrupt) -> track
```

`ingest` and `score` run in a daily batch over all jobs. The rest run per job, one LangGraph thread per job, so approvals can wait days. Interrupts use `interrupt()` and resume with `Command(resume=...)`. Remember that a resumed node restarts from its beginning, so keep side effects out of nodes before an interrupt.

See [docs/architecture.svg](docs/architecture.svg) for the visual version of this pipeline.

## 7. Phases

### Phase 0: Setup (half a day)

- Create repo, `uv` project, `.env.example`, pre-commit, CI for tests.
- Convert my base resumes into `profile/profile.json` (I review and correct every entry). Schema: roles with bullets, projects, skills, education, each item with an id, plain-text facts, and tags.
- Fill `rules.yaml` and a first `companies.yaml` of 30 to 50 target companies. Acceptance: `profile.json` validates against a schema; I have signed off on it.

### Phase 1: Discovery and scoring (weeks 1 to 2)

- Implement Greenhouse, Lever and Ashby source clients (public no-auth JSON APIs). Normalize to the `jobs` table; dedupe by external id; record first-seen time.
- Own search layer: title keywords, location, recency, hard filters from `rules.yaml`.
- `score` node: embed and compare the job description to profile entries, then an LLM pass produces `fit_score` (0 to 100), reasons, and a stretch flag. Hard-filter failures get `eligibility_ok = false` with the reason.
- CLI: `jobagent ingest`, `jobagent shortlist` prints the ranked list.
- Streamlit page: shortlist table. Acceptance: run against all target companies; on 20 jobs I hand-label as good or bad fit, scoring agrees on at least 80 percent.

### Phase 2: Tailoring and validation (weeks 2 to 3)

- `tailor` node: pick the base variant (Data Analytics or SAP ABAP), retrieve the most relevant profile items, and rewrite bullets to mirror the posting's language without adding facts. Generate a cover letter that states gaps honestly where they exist.
- `validate` node (reflection pattern): a critic LLM plus deterministic checks. Fails on any claim not in the profile, any em or en dash, page count over 1, missing keywords it should legitimately have. On failure, returns an error list to `tailor`.
- render: DOCX and PDF with the filename pattern. Acceptance: on the golden set, zero unsupported claims across 20 runs; outputs are one page and pass an ATS-parse check (text extraction reads correctly).

### Phase 3: Approval and assisted apply (weeks 3 to 4)

- Approval queue in Streamlit: shows job, score reasons, diff between base and tailored resume, cover letter; buttons approve, edit, reject.
- `apply` node with Playwright for Greenhouse, Lever, Ashby forms: upload resume, fill standard fields from profile, answer common questions from a stored answers file, and flag unknown questions for me. Stop before submit and take a screenshot.
- Anything needing account creation, CAPTCHA, or login: mark manual and give me the link and files. Acceptance: end to end on 5 real postings with me pressing submit each time; no submit ever happens without approval (test asserts this).

### Phase 4: Contacts and outreach (weeks 4 to 5)

- `contacts` node: find hiring manager, recruiter, and analytics or engineering peers at the company through the Apollo MCP connector (or a similar API) and the job posting itself.
- `outreach` node: draft connection notes under 300 characters, each personalized to the person's role and my relevant background, plus a longer email version for recruiters.
- Prefer warm paths: flag contacts who share my schools or past employers.
- I copy or approve each message; the agent never sends on LinkedIn.
- Follow-up scheduler: a reminder 5 to 7 days after applying or reaching out; a manual "mark accepted or replied" button feeds reply-rate stats. Acceptance: drafts for 10 companies reviewed by me with under 20 percent needing rewrites.

### Phase 5: Scheduling, evals, polish (week 6)

- Daily scheduled run (cron or GitHub Actions): ingest, score, and email or notify me the shortlist.
- Metrics page: applications per week, response rate, outreach acceptance rate by template and by contact type.
- Evals folder in CI: scoring agreement, tailoring truthfulness, style rules.
- README with architecture diagram, so this doubles as a portfolio project.

## 8. Risks and mitigations

- Workday and account-gated portals: treat as manual or assisted; do not block the MVP on them.
- LLM hallucinated claims: the validator plus the golden-set eval; failing evals block merges.
- Job APIs lack search: own filtering layer; keep the company list curated.
- API costs: cache job descriptions and embeddings; only run tailoring for shortlisted and approved jobs.
- Cold outreach yield: measure it, and shift effort to referrals and warm connections if acceptance stays low.

## 9. What I need to provide

- Review and correct `profile.json`.
- Anthropic API key, and confirmation the Apollo MCP connector is enabled for contact lookup (or an Apollo API key if not).
- 30 to 50 target companies with their career page URLs.
- A file of standard application answers (work history dates, authorization answers, notice period, and similar).
- 20 past jobs I labeled as good or bad fit, and my best past tailored resumes, for the evals.

## 10. First session prompt for Claude Code

Read PLAN.md and CLAUDE.md. Start with Phase 0 and Phase 1. First propose the exact `profile.json` schema and the SQLite schema and wait for my approval. Then implement the Greenhouse source client with tests, then Lever and Ashby, then the scoring node. Work in small commits and run the tests before each one.

## 11. Amendments log

- 2026-09-22: Contact lookup switched from a custom Apollo `httpx` client to the Apollo MCP connector already available in the build environment (sections 3, 4, 7 Phase 4, 9). Falls back to a hand-rolled `httpx` client if that connector isn't present in a given environment.
- 2026-09-22: Confirmed Anthropic (not OpenAI) as the LLM provider for this project, since an existing sibling project (`mcp-servers`) uses OpenAI and could have caused confusion by copy-paste.
- 2026-09-22: `profile_index.py` (section 6, Phase 1) uses Chroma's bundled local embedding model instead of an external embeddings API, since Anthropic doesn't offer one and this avoids a second AI vendor and API key. Works fully offline once the model is cached on first use.
- 2026-09-22: `score` node (Phase 1) defaults to `claude-haiku-4-5-20251001` rather than a larger Sonnet/Opus model, since scoring runs over every ingested job daily and is a bulk classification task, not open-ended writing. Tailoring and validation (Phase 2) should use a stronger model given the higher stakes of what they produce.
