# Job Search Agent

A Streamlit app that uses the Claude API to help with job applications:

- **Job Matcher** — paste (or fetch by URL) a job description and get a fit
  score out of 10, strengths, gaps, and a tailored cover letter.
- **Interview Coach** — generates interview questions for a job you've
  already matched, then reviews your answers live, gives feedback, and
  proposes an improved version. Approved answers are stored in a small vector
  DB (ChromaDB) so future feedback can draw on your best past answers.

Everything the agents know about you — your CV, side projects, and each job's
description/cover letter/interview answers — lives under `memory/`, so it
persists across sessions.

## Layout

```
job-search-agent/
├── app.py                    # Streamlit UI (Job Matcher + Interview Coach)
├── agents/
│   ├── job_matcher.py         # fit scoring + cover letter generation
│   └── interview_coach.py     # question generation + answer feedback
├── prompts.py                 # all prompts, kept separate from agent logic
├── shared_context.py          # reads/writes memory/ (CV, projects, per-job files)
├── rag.py                     # ChromaDB store for approved interview answers
├── memory/                    # persistent data (gitignored)
│   ├── cv.pdf                 # your CV, read by every agent
│   ├── projects.md            # optional extra context (side projects, etc.)
│   ├── chroma_db/              # vector store of approved interview answers
│   └── jobs/<job_name>/       # per-job artifacts, created by the app
│       ├── job_description.txt
│       ├── fit_analysis.md
│       ├── cover_letter.md
│       └── interview_answers.md
├── agent.py                   # standalone CLI: batch-analyze jobs/*.txt (legacy)
└── requirements.txt
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env and set your real ANTHROPIC_API_KEY
```

Add your CV to `memory/cv.pdf` (create the `memory/` directory if it doesn't
exist yet). Optionally add `memory/projects.md` with extra context — side
projects, achievements, anything not in the CV — that should also inform
scoring and cover letters.

## Use

```bash
streamlit run app.py
```

1. **Job Matcher** — enter a job name, paste a job description (or fetch one
   from a URL), and optionally add custom instructions (tone, what to
   emphasize/avoid). Click **Analyze**. This saves the job description, fit
   analysis, and cover letter to `memory/jobs/<job_name>/`.
2. **Interview Coach** — pick a job you've already matched, generate
   questions, and answer them one at a time. Each answer gets feedback and an
   improved version; approving one stores it in the vector DB and saves it to
   `memory/jobs/<job_name>/interview_answers.md` so later feedback (for this
   job or others) can reference your best past answers.

## Notes

- The model is set in `agents/job_matcher.py` and `agents/interview_coach.py`
  (`MODEL = "claude-sonnet-4-6"`). Change it in both if you want a different
  model.
- `memory/` and `jobs/` are gitignored — they hold your personal data and
  generated content, not project source.
- `agent.py` is a standalone CLI left over from an earlier version of this
  project: it reads `cv.pdf`/`cv.txt` and `jobs/*.txt` directly from the repo
  root (not `memory/`) and writes one Markdown report per job to `output/`.
  It doesn't share state with the Streamlit app. Run it with
  `python agent.py [file-or-url ...]` if you just want quick one-off reports
  without the UI.
