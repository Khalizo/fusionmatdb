"""Download ORNL Fusion Materials semiannual progress reports (volumes 1-77+)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

ORNL_BASE = "https://fmp.ornl.gov/semiannual-progress-reports"


def build_ornl_url(report_number: int) -> str:
    return f"{ORNL_BASE}/fusion-materials-semiannual-progress-report-{report_number}.pdf"


class ORNLDownloader:
    def __init__(self, output_dir: str | Path, max_report: int = 80):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_report = max_report

    def download_one(self, report_number: int, delay: float = 1.0) -> dict[str, Any]:
        path = self.output_dir / f"ornl_report_{report_number}.pdf"
        if path.exists():
            return {"number": report_number, "status": "skipped", "path": str(path)}

        url = build_ornl_url(report_number)
        try:
            resp = requests.get(url, timeout=60, stream=True)
        except requests.RequestException as e:
            return {"number": report_number, "status": "error", "error": str(e)}

        if resp.status_code == 404:
            return {"number": report_number, "status": "missing", "url": url}
        if resp.status_code != 200:
            return {"number": report_number, "status": "error", "http": resp.status_code}

        content = resp.content
        if len(content) < 1000:
            return {"number": report_number, "status": "missing", "reason": "too_small"}

        path.write_bytes(content)
        time.sleep(delay)
        return {"number": report_number, "status": "downloaded", "path": str(path), "bytes": len(content)}

    def download_all(self, delay: float = 1.0) -> list[dict[str, Any]]:
        results = []
        for n in tqdm(range(1, self.max_report + 1), desc="ORNL reports"):
            result = self.download_one(n, delay=delay)
            results.append(result)
        downloaded = [r for r in results if r["status"] == "downloaded"]
        skipped = [r for r in results if r["status"] == "skipped"]
        missing = [r for r in results if r["status"] == "missing"]
        print(f"\nDone: {len(downloaded)} downloaded, {len(skipped)} already present, {len(missing)} missing")
        return results
