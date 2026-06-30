# ================================================================
# formats/rtf
# ================================================================
# Objective:
#       Forward: extract plain text from .rtf using striprtf and
#       wrap it in a minimal Markdown document. Rich formatting
#       (bold, headings, tables) is not preserved in v1 -- this
#       is documented in the YAML front matter.
#       Reverse: write the markdown content as a minimal plain-
#       text RTF file (RTF header + paragraphs, no advanced
#       formatting).
# Inputs:
#       - forward: Path to .rtf source file
#       - reverse: Path to .md file
# Outputs:
#       - forward: sibling .md + meta.json sidecar
#       - reverse: sibling .rtf
# Notes:
#       - striprtf handles encoding detection internally.
#       - RTF generation is a plain-text wrapper only; color,
#         font tables, and character formatting are not added.
# ================================================================

from __future__ import annotations

import re
import time
from pathlib import Path

from src.converter.assets import asset_marker, write_meta
from src.converter.formats.txt import strip_markdown
from src.converter.naming import forward_output, reverse_output
from src.schemas import ConversionResult

# ------------------------------------------------
# Forward: RTF -> MD
# ------------------------------------------------

def convert_forward(
    source_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert a .rtf file to a sibling .md file (plain text extraction)."""
    from striprtf.striprtf import rtf_to_text  # type: ignore

    start = time.monotonic()
    output_path = forward_output(source_path, dest_dir)
    warnings = ["RTF forward conversion extracts plain text only; formatting is not preserved."]

    try:
        raw = source_path.read_text(encoding="utf-8", errors="replace")
        text = rtf_to_text(raw)
        text = text.strip()
    except Exception as exc:
        return ConversionResult(
            input_path=source_path,
            output_path=None,
            direction="forward",
            source_format="rtf",
            status="failure",
            error=str(exc),
        )

    today = _today()
    front_matter = (
        f"---\n"
        f"source: {source_path.name}\n"
        f"date: {today}\n"
        f"formatting_preserved: false\n"
        f"---\n"
    )
    marker = asset_marker(output_path)
    final_md = f"{front_matter}\n{marker}\n\n## Content\n\n{text}\n"

    output_path.write_text(final_md, encoding="utf-8")
    write_meta(output_path, "rtf")

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=source_path,
        output_path=output_path,
        direction="forward",
        source_format="rtf",
        status="success",
        warnings=warnings,
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Reverse: MD -> RTF
# ------------------------------------------------

def convert_reverse(
    md_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert a .md file to a minimal plain-text .rtf file."""
    start = time.monotonic()
    output_path = reverse_output(md_path, "rtf", dest_dir)
    warnings = ["RTF reverse conversion writes plain text only; no rich formatting is applied."]

    try:
        md_text = md_path.read_text(encoding="utf-8", errors="replace")
        plain = strip_markdown(md_text)
        rtf_content = build_rtf(plain)
        output_path.write_bytes(rtf_content)
    except Exception as exc:
        return ConversionResult(
            input_path=md_path,
            output_path=None,
            direction="reverse",
            source_format="rtf",
            status="failure",
            error=str(exc),
        )

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=md_path,
        output_path=output_path,
        direction="reverse",
        source_format="rtf",
        status="success",
        warnings=warnings,
        duration_ms=elapsed,
    )


# ------------------------------------------------
# RTF builder
# ------------------------------------------------

def build_rtf(plain_text: str) -> bytes:
    """
    Build a minimal RTF 1.9 document from plain text.
    Each non-empty paragraph becomes an RTF paragraph.
    Non-ASCII characters are encoded as RTF Unicode escapes.
    """
    header = (
        r"{\rtf1\ansi\ansicpg1252\deff0"
        r"{\fonttbl{\f0\froman\fcharset0 Times New Roman;}}"
        r"{\colortbl ;}"
        r"\widowctrl\wpaper12240\wpapr15840\margl1440\margr1440\margt1440\margb1440"
        r"\sectd\sbknone"
        "\n"
    )

    paragraphs: list[str] = []
    for para in plain_text.split("\n\n"):
        para = para.strip()
        if para:
            encoded = rtf_encode(para.replace("\n", " "))
            paragraphs.append(r"\pard\sa200 " + encoded + r"\par")

    body = "\n".join(paragraphs)
    rtf_doc = header + body + "\n}"

    return rtf_doc.encode("ascii", errors="replace")


def rtf_encode(text: str) -> str:
    """Encode non-ASCII characters as RTF Unicode escapes (\\uN?)."""
    result: list[str] = []
    for ch in text:
        code = ord(ch)
        if code < 128:
            if ch in ("\\", "{", "}"):
                result.append("\\" + ch)
            else:
                result.append(ch)
        else:
            result.append(f"\\u{code}?")
    return "".join(result)


def _today() -> str:
    from datetime import date
    return date.today().isoformat()
