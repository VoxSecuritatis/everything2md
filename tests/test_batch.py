# ================================================================
# tests/test_batch
# ================================================================

from __future__ import annotations

from pathlib import Path

from src.batch import (
    collect_forward_files,
    collect_reverse_files,
    is_assets_path,
    resolve_file_dest_dir,
    run_batch,
)


class TestCollectForwardFiles:
    def test_finds_txt_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        (tmp_path / "b.txt").write_text("x", encoding="utf-8")
        files = collect_forward_files(tmp_path, {"txt"}, recursive=False)
        assert len(files) == 2

    def test_skips_assets_dirs(self, tmp_path: Path) -> None:
        assets_dir = tmp_path / "doc_assets"
        assets_dir.mkdir()
        (assets_dir / "nested.txt").write_text("x", encoding="utf-8")
        (tmp_path / "real.txt").write_text("x", encoding="utf-8")
        files = collect_forward_files(tmp_path, {"txt"}, recursive=True)
        # Verify by name and count rather than string search (tmp_path itself may contain _assets)
        assert len(files) == 1
        assert files[0].name == "real.txt"

    def test_skips_word_lock_files(self, tmp_path: Path) -> None:
        (tmp_path / "~$locked.docx").write_text("x", encoding="utf-8")
        (tmp_path / "real.docx").write_text("PK", encoding="utf-8")
        files = collect_forward_files(tmp_path, {"docx"}, recursive=False)
        names = [f.name for f in files]
        assert "~$locked.docx" not in names

    def test_all_formats_when_empty_set(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        (tmp_path / "b.html").write_text("<html></html>", encoding="utf-8")
        files = collect_forward_files(tmp_path, set(), recursive=False)
        assert len(files) == 2

    def test_no_recursive_skips_subdirs(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("x", encoding="utf-8")
        (tmp_path / "top.txt").write_text("x", encoding="utf-8")
        files = collect_forward_files(tmp_path, {"txt"}, recursive=False)
        assert len(files) == 1
        assert files[0].name == "top.txt"


class TestCollectReverseFiles:
    def test_finds_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("# Hello", encoding="utf-8")
        (tmp_path / "b.md").write_text("# World", encoding="utf-8")
        files = collect_reverse_files(tmp_path, set(), recursive=False)
        assert len(files) == 2

    def test_skips_assets_md_files(self, tmp_path: Path) -> None:
        assets_dir = tmp_path / "doc_assets"
        assets_dir.mkdir()
        (assets_dir / "notes.md").write_text("# Notes", encoding="utf-8")
        (tmp_path / "real.md").write_text("# Real", encoding="utf-8")
        files = collect_reverse_files(tmp_path, set(), recursive=True)
        assert len(files) == 1


class TestIsAssetsPath:
    def test_detects_assets_path(self, tmp_path: Path) -> None:
        p = tmp_path / "doc_assets" / "images" / "img.png"
        assert is_assets_path(p)

    def test_non_assets_path(self, tmp_path: Path) -> None:
        p = tmp_path / "docs" / "report.txt"
        assert not is_assets_path(p)


class TestRunBatch:
    def test_dry_run_does_not_convert(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        batch = run_batch(tmp_path, direction="forward", dry_run=True)
        assert batch.total == 1
        assert batch.skipped == 1
        assert not (tmp_path / "a.md").exists()

    def test_forward_batch_converts_txt(self, sample_txt: Path) -> None:
        root = sample_txt.parent
        batch = run_batch(root, direction="forward", formats={"txt"})
        assert batch.total >= 1
        assert batch.succeeded >= 1
        assert (root / "sample.md").exists()

    def test_invariant_total_equals_sum(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        (tmp_path / "b.txt").write_text("world", encoding="utf-8")
        batch = run_batch(tmp_path, direction="forward", formats={"txt"})
        assert batch.total == batch.succeeded + batch.failed + batch.skipped

    def test_dest_dir_none_writes_next_to_source(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        batch = run_batch(tmp_path, direction="forward", formats={"txt"})
        assert batch.succeeded == 1
        assert (tmp_path / "a.md").exists()

    def test_dest_dir_writes_root_level_file_to_destination(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        dest = tmp_path / "out"
        batch = run_batch(tmp_path, direction="forward", formats={"txt"}, dest_dir=dest)
        assert batch.succeeded == 1
        assert (dest / "a.md").exists()
        assert not (tmp_path / "a.md").exists()

    def test_dest_dir_mirrors_subdirectory_structure(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("hello", encoding="utf-8")
        dest = tmp_path / "out"
        batch = run_batch(
            tmp_path, direction="forward", formats={"txt"}, recursive=True, dest_dir=dest
        )
        assert batch.succeeded == 1
        assert (dest / "sub" / "nested.md").exists()


class TestResolveFileDestDir:
    def test_returns_none_when_dest_dir_is_none(self, tmp_path: Path) -> None:
        file_path = tmp_path / "a.txt"
        assert resolve_file_dest_dir(file_path, tmp_path, None) is None

    def test_root_level_file_maps_to_dest_dir_itself(self, tmp_path: Path) -> None:
        file_path = tmp_path / "a.txt"
        dest = tmp_path / "out"
        assert resolve_file_dest_dir(file_path, tmp_path, dest) == dest

    def test_nested_file_mirrors_relative_subdir(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sub" / "deep" / "a.txt"
        dest = tmp_path / "out"
        assert resolve_file_dest_dir(file_path, tmp_path, dest) == dest / "sub" / "deep"
