from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
import streamlit as st
from dotenv import load_dotenv

from agents.interview_coach import (
    InterviewFeedback,
    answer_questions,
    generate_questions,
    get_feedback,
    revise_answer,
)
from agents.job_matcher import JobScoreResult, generate_cover_letter, save_score, score_job
from rag import store_answer
from shared_context import list_jobs, load_job_context, rename_job, save_job_file

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

def _unique_slug(name: str, exclude: set | None = None) -> str:
    """Slugify `name` (e.g. the model's suggested_name) and dedupe against existing jobs."""
    exclude = exclude or set()
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50].strip("-")
    if not slug:
        slug = "job"

    existing = set(list_jobs()) - exclude
    candidate = slug
    n = 2
    while candidate in existing:
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


def _show_fit_score(result: JobScoreResult) -> None:
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:
        color = "green" if result.fit_score >= 7 else ("orange" if result.fit_score >= 5 else "red")
        st.markdown("### Fit score")
        st.markdown(f"<h1 style='color:{color}'>{result.fit_score} / 10</h1>", unsafe_allow_html=True)

    with col2:
        st.markdown("### Strengths")
        for s in result.strengths:
            st.markdown(f"- {s}")

    with col3:
        st.markdown("### Gaps")
        for g in result.gaps:
            st.markdown(f"- {g}")


def _comment_widget(pending_key: str, history_key: str, on_send, item_label: str = "this") -> None:
    """Comment box + pending chips + a Send button that only appears once there's something to send.

    `on_send(all_comments)` runs when Send is pressed (all comments ever left on this
    item, oldest first) and is expected to regenerate the content and store it itself.
    """
    st.session_state.setdefault(pending_key, [])
    st.session_state.setdefault(history_key, [])
    nonce_key = f"{pending_key}__nonce"
    st.session_state.setdefault(nonce_key, 0)
    pending = st.session_state[pending_key]

    for c in pending:
        st.caption(f"💬 {c}")

    input_key = f"{pending_key}__input_{st.session_state[nonce_key]}"
    new_comment = st.text_input(
        "Add a comment",
        key=input_key,
        label_visibility="collapsed",
        placeholder=f"Suggest a change to {item_label}…",
    )
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("Add comment", key=f"{pending_key}__add", disabled=not new_comment.strip()):
            pending.append(new_comment.strip())
            st.session_state[nonce_key] += 1
            st.rerun()
    with c2:
        if pending and st.button("Send", key=f"{pending_key}__send", type="primary"):
            combined = st.session_state[history_key] + pending
            with st.spinner("Applying your feedback…"):
                try:
                    on_send(list(combined))
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.session_state[history_key] = combined
                    st.session_state[pending_key] = []
                    st.rerun()


def _save_quick_replies(job_name: str, qa_slots: list) -> None:
    answered = [s for s in qa_slots if s.get("reply")]
    if not answered:
        return
    md = "\n\n".join(f"**Q{i}. {s['question']}**\n\n{s['reply']}" for i, s in enumerate(answered, 1))
    save_job_file(job_name, "quick_replies.md", md)


def _clear_state_with_prefixes(*prefixes: str) -> None:
    for k in list(st.session_state.keys()):
        if k.startswith(prefixes):
            del st.session_state[k]


# ── Job Matcher ───────────────────────────────────────────────────────────────

