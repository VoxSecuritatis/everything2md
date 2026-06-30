# ================================================================
# formats/epub
# ================================================================
# Objective:
#       Forward: read .epub spine order with ebooklib, convert
#       each chapter's HTML content to Markdown using markdownify,
#       extract images to the sidecar, and assemble a single .md
#       with chapter sections.
#       Reverse: parse .md into chapters (by ## Chapter N headings),
#       build a new .epub with ebooklib (one HTML item per chapter),
#       embedding sidecar images where available.
# Inputs:
#       - forward: Path to .epub source file
#       - reverse: Path to .md file
# Outputs:
#       - forward: sibling .md + {stem}_assets/ sidecar
#       - reverse: sibling .epub
# Notes:
#       - ebooklib warns about cover images and NCX items; these
#         are expected and suppressed via logging filter.
#       - Images are identified by ebooklib item type ITEM_IMAGE.
# ================================================================

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from src.converter.assets import asset_marker, ensure_images_dir, write_meta
from src.converter.naming import forward_output, reverse_output
from src.schemas import ConversionResult

# Suppress ebooklib's noisy runtime warnings about cover images and NCX.
logging.getLogger("ebooklib").setLevel(logging.ERROR)
logging.getLogger("ebooklib.epub").setLevel(logging.ERROR)

# ------------------------------------------------
# Forward: EPUB -> MD
# ------------------------------------------------

