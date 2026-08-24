import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { JobContext, JobSummary } from "../types";

function downloadText(text: string, filename: string) {
  const blob = new Blob([text], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function PastMatches() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortByScore, setSortByScore] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [contexts, setContexts] = useState<Record<string, JobContext>>({});

  useEffect(() => {
    api
      .listJobs()
      .then(setJobs)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  async function toggleExpand(name: string) {
    if (expanded === name) {
      setExpanded(null);
      return;
    }
    setExpanded(name);
    if (!contexts[name]) {
      try {
        const ctx = await api.getJob(name);
        setContexts((prev) => ({ ...prev, [name]: ctx }));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }
  }

  if (error) return <div className="error">{error}</div>;
  if (jobs === null) return <p className="caption">Loading…</p>;

  if (jobs.length === 0) {
    return (
      <div>
        <h2>Past Matches</h2>
        <div className="info-box">No past matches yet. Run the Job Matcher to analyze a job.</div>
      </div>
    );
  }

  let visible = search ? jobs.filter((j) => j.name.toLowerCase().includes(search.toLowerCase())) : jobs;
  if (sortByScore) {
    visible = [...visible].sort((a, b) => (b.fit_score ?? -1) - (a.fit_score ?? -1));
  }

  return (
    <div>
      <h2>Past Matches</h2>
      <p className="caption">Everything the Job Matcher has saved to memory/jobs/, in one place.</p>

      <div className="row field">
        <input
          type="text"
          placeholder="Filter by name, e.g. stripe"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={sortByScore ? "score" : "name"} onChange={(e) => setSortByScore(e.target.value === "score")}>
          <option value="name">Sort: Name</option>
          <option value="score">Sort: Fit score (high → low)</option>
        </select>
      </div>

      {visible.length === 0 && <div className="info-box">No jobs match that filter.</div>}

      {visible.map((job) => {
        const ctx = contexts[job.name];
        const badge = job.fit_score !== null ? `${job.fit_score} / 10` : "—";
        return (
          <div className="card" key={job.name}>
            <div className="card-header" onClick={() => toggleExpand(job.name)}>
              <strong>{job.name}</strong>
              <span className="badge">fit {badge}</span>
            </div>
            {expanded === job.name && (
              <div style={{ marginTop: 12 }}>
                {!ctx ? (
                  <p className="caption">Loading…</p>
                ) : (
                  <>
                    {ctx.fit_analysis ? (
                      <div className="info-box">{ctx.fit_analysis}</div>
                    ) : (
                      <p className="caption">No fit analysis saved for this job.</p>
                    )}

                    {ctx.job_description && (
                      <details>
                        <summary>Job description</summary>
                        <div className="info-box">{ctx.job_description}</div>
                      </details>
                    )}

                    {ctx.cover_letter && (
                      <details>
                        <summary>Cover letter</summary>
                        <div className="info-box">{ctx.cover_letter}</div>
                        <button onClick={() => downloadText(ctx.cover_letter!, `${job.name}_cover_letter.md`)}>
                          Download cover letter
                        </button>
                      </details>
                    )}

                    {ctx.interview_answers && (
                      <details>
                        <summary>Interview answers</summary>
                        <div className="info-box">{ctx.interview_answers}</div>
                      </details>
                    )}

                    <div style={{ marginTop: 12 }}>
                      <button onClick={() => navigate(`/interview-coach?job=${encodeURIComponent(job.name)}`)}>
                        Open in Interview Coach →
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
