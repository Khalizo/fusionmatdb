"""
Vision-based PDF extraction using Gemini 3 Flash on Vertex AI.

Processes entire PDF pages as images — captures data from figures, graphs,
and tables that text-only extraction misses entirely.

Auth priority:
  1. GOOGLE_CLOUD_API_KEY env var (Vertex AI Express API key — recommended)
  2. SA key file (GOOGLE_APPLICATION_CREDENTIALS or SA_KEY_PATH)
  3. GOOGLE_API_KEY env var (direct Gemini API, 10 RPM free tier — slow)

Rate limits (Vertex AI): 1500 RPM — use asyncio concurrency for bulk extraction.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import fitz  # pymupdf

from fusionmatdb.extraction.prompts import VISION_EXTRACTION_PROMPT
from fusionmatdb.extraction.validator import validate_extraction, score_confidence


class VertexVisionExtractor:
    """Extract structured data from PDF pages using Gemini 3 Flash on Vertex AI.

    Auth priority:
      1. GOOGLE_CLOUD_API_KEY (Vertex AI Express key — fastest setup)
      2. SA key file
      3. GOOGLE_API_KEY (free tier fallback, very slow)

    Usage:
        extractor = VertexVisionExtractor()
        results = extractor.extract_pdf("path/to/report.pdf", paper_id="ornl_70")
    """

    MODEL = "gemini-3-flash-preview"           # Gemini 3 Flash via Vertex AI Express
    MODEL_SA = "publishers/google/models/gemini-2.5-flash"  # fallback for SA key auth
    # Set SA_KEY_PATH via constructor or GOOGLE_APPLICATION_CREDENTIALS env var
    SA_KEY_PATH: str | None = None
    # Set GCP_PROJECT via constructor or default to None (uses ADC project)
    GCP_PROJECT: str | None = None
    GCP_LOCATION = "us-central1"
    DPI = 120
    MAX_CONCURRENT = 20

    def __init__(
        self,
        sa_key_path: str | None = None,
        project: str | None = None,
        location: str | None = None,
    ):
        self._client = None
        self._model = None
        self.sa_key_path = sa_key_path or self.SA_KEY_PATH
        self.project = project or self.GCP_PROJECT
        self.location = location or self.GCP_LOCATION

    def _get_client(self):
        if self._client is None:
            from google import genai
            import google.oauth2.service_account

            vertex_api_key = os.environ.get("GOOGLE_CLOUD_API_KEY")
            if vertex_api_key:
                # Vertex AI Express API key — supports Gemini 3 Flash
                self._client = genai.Client(vertexai=True, api_key=vertex_api_key)
                self._model = self.MODEL
                return self._client

            # Try SA key — check GOOGLE_APPLICATION_CREDENTIALS first, then explicit path
            sa_path = self.sa_key_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if sa_path and Path(sa_path).exists():
                creds = google.oauth2.service_account.Credentials.from_service_account_file(
                    sa_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                self._client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.location,
                    credentials=creds,
                )
                self._model = self.MODEL_SA  # SA key auth uses 2.5 Flash model name format
            else:
                # Fallback to direct Gemini API key (10 RPM free tier)
                api_key = os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    raise RuntimeError(
                        "No credentials found. Set GOOGLE_CLOUD_API_KEY (recommended), "
                        f"provide SA key at {self.sa_key_path}, or set GOOGLE_API_KEY."
                    )
                import warnings
                warnings.warn(
                    "Falling back to GOOGLE_API_KEY (10 RPM limit). "
                    "Set GOOGLE_CLOUD_API_KEY for Gemini 3 Flash at full speed.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                self._client = genai.Client(api_key=api_key)
                self._model = "gemini-2.5-flash"
        return self._client

    def _page_to_image(self, page: fitz.Page) -> bytes:
        mat = fitz.Matrix(self.DPI / 72, self.DPI / 72)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")

    def _parse_response(self, raw: str, paper_id: str, page_num: int) -> list[dict[str, Any]]:
        """Parse Gemini JSON response, validate, and score each record."""
        raw = raw.strip()
        # Strip markdown fences
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            records = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if not isinstance(records, list):
            return []

        validated = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            errors = validate_extraction(rec)
            if len(errors) <= 2:
                rec["paper_id"] = paper_id
                rec["page"] = page_num
                rec["confidence_score"] = score_confidence(rec)
                rec["extraction_method"] = "gemini_vision"
                validated.append(rec)
        return validated

    def _make_config(self, types):
        """Build GenerateContentConfig. Disables thinking only for SA/Gemini-2.5 path."""
        if self._model == self.MODEL_SA or "2.5" in (self._model or ""):
            return types.GenerateContentConfig(
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
        # Disable thinking for structured JSON extraction — thinking adds cost
        # without improving accuracy on lookup/extraction tasks
        return types.GenerateContentConfig(
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

    def extract_page(
        self,
        page: fitz.Page,
        paper_id: str,
        page_num: int,
        pdf_path: str | Path | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Extract data from a single PDF page (synchronous).

        Args:
            pdf_path: If provided, enables disk caching of raw Gemini response.
        """
        from google.genai import types

        # Check cache if pdf_path given
        if pdf_path and use_cache:
            cached = self._load_cached_raw(Path(pdf_path), page_num)
            if cached is not None:
                return self._parse_response(cached, paper_id, page_num)

        client = self._get_client()
        img_bytes = self._page_to_image(page)

        try:
            resp = client.models.generate_content(
                model=self._model,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    VISION_EXTRACTION_PROMPT,
                ],
                config=self._make_config(types),
            )
            raw = resp.text
            if pdf_path:
                self._save_raw_cache(Path(pdf_path), page_num, raw)
            return self._parse_response(raw, paper_id, page_num)
        except Exception:
            return []

    def _raw_cache_path(self, pdf_path: Path, page_num: int) -> Path:
        """Return path for raw Gemini JSON cache: <pdf_stem>_raw/page_NNN.json"""
        cache_dir = pdf_path.parent / f"{pdf_path.stem}_raw"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir / f"page_{page_num:03d}.json"

    def _load_cached_raw(self, pdf_path: Path, page_num: int) -> str | None:
        """Return cached raw Gemini response text, or None if not cached."""
        path = self._raw_cache_path(pdf_path, page_num)
        if path.exists():
            data = json.loads(path.read_text())
            return data.get("raw_response")
        return None

    def _save_raw_cache(self, pdf_path: Path, page_num: int, raw: str) -> None:
        """Save raw Gemini response text to disk for free replay later."""
        path = self._raw_cache_path(pdf_path, page_num)
        path.write_text(json.dumps({
            "paper_id": pdf_path.stem,
            "page": page_num,
            "model": self._model,
            "raw_response": raw,
        }, indent=2))

    def extract_pdf(
        self,
        pdf_path: str | Path,
        paper_id: str,
        max_concurrent: int | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Extract all data from a PDF. Uses async concurrency for speed.

        Args:
            pdf_path: Path to PDF file.
            paper_id: Database paper ID (e.g. "ornl_70").
            max_concurrent: Max parallel Vertex AI requests (default: 20).
            use_cache: If True, skip API call for pages already cached on disk.
                       Cached raw JSON lives at <pdf_stem>_raw/page_NNN.json.
                       Re-run extraction free by replaying from cache.

        Returns:
            List of validated data records, each with paper_id, page, confidence_score.
        """
        return asyncio.run(
            self._extract_pdf_async(
                pdf_path, paper_id,
                max_concurrent or self.MAX_CONCURRENT,
                use_cache=use_cache,
            )
        )

    async def _extract_pdf_async(
        self,
        pdf_path: str | Path,
        paper_id: str,
        max_concurrent: int,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        from google.genai import types

        pdf_path = Path(pdf_path)
        client = self._get_client()
        doc = fitz.open(str(pdf_path))
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_page(i: int) -> list[dict[str, Any]]:
            page_num = i + 1
            async with semaphore:
                loop = asyncio.get_event_loop()

                # Check disk cache first — free replay, no API cost
                if use_cache:
                    cached = await loop.run_in_executor(
                        None, lambda: self._load_cached_raw(pdf_path, page_num)
                    )
                    if cached is not None:
                        return self._parse_response(cached, paper_id, page_num)

                img_bytes = await loop.run_in_executor(
                    None, lambda: self._page_to_image(doc[i])
                )
                try:
                    resp = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=self._model,
                            contents=[
                                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                                VISION_EXTRACTION_PROMPT,
                            ],
                            config=self._make_config(types),
                        ),
                    )
                    raw = resp.text
                    # Save raw response to disk before parsing
                    await loop.run_in_executor(
                        None, lambda: self._save_raw_cache(pdf_path, page_num, raw)
                    )
                    return self._parse_response(raw, paper_id, page_num)
                except Exception:
                    return []

        tasks = [process_page(i) for i in range(len(doc))]
        results = await asyncio.gather(*tasks)
        return [record for page_results in results for record in page_results]
