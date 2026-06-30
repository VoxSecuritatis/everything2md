# ================================================================
# converter/core
# ================================================================
# Objective:
#       Single dispatch point for all conversions. Detects the
#       source format from the file extension and delegates to
#       the appropriate format module. Wraps every call in a
#       try/except so batch mode always gets a ConversionResult
#       even on hard failure.
# Inputs:
#       - input_path: Path to source file (forward) or .md (reverse)
#       - direction: "forward" or "reverse"
#       - options: dict of optional flags (e.g. {"ocr": True})
#       - dest_dir: optional output directory override; defaults to
#         the input file's own directory when not given
# Outputs:
#       - ConversionResult (never raises)
# Notes:
#       - Format modules must implement convert_forward(path, options)
#         and convert_reverse(path, options) returning ConversionResult.
#       - Reverse conversion reads the asset marker from the .md to
#         determine the target format; falls back to inferring from
#         a sibling source file, then raises if still unknown.
# ================================================================

from __future__ import annotations

import time
from pathlib import Path

from src.converter.assets import read_meta
from src.logging_setup import log_result, setup_logging
from src.schemas import ConversionResult

setup_logging()

FORWARD_EXTENSIONS: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".html": "html",
    ".htm": "html",
    ".rtf": "rtf",
    ".epub": "epub",
}


def convert(
    input_path: Path,
    direction: str = "forward",
    options: dict | None = None,
    dest_dir: Path | None = None,
) -> ConversionResult:
    """
    Dispatch a single-file conversion.
    direction must be "forward" or "reverse".
    Never raises -- returns ConversionResult(status="failure") on any error.
    """
    if options is None:
        options = {}

    start = time.monotonic()

    try:
        if direction == "forward":
            result = dispatch_forward(input_path, options, dest_dir)
        elif direction == "reverse":
            result = dispatch_reverse(input_path, options, dest_dir)
        else:
            raise ValueError(f"direction must be 'forward' or 'reverse', got {direction!r}")
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        result = ConversionResult(
            input_path=input_path,
            output_path=None,
            direction=direction,
            source_format=input_path.suffix.lstrip(".").lower(),
            status="failure",
            error=str(exc),
            duration_ms=elapsed,
        )

    if result.duration_ms == 0.0:
        result.duration_ms = (time.monotonic() - start) * 1000

    log_result(result)
    return result


# ------------------------------------------------
# Forward dispatch
# ------------------------------------------------

def dispatch_forward(
    input_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Route a source file to its format module's convert_forward()."""
    ext = input_path.suffix.lower()
    fmt = FORWARD_EXTENSIONS.get(ext)
    if fmt is None:
        raise ValueError(f"Unsupported extension for forward conversion: {ext!r}")

    module = load_format_module(fmt)
    return module.convert_forward(input_path, options, dest_dir)


# ------------------------------------------------
# Reverse dispatch
# ------------------------------------------------

def dispatch_reverse(
    md_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Route a .md file to its format module's convert_reverse()."""
    if md_path.suffix.lower() != ".md":
        raise ValueError(f"Reverse conversion expects a .md file, got: {md_path.suffix!r}")

    # Determine target format: read asset marker first, then fallback.
    meta = read_meta(md_path)
    if meta and "source_format" in meta:
        fmt = meta["source_format"].lower()
    else:
        fmt = options.get("format")
        if fmt is None:
            fmt = infer_format_from_sibling(md_path)
        if fmt is None:
            raise ValueError(
                f"Cannot determine target format for {md_path.name}. "
                "No asset marker found and no --format flag provided."
            )

    module = load_format_module(fmt)
    return module.convert_reverse(md_path, options, dest_dir)


def infer_format_from_sibling(md_path: Path) -> str | None:
    """Check if a source file with the same stem exists alongside the .md."""
    for ext, fmt in FORWARD_EXTENSIONS.items():
        candidate = md_path.with_suffix(ext)
        if candidate.exists() and candidate != md_path:
            return fmt
    return None


# ------------------------------------------------
# Module loader
# ------------------------------------------------

def load_format_module(fmt: str):
    """Import and return the format module for the given format string."""
    import importlib
    module_name = f"src.converter.formats.{fmt}"
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ValueError(f"No format module found for format {fmt!r}: {exc}") from exc
