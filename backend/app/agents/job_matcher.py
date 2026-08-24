import anthropic
from pydantic import BaseModel, Field

from app.prompts import JOB_MATCHER_SYSTEM, build_cv_context, build_job_block
from app.shared_context import read_cv, read_projects, save_job_file

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096


class JobMatchResult(BaseModel):
    fit_score: int = Field(ge=0, le=10, description="Overall fit 0–10.")
    strengths: list[str] = Field(description="Ways the CV meets or exceeds requirements.")
    gaps: list[str] = Field(description="Requirements the CV does not evidence.")
    cover_letter: str = Field(description="Tailored cover letter in the candidate's voice.")


def _fit_analysis_md(result: JobMatchResult) -> str:
    strengths = "\n".join(f"- {s}" for s in result.strengths)
    gaps = "\n".join(f"- {g}" for g in result.gaps)
    return f"# Fit Analysis\n\n**Score:** {result.fit_score} / 10\n\n## Strengths\n\n{strengths}\n\n## Gaps\n\n{gaps}\n"


def analyze_job(job_name: str, job_description: str, custom_instructions: str = "") -> JobMatchResult:
    client = anthropic.Anthropic()
    cv_text = read_cv()
    projects = read_projects()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": JOB_MATCHER_SYSTEM,
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
        output_format=JobMatchResult,
    )

    result = response.parsed_output
    if result is None:
        raise RuntimeError(f"Model returned no output (stop_reason={response.stop_reason})")

    save_job_file(job_name, "job_description.txt", job_description)
    save_job_file(job_name, "fit_analysis.md", _fit_analysis_md(result))
    save_job_file(job_name, "cover_letter.md", result.cover_letter)

    return result
