import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from pydantic import BaseModel, Field

from prompts import (
    COVER_LETTER_SYSTEM,
    JOB_SCORER_SYSTEM,
    build_cover_letter_prompt,
    build_cv_context,
    build_job_block,
)
from shared_context import load_job_context, read_cv, read_projects, save_job_file

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096


class JobScoreResult(BaseModel):
    suggested_name: str = Field(
        description="A short kebab-case slug summarizing this role, e.g. "
        "'acme-backend-engineer' or 'series-b-fintech-staff-swe'. Base it on "
        "the company name (if the job description states one) and the role "
        "title/seniority — a summary of the posting, not its first line. "
        "Lowercase, words separated by single hyphens, no other punctuation, "
        "2–6 words."
    )
    fit_score: int = Field(ge=0, le=10, description="Overall fit 0–10.")
    strengths: list[str] = Field(description="Ways the CV meets or exceeds requirements.")
    gaps: list[str] = Field(description="Requirements the CV does not evidence.")


class _CoverLetterResult(BaseModel):
    cover_letter: str = Field(description="Tailored cover letter in the candidate's voice.")


def _fit_analysis_md(result: JobScoreResult) -> str:
    strengths = "\n".join(f"- {s}" for s in result.strengths)
    gaps = "\n".join(f"- {g}" for g in result.gaps)
    return f"# Fit Analysis\n\n**Score:** {result.fit_score} / 10\n\n## Strengths\n\n{strengths}\n\n## Gaps\n\n{gaps}\n"


def score_job(job_description: str, custom_instructions: str = "") -> JobScoreResult:
    """Fit score + strengths/gaps + a suggested name — no cover letter, nothing saved yet.

    The caller resolves the final job_name (typed name, or `suggested_name` if left
    blank) and then calls `save_score` to persist it, since the name isn't known
    until this call returns.
    """
    client = anthropic.Anthropic()
    cv_text = read_cv()
    projects = read_projects()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": JOB_SCORER_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": build_cv_context(cv_text, projects),
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": build_job_block(job_description, custom_instructions),
                    },
                ],
            }
        ],
        output_format=JobScoreResult,
    )

    result = response.parsed_output
    if result is None:
        raise RuntimeError(f"Model returned no output (stop_reason={response.stop_reason})")

    return result


def save_score(job_name: str, job_description: str, result: JobScoreResult) -> None:
    save_job_file(job_name, "job_description.txt", job_description)
    save_job_file(job_name, "fit_analysis.md", _fit_analysis_md(result))


def generate_cover_letter(job_name: str, custom_instructions: str = "", feedback: str = "") -> str:
    """Generate (or, with `feedback`, revise) the cover letter for an already-scored job."""
    client = anthropic.Anthropic()
    cv_text = read_cv()
    projects = read_projects()
    job_description = load_job_context(job_name).get("job_description", "")

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": COVER_LETTER_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": build_cv_context(cv_text, projects),
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": build_cover_letter_prompt(job_description, custom_instructions, feedback),
                    },
                ],
            }
        ],
        output_format=_CoverLetterResult,
    )

    result = response.parsed_output
    if result is None:
        raise RuntimeError(f"Model returned no output (stop_reason={response.stop_reason})")

    save_job_file(job_name, "cover_letter.md", result.cover_letter)
    return result.cover_letter
