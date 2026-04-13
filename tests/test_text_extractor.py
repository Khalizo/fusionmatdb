import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from fusionmatdb.access.text_extractor import extract_with_pdfplumber, GROBIDExtractor


def test_pdfplumber_extraction_returns_string():
    """extract_with_pdfplumber returns a non-empty string for a real PDF."""
    pdf_path = Path("/Users/khalizo/Documents/coding_projects/fusion_energy/papers/Machine-learning interatomic potential for radiation damage and defects in tungsten.pdf")
    if not pdf_path.exists():
        pytest.skip("Test PDF not available")
    text = extract_with_pdfplumber(pdf_path)
    assert isinstance(text, str)
    assert len(text) > 100


def test_pdfplumber_extraction_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_with_pdfplumber(Path("/no/such/file.pdf"))


def test_grobid_extractor_raises_when_server_down():
    """GROBIDExtractor.extract() raises ConnectionError when GROBID server is not running."""
    extractor = GROBIDExtractor(grobid_url="http://localhost:19999")
    pdf_path = Path("/Users/khalizo/Documents/coding_projects/fusion_energy/papers/Machine-learning interatomic potential for radiation damage and defects in tungsten.pdf")
    with pytest.raises(ConnectionError):
        extractor.extract(pdf_path)


def test_grobid_extract_text_strips_xml_tags():
    """extract_text_only strips XML tags from TEI response."""
    extractor = GROBIDExtractor(grobid_url="http://localhost:8070")
    fake_xml = "<TEI><body><p>Some text about tungsten irradiation</p></body></TEI>"
    with patch.object(extractor, "extract", return_value=fake_xml):
        text = extractor.extract_text_only(Path("fake.pdf"))
    assert "tungsten irradiation" in text
    assert "<TEI>" not in text
    assert "<p>" not in text
