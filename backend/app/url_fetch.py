"""Fetch a job posting URL and strip it down to plain text."""

from html.parser import HTMLParser

import httpx


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


def fetch_job_description(url: str) -> str:
    resp = httpx.get(url, follow_redirects=True, timeout=15,
                      headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    extractor = _TextExtractor()
    extractor.feed(resp.text)
    return "\n".join(extractor.parts)
