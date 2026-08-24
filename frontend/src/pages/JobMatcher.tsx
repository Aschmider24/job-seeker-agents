import { useState } from "react";
import { api } from "../api/client";
import type { JobMatchResult } from "../types";

function fitColor(score: number): string {
  if (score >= 7) return "var(--green)";
  if (score >= 5) return "var(--orange)";
  return "var(--red)";
}

function downloadCoverLetter(text: string) {
  const blob = new Blob([text], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "cover_letter.md";
  a.click();
  URL.revokeObjectURL(url);
}

export default function JobMatcher() {
  const [jobName, setJobName] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");
  const [fetching, setFetching] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [result, setResult] = useState<JobMatchResult | null>(null);

  async function handleFetchUrl() {
    setFetching(true);
    setError(null);
    try {
      const text = await api.fetchJobUrl(jobUrl);
      setJobDescription(text);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setFetching(false);
    }
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    setError(null);
    setSavedMsg(null);
    try {
      const r = await api.matchJob(jobName.trim(), jobDescription.trim(), customInstructions.trim());
      setResult(r);
      setSavedMsg(`Saved to memory/jobs/${jobName.trim()}/`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  }

  const canAnalyze = jobName.trim() && jobDescription.trim() && !analyzing;

  return (
    <div>
      <h2>Job Matcher</h2>
      <p className="caption">
        Paste a job description (or provide a URL) to get a fit score, strengths/gaps analysis, and a
        tailored cover letter.
      </p>

      <div className="field">
        <label>Job name</label>
        <input
          type="text"
          placeholder="e.g. stripe-backend-engineer"
          value={jobName}
          onChange={(e) => setJobName(e.target.value)}
        />
      </div>

      <div className="row field">
        <div>
          <label>Job URL (optional)</label>
          <input type="text" placeholder="https://..." value={jobUrl} onChange={(e) => setJobUrl(e.target.value)} />
        </div>
        <button onClick={handleFetchUrl} disabled={!jobUrl || fetching}>
          {fetching ? "Fetching…" : "Fetch"}
        </button>
      </div>

      <div className="field">
        <label>Job description</label>
        <textarea
          rows={12}
          placeholder="Paste the full job description here…"
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Instructions for this application (optional)</label>
        <textarea
          rows={3}
          placeholder="e.g. keep it formal, this is a corporate/banking client · or: casual tone, small startup · or: don't mention relocation, emphasize the ML projects"
          value={customInstructions}
          onChange={(e) => setCustomInstructions(e.target.value)}
        />
      </div>

      <button className="primary" onClick={handleAnalyze} disabled={!canAnalyze}>
        {analyzing ? "Analyzing…" : "Analyze"}
      </button>

      {error && <div className="error">{error}</div>}
      {savedMsg && <div className="success">{savedMsg}</div>}

      {result && (
        <>
          <hr className="divider" />
          <div className="columns">
            <div>
              <h3>Fit score</h3>
              <div className="fit-score" style={{ color: fitColor(result.fit_score) }}>
                {result.fit_score} / 10
              </div>
            </div>
            <div>
              <h3>Strengths</h3>
              <ul>
                {result.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Gaps</h3>
              <ul>
                {result.gaps.map((g, i) => (
                  <li key={i}>{g}</li>
                ))}
              </ul>
            </div>
          </div>

          <details>
            <summary>Cover letter</summary>
            <div className="info-box">{result.cover_letter}</div>
            <button onClick={() => downloadCoverLetter(result.cover_letter)}>Download cover letter</button>
          </details>
        </>
      )}
    </div>
  );
}
