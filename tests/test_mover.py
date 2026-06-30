# ================================================================
# tests/test_mover
# ================================================================

from __future__ import annotations

from pathlib import Path

import pytest

from src.mover import (
    MoveBatchResult,
    MoveResult,
    collect_mover_files,
    move_or_copy_file,
    resolve_mover_dest_path,
    run_mover,
)


class TestCollectMoverFiles:
    def test_finds_files_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        (tmp_path / "b.pdf").write_text("x", encoding="utf-8")
        (tmp_path / "other.epub").write_text("x", encoding="utf-8")
        files = collect_mover_files(tmp_path, {"txt", "pdf"}, recursive=False)
        names = {f.name for f in files}
        assert names == {"a.txt", "b.pdf"}

    def test_htm_matches_html_key(self, tmp_path: Path) -> None:
        (tmp_path / "page.htm").write_text("x", encoding="utf-8")
        (tmp_path / "page.html").write_text("x", encoding="utf-8")
        files = collect_mover_files(tmp_path, {"html"}, recursive=False)
        names = {f.name for f in files}
        assert names == {"page.htm", "page.html"}

    def test_skips_assets_directories(self, tmp_path: Path) -> None:
        assets_dir = tmp_path / "doc_assets"
        assets_dir.mkdir()
        (assets_dir / "notes.txt").write_text("x", encoding="utf-8")
        (tmp_path / "real.txt").write_text("x", encoding="utf-8")
        files = collect_mover_files(tmp_path, {"txt"}, recursive=True)
        assert len(files) == 1
        assert files[0].name == "real.txt"

    def test_skips_word_lock_files(self, tmp_path: Path) -> None:
        (tmp_path / "~$locked.docx").write_text("x", encoding="utf-8")
        (tmp_path / "real.docx").write_text("x", encoding="utf-8")
        files = collect_mover_files(tmp_path, {"docx"}, recursive=False)
        assert all(not f.name.startswith("~$") for f in files)
        assert any(f.name == "real.docx" for f in files)

    def test_recursive_includes_subdirs(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("x", encoding="utf-8")
        (tmp_path / "top.txt").write_text("x", encoding="utf-8")
        files = collect_mover_files(tmp_path, {"txt"}, recursive=True)
        assert len(files) == 2

    def test_non_recursive_skips_subdirs(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("x", encoding="utf-8")
        (tmp_path / "top.txt").write_text("x", encoding="utf-8")
        files = collect_mover_files(tmp_path, {"txt"}, recursive=False)
        assert len(files) == 1
        assert files[0].name == "top.txt"

    def test_empty_extensions_collects_all_types(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        (tmp_path / "b.md").write_text("x", encoding="utf-8")
        (tmp_path / "c.pdf").write_text("x", encoding="utf-8")
        files = collect_mover_files(tmp_path, set(), recursive=False)
        assert len(files) == 3


class TestResolveMoverDestPath:
    def test_root_level_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "a.txt"
        dest = tmp_path / "out"
        result = resolve_mover_dest_path(file_path, tmp_path, dest)
        assert result == dest / "a.txt"

    def test_nested_file_mirrors_subdir(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sub" / "deep" / "a.txt"
        dest = tmp_path / "out"
        result = resolve_mover_dest_path(file_path, tmp_path, dest)
        assert result == dest / "sub" / "deep" / "a.txt"


class TestMoveOrCopyFile:
    def test_copy_leaves_source_intact(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "a.txt"
        src.parent.mkdir()
        src.write_text("hello", encoding="utf-8")
        dest = tmp_path / "out" / "a.txt"

        result = move_or_copy_file(src, dest, mode="copy")

        assert result.status == "success"
        assert src.exists()
        assert dest.read_text(encoding="utf-8") == "hello"

    def test_copy_creates_dest_parent(self, tmp_path: Path) -> None:
        src = tmp_path / "a.txt"
        src.write_text("x", encoding="utf-8")
        dest = tmp_path / "deep" / "nested" / "a.txt"
        result = move_or_copy_file(src, dest, mode="copy")
        assert result.status == "success"
        assert dest.exists()

    def test_move_removes_source(self, tmp_path: Path) -> None:
        src = tmp_path / "a.txt"
        src.write_text("hello", encoding="utf-8")
        dest = tmp_path / "out" / "a.txt"

        result = move_or_copy_file(src, dest, mode="move")

        assert result.status == "success"
        assert not src.exists()
        assert dest.read_text(encoding="utf-8") == "hello"

    def test_copy_overwrites_existing_dest(self, tmp_path: Path) -> None:
        src = tmp_path / "a.txt"
        src.write_text("new content", encoding="utf-8")
        dest = tmp_path / "out" / "a.txt"
        dest.parent.mkdir()
        dest.write_text("old content", encoding="utf-8")

        result = move_or_copy_file(src, dest, mode="copy")

        assert result.status == "success"
        assert dest.read_text(encoding="utf-8") == "new content"

    def test_move_overwrites_existing_dest(self, tmp_path: Path) -> None:
        src = tmp_path / "a.txt"
        src.write_text("new content", encoding="utf-8")
        dest = tmp_path / "out" / "a.txt"
        dest.parent.mkdir()
        dest.write_text("old content", encoding="utf-8")

        result = move_or_copy_file(src, dest, mode="move")

        assert result.status == "success"
        assert dest.read_text(encoding="utf-8") == "new content"
        assert not src.exists()

    def test_copy_md_carries_sidecar(self, tmp_path: Path) -> None:
        src = tmp_path / "doc.md"
        src.write_text("# Doc", encoding="utf-8")
        sidecar = tmp_path / "doc_assets"
        sidecar.mkdir()
        (sidecar / "meta.json").write_text('{"source_format":"pdf"}', encoding="utf-8")

        dest = tmp_path / "out" / "doc.md"
        result = move_or_copy_file(src, dest, mode="copy")

        assert result.status == "success"
        assert src.exists()  # source .md still there
        assert dest.exists()
        assert (tmp_path / "out" / "doc_assets" / "meta.json").exists()

    def test_move_md_moves_sidecar(self, tmp_path: Path) -> None:
        src = tmp_path / "doc.md"
        src.write_text("# Doc", encoding="utf-8")
        sidecar = tmp_path / "doc_assets"
        sidecar.mkdir()
        (sidecar / "meta.json").write_text('{"source_format":"pdf"}', encoding="utf-8")

        dest = tmp_path / "out" / "doc.md"
        result = move_or_copy_file(src, dest, mode="move")

        assert result.status == "success"
        assert not src.exists()
        assert not sidecar.exists()
        assert (tmp_path / "out" / "doc_assets" / "meta.json").exists()

    def test_non_md_does_not_carry_sidecar(self, tmp_path: Path) -> None:
        src = tmp_path / "a.txt"
        src.write_text("hello", encoding="utf-8")
        sidecar = tmp_path / "a_assets"
        sidecar.mkdir()
        (sidecar / "meta.json").write_text("{}", encoding="utf-8")

        dest = tmp_path / "out" / "a.txt"
        move_or_copy_file(src, dest, mode="copy")

        assert not (tmp_path / "out" / "a_assets").exists()


class TestRunMover:
    def test_copies_root_level_file_to_dest(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        dest = tmp_path / "out"
        batch = run_mover(tmp_path, dest, extensions={"txt"}, mode="copy")
        assert batch.succeeded == 1
        assert (dest / "a.txt").exists()
        assert (tmp_path / "a.txt").exists()

    def test_mirrors_subdirectory_structure(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("hello", encoding="utf-8")
        dest = tmp_path / "out"
        batch = run_mover(tmp_path, dest, extensions={"txt"}, mode="copy", recursive=True)
        assert batch.succeeded == 1
        assert (dest / "sub" / "nested.txt").exists()

    def test_skips_non_matching_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        (tmp_path / "b.pdf").write_text("x", encoding="utf-8")
        dest = tmp_path / "out"
        batch = run_mover(tmp_path, dest, extensions={"txt"}, mode="copy")
        assert batch.succeeded == 1
        assert (dest / "a.txt").exists()
        assert not (dest / "b.pdf").exists()

    def test_move_removes_source_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        dest = tmp_path / "out"
        batch = run_mover(tmp_path, dest, extensions={"txt"}, mode="move")
        assert batch.succeeded == 1
        assert not (tmp_path / "a.txt").exists()
        assert (dest / "a.txt").exists()

    def test_invariant_total_equals_sum(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        (tmp_path / "b.txt").write_text("x", encoding="utf-8")
        dest = tmp_path / "out"
        batch = run_mover(tmp_path, dest, extensions={"txt"}, mode="copy")
        assert batch.total == batch.succeeded + batch.failed
