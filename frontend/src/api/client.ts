import type { HealthResponse, InterviewFeedback, JobContext, JobMatchResult, JobSummary } from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON, fall back to statusText
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),

  fetchJobUrl: (url: string) =>
    request<{ text: string }>("/api/fetch-url", {
      method: "POST",
      body: JSON.stringify({ url }),
    }).then((r) => r.text),

  listJobs: () => request<JobSummary[]>("/api/jobs"),

  getJob: (jobName: string) => request<JobContext>(`/api/jobs/${encodeURIComponent(jobName)}`),

  matchJob: (jobName: string, jobDescription: string, customInstructions: string) =>
    request<JobMatchResult>(`/api/jobs/${encodeURIComponent(jobName)}/match`, {
      method: "POST",
      body: JSON.stringify({ job_description: jobDescription, custom_instructions: customInstructions }),
    }),

  generateQuestions: (jobName: string) =>
    request<{ questions: string[] }>(`/api/jobs/${encodeURIComponent(jobName)}/questions`, {
      method: "POST",
    }).then((r) => r.questions),

  getFeedback: (jobName: string, question: string, answer: string) =>
    request<InterviewFeedback>(`/api/jobs/${encodeURIComponent(jobName)}/feedback`, {
      method: "POST",
      body: JSON.stringify({ question, answer }),
    }),

  approveAnswer: (jobName: string, question: string, improvedAnswer: string) =>
    request<void>(`/api/jobs/${encodeURIComponent(jobName)}/approve`, {
      method: "POST",
      body: JSON.stringify({ question, improved_answer: improvedAnswer }),
    }),
};
