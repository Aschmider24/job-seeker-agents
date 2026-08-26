"""Assembles context from memory/ for any agent."""

import re
import shutil
from pathlib import Path

from pypdf import PdfReader

MEMORY_DIR = Path(__file__).parent / "memory"
CV_PATH = MEMORY_DIR / "cv.pdf"
PROJECTS_PATH = MEMORY_DIR / "projects.md"
JOBS_DIR = MEMORY_DIR / "jobs"
EXTRA_DIR = MEMORY_DIR / "extra"

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


def save_cv(data: bytes) -> None:
    """Replace memory/cv.pdf with newly uploaded bytes."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    CV_PATH.write_bytes(data)


def read_projects_text() -> str:
    """Raw contents of memory/projects.md, for display/editing (no extra files)."""
    if not PROJECTS_PATH.exists():
        return ""
    return PROJECTS_PATH.read_text(encoding="utf-8").strip()


def save_projects_text(content: str) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_PATH.write_text(content.strip(), encoding="utf-8")


def _extra_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def list_extra_files() -> list:
    """Names of everything saved under memory/extra/ (uploaded files and pasted notes)."""
    if not EXTRA_DIR.exists():
        return []
    return sorted(p.name for p in EXTRA_DIR.iterdir() if p.is_file())


def read_extra_file(filename: str) -> str:
    """Extracted text of one file in memory/extra/, for previewing."""
    path = (EXTRA_DIR / Path(filename).name)
    if not path.exists():
        return ""
    return _extra_text(path)


def save_extra_file(filename: str, data: bytes) -> None:
    """Save an uploaded reference file (PDF, txt, md, …) under memory/extra/."""
    EXTRA_DIR.mkdir(parents=True, exist_ok=True)
    (EXTRA_DIR / Path(filename).name).write_bytes(data)


def save_extra_note(title: str, content: str) -> str:
    """Save pasted text as a new .md file under memory/extra/. Returns the filename used."""
    EXTRA_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50].strip("-") or "note"
    candidate, n = f"{slug}.md", 2
    while (EXTRA_DIR / candidate).exists():
        candidate = f"{slug}-{n}.md"
        n += 1
    (EXTRA_DIR / candidate).write_text(content.strip(), encoding="utf-8")
    return candidate


def delete_extra_file(filename: str) -> None:
    path = EXTRA_DIR / Path(filename).name
    if path.exists():
        path.unlink()


def read_projects() -> str:
    """projects.md plus everything saved under memory/extra/ — this is what agents see."""
    parts = []
    base = read_projects_text()
    if base:
        parts.append(base)
    for filename in list_extra_files():
        text = read_extra_file(filename)
        if text:
            parts.append(f"### {filename}\n\n{text}")
    return "\n\n".join(parts)


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


def delete_job(job_name: str) -> None:
    """Permanently remove memory/jobs/<job_name>/ and everything saved under it."""
    job_dir = _job_dir(job_name)
    if not job_dir.exists():
        raise FileNotFoundError(f"No saved job named {job_name!r}.")
    shutil.rmtree(job_dir)


def list_jobs() -> list:
    if not JOBS_DIR.exists():
        return []
    return sorted(d.name for d in JOBS_DIR.iterdir() if d.is_dir())
