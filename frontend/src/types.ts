export interface JobMatchResult {
  fit_score: number;
  strengths: string[];
  gaps: string[];
  cover_letter: string;
}

export interface InterviewFeedback {
  feedback: string;
  improved_answer: string;
}

export interface JobSummary {
  name: string;
  fit_score: number | null;
}

export interface JobContext {
  job_description?: string | null;
  cover_letter?: string | null;
  fit_analysis?: string | null;
  interview_answers?: string | null;
}

export interface HealthResponse {
  status: string;
  version: string;
}