if page == "🎯  Job Matcher":
    st.title("Job Matcher")
    st.caption(
        "Paste a job description (or provide a URL) to get a fit score first. "
        "From there, generate a cover letter and/or draft replies to the "
        "application form's own questions — everything the AI writes can be "
        "refined with comments."
    )

    # ── init session state ────────────────────────────────────────────────────
    jm_defaults = {
        "jm_active_job": None,     # str | None — job currently being worked on
        "jm_score": None,          # JobScoreResult | None
        "jm_cover_letter": None,   # str | None
        "jm_qa_slots": [],         # list[{"question": str, "reply": str | None}]
    }
    for k, v in jm_defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    job_name_field = st.text_input(
        "Job name",
        key="jm_name_field",
        placeholder="optional — auto-filled from the description if left blank",
    )

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

    if st.button("Analyze", type="primary", disabled=not job_description.strip()):
        prior_active = st.session_state.jm_active_job

        with st.spinner("Analyzing…"):
            try:
                score = score_job(job_description.strip())
            except Exception as exc:
                st.error(str(exc))
                score = None

        if score:
            typed_name = job_name_field.strip()
            if typed_name:
                job_name = typed_name
            elif prior_active:
                job_name = prior_active  # blank field on re-analyze = keep updating the same job
            else:
                job_name = _unique_slug(score.suggested_name)

            save_score(job_name, job_description.strip(), score)
            st.session_state.jm_active_job = job_name
            st.session_state.jm_score = score
            st.session_state.jm_cover_letter = None
            st.session_state.jm_qa_slots = []
            # drop any comment / compose-box state left over from a previous
            # job's cover letter or application questions
            _clear_state_with_prefixes(
                "jm_cl_pending", "jm_cl_history",
                "jm_qa_pending_", "jm_qa_history_", "jm_qa_input_",
            )
            st.rerun()

    active = st.session_state.jm_active_job
    score = st.session_state.jm_score

    if active and score:
        _show_fit_score(score)

        # ── rename (works at any time once a job has been saved) ─────────────
        with st.expander(f"📁 Saved as **{active}** — rename"):
            new_name = st.text_input("New name", value=active, key=f"jm_rename_field__{active}")
            if new_name.strip() and new_name.strip() != active and st.button("Rename"):
                try:
                    rename_job(active, new_name.strip())
                    st.session_state.jm_active_job = new_name.strip()
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        custom_instructions = st.text_area(
            "Instructions for this application (optional)",
            height=80,
            placeholder="e.g. keep it formal, this is a corporate/banking client · "
                         "or: casual tone, small startup · "
                         "or: don't mention relocation, emphasize the ML projects",
            key="jm_instructions",
        )

        # ── what's next: cover letter and/or application-form questions ───────
        st.markdown("### What's next?")
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.jm_cover_letter is None:
                if st.button("✉️  Generate cover letter", type="primary"):
                    with st.spinner("Writing cover letter…"):
                        try:
                            letter = generate_cover_letter(active, custom_instructions.strip())
                        except Exception as exc:
                            st.error(str(exc))
                        else:
                            st.session_state.jm_cover_letter = letter
                            st.rerun()
        with col2:
            if st.button("➕  Add specific question"):
                st.session_state.jm_qa_slots.append({"question": "", "reply": None})
                st.rerun()

        # ── cover letter ───────────────────────────────────────────────────────
        if st.session_state.jm_cover_letter:
            st.divider()
            st.markdown("### Cover letter")
            st.markdown(st.session_state.jm_cover_letter)
            st.download_button(
                "Download cover letter",
                data=st.session_state.jm_cover_letter,
                file_name=f"{active}_cover_letter.md",
                mime="text/markdown",
            )

            def _resend_cover_letter(all_comments: list) -> None:
                feedback_text = "\n".join(f"- {c}" for c in all_comments)
                st.session_state.jm_cover_letter = generate_cover_letter(
                    active, custom_instructions.strip(), feedback=feedback_text
                )

            _comment_widget("jm_cl_pending", "jm_cl_history", _resend_cover_letter, "the cover letter")

        # ── application form questions, added and answered one at a time ──────
        if st.session_state.jm_qa_slots:
            st.divider()
            st.markdown("### Application form questions")
            st.caption(
                "Type a question from the application form and get a draft reply, "
                "ready to copy back into the form."
            )

            for i, slot in enumerate(st.session_state.jm_qa_slots):
                with st.container(border=True):
                    if slot["reply"] is None:
                        q_text = st.text_input(
                            f"Question {i + 1}",
                            key=f"jm_qa_input_{i}",
                            placeholder="e.g. Why do you want to work at this company?",
                        )
                        if st.button("Get reply", key=f"jm_qa_getreply_{i}", disabled=not q_text.strip()):
                            with st.spinner("Writing reply…"):
                                try:
                                    reply = answer_questions(
                                        active, [q_text.strip()], custom_instructions.strip()
                                    )[0]
                                except Exception as exc:
                                    st.error(str(exc))
                                else:
                                    slot["question"] = q_text.strip()
                                    slot["reply"] = reply
                                    _save_quick_replies(active, st.session_state.jm_qa_slots)
                                    st.rerun()
                    else:
                        st.markdown(f"**{i + 1}. {slot['question']}**")
                        st.write(slot["reply"])

                        def _make_resend(idx):
                            def _resend(all_comments: list) -> None:
                                feedback_text = "\n".join(f"- {c}" for c in all_comments)
                                s = st.session_state.jm_qa_slots[idx]
                                s["reply"] = revise_answer(
                                    active, s["question"], s["reply"], feedback_text,
                                    custom_instructions.strip(),
                                )
                                _save_quick_replies(active, st.session_state.jm_qa_slots)
                            return _resend

                        _comment_widget(
                            f"jm_qa_pending_{i}",
                            f"jm_qa_history_{i}",
                            _make_resend(i),
                            f"reply {i + 1}",
                        )


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

            if "quick_replies" in ctx:
                with st.expander("Application form question replies", expanded=False):
                    st.markdown(ctx["quick_replies"])

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
