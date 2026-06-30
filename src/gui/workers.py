# ================================================================
# gui/workers
# ================================================================
# Objective:
#       QThread workers that run batch conversions and Mover
#       copy/move jobs off the main thread so the GUI remains
#       responsive. Emits signals for per-file progress and final
#       batch completion.
# Inputs:
#       - BatchWorker: root_dir, direction, formats, options,
#         recursive, dest_dir passed in from the main window
#       - MoverWorker: root_dir, dest_dir, extensions, mode,
#         recursive passed in from the main window
# Outputs:
#       - file_done / batch_done signals per worker, carrying
#         ConversionResult/BatchResult or MoveResult/MoveBatchResult
# Notes:
#       - Worker holds a strong reference in MainWindow._worker
#         to prevent GC while running.
# ================================================================

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal  # type: ignore

from src.batch import (
    collect_forward_files,
    collect_reverse_files,
    is_assets_path,
    resolve_file_dest_dir,
)
from src.converter.core import convert
from src.mover import collect_mover_files, move_or_copy_file, resolve_mover_dest_path
from src.mover import MoveBatchResult, MoveResult
from src.schemas import BatchResult, ConversionResult


class BatchWorker(QThread):
    """Run a full batch conversion in a background thread."""

    file_done: Signal = Signal(object)   # ConversionResult
    batch_done: Signal = Signal(object)  # BatchResult

    def __init__(
        self,
        root_dir: Path,
        direction: str,
        formats: set[str],
        options: dict,
        recursive: bool,
        dest_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.root_dir = root_dir
        self.direction = direction
        self.formats = formats
        self.options = options
        self.recursive = recursive
        self.dest_dir = dest_dir
        self.abort = False

    def run(self) -> None:
        if self.direction == "forward":
            files = collect_forward_files(self.root_dir, self.formats, self.recursive)
        else:
            files = collect_reverse_files(self.root_dir, self.formats, self.recursive)

        results: list[ConversionResult] = []
        succeeded = failed = skipped = 0

        for file_path in files:
            if self.abort:
                break
            file_dest_dir = resolve_file_dest_dir(file_path, self.root_dir, self.dest_dir)
            result = convert(
                file_path, direction=self.direction, options=self.options, dest_dir=file_dest_dir
            )
            results.append(result)
            if result.status == "success":
                succeeded += 1
            else:
                failed += 1
            self.file_done.emit(result)

        batch = BatchResult(
            total=len(files),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            results=results,
        )
        self.batch_done.emit(batch)


class MoverWorker(QThread):
    """Run a copy/move batch in a background thread."""

    file_done: Signal = Signal(object)   # MoveResult
    batch_done: Signal = Signal(object)  # MoveBatchResult

    def __init__(
        self,
        root_dir: Path,
        dest_dir: Path,
        extensions: set[str],
        mode: str,
        recursive: bool,
        files: list[Path] | None = None,
    ) -> None:
        super().__init__()
        self.root_dir = root_dir
        self.dest_dir = dest_dir
        self.extensions = extensions
        self.mode = mode
        self.recursive = recursive
        self.files = files  # pre-collected list; None means collect in run()
        self.abort = False

    def run(self) -> None:
        files = self.files if self.files is not None else collect_mover_files(
            self.root_dir, self.extensions, self.recursive
        )

        results: list[MoveResult] = []
        succeeded = 0
        failed = 0

        for file_path in files:
            if self.abort:
                break
            dest_path = resolve_mover_dest_path(file_path, self.root_dir, self.dest_dir)
            result = move_or_copy_file(file_path, dest_path, self.mode)
            results.append(result)
            if result.status == "success":
                succeeded += 1
            else:
                failed += 1
            self.file_done.emit(result)

        batch = MoveBatchResult(
            total=len(files), succeeded=succeeded, failed=failed, results=results
        )
        self.batch_done.emit(batch)
