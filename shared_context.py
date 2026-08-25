"""Assembles context from memory/ for any agent."""

from pathlib import Path

from pypdf import PdfReader

MEMORY_DIR = Path(__file__).parent / "memory"
CV_PATH = MEMORY_DIR / "cv.pdf"
PROJECTS_PATH = MEMORY_DIR / "projects.md"
JOBS_DIR = MEMORY_DIR / "jobs"

_JOB_CONTEXT_FILES = {
    "job_description": "job_description.txt",
    "cover_letter": "cover_letter.md",
    "fit_analysis": "fit_analysis.md",
    "interview_answers": "interview_answers.md",
    "quick_replies": "quick_replies.md",
}


def _job_dir(job_name: str) -> Path:
    """Resolve memory/jobs/<job_name>, rejecting names that would escape JOBS_DIR."""
    job_dir = (JOBS_DIR / job_name).resolve()
    jobs_root = JOBS_DIR.resolve()
    if job_dir != jobs_root and jobs_root not in job_dir.parents:
        raise ValueError(f"Invalid job name: {job_name!r}")
    return job_dir


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
    job_dir = _job_dir(job_name)
    return {
        key: (job_dir / filename).read_text(encoding="utf-8").strip()
        for key, filename in _JOB_CONTEXT_FILES.items()
        if (job_dir / filename).exists()
    }


def save_job_file(job_name: str, filename: str, content: str) -> None:
    job_dir = _job_dir(job_name)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / filename).write_text(content, encoding="utf-8")


def rename_job(old_name: str, new_name: str) -> None:
    """Rename memory/jobs/<old_name>/ to memory/jobs/<new_name>/."""
    old_dir = _job_dir(old_name)
    new_dir = _job_dir(new_name)
    if not old_dir.exists():
        raise FileNotFoundError(f"No saved job named {old_name!r}.")
    if old_dir == new_dir:
        return
    if new_dir.exists():
        raise FileExistsError(f"A job named {new_name!r} already exists.")
    new_dir.parent.mkdir(parents=True, exist_ok=True)
    old_dir.rename(new_dir)


def list_jobs() -> list:
    if not JOBS_DIR.exists():
        return []
    return sorted(d.name for d in JOBS_DIR.iterdir() if d.is_dir())
