# ================================================================
# formats/html
# ================================================================
# Objective:
#       Forward: convert .html/.htm to .md using markdownify.
#       Images linked in the HTML are copied to the sidecar.
#       Reverse: render .md to HTML using the markdown package,
#       wrapped in a minimal HTML5 document.
# Inputs:
#       - forward: Path to .html/.htm source file
#       - reverse: Path to .md file
# Outputs:
#       - forward: sibling .md + {stem}_assets/ sidecar
#       - reverse: sibling .html
# Notes:
#       - Only file-relative image references are copied (not http).
#       - The title is extracted from the <title> tag if present.
# ================================================================

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

from src.converter.assets import asset_marker, ensure_images_dir, write_meta
from src.converter.naming import forward_output, reverse_output
from src.schemas import ConversionResult

# ------------------------------------------------
# Forward: HTML -> MD
# ------------------------------------------------

def convert_forward(
    source_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert an HTML file to a sibling .md file."""
    import markdownify  # type: ignore

    start = time.monotonic()
    output_path = forward_output(source_path, dest_dir)
    warnings: list[str] = []
    image_count = 0

    try:
        html_text = source_path.read_text(encoding="utf-8", errors="replace")
        title = extract_title(html_text)

        # Copy local images to sidecar (next to output_path) and rewrite src attributes
        html_text, image_count, img_warnings = relocate_images(
            html_text, source_path, output_path
        )
        warnings.extend(img_warnings)

        md_text = markdownify.markdownify(
            html_text,
            heading_style="ATX",
            strip=["script", "style"],
        )
        md_text = re.sub(r"\n{3,}", "\n\n", md_text).strip()

        today = _today()
        title_line = f"title: {title}\n" if title else ""
        front_matter = (
            f"---\n"
            f"source: {source_path.name}\n"
            f"date: {today}\n"
            f"{title_line}"
            f"images: {image_count}\n"
            f"---\n"
        )
        marker = asset_marker(output_path)
        final_md = f"{front_matter}\n{marker}\n\n{md_text}\n"

        output_path.write_text(final_md, encoding="utf-8")
        write_meta(output_path, "html", image_count=image_count)

    except Exception as exc:
        return ConversionResult(
            input_path=source_path,
            output_path=None,
            direction="forward",
            source_format="html",
            status="failure",
            error=str(exc),
        )

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=source_path,
        output_path=output_path,
        direction="forward",
        source_format="html",
        status="success",
        warnings=warnings,
        image_count=image_count,
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Reverse: MD -> HTML
# ------------------------------------------------

def convert_reverse(
    md_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert a .md file to an .html file."""
    import markdown as md_lib  # type: ignore

    start = time.monotonic()
    output_path = reverse_output(md_path, "html", dest_dir)
    warnings: list[str] = []

    try:
        md_text = md_path.read_text(encoding="utf-8", errors="replace")
        title = extract_md_title(md_text)
        md_text = strip_front_matter(md_text)

        html_body = md_lib.markdown(
            md_text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
        html = build_html_page(html_body, title=title or md_path.stem)
        output_path.write_text(html, encoding="utf-8")

    except Exception as exc:
        return ConversionResult(
            input_path=md_path,
            output_path=None,
            direction="reverse",
            source_format="html",
            status="failure",
            error=str(exc),
        )

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=md_path,
        output_path=output_path,
        direction="reverse",
        source_format="html",
        status="success",
        warnings=warnings,
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Helpers
# ------------------------------------------------

def extract_title(html_text: str) -> str:
    """Extract the content of the <title> tag, or empty string."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_md_title(md_text: str) -> str:
    """Extract title from YAML front matter."""
    match = re.search(r"^---\n.*?^title:\s*(.+?)\n.*?^---\n", md_text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def relocate_images(
    html_text: str, source_path: Path, output_path: Path
) -> tuple[str, int, list[str]]:
    """
    Copy local image files to the sidecar (next to output_path) and rewrite
    src attributes. Returns (updated_html, image_count, warnings).
    """
    warnings: list[str] = []
    counter = [0]

    def rewrite_src(match: re.Match) -> str:
        src = match.group(1)
        parsed = urlparse(src)
        # Skip remote URLs
        if parsed.scheme in ("http", "https", "data", "ftp"):
            return match.group(0)

        # Resolve relative path from source file directory
        img_src = source_path.parent / src
        if not img_src.exists():
            warnings.append(f"Image not found (skipped): {src}")
            return match.group(0)

        try:
            img_dir = ensure_images_dir(output_path)
            counter[0] += 1
            dest_name = f"{output_path.stem}_image_{counter[0]}{img_src.suffix}"
            dest = img_dir / dest_name
            shutil.copy2(str(img_src), str(dest))
            new_src = f"images/{dest_name}"
            return f'src="{new_src}"'
        except Exception as exc:
            warnings.append(f"Could not copy image {src}: {exc}")
            return match.group(0)

    updated = re.sub(r'src="([^"]+)"', rewrite_src, html_text)
    updated = re.sub(r"src='([^']+)'", rewrite_src, updated)
    return updated, counter[0], warnings


def strip_front_matter(text: str) -> str:
    """Remove YAML front matter and asset marker from markdown text."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text.strip()


def build_html_page(body: str, title: str = "") -> str:
    """Wrap an HTML body in a minimal HTML5 document."""
    return (
        "<!DOCTYPE html>\n"
        "<html><head>\n"
        "<meta charset='utf-8'>\n"
        f"<title>{title}</title>\n"
        "<style>"
        "body { font-family: sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; }"
        "pre, code { font-family: monospace; background: #f5f5f5; padding: 2px 4px; }"
        "table { border-collapse: collapse; } th, td { border: 1px solid #ccc; padding: 4px 8px; }"
        "</style>\n"
        "</head><body>\n"
        f"{body}\n"
        "</body></html>"
    )


def _today() -> str:
    from datetime import date
    return date.today().isoformat()
