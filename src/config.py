# ================================================================
# config
# ================================================================
# Objective:
#       Central constants and path definitions for everything2md.
#       Loaded at import time; no side effects beyond resolving paths.
# Inputs:
#       - __file__ location
# Outputs:
#       - ROOT_DIR, LOGS_DIR, INPUT_DIR, OUTPUT_DIR
# Notes:
#       - .env is loaded silently; no required env vars in v1.
# ================================================================

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
LOGS_DIR: Path = ROOT_DIR / "logs"
INPUT_DIR: Path = ROOT_DIR / "input"
OUTPUT_DIR: Path = ROOT_DIR / "output"

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".txt", ".html", ".htm", ".rtf", ".epub")

load_dotenv(ROOT_DIR / ".env", override=False)

# ctypes.util.find_library() (used by cffi/WeasyPrint) only searches PATH on
# Windows, not directories registered via os.add_dll_directory(). Prepend the
# same directory here so WeasyPrint's Pango/GObject DLLs can be located.
_weasyprint_dll_dirs = os.environ.get("WEASYPRINT_DLL_DIRECTORIES")
if _weasyprint_dll_dirs:
    os.environ["PATH"] = _weasyprint_dll_dirs + os.pathsep + os.environ.get("PATH", "")
