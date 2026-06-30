# ================================================================
# cli
# ================================================================
# Objective:
#       Command-line entry point for everything2md.
#       Three commands: forward, reverse, status.
#       Each command validates arguments, calls batch.run_batch(),
#       prints per-file results and a summary, and exits with
#       code 0 (all succeeded) or 1 (any failure or bad args).
# Inputs:
#       - sys.argv
# Outputs:
#       - stdout: per-file OK/FAIL/DRY lines and batch summary
#       - exit code: 0 success, 1 failure
# Notes:
#       - Uses sys.stdout.buffer for output to avoid cp1252
#         encoding errors on Windows consoles.
# ================================================================

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.batch import EXT_TO_FORMAT, run_batch
from src.config import SUPPORTED_EXTENSIONS
from src.logging_setup import setup_logging
from src.schemas import ConversionResult

setup_logging()

ALL_FORMATS = sorted(set(EXT_TO_FORMAT.values()))


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "command") or args.command is None:
        parser.print_help()
        return 1

    root = Path(args.root)
    if not root.is_dir():
        print_err(f"Root directory does not exist: {root}")
        return 1

    if args.command == "status":
        return cmd_status(root, args)

    direction = "forward" if args.command == "forward" else "reverse"
    formats: set[str] = set(args.format) if args.format else set()
    options: dict = {}

    if args.command == "forward" and getattr(args, "ocr", False):
        options["ocr"] = True

    if args.command == "reverse" and getattr(args, "target_format", None):
        options["format"] = args.target_format

    batch = run_batch(
        root_dir=root,
        direction=direction,
        formats=formats,
        options=options,
        recursive=not args.no_recursive,
        dry_run=getattr(args, "dry_run", False),
    )

    any_fail = print_results(batch.results)
    print_summary(batch)

    return 1 if (any_fail or batch.failed > 0) else 0


# ------------------------------------------------
# Command: status
# ------------------------------------------------

def cmd_status(root: Path, args) -> int:
    """Report how many source files have and don't have a .md sibling."""
    recursive = not args.no_recursive
    formats: set[str] = set(args.format) if args.format else set()

    from src.batch import collect_forward_files
    source_files = collect_forward_files(root, formats, recursive)

    has_md = [f for f in source_files if f.with_suffix(".md").exists()]
    no_md = [f for f in source_files if not f.with_suffix(".md").exists()]

    print_out(f"Root: {root}")
    print_out(f"Source files found: {len(source_files)}")
    print_out(f"  Converted (has .md):  {len(has_md)}")
    print_out(f"  Not converted:        {len(no_md)}")

    if no_md:
        print_out("\nNot yet converted:")
        for f in no_md:
            print_out(f"  {f}")

    return 0


# ------------------------------------------------
# Output helpers
# ------------------------------------------------

def print_results(results: list[ConversionResult]) -> bool:
    """Print per-file result lines. Returns True if any failure."""
    any_fail = False
    for r in results:
        if r.status == "success":
            stats = f"{r.duration_ms:.0f}ms"
            if r.table_count:
                stats += f", {r.table_count} table{'s' if r.table_count != 1 else ''}"
            if r.image_count:
                stats += f", {r.image_count} image{'s' if r.image_count != 1 else ''}"
            line = f"OK   {r.input_path.name} -> {r.output_path.name} ({stats})"
            print_out(line)
            for w in r.warnings:
                print_out(f"     WARNING: {w}")
        else:
            print_out(f"FAIL {r.input_path.name} -- {r.error}")
            any_fail = True

    return any_fail


def print_summary(batch) -> None:
    summary = (
        f"\nBatch complete: {batch.total} total, "
        f"{batch.succeeded} succeeded, "
        f"{batch.failed} failed, "
        f"{batch.skipped} skipped"
    )
    print_out(summary)


def print_out(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


def print_err(msg: str) -> None:
    sys.stderr.write(msg + "\n")


# ------------------------------------------------
# Argument parser
# ------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="everything2md",
        description="Bidirectional batch file converter: source <-> Markdown.",
    )
    sub = parser.add_subparsers(dest="command")

    # Shared options factory
    def add_shared(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--root", "-r",
            required=True,
            help="Root directory to scan.",
        )
        p.add_argument(
            "--format", "-f",
            nargs="+",
            choices=ALL_FORMATS,
            metavar="FORMAT",
            help=f"Limit to these formats: {', '.join(ALL_FORMATS)}. Default: all.",
        )
        p.add_argument(
            "--no-recursive",
            action="store_true",
            default=False,
            help="Do not walk subdirectories.",
        )
        p.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="List files that would be processed; no conversions performed.",
        )

    # forward
    forward_p = sub.add_parser("forward", help="Convert source files -> .md")
    add_shared(forward_p)
    forward_p.add_argument(
        "--ocr",
        action="store_true",
        default=False,
        help="Enable OCR for image-only PDF pages.",
    )

    # reverse
    reverse_p = sub.add_parser("reverse", help="Convert .md files -> source format")
    add_shared(reverse_p)
    reverse_p.add_argument(
        "--target-format",
        choices=ALL_FORMATS,
        metavar="FORMAT",
        help="Target format when .md has no asset marker.",
    )

    # status
    status_p = sub.add_parser("status", help="Report conversion status for a directory")
    add_shared(status_p)

    return parser


if __name__ == "__main__":
    sys.exit(main())
