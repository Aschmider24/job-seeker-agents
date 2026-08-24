# Job Search Agent

A FastAPI backend + React/TypeScript frontend that use the Claude API to help
with job applications:

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
├── backend/                    # FastAPI app
│   ├── app/
│   │   ├── main.py             # routes
│   │   ├── agents/
│   │   │   ├── job_matcher.py     # fit scoring + cover letter generation
│   │   │   └── interview_coach.py # question generation + answer feedback
│   │   ├── schemas.py          # API request/response models
│   │   ├── url_fetch.py        # job posting URL -> plain text
│   │   ├── prompts.py          # all prompts, kept separate from agent logic
│   │   ├── shared_context.py   # reads/writes memory/ (CV, projects, per-job files)
│   │   └── rag.py              # ChromaDB store for approved interview answers
│   └── requirements.txt
├── frontend/                   # React + TypeScript (Vite)
│   └── src/
│       ├── api/client.ts       # talks to the backend's /api/* routes
│       └── pages/               # Job Matcher, Past Matches, Interview Coach
├── memory/                      # persistent data (gitignored)
│   ├── cv.pdf                   # your CV, read by every agent
│   ├── projects.md              # optional extra context (side projects, etc.)
│   ├── chroma_db/                # vector store of approved interview answers
│   └── jobs/<job_name>/          # per-job artifacts, created by the backend
│       ├── job_description.txt
│       ├── fit_analysis.md
│       ├── cover_letter.md
│       └── interview_answers.md
└── deploy/                      # Mac mini deployment (see deploy/README.md)
```

## Setup

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..
cp .env.example .env   # then edit .env and set your real ANTHROPIC_API_KEY

# Frontend
cd frontend
npm install
```

Add your CV to `memory/cv.pdf` (create the `memory/` directory if it doesn't
exist yet). Optionally add `memory/projects.md` with extra context — side
projects, achievements, anything not in the CV — that should also inform
scoring and cover letters.

## Use

Run both in separate terminals:

```bash
# Terminal 1 — backend (http://localhost:8000)
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (http://localhost:5173)
cd frontend
npm run dev
```

Open http://localhost:5173.

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

- The model is set in `backend/app/agents/job_matcher.py` and
  `backend/app/agents/interview_coach.py` (`MODEL = "claude-sonnet-4-6"`).
  Change it in both if you want a different model.
- `memory/` is gitignored — it holds your personal data and generated
  content, not project source.
- The backend reads `.env` from the repo root (not `backend/.env`) — see
  `backend/app/main.py`.
- In production the backend and frontend run as two separate services on
  the Mac mini; see `deploy/README.md`.
