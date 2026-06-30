# ================================================================
# tests/test_html
# ================================================================

from __future__ import annotations

from pathlib import Path

import pytest

from src.converter.formats import html as html_fmt


class TestForward:
    def test_creates_md_file(self, sample_html: Path) -> None:
        result = html_fmt.convert_forward(sample_html, {})
        assert result.status == "success"
        assert result.output_path.exists()
        assert result.output_path.suffix == ".md"

    def test_extracts_title(self, sample_html: Path) -> None:
        result = html_fmt.convert_forward(sample_html, {})
        md_text = result.output_path.read_text(encoding="utf-8")
        assert "Sample HTML Document" in md_text

    def test_contains_heading_content(self, sample_html: Path) -> None:
        result = html_fmt.convert_forward(sample_html, {})
        md_text = result.output_path.read_text(encoding="utf-8")
        assert "Sample HTML" in md_text

    def test_yaml_front_matter_present(self, sample_html: Path) -> None:
        result = html_fmt.convert_forward(sample_html, {})
        md_text = result.output_path.read_text(encoding="utf-8")
        assert md_text.startswith("---\n")
        assert "source: sample.html" in md_text

    def test_asset_marker_present(self, sample_html: Path) -> None:
        result = html_fmt.convert_forward(sample_html, {})
        md_text = result.output_path.read_text(encoding="utf-8")
        assert "<!-- assets:" in md_text

    def test_missing_file_returns_failure(self, tmp_path: Path) -> None:
        fake = tmp_path / "nonexistent.html"
        result = html_fmt.convert_forward(fake, {})
        assert result.status == "failure"


class TestReverse:
    def test_roundtrip_creates_html(self, sample_html: Path) -> None:
        fwd = html_fmt.convert_forward(sample_html, {})
        rev = html_fmt.convert_reverse(fwd.output_path, {})
        assert rev.status == "success"
        assert rev.output_path.exists()
        assert rev.output_path.suffix == ".html"

    def test_roundtrip_output_is_valid_html(self, sample_html: Path) -> None:
        fwd = html_fmt.convert_forward(sample_html, {})
        rev = html_fmt.convert_reverse(fwd.output_path, {})
        html_text = rev.output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html_text
        assert "<body>" in html_text

    def test_roundtrip_preserves_text_content(self, sample_html: Path) -> None:
        fwd = html_fmt.convert_forward(sample_html, {})
        rev = html_fmt.convert_reverse(fwd.output_path, {})
        html_text = rev.output_path.read_text(encoding="utf-8")
        assert "Sample HTML" in html_text


class TestHelpers:
    def test_extract_title(self) -> None:
        html = "<html><head><title>My Title</title></head><body></body></html>"
        assert html_fmt.extract_title(html) == "My Title"

    def test_extract_title_missing(self) -> None:
        html = "<html><body>No title</body></html>"
        assert html_fmt.extract_title(html) == ""

    def test_strip_front_matter(self) -> None:
        text = "---\nsource: test.html\n---\n\n<!-- assets: x -->\n\nContent."
        result = html_fmt.strip_front_matter(text)
        assert "source:" not in result
        assert "assets:" not in result
        assert "Content." in result
