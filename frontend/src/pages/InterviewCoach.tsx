import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { InterviewFeedback, JobSummary } from "../types";

type Phase = "idle" | "questions_ready" | "answering" | "reviewing" | "done";

export default function InterviewCoach() {
  const [searchParams] = useSearchParams();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [jobName, setJobName] = useState<string>(searchParams.get("job") ?? "");
  const [hasDescription, setHasDescription] = useState(true);

  const [phase, setPhase] = useState<Phase>("idle");
  const [questions, setQuestions] = useState<string[]>([]);
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState("");
  const [lastAnswer, setLastAnswer] = useState("");
  const [feedback, setFeedback] = useState<InterviewFeedback | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listJobs().then((list) => {
      setJobs(list);
      if (!jobName && list.length > 0) setJobName(list[0].name);
    });
    // run once on mount only — jobName here is just the initial ?job= query param
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function resetSession() {
    setPhase("idle");
    setQuestions([]);
    setIdx(0);
    setAnswer("");
    setLastAnswer("");
    setFeedback(null);
    setError(null);
  }

  function selectJob(name: string) {
    setJobName(name);
    resetSession();
    api
      .getJob(name)
      .then((ctx) => setHasDescription(!!ctx.job_description))
      .catch(() => setHasDescription(true));
  }

  useEffect(() => {
    if (jobName) selectJob(jobName);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.length]);

  async function handleGenerateQuestions() {
    setBusy(true);
    setError(null);
    try {
      const qs = await api.generateQuestions(jobName);
      setQuestions(qs);
      setPhase("questions_ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitAnswer() {
    setBusy(true);
    setError(null);
    try {
      const fb = await api.getFeedback(jobName, questions[idx], answer.trim());
      setFeedback(fb);
      setLastAnswer(answer.trim());
      setPhase("reviewing");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    if (!feedback) return;
    setBusy(true);
    setError(null);
    try {
      await api.approveAnswer(jobName, questions[idx], feedback.improved_answer);
      const next = idx + 1;
      if (next >= questions.length) {
        setPhase("done");
      } else {
        setIdx(next);
        setAnswer("");
        setFeedback(null);
        setPhase("answering");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (jobs.length === 0) {
    return (
      <div>
        <h2>Interview Coach</h2>
        <div className="info-box">No jobs found. Run the Job Matcher first to create a job entry.</div>
      </div>
    );
  }

  return (
    <div>
      <h2>Interview Coach</h2>
      <p className="caption">Generate interview questions and get live feedback on your answers.</p>

      <div className="field">
        <label>Select a job</label>
        <select value={jobName} onChange={(e) => selectJob(e.target.value)}>
          {jobs.map((j) => (
            <option key={j.name} value={j.name}>
              {j.name}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="error">{error}</div>}

      {phase === "idle" && (
        <>
          {!hasDescription ? (
            <div className="error">This job has no job description yet. Run the Job Matcher first.</div>
          ) : (
            <button className="primary" onClick={handleGenerateQuestions} disabled={busy}>
              {busy ? "Generating…" : "Generate Questions"}
            </button>
          )}
        </>
      )}

      {phase === "questions_ready" && (
        <>
          <h3>Interview questions</h3>
          <ol>
            {questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
          <div className="row" style={{ maxWidth: 320 }}>
            <button className="primary" onClick={() => setPhase("answering")}>
              Start Interview
            </button>
            <button onClick={() => setPhase("idle")}>Regenerate</button>
          </div>
        </>
      )}

      {phase === "answering" && (
        <>
          <p className="progress-text">
            Question {idx + 1} of {questions.length}
          </p>
          <h3>{questions[idx]}</h3>
          <div className="field">
            <label>Your answer</label>
            <textarea rows={8} value={answer} onChange={(e) => setAnswer(e.target.value)} />
          </div>
          <button className="primary" onClick={handleSubmitAnswer} disabled={!answer.trim() || busy}>
            {busy ? "Getting feedback…" : "Submit"}
          </button>
        </>
      )}

      {phase === "reviewing" && feedback && (
        <>
          <p className="progress-text">
            Question {idx + 1} of {questions.length}
          </p>
          <h3>{questions[idx]}</h3>

          <details>
            <summary>Your answer</summary>
            <div className="info-box">{lastAnswer}</div>
          </details>

          <h4>Feedback</h4>
          <div className="info-box">{feedback.feedback}</div>

          <h4>Improved answer</h4>
          <div className="info-box">{feedback.improved_answer}</div>

          <div className="row" style={{ maxWidth: 320 }}>
            <button className="primary" onClick={handleApprove} disabled={busy}>
              ✅ Approve & continue
            </button>
            <button onClick={() => setPhase("answering")} disabled={busy}>
              ↩ Try again
            </button>
          </div>
        </>
      )}

      {phase === "done" && (
        <>
          <div className="success">
            Interview complete! All approved answers have been saved to the knowledge base.
          </div>
          <button onClick={resetSession}>Start over</button>
        </>
      )}
    </div>
  );
}
