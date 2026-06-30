# ================================================================
# mover
# ================================================================
# Objective:
#       Copy or move files by extension (.txt, .pdf, .docx, .md,
#       .rtf, .html/.htm) from a source root directory into a
#       destination directory, mirroring the source's subdirectory
#       structure filtered to only the matching files. A .md file's
#       {stem}_assets/ sidecar (if present) travels with it.
# Inputs:
#       - root_dir: Path to source root directory
#       - dest_dir: Path to destination directory (required)
#       - extensions: set of format keys from MOVER_EXTENSIONS
#       - mode: "copy" or "move"
#       - recursive: whether to walk subdirectories (default True)
# Outputs:
#       - MoveBatchResult with per-file MoveResult list
# Notes:
#       - Files in _assets/ sidecars are automatically skipped as
#         top-level matches (they are only ever carried along with
#         their parent .md file).
#       - Destination conflicts are overwritten, consistent with the
#         project's "no collision suffixes" convention.
# ================================================================

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from src.batch import is_assets_path, resolve_file_dest_dir
from src.converter.assets import assets_dir

# Extensions that map to each mover file-type key
MOVER_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "txt":  (".txt",),
    "pdf":  (".pdf",),
    "docx": (".docx",),
    "md":   (".md",),
    "rtf":  (".rtf",),
    "html": (".html", ".htm"),
}


@dataclass
class MoveResult:
    """Result for a single file copy/move operation."""

    input_path: Path
    output_path: Path | None       # None when the operation fails before writing
    status: str                    # "success" or "failure"
    error: str = ""


@dataclass
class MoveBatchResult:
    """Aggregated result for a Mover batch run."""

    total: int
    succeeded: int
    failed: int
    results: list[MoveResult] = field(default_factory=list)


def collect_mover_files(
    root_dir: Path,
    extensions: set[str],
    recursive: bool,
) -> list[Path]:
    """Collect files under root_dir matching the selected extension keys."""
    allowed_exts: set[str] = set()
    if extensions:
        for key in extensions:
            allowed_exts.update(MOVER_EXTENSIONS.get(key, ()))
    else:
        for exts in MOVER_EXTENSIONS.values():
            allowed_exts.update(exts)

    pattern = "**/*" if recursive else "*"
    files: list[Path] = []
    for path in root_dir.glob(pattern):
        if not path.is_file():
            continue
        if path.suffix.lower() not in allowed_exts:
            continue
        if is_assets_path(path):
            continue
        if path.name.startswith("~$"):  # Word lock file
            continue
        files.append(path)

    return sorted(files)


def resolve_mover_dest_path(file_path: Path, root_dir: Path, dest_dir: Path) -> Path:
    """Return the mirrored destination file path for file_path under dest_dir."""
    file_dest_dir = resolve_file_dest_dir(file_path, root_dir, dest_dir)
    return file_dest_dir / file_path.name


def move_or_copy_file(file_path: Path, dest_path: Path, mode: str) -> MoveResult:
    """
    Copy or move file_path to dest_path, overwriting on conflict.
    If file_path is a .md file with a {stem}_assets/ sidecar, the sidecar
    is carried along to dest_path.parent. Never raises.
    """
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if mode == "copy":
            shutil.copy2(file_path, dest_path)
        elif mode == "move":
            if dest_path.exists():
                dest_path.unlink()
            shutil.move(str(file_path), str(dest_path))
        else:
            raise ValueError(f"mode must be 'copy' or 'move', got {mode!r}")

        if file_path.suffix.lower() == ".md":
            move_or_copy_sidecar(file_path, dest_path, mode)

        return MoveResult(input_path=file_path, output_path=dest_path, status="success")
    except (OSError, shutil.Error) as exc:
        return MoveResult(
            input_path=file_path, output_path=None, status="failure", error=str(exc)
        )


def move_or_copy_sidecar(file_path: Path, dest_path: Path, mode: str) -> None:
    """Carry a .md file's {stem}_assets/ sidecar along to dest_path.parent."""
    sidecar = assets_dir(file_path)
    if not sidecar.is_dir():
        return

    dest_sidecar = dest_path.parent / sidecar.name
    if mode == "copy":
        shutil.copytree(sidecar, dest_sidecar, dirs_exist_ok=True)
    else:
        if dest_sidecar.exists():
            shutil.rmtree(dest_sidecar)
        shutil.move(str(sidecar), str(dest_sidecar))


def run_mover(
    root_dir: Path,
    dest_dir: Path,
    extensions: set[str] | None = None,
    mode: str = "copy",
    recursive: bool = True,
) -> MoveBatchResult:
    """Run a copy/move batch over root_dir, mirroring structure under dest_dir."""
    if extensions is None:
        extensions = set()

    files = collect_mover_files(root_dir, extensions, recursive)

    results: list[MoveResult] = []
    succeeded = 0
    failed = 0

    for file_path in files:
        dest_path = resolve_mover_dest_path(file_path, root_dir, dest_dir)
        result = move_or_copy_file(file_path, dest_path, mode)
        results.append(result)
        if result.status == "success":
            succeeded += 1
        else:
            failed += 1

    return MoveBatchResult(
        total=len(files), succeeded=succeeded, failed=failed, results=results
    )
