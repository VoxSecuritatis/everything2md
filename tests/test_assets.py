# ================================================================
# tests/test_assets
# ================================================================

from __future__ import annotations

import json
from pathlib import Path

from src.converter import assets


class TestAssetsDir:
    def test_assets_dir_name(self, tmp_path: Path) -> None:
        source = tmp_path / "report.docx"
        assert assets.assets_dir(source) == tmp_path / "report_assets"

    def test_images_dir_name(self, tmp_path: Path) -> None:
        source = tmp_path / "report.docx"
        assert assets.images_dir(source) == tmp_path / "report_assets" / "images"


class TestWriteMeta:
    def test_creates_meta_json(self, tmp_path: Path) -> None:
        source = tmp_path / "doc.pdf"
        source.write_text("", encoding="utf-8")
        meta_path = assets.write_meta(source, "pdf", image_count=2, table_count=1)
        assert meta_path.exists()
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        assert data["source_format"] == "pdf"
        assert data["source_filename"] == "doc.pdf"
        assert data["image_count"] == 2
        assert data["table_count"] == 1
        assert "converted_at" in data

    def test_creates_assets_dir(self, tmp_path: Path) -> None:
        source = tmp_path / "doc.pdf"
        source.write_text("", encoding="utf-8")
        assets.write_meta(source, "pdf")
        assert (tmp_path / "doc_assets").is_dir()


class TestAssetMarker:
    def test_marker_format(self, tmp_path: Path) -> None:
        source = tmp_path / "report.docx"
        marker = assets.asset_marker(source)
        assert marker == "<!-- assets: report_assets/meta.json -->"


class TestReadMeta:
    def test_reads_marker_from_md(self, tmp_path: Path) -> None:
        source = tmp_path / "doc.txt"
        source.write_text("", encoding="utf-8")
        assets.write_meta(source, "txt")

        md_path = tmp_path / "doc.md"
        marker = assets.asset_marker(source)
        md_path.write_text(f"---\nsource: doc.txt\n---\n\n{marker}\n\nContent.", encoding="utf-8")

        meta = assets.read_meta(md_path)
        assert meta is not None
        assert meta["source_format"] == "txt"

    def test_returns_none_when_no_marker(self, tmp_path: Path) -> None:
        md_path = tmp_path / "plain.md"
        md_path.write_text("No marker here.", encoding="utf-8")
        assert assets.read_meta(md_path) is None

    def test_returns_none_when_meta_missing(self, tmp_path: Path) -> None:
        md_path = tmp_path / "doc.md"
        md_path.write_text("<!-- assets: doc_assets/meta.json -->", encoding="utf-8")
        # assets dir not created -- meta.json missing
        assert assets.read_meta(md_path) is None
