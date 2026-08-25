"""Job search agent.

Reads your CV (cv.txt) and one or more job descriptions, asks Claude to assess
the fit, and writes a Markdown report per job into output/.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...

    python agent.py                                    # analyze every .txt in jobs/
    python agent.py jobs/acme-backend.txt              # analyze a local file
    python agent.py https://example.com/jobs/engineer  # fetch from a URL
    python agent.py jobs/role.txt https://...          # mix freely
"""

import re
import sys
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import anthropic
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from prompts import JOB_MATCHER_SYSTEM, build_cv_context, build_job_block

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

BASE_DIR = Path(__file__).resolve().parent
CV_PDF = BASE_DIR / "cv.pdf"
CV_TXT = BASE_DIR / "cv.txt"
JOBS_DIR = BASE_DIR / "jobs"
OUTPUT_DIR = BASE_DIR / "output"


class JobFitAnalysis(BaseModel):
    """The structured result Claude returns for one job."""

    fit_score: int = Field(
        ge=0, le=10, description="Overall fit, integer 0-10 (10 = perfect match)."
    )
    summary: str = Field(description="One- or two-sentence overall verdict.")
    strengths: list[str] = Field(
        description="Specific ways the CV meets or exceeds the role's requirements."
    )
    gaps: list[str] = Field(
        description="Requirements the CV does not (or only weakly) evidence."
    )
    cover_letter: str = Field(
        description="A tailored cover letter for this role, in the candidate's voice."
    )


@dataclass
class JobSource:
    text: str
    title: str   # human-readable name used in the prompt and markdown header
    slug: str    # safe filename stem for output/<slug>.md
    origin: str  # original file path or URL shown in the markdown Source line


class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and collapse whitespace using stdlib html.parser."""

    _SKIP_TAGS = {"script", "style", "head", "nav", "footer", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "\n".join(self._parts)
        lines = [ln.strip() for ln in raw.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def fetch_url(url: str) -> JobSource:
    """Fetch a job posting URL, strip HTML, and return a JobSource."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        sys.exit(f"Failed to fetch {url}: {exc}")

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type:
        extractor = _HTMLTextExtractor()
        extractor.feed(resp.text)
        text = extractor.get_text()
    else:
        text = resp.text.strip()

    if not text:
        sys.exit(f"No text content extracted from {url}")

    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    raw_name = path_parts[-1] if path_parts else parsed.netloc
    # include the domain so slugs from different sites don't collide
    domain = parsed.netloc.replace("www.", "").split(".")[0]
    raw_slug = f"{domain}-{raw_name}" if raw_name and raw_name != domain else domain
    slug = re.sub(r"[^\w-]", "-", raw_slug).strip("-") or "job"
    title = slug.replace("-", " ").replace("_", " ").title()

    return JobSource(text=text, title=title, slug=slug, origin=url)


def read_cv() -> str:
    if CV_PDF.exists():
        from pypdf import PdfReader
        reader = PdfReader(CV_PDF)
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if text:
            return text
    if CV_TXT.exists():
        text = CV_TXT.read_text(encoding="utf-8").strip()
        if text:
            return text
    sys.exit(f"No CV found. Add cv.pdf (or cv.txt) to {BASE_DIR}.")


def resolve_sources(args: list[str]) -> list[JobSource]:
    """Turn CLI args (file paths or URLs) into JobSources.

    With no args, falls back to every .txt file in jobs/.
    """
    if not args:
        paths = sorted(JOBS_DIR.glob("*.txt"))
        if not paths:
            sys.exit(f"No .txt job files found in {JOBS_DIR}. Add one and retry.")
        return [_source_from_path(p) for p in paths]

    sources: list[JobSource] = []
    for arg in args:
        if arg.startswith(("http://", "https://")):
            print(f"Fetching {arg} ...")
            sources.append(fetch_url(arg))
        else:
            p = Path(arg)
            if not p.exists():
                print(f"  ! skipping {p} (not found)")
                continue
            sources.append(_source_from_path(p))
    return sources


def _source_from_path(p: Path) -> JobSource:
    return JobSource(
        text=p.read_text(encoding="utf-8").strip(),
        title=p.stem.replace("-", " ").replace("_", " ").title(),
        slug=p.stem,
        origin=str(p),
    )


def analyze(
    client: anthropic.Anthropic, cv_text: str, source: JobSource
) -> JobFitAnalysis:
    """Call Claude and return a validated JobFitAnalysis for one job."""
    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=JOB_MATCHER_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": build_cv_context(cv_text, "") + "\n\n" + build_job_block(source.text),
            }
        ],
        output_format=JobFitAnalysis,
    )
    if response.parsed_output is None:
        raise RuntimeError(
            f"Model did not return a parseable analysis "
            f"(stop_reason={response.stop_reason})."
        )
    return response.parsed_output


def to_markdown(source: JobSource, analysis: JobFitAnalysis) -> str:
    strengths = "\n".join(f"- {s}" for s in analysis.strengths) or "- (none)"
    gaps = "\n".join(f"- {g}" for g in analysis.gaps) or "- (none)"

    return f"""# Job Fit Analysis — {source.title}

**Source:** {source.origin}
**Generated:** {date.today().isoformat()}
**Fit score:** {analysis.fit_score} / 10

## Summary

{analysis.summary}

## Strengths

{strengths}

## Gaps

{gaps}

## Tailored Cover Letter

{analysis.cover_letter}
"""


def main() -> None:
    cv_text = read_cv()
    sources = resolve_sources(sys.argv[1:])
    OUTPUT_DIR.mkdir(exist_ok=True)
    client = anthropic.Anthropic()

    for source in sources:
        print(f"Analyzing {source.title} ...")
        analysis = analyze(client, cv_text, source)
        out_path = OUTPUT_DIR / f"{source.slug}.md"
        out_path.write_text(to_markdown(source, analysis), encoding="utf-8")
        print(f"  -> {out_path}  (fit {analysis.fit_score}/10)")


if __name__ == "__main__":
    main()
