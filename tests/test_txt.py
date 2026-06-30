# ================================================================
# tests/test_txt
# ================================================================

from __future__ import annotations

from pathlib import Path

import pytest

from src.converter.formats import txt


class TestForward:
    def test_creates_md_file(self, sample_txt: Path) -> None:
        result = txt.convert_forward(sample_txt, {})
        assert result.status == "success"
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.output_path.suffix == ".md"

    def test_output_contains_source_content(self, sample_txt: Path) -> None:
        result = txt.convert_forward(sample_txt, {})
        md_text = result.output_path.read_text(encoding="utf-8")
        assert "Hello, everything2md" in md_text

    def test_output_has_yaml_front_matter(self, sample_txt: Path) -> None:
        result = txt.convert_forward(sample_txt, {})
        md_text = result.output_path.read_text(encoding="utf-8")
        assert md_text.startswith("---\n")
        assert "source: sample.txt" in md_text

    def test_output_has_asset_marker(self, sample_txt: Path) -> None:
        result = txt.convert_forward(sample_txt, {})
        md_text = result.output_path.read_text(encoding="utf-8")
        assert "<!-- assets:" in md_text

    def test_meta_json_written(self, sample_txt: Path) -> None:
        txt.convert_forward(sample_txt, {})
        meta = sample_txt.parent / "sample_assets" / "meta.json"
        assert meta.exists()

    def test_overwrites_existing_md(self, sample_txt: Path) -> None:
        md_path = sample_txt.with_suffix(".md")
        md_path.write_text("old content", encoding="utf-8")
        txt.convert_forward(sample_txt, {})
        new_text = md_path.read_text(encoding="utf-8")
        assert "old content" not in new_text

    def test_missing_file_returns_failure(self, tmp_path: Path) -> None:
        fake = tmp_path / "nonexistent.txt"
        result = txt.convert_forward(fake, {})
        assert result.status == "failure"
        assert result.output_path is None


class TestReverse:
    def test_roundtrip_creates_txt(self, sample_txt: Path) -> None:
        fwd = txt.convert_forward(sample_txt, {})
        md_path = fwd.output_path
        rev = txt.convert_reverse(md_path, {})
        assert rev.status == "success"
        assert rev.output_path.exists()
        assert rev.output_path.suffix == ".txt"

    def test_roundtrip_preserves_content(self, sample_txt: Path) -> None:
        original = sample_txt.read_text(encoding="utf-8").strip()
        fwd = txt.convert_forward(sample_txt, {})
        rev = txt.convert_reverse(fwd.output_path, {})
        restored = rev.output_path.read_text(encoding="utf-8").strip()
        assert original in restored

    def test_strips_yaml_front_matter(self, sample_txt: Path) -> None:
        fwd = txt.convert_forward(sample_txt, {})
        rev = txt.convert_reverse(fwd.output_path, {})
        restored = rev.output_path.read_text(encoding="utf-8")
        assert "---" not in restored
        assert "source:" not in restored

    def test_missing_md_returns_failure(self, tmp_path: Path) -> None:
        fake = tmp_path / "nonexistent.md"
        result = txt.convert_reverse(fake, {})
        assert result.status == "failure"


class TestStripMarkdown:
    def test_strips_headings(self) -> None:
        result = txt.strip_markdown("# Heading\n\nParagraph.")
        assert "# " not in result
        assert "Heading" in result

    def test_strips_bold(self) -> None:
        result = txt.strip_markdown("**bold text**")
        assert "**" not in result
        assert "bold text" in result

    def test_strips_yaml_front_matter(self) -> None:
        text = "---\nsource: test.txt\ndate: 2026-01-01\n---\n\nContent here."
        result = txt.strip_markdown(text)
        assert "source:" not in result
        assert "Content here." in result

    def test_strips_asset_marker(self) -> None:
        text = "<!-- assets: sample_assets/meta.json -->\n\nContent."
        result = txt.strip_markdown(text)
        assert "<!-- assets:" not in result
        assert "Content." in result
