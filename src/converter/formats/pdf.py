# ================================================================
# formats/pdf
# ================================================================
# Objective:
#       Forward: convert .pdf to .md using PyMuPDF for text
#       extraction, pdfplumber for table detection, and RapidOCR
#       for image-only pages (optional). Per-page sections with
#       YAML front matter.
#       Reverse: render .md to PDF via the markdown package
#       (MD->HTML) and weasyprint (HTML->PDF).
# Inputs:
#       - forward: Path to .pdf source file
#       - reverse: Path to .md file
# Outputs:
#       - forward: sibling .md + {stem}_assets/ sidecar
#       - reverse: sibling .pdf (best-effort, not pixel-exact)
# Notes:
#       - OCR is off by default; enable via options["ocr"] = True.
#       - OCR engine failure is non-fatal (warning + no OCR text).
#       - pdfplumber is opened separately from fitz; both operate
#         read-only on the source file so they do not conflict.
# ================================================================

from __future__ import annotations

import re
import time
from pathlib import Path

from src.converter.assets import asset_marker, ensure_images_dir, write_meta
from src.converter.naming import forward_output, reverse_output
from src.schemas import ConversionResult

# Characters below this count on a page trigger OCR consideration.
OCR_TEXT_THRESHOLD = 50

# Heading size ratios relative to the body text size.
HEADING_RATIOS: list[tuple[float, int]] = [
    (1.6, 1),
    (1.4, 2),
    (1.2, 3),
    (1.1, 4),
]

# ------------------------------------------------
# Forward: PDF -> MD
# ------------------------------------------------

