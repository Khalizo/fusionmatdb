"""PDF text extraction via pdfplumber (primary) or GROBID (structural)."""
from __future__ import annotations

import re
from pathlib import Path

import pdfplumber
import requests


def extract_with_pdfplumber(pdf_path: str | Path) -> str:
    """Extract all text from a PDF using pdfplumber. Best for ORNL-style reports."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


class GROBIDExtractor:
    """Structural PDF extraction via GROBID server.

    Start GROBID with:
        docker run -d -p 8070:8070 grobid/grobid:0.8.2
    """

    def __init__(self, grobid_url: str = "http://localhost:8070"):
        self.grobid_url = grobid_url.rstrip("/")

    def _check_alive(self) -> None:
        try:
            resp = requests.get(f"{self.grobid_url}/api/isalive", timeout=5)
            if resp.status_code != 200:
                raise ConnectionError(f"GROBID returned {resp.status_code}")
        except requests.ConnectionError as e:
            raise ConnectionError(f"GROBID server not reachable at {self.grobid_url}: {e}") from e

    def extract(self, pdf_path: str | Path) -> str:
        """Return TEI-XML string for the given PDF."""
        self._check_alive()
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        with open(pdf_path, "rb") as f:
            resp = requests.post(
                f"{self.grobid_url}/api/processFulltextDocument",
                files={"input": f},
                data={"consolidateHeader": "1"},
                timeout=120,
            )
        if resp.status_code != 200:
            raise RuntimeError(f"GROBID error {resp.status_code}: {resp.text[:200]}")
        return resp.text

    def extract_text_only(self, pdf_path: str | Path) -> str:
        """Extract plain text from GROBID TEI-XML (strips tags)."""
        tei_xml = self.extract(pdf_path)
        text = re.sub(r"<[^>]+>", " ", tei_xml)
        text = re.sub(r"\s+", " ", text).strip()
        return text
