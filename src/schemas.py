# ================================================================
# schemas
# ================================================================
# Objective:
#       Data classes shared across all conversion modules and
#       the CLI/GUI layers. No validation logic here -- just
#       plain containers.
# Inputs:
#       - populated by converter/core.py after each conversion
# Outputs:
#       - ConversionResult, BatchResult consumed by cli.py / gui
# ================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConversionResult:
    """Result for a single file conversion (forward or reverse)."""

    input_path: Path
    output_path: Path | None       # None when conversion fails before writing
    direction: str                 # "forward" or "reverse"
    source_format: str             # e.g. "pdf", "docx", "txt"
    status: str                    # "success" or "failure"
    warnings: list[str] = field(default_factory=list)
    image_count: int = 0
    table_count: int = 0
    duration_ms: float = 0.0
    error: str = ""


@dataclass
class BatchResult:
    """Aggregated result for a batch conversion run."""

    total: int
    succeeded: int
    failed: int
    skipped: int
    results: list[ConversionResult] = field(default_factory=list)
