import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from fusionmatdb.discovery.ornl_reports import build_ornl_url, ORNLDownloader


def test_build_ornl_url():
    url = build_ornl_url(77)
    assert url == "https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-77.pdf"


def test_build_ornl_url_low_number():
    url = build_ornl_url(1)
    assert "fusion-materials-semiannual-progress-report-1.pdf" in url


def test_downloader_skips_existing(tmp_path):
    """Downloader should skip reports whose PDF already exists."""
    existing = tmp_path / "ornl_report_5.pdf"
    existing.write_bytes(b"%PDF fake")
    downloader = ORNLDownloader(output_dir=tmp_path)
    result = downloader.download_one(5)
    assert result["status"] == "skipped"
    assert result["path"] == str(existing)


def test_downloader_marks_404_as_missing(tmp_path):
    """Downloader should handle 404 gracefully."""
    with patch("fusionmatdb.discovery.ornl_reports.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=404)
        downloader = ORNLDownloader(output_dir=tmp_path)
        result = downloader.download_one(99)
    assert result["status"] == "missing"
