import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from pydantic import BaseModel

from prompts import (
    QUESTION_GEN_SYSTEM,
    INTERVIEW_FEEDBACK_SYSTEM,
    BULK_ANSWER_SYSTEM,
    build_question_gen_prompt,
    build_feedback_prompt,
    build_bulk_answer_prompt,
    build_answer_revision_prompt,
)
from shared_context import read_cv, read_projects, load_job_context
from rag import retrieve_similar

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048
BULK_MAX_TOKENS = 4096


class QuestionList(BaseModel):
    questions: list[str]


class InterviewFeedback(BaseModel):
    feedback: str
    improved_answer: str


class _BulkAnswers(BaseModel):
    answers: list[str]


class _SingleAnswer(BaseModel):
    answer: str


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


def answer_questions(
    job_name: str, questions: list, custom_instructions: str = "", feedback: str = ""
) -> list:
    """Write a ready-to-copy first-person answer for every question at once.

    `custom_instructions` is the same per-application tone/emphasis instructions
    used for the cover letter. `feedback` (optional) applies to all answers in
    this call — used when the user comments on the whole batch and regenerates it.
    """
    client = anthropic.Anthropic()
    cv_text = read_cv()
    projects = read_projects()
    ctx = load_job_context(job_name)

    response = client.messages.parse(
        model=MODEL,
        max_tokens=BULK_MAX_TOKENS,
        system=BULK_ANSWER_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": build_bulk_answer_prompt(
                    cv_text=cv_text,
                    projects=projects,
                    job_description=ctx.get("job_description", ""),
                    questions=questions,
                    custom_instructions=custom_instructions,
                    feedback=feedback,
                ),
            }
        ],
        output_format=_BulkAnswers,
    )

    result = response.parsed_output
    if result is None or len(result.answers) != len(questions):
        raise RuntimeError("Failed to generate a reply for every question.")
    return result.answers


def revise_answer(
    job_name: str,
    question: str,
    previous_answer: str,
    feedback: str,
    custom_instructions: str = "",
) -> str:
    """Rewrite a single reply, incorporating the candidate's comments."""
    client = anthropic.Anthropic()
    cv_text = read_cv()
    projects = read_projects()
    ctx = load_job_context(job_name)

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=BULK_ANSWER_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": build_answer_revision_prompt(
                    cv_text=cv_text,
                    projects=projects,
                    job_description=ctx.get("job_description", ""),
                    question=question,
                    previous_answer=previous_answer,
                    feedback=feedback,
                    custom_instructions=custom_instructions,
                ),
            }
        ],
        output_format=_SingleAnswer,
    )

    result = response.parsed_output
    if result is None:
        raise RuntimeError("Failed to revise the answer.")
    return result.answer
