import anthropic
from pydantic import BaseModel

from app.prompts import (
    QUESTION_GEN_SYSTEM,
    INTERVIEW_FEEDBACK_SYSTEM,
    build_question_gen_prompt,
    build_feedback_prompt,
)
from app.shared_context import read_cv, read_projects, load_job_context
from app.rag import retrieve_similar

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048


class QuestionList(BaseModel):
    questions: list[str]


class InterviewFeedback(BaseModel):
    feedback: str
    improved_answer: str


def generate_questions(job_name: str) -> list:
    """Phase 1 — generate interview questions for the given job."""
    client = anthropic.Anthropic()
    cv_text = read_cv()
    projects = read_projects()
    ctx = load_job_context(job_name)

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=QUESTION_GEN_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": build_question_gen_prompt(
                    cv_text=cv_text,
                    projects=projects,
                    job_description=ctx.get("job_description", ""),
                    cover_letter=ctx.get("cover_letter", ""),
                ),
            }
        ],
        output_format=QuestionList,
    )

    result = response.parsed_output
    if result is None:
        raise RuntimeError("Failed to generate questions.")
    return result.questions


def get_feedback(question: str, user_answer: str, job_name: str) -> InterviewFeedback:
    """Phase 2 — return feedback and an improved answer for one question."""
    client = anthropic.Anthropic()
    similar = retrieve_similar(question)

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=INTERVIEW_FEEDBACK_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": build_feedback_prompt(question, user_answer, similar),
            }
        ],
        output_format=InterviewFeedback,
    )

    result = response.parsed_output
    if result is None:
        raise RuntimeError("Failed to get feedback.")
    return result
