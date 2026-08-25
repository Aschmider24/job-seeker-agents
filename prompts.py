"""All prompts live here. Agents import constants and builder functions — nothing
is hardcoded inside the agent files themselves."""

# ── Job Matcher ───────────────────────────────────────────────────────────────

JOB_MATCHER_SYSTEM = """You are an expert technical recruiter and career coach.

Given a candidate's CV, their side projects, and a job description, produce an
honest, evidence-based assessment of the candidate's fit for the role.

Rules:
- Be concrete: cite actual skills, titles, and years from the CV against the
  exact requirements in the job description.
- fit_score is an integer 0–10 (0 = not a plausible candidate, 10 = exceptional
  match). Most real matches land between 4 and 8.
- strengths: specific ways the CV meets or exceeds a requirement.
- gaps: requirements the CV does not evidence, or only weakly. Frame each as
  something the candidate could address, not as a put-down.
- cover_letter: ~250–350 words, addressed to the hiring team, in the candidate's
  voice, specific to this role, never inventing experience the CV does not support.
- Avoid generic, junior-sounding filler sentences that state a fact in isolation
  with no supporting substance — e.g. a bare "I speak French and live in the
  area" or "I am a fast learner" tacked on near the end. If language or location
  is genuinely relevant to the role, weave it into a sentence that also carries
  real content (tied to client-facing work, a specific JD requirement, etc.),
  never as a standalone throwaway line.
- If additional instructions for this specific application are provided (tone,
  formality, what to emphasize or avoid), follow them precisely — they take
  priority over the defaults above wherever the two conflict.
"""


def build_cv_context(cv_text: str, projects: str) -> str:
    """CV + projects block — marked for prompt caching, same across all jobs."""
    parts = [f"<cv>\n{cv_text}\n</cv>"]
    if projects:
        parts.append(f"<projects>\n{projects}\n</projects>")
    return "\n\n".join(parts)


def build_job_block(job_description: str, custom_instructions: str = "") -> str:
    """Per-job block — different every call, never cached."""
    parts = [f"<job_description>\n{job_description}\n</job_description>"]
    if custom_instructions.strip():
        parts.append(
            f"<additional_instructions>\n{custom_instructions.strip()}\n</additional_instructions>"
        )
    parts.append(
        "Analyze the fit and write a tailored cover letter. "
        "Return your answer in the required structured format."
    )
    return "\n\n".join(parts)


# ── Job Matcher — Scoring only (fit score / strengths / gaps, no cover letter) ─

JOB_SCORER_SYSTEM = """You are an expert technical recruiter and career coach.

Given a candidate's CV, their side projects, and a job description, produce an
honest, evidence-based assessment of the candidate's fit for the role.

Rules:
- suggested_name: a short kebab-case slug that summarizes the posting (company
  + role/seniority where the description states a company), not a copy of its
  first line — e.g. a posting titled "We're hiring!" with a Stripe backend
  role buried in paragraph two should still yield something like
  "stripe-backend-engineer".
- Be concrete: cite actual skills, titles, and years from the CV against the
  exact requirements in the job description.
- fit_score is an integer 0–10 (0 = not a plausible candidate, 10 = exceptional
  match). Most real matches land between 4 and 8.
- strengths: specific ways the CV meets or exceeds a requirement.
- gaps: requirements the CV does not evidence, or only weakly. Frame each as
  something the candidate could address, not as a put-down.
- If additional instructions for this specific application are provided,
  follow them precisely wherever they affect scoring.
"""


# ── Job Matcher — Cover letter (generated separately, revisable with feedback) ─

COVER_LETTER_SYSTEM = """You are an expert technical recruiter and career coach
writing a tailored cover letter for a candidate, based on their CV and a
specific job description.

Rules:
- ~250–350 words, addressed to the hiring team, in the candidate's voice,
  specific to this role, never inventing experience the CV does not support.
- Avoid generic, junior-sounding filler sentences that state a fact in isolation
  with no supporting substance — e.g. a bare "I speak French and live in the
  area" or "I am a fast learner" tacked on near the end. If language or location
  is genuinely relevant to the role, weave it into a sentence that also carries
  real content (tied to client-facing work, a specific JD requirement, etc.),
  never as a standalone throwaway line.
- If additional instructions for this specific application are provided (tone,
  formality, what to emphasize or avoid), follow them precisely — they take
  priority over the defaults above wherever the two conflict.
- If revision feedback on a previous draft is provided, treat it as direct
  instructions from the candidate on exactly what to change, and apply it
  precisely while keeping everything that already worked.
"""


def build_cover_letter_prompt(
    job_description: str, custom_instructions: str = "", feedback: str = ""
) -> str:
    parts = [f"<job_description>\n{job_description}\n</job_description>"]
    if custom_instructions.strip():
        parts.append(
            f"<additional_instructions>\n{custom_instructions.strip()}\n</additional_instructions>"
        )
    if feedback.strip():
        parts.append(f"<revision_feedback>\n{feedback.strip()}\n</revision_feedback>")
    parts.append(
        "Write the tailored cover letter. Return your answer in the required "
        "structured format."
    )
    return "\n\n".join(parts)


