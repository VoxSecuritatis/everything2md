# ================================================================
# naming
# ================================================================
# Objective:
#       Resolve the output file path for both forward and reverse
#       conversions. Forward: source -> .md sibling. Reverse:
#       .md -> source sibling using the target format extension.
#       Both directions overwrite existing files (no collision suffix).
# Inputs:
#       - input_path: Path to source file (forward) or .md (reverse)
#       - target_ext: extension for reverse output (e.g. ".pdf")
#       - dest_dir: optional override directory; defaults to the
#         input file's own directory when not given
# Outputs:
#       - resolved output Path
# Notes:
#       - When dest_dir is given, it is created (with parents) so
#         callers can write the output immediately.
# ================================================================

from __future__ import annotations

from pathlib import Path

EXT_MAP: dict[str, str] = {
    "pdf": ".pdf",
    "docx": ".docx",
    "txt": ".txt",
    "html": ".html",
    "htm": ".html",
    "rtf": ".rtf",
    "epub": ".epub",
}


def forward_output(source_path: Path, dest_dir: Path | None = None) -> Path:
    """Return the .md output path for a forward conversion."""
    if dest_dir is None:
        return source_path.with_suffix(".md")
    dest_dir.mkdir(parents=True, exist_ok=True)
    return (dest_dir / source_path.name).with_suffix(".md")


def reverse_output(md_path: Path, source_format: str, dest_dir: Path | None = None) -> Path:
    """
    Return the source-format output path for a reverse conversion.
    source_format is the format string from meta.json (e.g. "pdf", "docx").
    """
    ext = EXT_MAP.get(source_format.lower())
    if ext is None:
        raise ValueError(f"Unknown source format for reverse output: {source_format!r}")
    if dest_dir is None:
        return md_path.with_suffix(ext)
    dest_dir.mkdir(parents=True, exist_ok=True)
    return (dest_dir / md_path.name).with_suffix(ext)