def convert_forward(
    source_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert a .pdf file to a sibling .md file."""
    import fitz  # type: ignore

    start = time.monotonic()
    output_path = forward_output(source_path, dest_dir)
    warnings: list[str] = []
    ocr_enabled: bool = options.get("ocr", False)
    ocr_pages = 0
    table_count = 0
    image_count = 0

    try:
        doc = fitz.open(str(source_path))
        page_count = doc.page_count
        tables_by_page = extract_tables_from_pdf(source_path, page_count)

        page_sections: list[str] = []

        for page_idx in range(page_count):
            fitz_page = doc[page_idx]
            page_data = extract_page_text(fitz_page)

            if ocr_enabled and page_data["needs_ocr"]:
                ocr_result = run_ocr(fitz_page)
                if ocr_result["text"]:
                    page_data["blocks"] = [(None, ocr_result["text"])]
                    ocr_pages += 1
                else:
                    warnings.append(f"Page {page_idx + 1}: OCR returned no text.")

            # Retrieve images from OCR pages for sidecar
            if page_data["needs_ocr"] and ocr_pages > 0:
                img_path = save_page_image(fitz_page, output_path, page_idx)
                if img_path:
                    image_count += 1

            page_tables = tables_by_page.get(page_idx, [])
            table_count += len(page_tables)

            section_md = render_page_section(page_idx, page_data, page_tables)
            page_sections.append(section_md)

        doc.close()

        confidence = compute_confidence(page_count, ocr_pages)
        today = _today()
        front_matter = (
            f"---\n"
            f"source: {source_path.name}\n"
            f"pages: {page_count}\n"
            f"date: {today}\n"
            f"confidence: {confidence}\n"
            f"ocr_used: {'true' if ocr_pages > 0 else 'false'}\n"
            f"tables: {table_count}\n"
            f"---\n"
        )
        marker = asset_marker(output_path)
        body = "\n\n".join(page_sections)
        final_md = f"{front_matter}\n{marker}\n\n{body}\n"

        output_path.write_text(final_md, encoding="utf-8")
        write_meta(output_path, "pdf", image_count=image_count, table_count=table_count)

    except Exception as exc:
        return ConversionResult(
            input_path=source_path,
            output_path=None,
            direction="forward",
            source_format="pdf",
            status="failure",
            error=str(exc),
        )

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=source_path,
        output_path=output_path,
        direction="forward",
        source_format="pdf",
        status="success",
        warnings=warnings,
        image_count=image_count,
        table_count=table_count,
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Reverse: MD -> PDF
# ------------------------------------------------

def convert_reverse(
    md_path: Path, options: dict, dest_dir: Path | None = None
) -> ConversionResult:
    """Convert a .md file to a best-effort .pdf via weasyprint."""
    import markdown as md_lib  # type: ignore
    from weasyprint import HTML  # type: ignore

    start = time.monotonic()
    output_path = reverse_output(md_path, "pdf", dest_dir)
    warnings: list[str] = []

    try:
        md_text = md_path.read_text(encoding="utf-8", errors="replace")
        # Strip YAML front matter and asset marker before rendering
        md_text = strip_front_matter(md_text)

        html_body = md_lib.markdown(
            md_text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
        html = build_html_page(html_body, title=md_path.stem)
        HTML(string=html, base_url=str(md_path.parent)).write_pdf(str(output_path))

    except Exception as exc:
        return ConversionResult(
            input_path=md_path,
            output_path=None,
            direction="reverse",
            source_format="pdf",
            status="failure",
            error=str(exc),
        )

    elapsed = (time.monotonic() - start) * 1000
    return ConversionResult(
        input_path=md_path,
        output_path=output_path,
        direction="reverse",
        source_format="pdf",
        status="success",
        warnings=warnings,
        duration_ms=elapsed,
    )


# ------------------------------------------------
# Text extraction helpers
# ------------------------------------------------

def extract_page_text(fitz_page) -> dict:
    """Extract text and metrics from a fitz page."""
    raw_text = fitz_page.get_text("text")
    raw_text = clean_text(raw_text)
    char_count = len(raw_text.strip())
    word_count = len(raw_text.split())

    dict_data = fitz_page.get_text("dict")
    blocks = render_blocks(dict_data.get("blocks", []))

    return {
        "blocks": blocks,
        "char_count": char_count,
        "word_count": word_count,
        "needs_ocr": char_count < OCR_TEXT_THRESHOLD,
    }


def clean_text(text: str) -> str:
    """Remove control characters and normalize Unicode typography to ASCII."""
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
    replacements = {
        "–": "-", "—": "-",    # en/em dash
        "‘": "'", "’": "'",    # smart single quotes
        "“": '"', "”": '"',    # smart double quotes
        "…": "...",                  # ellipsis
        " ": " ",                   # non-breaking space
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text


def render_blocks(raw_blocks: list) -> list[tuple]:
    """Convert fitz block dicts to (bbox, markdown_str) tuples."""
    text_blocks = [b for b in raw_blocks if b.get("type") == 0]
    if not text_blocks:
        return []

    body_size = estimate_body_size(text_blocks)
    result: list[tuple] = []

    for block in text_blocks:
        lines_md: list[str] = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = clean_text(span.get("text", "").strip())
                if not text:
                    continue
                size = span.get("size", body_size)
                flags = span.get("flags", 0)
                font = span.get("font", "").lower()

                is_bold = bool(flags & 16) or "bold" in font
                is_mono = any(m in font for m in ("courier", "menlo", "consolas", "lucida", "code"))
                ratio = size / body_size if body_size else 1.0

                heading_level = 0
                for min_ratio, level in HEADING_RATIOS:
                    if ratio >= min_ratio:
                        heading_level = level
                        break

                if heading_level:
                    lines_md.append(f"{'#' * heading_level} {text}")
                elif is_mono:
                    lines_md.append(f"`{text}`")
                elif is_bold and len(text) <= 80:
                    lines_md.append(f"**{text}**")
                else:
                    lines_md.append(text)

        if lines_md:
            bbox = block.get("bbox")
            result.append((bbox, " ".join(lines_md)))

    return result


def estimate_body_size(blocks: list) -> float:
    """Find the most common font size across all spans (histogram)."""
    from collections import Counter
    sizes: list[float] = []
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                s = span.get("size")
                if s:
                    sizes.append(round(s, 1))
    if not sizes:
        return 12.0
    return Counter(sizes).most_common(1)[0][0]


# ------------------------------------------------
# Table extraction helpers
# ------------------------------------------------

def extract_tables_from_pdf(pdf_path: Path, page_count: int) -> dict[int, list]:
    """Extract table data from each page using pdfplumber."""
    import pdfplumber  # type: ignore

    tables_by_page: dict[int, list] = {}
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_idx in range(min(page_count, len(pdf.pages))):
                page = pdf.pages[page_idx]
                raw_tables = page.find_tables()
                page_tables = []
                for tbl in raw_tables:
                    rows = tbl.extract()
                    if rows:
                        page_tables.append((tbl.bbox, rows))
                if page_tables:
                    tables_by_page[page_idx] = page_tables
    except Exception:
        pass  # Table extraction is best-effort; fail silently.
    return tables_by_page


def render_gfm_table(rows: list[list]) -> str:
    """Convert a list of rows (each a list of cell strings) to a GFM table."""
    if not rows:
        return ""

    col_count = max(len(r) for r in rows)

    def escape(cell) -> str:
        s = str(cell or "").replace("|", r"\|").replace("\n", " ")
        return s

    lines: list[str] = []
    for row_idx, row in enumerate(rows):
        cells = [escape(c) for c in row]
        while len(cells) < col_count:
            cells.append("")
        lines.append("| " + " | ".join(cells) + " |")
        if row_idx == 0:
            lines.append("| " + " | ".join(["---"] * col_count) + " |")

    return "\n".join(lines)


# ------------------------------------------------
# OCR helpers
# ------------------------------------------------

_ocr_engine = None
_ocr_unavailable = False


def run_ocr(fitz_page) -> dict:
    """Run RapidOCR on a fitz page. Returns {"text": str, "confidence": float}."""
    global _ocr_engine, _ocr_unavailable

    if _ocr_unavailable:
        return {"text": "", "confidence": 0.0}

    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
            _ocr_engine = RapidOCR()
        except Exception:
            _ocr_unavailable = True
            return {"text": "", "confidence": 0.0}

    try:
        import numpy as np  # type: ignore

        # Render page at 2x scale for better OCR accuracy
        mat = fitz_page.get_pixmap(matrix=fitz_page.CropBox, dpi=144)
        img_array = np.frombuffer(mat.samples, dtype=np.uint8).reshape(
            mat.height, mat.width, mat.n
        )

        result, elapse = _ocr_engine(img_array)
        if not result:
            return {"text": "", "confidence": 0.0}

        # Sort by y-coordinate (top of bounding box), then x-coordinate
        result_sorted = sorted(result, key=lambda r: (r[0][0][1], r[0][0][0]))
        texts = [r[1] for r in result_sorted]
        confidences = [r[2] for r in result_sorted]
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return {"text": "\n".join(texts), "confidence": mean_conf}
    except Exception:
        return {"text": "", "confidence": 0.0}


# ------------------------------------------------
# Image sidecar helpers
# ------------------------------------------------

def save_page_image(fitz_page, output_path: Path, page_idx: int) -> Path | None:
    """Save a rendered page pixmap to the sidecar images directory."""
    try:
        img_dir = ensure_images_dir(output_path)
        filename = f"{output_path.stem}_p{page_idx + 1}.png"
        dest = img_dir / filename
        mat = fitz_page.get_pixmap(dpi=72)
        mat.save(str(dest))
        return dest
    except Exception:
        return None


# ------------------------------------------------
# Page section rendering
# ------------------------------------------------

def render_page_section(page_idx: int, page_data: dict, page_tables: list) -> str:
    """Combine text blocks and tables into a ## Page N section."""
    items: list[tuple[float, str]] = []

    for bbox, md_str in page_data["blocks"]:
        top_y = bbox[1] if bbox else 0.0
        items.append((top_y, md_str))

    for table_bbox, rows in page_tables:
        top_y = table_bbox[1] if table_bbox else 0.0
        table_md = render_gfm_table(rows)
        if table_md:
            items.append((top_y, table_md))

    items.sort(key=lambda x: x[0])
    body = "\n\n".join(md_str for _, md_str in items)
    return f"## Page {page_idx + 1}\n\n{body}"


# ------------------------------------------------
# Confidence scoring
# ------------------------------------------------

def compute_confidence(page_count: int, ocr_pages: int) -> int:
    """Return a 0-100 confidence score based on OCR usage."""
    if page_count == 0:
        return 0
    non_ocr_pages = page_count - ocr_pages
    score = (non_ocr_pages / page_count) * 100
    return round(score)


# ------------------------------------------------
# Reverse helpers
# ------------------------------------------------

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
        f"<meta charset='utf-8'>\n"
        f"<title>{title}</title>\n"
        "<style>"
        "body { font-family: serif; margin: 2cm; font-size: 12pt; }"
        "h1,h2,h3,h4 { font-family: sans-serif; }"
        "pre, code { font-family: monospace; background: #f0f0f0; padding: 2px 4px; }"
        "table { border-collapse: collapse; width: 100%; }"
        "th, td { border: 1px solid #ccc; padding: 4px 8px; }"
        "</style>\n"
        "</head><body>\n"
        f"{body}\n"
        "</body></html>"
    )


def _today() -> str:
    from datetime import date
    return date.today().isoformat()
