"""Page quality triage — cheap LLM pre-screening before extraction."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import fitz

from fusionmatdb.extraction.prompts import PAGE_TRIAGE_PROMPT


@dataclass
class TriageResult:
    page_number: int
    classification: str
    reason: str
    has_extractable_data: bool


def is_record_incomplete(record: dict) -> bool:
    """Check if an extracted record is missing critical context fields."""
    has_property = any(
        record.get(f) is not None
        for f in [
            "yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
            "uts_mpa_irradiated", "hardness_value", "fracture_toughness_mpa_sqrt_m",
            "dbtt_k_irradiated", "volumetric_swelling_pct",
        ]
    )
    if not has_property:
        return False
    if not record.get("material_name"):
        return True
    has_conditions = (
        record.get("dose_dpa") is not None or record.get("irradiation_temp_c") is not None
    )
    if not has_conditions:
        return True
    return False


def get_adjacent_page_text(doc: fitz.Document, page_idx: int) -> tuple[str, str]:
    """Extract text from pages adjacent to page_idx using pymupdf."""
    prev_text = ""
    next_text = ""
    if page_idx > 0:
        prev_text = doc[page_idx - 1].get_text()
    if page_idx < len(doc) - 1:
        next_text = doc[page_idx + 1].get_text()
    return prev_text, next_text


class PageTriager:
    """Classify PDF pages for extraction readability using a cheap LLM call."""

    MAX_CONCURRENT = 20

    def __init__(self):
        self._client = None
        self._model = None

    def _get_client(self):
        if self._client is None:
            import os
            from google import genai
            vertex_api_key = os.environ.get("GOOGLE_CLOUD_API_KEY")
            if vertex_api_key:
                self._client = genai.Client(vertexai=True, api_key=vertex_api_key)
                self._model = "gemini-3-flash-preview"
            else:
                api_key = os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    raise RuntimeError("No Google API key found. Set GOOGLE_CLOUD_API_KEY or GOOGLE_API_KEY.")
                self._client = genai.Client(api_key=api_key)
                self._model = "gemini-2.5-flash"
        return self._client

    def _page_to_image(self, page: fitz.Page) -> bytes:
        mat = fitz.Matrix(72 / 72, 72 / 72)  # Lower DPI for triage — saves tokens
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")

    def _parse_triage(self, raw: str, page_num: int) -> TriageResult:
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return TriageResult(page_num, "clean", "Failed to parse triage response", True)
        return TriageResult(
            page_number=page_num,
            classification=data.get("classification", "clean"),
            reason=data.get("reason", ""),
            has_extractable_data=data.get("has_extractable_data", True),
        )

    def triage_pdf(self, pdf_path: str | Path) -> list[TriageResult]:
        """Triage all pages in a PDF. Returns classification per page."""
        return asyncio.run(self._triage_pdf_async(pdf_path))

    async def _triage_pdf_async(self, pdf_path: str | Path) -> list[TriageResult]:
        from google.genai import types
        client = self._get_client()
        doc = fitz.open(str(pdf_path))
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)

        async def process_page(i: int) -> TriageResult:
            page_num = i + 1
            async with semaphore:
                loop = asyncio.get_event_loop()
                img_bytes = await loop.run_in_executor(None, lambda: self._page_to_image(doc[i]))
                try:
                    resp = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=self._model,
                            contents=[
                                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                                PAGE_TRIAGE_PROMPT,
                            ],
                            config=types.GenerateContentConfig(
                                temperature=0,
                                thinking_config=types.ThinkingConfig(thinking_budget=0),
                            ),
                        ),
                    )
                    return self._parse_triage(resp.text, page_num)
                except Exception:
                    return TriageResult(page_num, "clean", "Triage failed, defaulting to clean", True)

        tasks = [process_page(i) for i in range(len(doc))]
        return await asyncio.gather(*tasks)
