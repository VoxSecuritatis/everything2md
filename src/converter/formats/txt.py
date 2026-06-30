# ================================================================
# formats/txt
# ================================================================
# Objective:
#       Forward: read a .txt file and wrap its content in a
#       minimal Markdown document with YAML front matter.
#       Reverse: strip Markdown syntax from a .md file and write
#       the result as a plain UTF-8 .txt file.
# Inputs:
#       - forward: Path to .txt source file
#       - reverse: Path to .md file
# Outputs:
#       - forward: sibling .md file + meta.json sidecar
#       - reverse: sibling .txt file
# Notes:
#       - TXT has no images; assets dir is not created.
#       - Reverse strips headings, bold, italic, links, fenced
#         code blocks, and the YAML front matter block.
# ================================================================

from __future__ import annotations

import re
import time
from pathlib import Path

from src.converter.assets import asset_marker, write_meta
from src.converter.naming import forward_output, reverse_output
from src.schemas import ConversionResult

# ------------------------------------------------
# Forward: TXT -> MD
# ------------------------------------------------

def convert_forward(
    source_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert a .txt file to a sibling .md file."""
    start = time.monotonic()
    output_path = forward_output(source_path, dest_dir)

    try:
        text = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ConversionResult(
            input_path=source_path,
            output_path=None,
            direction="forward",
            source_format="txt",
            status="failure",
            error=str(exc),
        )

    today = _today()
    front_matter = (
        f"---\n"
        f"source: {source_path.name}\n"
        f"date: {today}\n"
        f"---\n"
    )
    marker = asset_marker(output_path)
    md_content = f"{front_matter}\n{marker}\n\n## Content\n\n{text.rstrip()}\n"

    output_path.write_text(md_content, encoding="utf-8")
    meta_path = write_meta(output_path, source_format="txt")  # noqa: F841

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=source_path,
        output_path=output_path,
        direction="forward",
        source_format="txt",
        status="success",
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Reverse: MD -> TXT
# ------------------------------------------------

def convert_reverse(
    md_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert a .md file back to a plain .txt file."""
    start = time.monotonic()
    output_path = reverse_output(md_path, "txt", dest_dir)

    try:
        md_text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ConversionResult(
            input_path=md_path,
            output_path=None,
            direction="reverse",
            source_format="txt",
            status="failure",
            error=str(exc),
        )

    plain = strip_markdown(md_text)
    output_path.write_text(plain, encoding="utf-8")

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=md_path,
        output_path=output_path,
        direction="reverse",
        source_format="txt",
        status="success",
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Helpers
# ------------------------------------------------

def strip_markdown(text: str) -> str:
    """
    Remove common Markdown syntax and return plain text.
    Handles: YAML front matter, asset markers, headings, bold,
    italic, inline code, fenced code blocks, links, images, HTML comments.
    """
    # YAML front matter (--- ... ---)
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    # HTML comments (asset markers etc.)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Fenced code blocks
    text = re.sub(r"```[^\n]*\n(.*?)```", r"\1", text, flags=re.DOTALL)
    # Headings
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bold/italic (*** ** * ___ __ _)
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Images ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Links [text](url)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Table rows -- keep cell content, strip pipes
    text = re.sub(r"^\|(.+)\|$", lambda m: " ".join(
        c.strip() for c in m.group(1).split("|")
    ), text, flags=re.MULTILINE)
    # Table separator rows (|---|---|)
    text = re.sub(r"^\|[-| :]+\|$", "", text, flags=re.MULTILINE)
    # Collapse excess blank lines (max 2)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _today() -> str:
    from datetime import date
    return date.today().isoformat()