def convert_forward(
    source_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert an .epub file to a sibling .md file."""
    import ebooklib  # type: ignore
    import ebooklib.epub as epub  # type: ignore
    import markdownify  # type: ignore

    start = time.monotonic()
    output_path = forward_output(source_path, dest_dir)
    warnings: list[str] = []
    image_count = 0
    chapter_count = 0

    try:
        book = epub.read_epub(str(source_path), options={"ignore_ncx": True})
        img_dir = ensure_images_dir(output_path)

        # Extract all images from the EPUB to the sidecar
        img_name_map: dict[str, str] = {}
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            dest_name = f"{output_path.stem}_image_{len(img_name_map) + 1}{Path(item.get_name()).suffix}"
            dest = img_dir / dest_name
            dest.write_bytes(item.get_content())
            img_name_map[item.get_name()] = f"images/{dest_name}"
            image_count += 1

        # Walk spine in reading order
        sections: list[str] = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html_content = item.get_content().decode("utf-8", errors="replace")

            # Rewrite image src attributes to point to sidecar
            def rewrite_img(m: re.Match) -> str:
                src = m.group(1)
                # EPUB image names may be relative with ../ prefixes
                normalized = src.lstrip("./").lstrip("/")
                for epub_name, local_path in img_name_map.items():
                    if epub_name.endswith(normalized) or normalized.endswith(Path(epub_name).name):
                        return f'src="{local_path}"'
                return m.group(0)

            html_content = re.sub(r'src="([^"]+)"', rewrite_img, html_content)
            html_content = re.sub(r"src='([^']+)'", rewrite_img, html_content)

            md_chunk = markdownify.markdownify(
                html_content,
                heading_style="ATX",
                strip=["script", "style"],
            )
            md_chunk = re.sub(r"\n{3,}", "\n\n", md_chunk).strip()
            if md_chunk:
                chapter_count += 1
                sections.append(f"## Chapter {chapter_count}\n\n{md_chunk}")

        body = "\n\n".join(sections)
        today = _today()
        front_matter = (
            f"---\n"
            f"source: {source_path.name}\n"
            f"date: {today}\n"
            f"chapters: {chapter_count}\n"
            f"images: {image_count}\n"
            f"---\n"
        )
        marker = asset_marker(output_path)
        final_md = f"{front_matter}\n{marker}\n\n{body}\n"

        output_path.write_text(final_md, encoding="utf-8")
        write_meta(output_path, "epub", image_count=image_count, table_count=0)

        # Clean up empty images dir
        if img_dir.exists() and not any(img_dir.iterdir()):
            img_dir.rmdir()

    except Exception as exc:
        return ConversionResult(
            input_path=source_path,
            output_path=None,
            direction="forward",
            source_format="epub",
            status="failure",
            error=str(exc),
        )

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=source_path,
        output_path=output_path,
        direction="forward",
        source_format="epub",
        status="success",
        warnings=warnings,
        image_count=image_count,
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Reverse: MD -> EPUB
# ------------------------------------------------

def convert_reverse(
    md_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert a .md file to a best-effort .epub."""
    import ebooklib.epub as epub  # type: ignore
    import markdown as md_lib  # type: ignore

    start = time.monotonic()
    output_path = reverse_output(md_path, "epub", dest_dir)
    warnings: list[str] = []
    image_count = 0

    try:
        md_text = md_path.read_text(encoding="utf-8", errors="replace")
        title = extract_md_title(md_text) or md_path.stem
        md_text = strip_front_matter(md_text)

        book = epub.EpubBook()
        book.set_title(title)
        book.set_language("en")

        # Split by ## Chapter N headings
        chapters = split_into_chapters(md_text)
        if not chapters:
            chapters = [("Content", md_text)]

        epub_chapters: list = []
        sidecar_dir = md_path.parent / f"{md_path.stem}_assets" / "images"

        for ch_idx, (ch_title, ch_md) in enumerate(chapters):
            html_body = md_lib.markdown(
                ch_md,
                extensions=["tables", "fenced_code", "nl2br"],
            )
            html_body = embed_epub_images(html_body, sidecar_dir, book)
            html_full = (
                f"<?xml version='1.0' encoding='utf-8'?>"
                f"<!DOCTYPE html><html xmlns='http://www.w3.org/1999/xhtml'>"
                f"<head><meta charset='utf-8'/><title>{ch_title}</title></head>"
                f"<body>{html_body}</body></html>"
            )
            ch_item = epub.EpubHtml(
                title=ch_title,
                file_name=f"chap_{ch_idx + 1:03d}.xhtml",
                lang="en",
            )
            ch_item.content = html_full.encode("utf-8")
            book.add_item(ch_item)
            epub_chapters.append(ch_item)

        book.toc = tuple(epub.Link(c.file_name, c.title, c.file_name) for c in epub_chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + epub_chapters

        epub.write_epub(str(output_path), book)

    except Exception as exc:
        return ConversionResult(
            input_path=md_path,
            output_path=None,
            direction="reverse",
            source_format="epub",
            status="failure",
            error=str(exc),
        )

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=md_path,
        output_path=output_path,
        direction="reverse",
        source_format="epub",
        status="success",
        warnings=warnings,
        image_count=image_count,
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Helpers
# ------------------------------------------------

def split_into_chapters(md_text: str) -> list[tuple[str, str]]:
    """Split markdown by '## Chapter N' headings into (title, content) pairs."""
    pattern = re.compile(r"^## (Chapter .+)$", re.MULTILINE)
    matches = list(pattern.finditer(md_text))
    if not matches:
        return []

    chapters: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        title = match.group(1)
        content_start = match.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        content = md_text[content_start:content_end].strip()
        chapters.append((title, content))

    return chapters


def embed_epub_images(html_body: str, sidecar_dir: Path, book) -> str:
    """Add local images from sidecar as EpubImage items and rewrite src."""
    import ebooklib.epub as epub  # type: ignore

    added: dict[str, str] = {}

    def rewrite(m: re.Match) -> str:
        src = m.group(1)
        parsed_name = Path(src).name
        img_file = sidecar_dir / parsed_name if sidecar_dir.exists() else None
        if img_file is None or not img_file.exists():
            return m.group(0)

        if src not in added:
            epub_name = f"images/{parsed_name}"
            img_item = epub.EpubImage(
                uid=f"img_{len(added)}",
                file_name=epub_name,
                media_type=guess_mime(img_file.suffix),
                content=img_file.read_bytes(),
            )
            book.add_item(img_item)
            added[src] = epub_name

        return f'src="{added[src]}"'

    html_body = re.sub(r'src="([^"]+)"', rewrite, html_body)
    return html_body


def guess_mime(suffix: str) -> str:
    """Return a MIME type for common image suffixes."""
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(suffix.lower(), "image/png")


def extract_md_title(md_text: str) -> str:
    """Extract title from YAML front matter."""
    match = re.search(r"^---\n.*?^title:\s*(.+?)\n.*?^---\n", md_text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def strip_front_matter(text: str) -> str:
    """Remove YAML front matter and asset marker from markdown text."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text.strip()


def _today() -> str:
    from datetime import date
    return date.today().isoformat()
