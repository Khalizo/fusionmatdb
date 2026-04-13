# fusionmatdb/fusionmatdb/extraction/llm_extractor.py
"""LLM-based data extraction using Claude API."""
from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from fusionmatdb.extraction.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_TEMPLATE
from fusionmatdb.extraction.validator import validate_extraction, score_confidence

MAX_TEXT_CHARS = 80_000


class LLMExtractor:
    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-5"):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def extract(self, text: str, paper_id: str, chunk_size: int = MAX_TEXT_CHARS) -> list[dict[str, Any]]:
        """Extract structured data records from paper text. Returns validated records."""
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        all_records = []
        for chunk in chunks:
            records = self._extract_chunk(chunk, paper_id)
            all_records.extend(records)
        # Deduplicate by key fields
        seen = set()
        unique = []
        for r in all_records:
            key = (r.get("material_name"), r.get("dose_dpa"), r.get("yield_strength_mpa_irradiated"))
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def _extract_chunk(self, text: str, paper_id: str) -> list[dict[str, Any]]:
        prompt = EXTRACTION_USER_TEMPLATE.format(text=text[:MAX_TEXT_CHARS])
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            records = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(records, list):
            return []
        validated = []
        for record in records:
            errors = validate_extraction(record)
            if len(errors) <= 2:
                record["paper_id"] = paper_id
                record["confidence_score"] = score_confidence(record)
                record["extraction_method"] = "llm_fulltext"
                record["raw_validation_errors"] = errors
                validated.append(record)
        return validated
