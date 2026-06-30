# ================================================================
# assets
# ================================================================
# Objective:
#       Manage the {stem}_assets/ sidecar directory for each
#       converted document. Handles writing meta.json, creating
#       the images/ subdirectory, and reading the asset marker
#       embedded in .md files so reverse conversion knows the
#       target format and where to find images.
# Inputs:
#       - source or .md file Path
#       - conversion metadata (format, counts, timestamp)
# Outputs:
#       - {stem}_assets/meta.json written to disk
#       - asset marker string for insertion into .md
#       - meta.json dict when reading back for reverse conversion
# Notes:
#       - assets/ dir created lazily (only when something is saved)
#       - marker format: <!-- assets: {stem}_assets/meta.json -->
# ================================================================

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

MARKER_PREFIX = "<!-- assets:"
MARKER_SUFFIX = "-->"
MARKER_PATTERN = re.compile(r"<!-- assets:\s*(.+?)\s*-->")


def assets_dir(source_path: Path) -> Path:
    """Return the sidecar directory path for a given source or .md file."""
    return source_path.parent / f"{source_path.stem}_assets"


def images_dir(source_path: Path) -> Path:
    """Return the images subdirectory path inside the sidecar directory."""
    return assets_dir(source_path) / "images"


def ensure_images_dir(source_path: Path) -> Path:
    """Create and return the images directory (lazy creation)."""
    img_dir = images_dir(source_path)
    img_dir.mkdir(parents=True, exist_ok=True)
    return img_dir


def write_meta(
    source_path: Path,
    source_format: str,
    image_count: int = 0,
    table_count: int = 0,
) -> Path:
    """Write meta.json to the sidecar directory. Returns the meta.json path."""
    adir = assets_dir(source_path)
    adir.mkdir(parents=True, exist_ok=True)
    meta_path = adir / "meta.json"
    meta = {
        "source_format": source_format,
        "source_filename": source_path.name,
        "converted_at": datetime.now().isoformat(timespec="seconds"),
        "image_count": image_count,
        "table_count": table_count,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta_path


def asset_marker(source_path: Path) -> str:
    """Return the marker string to embed in the .md file."""
    rel = f"{source_path.stem}_assets/meta.json"
    return f"{MARKER_PREFIX} {rel} {MARKER_SUFFIX}"


def read_meta(md_path: Path) -> dict | None:
    """
    Parse the asset marker from a .md file and load meta.json.
    Returns the meta dict, or None if no marker or meta.json not found.
    """
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return None

    match = MARKER_PATTERN.search(text)
    if not match:
        return None

    rel_meta = match.group(1).strip()
    meta_path = md_path.parent / rel_meta
    if not meta_path.exists():
        return None

    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def resolve_images_from_meta(md_path: Path) -> Path | None:
    """
    Return the images/ directory for a .md file based on its asset marker.
    Returns None if the directory does not exist.
    """
    meta = read_meta(md_path)
    if meta is None:
        return None
    img_dir = md_path.parent / f"{md_path.stem}_assets" / "images"
    return img_dir if img_dir.exists() else None
