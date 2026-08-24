import { useEffect, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import JobMatcher from "./pages/JobMatcher";
import PastMatches from "./pages/PastMatches";
import InterviewCoach from "./pages/InterviewCoach";

export default function App() {
  const [version, setVersion] = useState("dev");

  useEffect(() => {
    api.health().then((h) => setVersion(h.version)).catch(() => {});
  }, []);

  return (
    <BrowserRouter>
      <nav className="sidebar">
        <h1>💼 Job Search Agent</h1>
        <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
          🎯 Job Matcher
        </NavLink>
        <NavLink to="/past-matches" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
          📁 Past Matches
        </NavLink>
        <NavLink to="/interview-coach" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
          🎤 Interview Coach
        </NavLink>
        <span className="version">Version {version}</span>
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<JobMatcher />} />
          <Route path="/past-matches" element={<PastMatches />} />
          <Route path="/interview-coach" element={<InterviewCoach />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
