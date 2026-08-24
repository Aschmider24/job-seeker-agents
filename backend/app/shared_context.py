"""Assembles context from memory/ for any agent."""

import os
import re
from pathlib import Path

from pypdf import PdfReader

# memory/ lives at the repo root (backend/app/shared_context.py -> app -> backend -> root),
# shared with pull-memory.sh/push-memory.sh and .gitignore. Overridable via env var.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", REPO_ROOT / "memory"))
CV_PATH = MEMORY_DIR / "cv.pdf"
PROJECTS_PATH = MEMORY_DIR / "projects.md"
JOBS_DIR = MEMORY_DIR / "jobs"

_FIT_SCORE_RE = re.compile(r"\*\*Score:\*\*\s*(\d+)\s*/\s*10")


def read_cv() -> str:
    if not CV_PATH.exists():
        raise FileNotFoundError(f"CV not found at {CV_PATH}. Add cv.pdf to memory/.")
    reader = PdfReader(CV_PATH)
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def read_projects() -> str:
    if not PROJECTS_PATH.exists():
        return ""
    return PROJECTS_PATH.read_text(encoding="utf-8").strip()


def load_job_context(job_name: str) -> dict:
    """Return {key: content} for files that exist in memory/jobs/<job_name>/."""
    job_dir = JOBS_DIR / job_name
    mapping = {
        "job_description": "job_description.txt",
        "cover_letter": "cover_letter.md",
        "fit_analysis": "fit_analysis.md",
        "interview_answers": "interview_answers.md",
    }
    return {
        key: (job_dir / filename).read_text(encoding="utf-8").strip()
        for key, filename in mapping.items()
        if (job_dir / filename).exists()
    }


def save_job_file(job_name: str, filename: str, content: str) -> None:
    job_dir = JOBS_DIR / job_name
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / filename).write_text(content, encoding="utf-8")


def append_interview_answer(job_name: str, question: str, approved_answer: str) -> None:
    """Append one approved Q/A pair to memory/jobs/<job_name>/interview_answers.md."""
    job_dir = JOBS_DIR / job_name
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / "interview_answers.md"
    entry = f"## {question}\n\n{approved_answer}\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8").rstrip()
        path.write_text(f"{existing}\n\n{entry}", encoding="utf-8")
    else:
        path.write_text(f"# Interview Answers\n\n{entry}", encoding="utf-8")


def list_jobs() -> list:
    if not JOBS_DIR.exists():
        return []
    return sorted(d.name for d in JOBS_DIR.iterdir() if d.is_dir())


def parse_fit_score(fit_analysis_md: str) -> int | None:
    """Extract the integer fit score from a fit_analysis.md's '**Score:** N / 10' line."""
    m = _FIT_SCORE_RE.search(fit_analysis_md)
    return int(m.group(1)) if m else None
