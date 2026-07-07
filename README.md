# Job Search Agent

Reads your CV and a set of job descriptions, then uses the Claude API
(`claude-sonnet-4-6`) to produce, per job: a fit score out of 10, a list of
strengths, a list of gaps, and a tailored cover letter — saved as Markdown.

## Layout

```
job-search-agent/
├── cv.txt        # your CV as plain text (read by the agent)
├── jobs/         # paste each job description as its own .txt file
├── output/       # one <jobname>.md report is written here per job
├── agent.py      # main script
├── prompts.py    # all prompts, kept separate from logic
└── requirements.txt
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Use

1. Put your CV text in `cv.txt`.
2. Drop one or more job descriptions into `jobs/` as `.txt` files.
3. Run:

```bash
python agent.py                          # analyze every job in jobs/
python agent.py jobs/example-backend-engineer.txt   # just one
```

Reports land in `output/<jobname>.md`.

## Notes

- The model is set in `agent.py` (`MODEL = "claude-sonnet-4-6"`). Change it
  there if you want a different model.
- The agent reads the CV from `cv.txt`. If you'd rather keep your CV as
  `cv.pdf`, install `pip install "anthropic"` (already a dependency) and send
  the PDF as a `document` content block instead of reading `cv.txt` — see the
  Anthropic PDF-input docs. The current scaffold uses plain text to stay simple.
```
