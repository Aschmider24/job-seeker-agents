"""Assembles context from memory/ for any agent."""

from pathlib import Path

from pypdf import PdfReader

MEMORY_DIR = Path(__file__).parent / "memory"
CV_PATH = MEMORY_DIR / "cv.pdf"
PROJECTS_PATH = MEMORY_DIR / "projects.md"
JOBS_DIR = MEMORY_DIR / "jobs"


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


def list_jobs() -> list:
    if not JOBS_DIR.exists():
        return []
    return sorted(d.name for d in JOBS_DIR.iterdir() if d.is_dir())
