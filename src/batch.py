# ================================================================
# batch
# ================================================================
# Objective:
#       Recursively walk a root directory, collect source files
#       (forward mode) or .md files (reverse mode), and run each
#       through converter/core.py. Provides format filtering,
#       dry-run support, and per-file error isolation.
#       Returns a BatchResult summarizing the run.
# Inputs:
#       - root_dir: Path to root directory to walk
#       - direction: "forward" or "reverse"
#       - formats: set of format strings to include (e.g. {"pdf","docx"})
#         empty set means all supported formats
#       - options: dict passed through to converter/core.convert()
#       - recursive: whether to walk subdirectories (default True)
#       - dry_run: list files only, no conversions performed
#       - dest_dir: optional output directory override; when set and
#         recursive, each file's subdirectory structure relative to
#         root_dir is mirrored under dest_dir
# Outputs:
#       - BatchResult with per-file ConversionResult list
# Notes:
#       - Files in _assets/ sidecars are automatically skipped.
#       - Word lock files (~$name.docx) are skipped in forward mode.
#       - One file failure does not stop the batch.
# ================================================================

from __future__ import annotations

from pathlib import Path

from src.config import SUPPORTED_EXTENSIONS
from src.converter.core import convert
from src.schemas import BatchResult, ConversionResult

# Extensions that map to each format string (for forward mode filtering)
FORMAT_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "pdf":  (".pdf",),
    "docx": (".docx",),
    "txt":  (".txt",),
    "html": (".html", ".htm"),
    "rtf":  (".rtf",),
    "epub": (".epub",),
}

# Reverse of the above: extension -> format string
EXT_TO_FORMAT: dict[str, str] = {
    ext: fmt
    for fmt, exts in FORMAT_EXTENSIONS.items()
    for ext in exts
}


def collect_forward_files(
    root_dir: Path,
    formats: set[str],
    recursive: bool,
) -> list[Path]:
    """Collect source files for forward conversion."""
    allowed_exts: set[str] = set()
    if formats:
        for fmt in formats:
            allowed_exts.update(FORMAT_EXTENSIONS.get(fmt, ()))
    else:
        allowed_exts = set(SUPPORTED_EXTENSIONS)

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


def collect_reverse_files(
    root_dir: Path,
    formats: set[str],
    recursive: bool,
) -> list[Path]:
    """Collect .md files for reverse conversion."""
    pattern = "**/*.md" if recursive else "*.md"
    files: list[Path] = []
    for path in root_dir.glob(pattern):
        if not path.is_file():
            continue
        if is_assets_path(path):
            continue
        # If format filter is active, check the asset marker
        if formats:
            from src.converter.assets import read_meta
            meta = read_meta(path)
            if meta:
                src_fmt = meta.get("source_format", "")
                if src_fmt not in formats:
                    continue
            # If no meta, include the file anyway (format check happens at convert time)
        files.append(path)

    return sorted(files)


def run_batch(
    root_dir: Path,
    direction: str = "forward",
    formats: set[str] | None = None,
    options: dict | None = None,
    recursive: bool = True,
    dry_run: bool = False,
    dest_dir: Path | None = None,
) -> BatchResult:
    """
    Run a batch conversion over root_dir.
    direction: "forward" or "reverse".
    formats: set of format strings; None means all formats.
    """
    if formats is None:
        formats = set()
    if options is None:
        options = {}

    if direction == "forward":
        files = collect_forward_files(root_dir, formats, recursive)
    elif direction == "reverse":
        files = collect_reverse_files(root_dir, formats, recursive)
    else:
        raise ValueError(f"direction must be 'forward' or 'reverse', got {direction!r}")

    results: list[ConversionResult] = []
    succeeded = 0
    failed = 0
    skipped = 0

    for file_path in files:
        if dry_run:
            skipped += 1
            results.append(
                ConversionResult(
                    input_path=file_path,
                    output_path=None,
                    direction=direction,
                    source_format=EXT_TO_FORMAT.get(file_path.suffix.lower(), ""),
                    status="success",  # dry-run always "success" for reporting
                    warnings=["[dry-run] would convert"],
                )
            )
            continue

        file_dest_dir = resolve_file_dest_dir(file_path, root_dir, dest_dir)
        result = convert(file_path, direction=direction, options=options, dest_dir=file_dest_dir)
        results.append(result)
        if result.status == "success":
            succeeded += 1
        else:
            failed += 1

    return BatchResult(
        total=len(files),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        results=results,
    )


def is_assets_path(path: Path) -> bool:
    """Return True if the file lives inside an _assets directory."""
    return any(parent.name.endswith("_assets") for parent in path.parents)


def resolve_file_dest_dir(file_path: Path, root_dir: Path, dest_dir: Path | None) -> Path | None:
    """
    Return the mirrored destination directory for file_path, or None if
    dest_dir is unset. Mirrors file_path's subdirectory structure relative
    to root_dir under dest_dir, so root-level files map to dest_dir itself.
    """
    if dest_dir is None:
        return None
    rel_dir = file_path.parent.relative_to(root_dir)
    return dest_dir / rel_dir
