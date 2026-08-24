import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path as PathParam
from fastapi.middleware.cors import CORSMiddleware

from app.agents.interview_coach import InterviewFeedback, generate_questions, get_feedback
from app.agents.job_matcher import JobMatchResult, analyze_job
from app.rag import store_answer
from app.schemas import (
    ApproveRequest,
    FeedbackRequest,
    FetchUrlRequest,
    FetchUrlResponse,
    HealthResponse,
    JobContext,
    JobSummary,
    MatchRequest,
    QuestionsResponse,
)
from app.shared_context import append_interview_answer, list_jobs, load_job_context, parse_fit_score
from app.url_fetch import fetch_job_description

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")

app = FastAPI(title="Job Search Agent API")

_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# job_name arrives as a URL path segment now (was a plain Streamlit text
# input before) — keep it restricted to safe filesystem-friendly characters.
_JOB_NAME_RE = re.compile(r"^[\w.-]+$")


def _job_name(job_name: str = PathParam(..., description="Job identifier")) -> str:
    if not _JOB_NAME_RE.match(job_name):
        raise HTTPException(422, "job_name may only contain letters, numbers, '.', '_', '-'.")
    return job_name


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    version_file = REPO_ROOT / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "dev"
    return HealthResponse(status="ok", version=version)


@app.post("/api/fetch-url", response_model=FetchUrlResponse)
def fetch_url(body: FetchUrlRequest) -> FetchUrlResponse:
    try:
        return FetchUrlResponse(text=fetch_job_description(body.url))
    except Exception as exc:
        raise HTTPException(400, f"Could not fetch URL: {exc}")


@app.get("/api/jobs", response_model=list[JobSummary])
def get_jobs() -> list[JobSummary]:
    summaries = []
    for name in list_jobs():
        ctx = load_job_context(name)
        fit_score = parse_fit_score(ctx["fit_analysis"]) if "fit_analysis" in ctx else None
        summaries.append(JobSummary(name=name, fit_score=fit_score))
    return summaries


@app.get("/api/jobs/{job_name}", response_model=JobContext)
def get_job(job_name: str = PathParam(...)) -> JobContext:
    job_name = _job_name(job_name)
    return JobContext(**load_job_context(job_name))


@app.post("/api/jobs/{job_name}/match", response_model=JobMatchResult)
def match_job(body: MatchRequest, job_name: str = PathParam(...)) -> JobMatchResult:
    job_name = _job_name(job_name)
    try:
        return analyze_job(job_name, body.job_description, body.custom_instructions)
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/jobs/{job_name}/questions", response_model=QuestionsResponse)
def get_questions(job_name: str = PathParam(...)) -> QuestionsResponse:
    job_name = _job_name(job_name)
    ctx = load_job_context(job_name)
    if "job_description" not in ctx:
        raise HTTPException(400, "This job has no job description yet. Run the Job Matcher first.")
    try:
        return QuestionsResponse(questions=generate_questions(job_name))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/jobs/{job_name}/feedback", response_model=InterviewFeedback)
def post_feedback(body: FeedbackRequest, job_name: str = PathParam(...)) -> InterviewFeedback:
    job_name = _job_name(job_name)
    try:
        return get_feedback(body.question, body.answer, job_name)
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/jobs/{job_name}/approve", status_code=204)
def approve_answer(body: ApproveRequest, job_name: str = PathParam(...)) -> None:
    job_name = _job_name(job_name)
    store_answer(job_name, body.question, body.improved_answer)
    append_interview_answer(job_name, body.question, body.improved_answer)
