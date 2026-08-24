import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
import streamlit as st
from dotenv import load_dotenv

from agents.interview_coach import InterviewFeedback, generate_questions, get_feedback
from agents.job_matcher import JobMatchResult, analyze_job
from rag import store_answer
from shared_context import list_jobs, load_job_context

load_dotenv()

st.set_page_config(page_title="Job Search Agent", page_icon="💼", layout="wide")

NAV_PAGES = ["🎯  Job Matcher", "📁  Past Matches", "🎤  Interview Coach"]
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = NAV_PAGES[0]

page = st.sidebar.radio("Navigation", NAV_PAGES, key="nav_page", label_visibility="collapsed")

_version_file = Path(__file__).parent / "VERSION"
_version = _version_file.read_text().strip() if _version_file.exists() else "dev"
st.sidebar.caption(f"Version {_version}")


# ── URL fetching ──────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "head", "noscript", "nav", "footer"}

    def __init__(self):
        super().__init__()
        self._depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data):
        if not self._depth:
            text = data.strip()
            if text:
                self.parts.append(text)


def _fetch_job_description(url: str) -> str:
    resp = httpx.get(url, follow_redirects=True, timeout=15,
                     headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    extractor = _TextExtractor()
    extractor.feed(resp.text)
    return "\n".join(extractor.parts)


# ── helpers ───────────────────────────────────────────────────────────────────

def _show_match_result(result: JobMatchResult) -> None:
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:
        color = "green" if result.fit_score >= 7 else ("orange" if result.fit_score >= 5 else "red")
        st.markdown(f"### Fit score")
        st.markdown(f"<h1 style='color:{color}'>{result.fit_score} / 10</h1>", unsafe_allow_html=True)

    with col2:
        st.markdown("### Strengths")
        for s in result.strengths:
            st.markdown(f"- {s}")

    with col3:
        st.markdown("### Gaps")
        for g in result.gaps:
            st.markdown(f"- {g}")

    with st.expander("Cover letter", expanded=False):
        st.markdown(result.cover_letter)
        st.download_button(
            "Download cover letter",
            data=result.cover_letter,
            file_name="cover_letter.md",
            mime="text/markdown",
        )


# ── Job Matcher ───────────────────────────────────────────────────────────────

if page == "🎯  Job Matcher":
    st.title("Job Matcher")
    st.caption("Paste a job description (or provide a URL) to get a fit score, strengths/gaps analysis, and a tailored cover letter.")

    job_name = st.text_input("Job name", placeholder="e.g. stripe-backend-engineer")

    url_col, btn_col = st.columns([5, 1])
    with url_col:
        job_url = st.text_input("Job URL (optional)", placeholder="https://...")
    with btn_col:
        st.write("")
        fetch_clicked = st.button("Fetch", disabled=not job_url)

    if fetch_clicked:
        with st.spinner("Fetching job description…"):
            try:
                st.session_state["jm_desc"] = _fetch_job_description(job_url)
                st.rerun()
            except Exception as exc:
                st.error(f"Could not fetch URL: {exc}")

    if "jm_desc" not in st.session_state:
        st.session_state["jm_desc"] = ""

    job_description = st.text_area(
        "Job description",
        height=280,
        placeholder="Paste the full job description here…",
        key="jm_desc",
    )

    custom_instructions = st.text_area(
        "Instructions for this application (optional)",
        height=80,
        placeholder="e.g. keep it formal, this is a corporate/banking client · "
                     "or: casual tone, small startup · "
                     "or: don't mention relocation, emphasize the ML projects",
        key="jm_instructions",
    )

    if st.button("Analyze", type="primary", disabled=not (job_name and job_description)):
        with st.spinner("Analyzing…"):
            try:
                result = analyze_job(job_name.strip(), job_description.strip(), custom_instructions.strip())
                st.session_state[f"jm_{job_name}"] = result
                st.success(f"Saved to memory/jobs/{job_name.strip()}/")
            except Exception as exc:
                st.error(str(exc))
                result = None

        if result:
            _show_match_result(result)

    elif f"jm_{job_name}" in st.session_state:
        _show_match_result(st.session_state[f"jm_{job_name}"])


# ── Past Matches ──────────────────────────────────────────────────────────────

elif page == "📁  Past Matches":
    st.title("Past Matches")
    st.caption("Everything the Job Matcher has saved to memory/jobs/, in one place.")

    jobs = list_jobs()
    if not jobs:
        st.info("No past matches yet. Run the Job Matcher to analyze a job.")
        st.stop()

    def _fit_score(job: str) -> int | None:
        m = re.search(r"\*\*Score:\*\*\s*(\d+)\s*/\s*10", load_job_context(job).get("fit_analysis", ""))
        return int(m.group(1)) if m else None

    scores = {job: _fit_score(job) for job in jobs}

    filter_col, sort_col = st.columns([3, 2])
    with filter_col:
        search = st.text_input("Filter by name", placeholder="e.g. stripe", label_visibility="collapsed")
    with sort_col:
        sort_choice = st.selectbox("Sort by", ["Name", "Fit score (high → low)"], label_visibility="collapsed")

    visible = [j for j in jobs if search.lower() in j.lower()] if search else list(jobs)
    if sort_choice == "Fit score (high → low)":
        visible = sorted(visible, key=lambda j: (scores[j] is None, -(scores[j] or 0)))

    if not visible:
        st.info("No jobs match that filter.")

    for job in visible:
        ctx = load_job_context(job)
        score = scores[job]
        badge = f"{score} / 10" if score is not None else "—"
        with st.expander(f"**{job}**   ·   fit {badge}"):
            if "fit_analysis" in ctx:
                st.markdown(ctx["fit_analysis"])
            else:
                st.caption("No fit analysis saved for this job.")

            if "job_description" in ctx:
                with st.expander("Job description", expanded=False):
                    st.text(ctx["job_description"])

            if "cover_letter" in ctx:
                with st.expander("Cover letter", expanded=False):
                    st.markdown(ctx["cover_letter"])
                    st.download_button(
                        "Download cover letter",
                        data=ctx["cover_letter"],
                        file_name=f"{job}_cover_letter.md",
                        mime="text/markdown",
                        key=f"dl_{job}",
                    )

            if "interview_answers" in ctx:
                with st.expander("Interview answers", expanded=False):
                    st.markdown(ctx["interview_answers"])

            if st.button("Open in Interview Coach →", key=f"open_ic_{job}"):
                st.session_state["ic_job"] = job
                st.session_state["nav_page"] = "🎤  Interview Coach"
                st.rerun()


# ── Interview Coach ───────────────────────────────────────────────────────────

elif page == "🎤  Interview Coach":
    st.title("Interview Coach")
    st.caption("Generate interview questions and get live feedback on your answers.")

    # ── init session state ────────────────────────────────────────────────────
    defaults = {
        "ic_job": None,
        "ic_questions": [],
        "ic_idx": 0,
        "ic_phase": "idle",       # idle | questions_ready | answering | reviewing | done
        "ic_feedback": None,      # InterviewFeedback | None
        "ic_last_answer": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── job selector ──────────────────────────────────────────────────────────
    jobs = list_jobs()
    if not jobs:
        st.info("No jobs found. Run the Job Matcher first to create a job entry.")
        st.stop()

    default_idx = jobs.index(st.session_state.ic_job) if st.session_state.ic_job in jobs else 0
    selected = st.selectbox("Select a job", jobs, index=default_idx)

    if selected != st.session_state.ic_job:
        # reset everything when the job changes
        st.session_state.ic_job = selected
        st.session_state.ic_questions = []
        st.session_state.ic_idx = 0
        st.session_state.ic_phase = "idle"
        st.session_state.ic_feedback = None
        st.session_state.ic_last_answer = ""

    job_name = st.session_state.ic_job

    # ── phase: idle ───────────────────────────────────────────────────────────
    if st.session_state.ic_phase == "idle":
        ctx = load_job_context(job_name)
        if "job_description" not in ctx:
            st.warning("This job has no job description yet. Run the Job Matcher first.")
            st.stop()

        if st.button("Generate Questions", type="primary"):
            with st.spinner("Generating interview questions…"):
                try:
                    questions = generate_questions(job_name)
                    st.session_state.ic_questions = questions
                    st.session_state.ic_phase = "questions_ready"
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    # ── phase: questions ready ────────────────────────────────────────────────
    elif st.session_state.ic_phase == "questions_ready":
        st.markdown("### Interview questions")
        for i, q in enumerate(st.session_state.ic_questions, 1):
            st.markdown(f"**{i}.** {q}")

        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("Start Interview", type="primary"):
                st.session_state.ic_idx = 0
                st.session_state.ic_phase = "answering"
                st.rerun()
        with col2:
            if st.button("Regenerate"):
                st.session_state.ic_phase = "idle"
                st.rerun()

    # ── phase: answering ──────────────────────────────────────────────────────
    elif st.session_state.ic_phase == "answering":
        questions = st.session_state.ic_questions
        idx = st.session_state.ic_idx
        total = len(questions)

        st.progress((idx) / total, text=f"Question {idx + 1} of {total}")
        st.markdown(f"### {questions[idx]}")

        answer = st.text_area("Your answer", height=180, key=f"answer_{idx}")

        if st.button("Submit", type="primary", disabled=not answer.strip()):
            with st.spinner("Getting feedback…"):
                try:
                    feedback = get_feedback(questions[idx], answer.strip(), job_name)
                    st.session_state.ic_feedback = feedback
                    st.session_state.ic_last_answer = answer.strip()
                    st.session_state.ic_phase = "reviewing"
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    # ── phase: reviewing ──────────────────────────────────────────────────────
    elif st.session_state.ic_phase == "reviewing":
        questions = st.session_state.ic_questions
        idx = st.session_state.ic_idx
        total = len(questions)
        feedback: InterviewFeedback = st.session_state.ic_feedback

        st.progress((idx) / total, text=f"Question {idx + 1} of {total}")
        st.markdown(f"### {questions[idx]}")

        with st.expander("Your answer", expanded=False):
            st.write(st.session_state.ic_last_answer)

        st.markdown("#### Feedback")
        st.info(feedback.feedback)

        st.markdown("#### Improved answer")
        st.success(feedback.improved_answer)

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✅  Approve & continue", type="primary"):
                store_answer(job_name, questions[idx], feedback.improved_answer)
                next_idx = idx + 1
                if next_idx >= total:
                    st.session_state.ic_phase = "done"
                else:
                    st.session_state.ic_idx = next_idx
                    st.session_state.ic_phase = "answering"
                    st.session_state.ic_feedback = None
                st.rerun()
        with col2:
            if st.button("↩  Try again"):
                st.session_state.ic_phase = "answering"
                st.session_state.ic_feedback = None
                st.rerun()

    # ── phase: done ───────────────────────────────────────────────────────────
    elif st.session_state.ic_phase == "done":
        st.success("Interview complete! All approved answers have been saved to the knowledge base.")
        if st.button("Start over"):
            st.session_state.ic_phase = "idle"
            st.session_state.ic_questions = []
            st.session_state.ic_idx = 0
            st.session_state.ic_feedback = None
            st.rerun()
