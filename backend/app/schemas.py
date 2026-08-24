"""Request/response models for the API that aren't already defined in agents/."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class FetchUrlRequest(BaseModel):
    url: str


class FetchUrlResponse(BaseModel):
    text: str


class MatchRequest(BaseModel):
    job_description: str
    custom_instructions: str = ""


class JobSummary(BaseModel):
    name: str
    fit_score: int | None = None


class JobContext(BaseModel):
    job_description: str | None = None
    cover_letter: str | None = None
    fit_analysis: str | None = None
    interview_answers: str | None = None


class QuestionsResponse(BaseModel):
    questions: list[str]


class FeedbackRequest(BaseModel):
    question: str
    answer: str


class ApproveRequest(BaseModel):
    question: str
    improved_answer: str