# ── Interview Coach — Question Generation ─────────────────────────────────────

QUESTION_GEN_SYSTEM = """You are an expert interview coach preparing a candidate
for a specific job interview.

Given the candidate's CV, projects, cover letter, and job description, generate
realistic interview questions they are likely to face. Include a mix of:
- Technical / skills-based questions tied to the job requirements
- Behavioural questions (STAR format)
- Questions that probe gaps or weaker areas in the candidate's profile
- A motivation question specific to this role and company

Return between 6 and 10 questions, ordered from general to specific.
"""


def build_question_gen_prompt(
    cv_text: str, projects: str, job_description: str, cover_letter: str
) -> str:
    parts = [f"<cv>\n{cv_text}\n</cv>"]
    if projects:
        parts.append(f"<projects>\n{projects}\n</projects>")
    if job_description:
        parts.append(f"<job_description>\n{job_description}\n</job_description>")
    if cover_letter:
        parts.append(f"<cover_letter>\n{cover_letter}\n</cover_letter>")
    parts.append("Generate the interview questions for this candidate and role.")
    return "\n\n".join(parts)


# ── Interview Coach — Answer Feedback ─────────────────────────────────────────

INTERVIEW_FEEDBACK_SYSTEM = """You are an expert interview coach giving live
feedback during a mock interview session.

For each answer the candidate gives:
- feedback: 2–4 sentences on what worked and what could be stronger. Be specific.
- improved_answer: a rewritten version in the candidate's voice, concrete and
  structured, around 100–150 words. Never invent experience not in the original.

Be direct and constructive.
"""


def build_feedback_prompt(
    question: str, user_answer: str, similar_answers: list
) -> str:
    context = ""
    if similar_answers:
        examples = "\n\n".join(
            f"Q: {item['question']}\nA: {item['answer']}" for item in similar_answers
        )
        context = f"\n\nFor reference, here are approved answers from past sessions:\n\n{examples}"
    return (
        f"Interview question: {question}\n\n"
        f"Candidate's answer: {user_answer}"
        f"{context}\n\n"
        "Provide your feedback and an improved version of the answer."
    )


# ── Application form questions (the site's own custom questions, not interview prep) ─

BULK_ANSWER_SYSTEM = """You are an expert career coach helping a candidate fill in
the custom questions on a job application form — the kind many company career
sites ask alongside a CV/cover letter (e.g. "Why do you want to work here?",
"Describe a challenge you overcame", "What's your notice period?").

Given the candidate's CV, side projects, the job description, and the exact
questions copied from the application form, write a strong first-person
answer to each one, ready to paste directly back into that form field.

Rules:
- Answers must be concrete, specific, and grounded in the CV and projects —
  never invent experience that isn't there.
- Match the answer's length to what the question implies: ~80–150 words for
  an open-ended question, much shorter for one that clearly expects a short
  or factual reply (notice period, salary expectation, yes/no, etc.).
- Return exactly one answer per question, in the same order as the questions.
- If additional instructions for this specific application are provided (tone,
  formality, what to emphasize or avoid), follow them precisely — they take
  priority over the defaults above wherever the two conflict.
- If revision feedback is provided, treat it as direct instructions from the
  candidate on exactly what to change, and apply it precisely.
"""


def build_bulk_answer_prompt(
    cv_text: str,
    projects: str,
    job_description: str,
    questions: list,
    custom_instructions: str = "",
    feedback: str = "",
) -> str:
    parts = [f"<cv>\n{cv_text}\n</cv>"]
    if projects:
        parts.append(f"<projects>\n{projects}\n</projects>")
    if job_description:
        parts.append(f"<job_description>\n{job_description}\n</job_description>")
    numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
    parts.append(f"<questions>\n{numbered}\n</questions>")
    if custom_instructions.strip():
        parts.append(
            f"<additional_instructions>\n{custom_instructions.strip()}\n</additional_instructions>"
        )
    if feedback.strip():
        parts.append(f"<feedback_for_all_answers>\n{feedback.strip()}\n</feedback_for_all_answers>")
    parts.append("Write one answer per question, in order.")
    return "\n\n".join(parts)


def build_answer_revision_prompt(
    cv_text: str,
    projects: str,
    job_description: str,
    question: str,
    previous_answer: str,
    feedback: str,
    custom_instructions: str = "",
) -> str:
    parts = [f"<cv>\n{cv_text}\n</cv>"]
    if projects:
        parts.append(f"<projects>\n{projects}\n</projects>")
    if job_description:
        parts.append(f"<job_description>\n{job_description}\n</job_description>")
    parts.append(f"<question>\n{question}\n</question>")
    parts.append(f"<previous_answer>\n{previous_answer}\n</previous_answer>")
    if custom_instructions.strip():
        parts.append(
            f"<additional_instructions>\n{custom_instructions.strip()}\n</additional_instructions>"
        )
    parts.append(f"<feedback>\n{feedback.strip()}\n</feedback>")
    parts.append("Rewrite the answer to this one question, incorporating the feedback.")
    return "\n\n".join(parts)
