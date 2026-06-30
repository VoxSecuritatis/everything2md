# everything2md

A bidirectional batch file converter. Converts PDF, DOCX, TXT, HTML, RTF, and EPUB documents to Markdown, and converts Markdown back to the original format. Includes a PySide6 GUI and a command-line interface.

---

## Features

- **Forward conversion** — source documents → `.md` with YAML front matter
- **Reverse conversion** — `.md` files → original format (best-effort)
- **Asset sidecars** — extracted images and metadata saved to `{stem}_assets/` alongside each `.md`
- **Recursive batch processing** — walks a root directory and all subdirectories
- **Optional destination directory** — output can be written to a separate folder, mirroring the source tree
- **Mover tab** — copy or move files by extension with mirrored directory structure (GUI only)
- **OCR support** — RapidOCR for image-only PDF pages (forward, optional)
- **GUI + CLI** — PySide6 two-tab GUI and a full-featured `argparse` CLI

---

## Supported Formats

| Extension    | Forward library              | Reverse library         |
|--------------|------------------------------|-------------------------|
| `.pdf`       | PyMuPDF + pdfplumber         | WeasyPrint              |
| `.docx`      | mammoth + python-docx        | python-docx             |
| `.txt`       | stdlib                       | stdlib                  |
| `.html/.htm` | markdownify                  | markdown                |
| `.rtf`       | striprtf                     | plain-text RTF wrapper  |
| `.epub`      | ebooklib + markdownify       | ebooklib                |

---

## Installation

### Step 1 — Verify Python 3.12

Python **3.12** is required. The `rapidocr-onnxruntime` package (used for PDF OCR) does not have a build for Python 3.13 or later.

```powershell
python --version
# Should print: Python 3.12.x
```

If you have multiple Python versions installed, use the full path to 3.12 in Step 2, e.g. `D:\Python312\python.exe`.

---

### Step 2 — Get the project

Clone or download and extract the repository, then open a PowerShell terminal in the project root folder.

---

### Step 3 — Create a virtual environment

```powershell
python -m venv .venv
```

If you need to target a specific Python 3.12 installation:

```powershell
D:\Python312\python.exe -m venv .venv
```

---

### Step 4 — Activate the virtual environment

```powershell
.venv\Scripts\Activate.ps1
```

Your prompt will change to show `(.venv)` when the environment is active.

---

### Step 5 — Install dependencies

```powershell
pip install -r requirements.txt
```

This installs all conversion libraries (PyMuPDF, mammoth, WeasyPrint, ebooklib, etc.) and the PySide6 GUI toolkit.

---

### Step 6 — Configure environment variables

Copy the provided example file to create your own `.env`:

```powershell
Copy-Item .env.example .env
```

The `.env` file is where you set any local configuration. For most users this file can remain as-is unless you need Markdown → PDF support (see Step 7).

---

### Step 7 — (Optional) Enable Markdown → PDF on Windows

Converting `.md` files back to `.pdf` (reverse conversion) requires WeasyPrint, which depends on GTK/Pango DLLs that `pip` cannot install. **Skip this step if you do not need MD → PDF output.**

1. Download and install [MSYS2](https://www.msys2.org/) (the default install location is `C:\msys64`).

2. Open the **MSYS2 MINGW64** shell (not the default MSYS2 shell) and run:
   ```bash
   pacman -S mingw-w64-x86_64-pango
   ```

3. Open your `.env` file and set the path to the MSYS2 `mingw64\bin` folder:
   ```
   WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin
   ```
   Adjust the path if you installed MSYS2 to a different location.

---

### Quick start — launch the GUI

Once steps 1–6 are complete, launch the GUI with:

```powershell
python -m src.gui
```

Or use the included launcher script, which creates the virtual environment and installs dependencies automatically on first run:

```powershell
.\run.ps1
```

---

## GUI

### Convert Tab

| Control | Description |
|---|---|
| Root directory | Folder to scan for source files |
| Destination directory | Optional override; output written here instead of next to source. Subdirectory structure is mirrored when Recursive is on. Leave blank for default (same folder as source). |
| Direction | **Forward** (source → .md) or **Reverse** (.md → source) |
| Formats | Checkboxes to include/exclude PDF, DOCX, TXT, HTML, RTF, EPUB |
| Enable OCR | OCR image-only PDF pages (Forward + PDF only) |
| Recursive | Include subdirectories (default: on) |
| Convert | Runs the batch in a background thread; results appear per-file |

### Mover Tab

Copies or moves files by extension into a destination directory, recreating the filtered source tree at the destination.

| Control | Description |
|---|---|
| Source directory | Root folder to scan |
| Destination directory | Required; matched files are placed here with mirrored subdirectory structure |
| Mode | **Copy** (source untouched, runs immediately) or **Move** (source deleted after copy, requires confirmation) |
| File types | TXT, PDF, DOCX, MD, RTF, HTML (.html + .htm) — all checked by default |
| Recursive | Include subdirectories (default: on) |
| Copy/Move | Runs the operation in a background thread |

**Sidecar behavior:** when a `.md` file is copied or moved and a `{stem}_assets/` folder exists alongside it, the sidecar is automatically carried to the destination. Conflicts at the destination are overwritten.

---

## CLI

```
python -m src.cli <command> --root <directory> [options]
```

### Commands

**`forward`** — convert source files to Markdown

```powershell
python -m src.cli forward --root .\docs\
python -m src.cli forward --root .\docs\ --format pdf docx --ocr
python -m src.cli forward --root .\docs\ --no-recursive --dry-run
```

**`reverse`** — convert Markdown files back to source format

```powershell
python -m src.cli reverse --root .\docs\
python -m src.cli reverse --root .\docs\ --format txt
```

**`status`** — report how many source files have and don't have a `.md` sibling

```powershell
python -m src.cli status --root .\docs\
```

### Shared Options

| Flag | Description |
|---|---|
| `--root`, `-r` | Root directory to scan (required) |
| `--format`, `-f` | Limit to one or more formats: `pdf docx txt html rtf epub` |
| `--no-recursive` | Do not walk subdirectories |
| `--dry-run` | List files that would be processed; no conversions performed |

**`forward` only:** `--ocr` — enable OCR for image-only PDF pages

**`reverse` only:** `--target-format FORMAT` — target format when a `.md` has no asset marker

### Exit Codes

- `0` — all files succeeded
- `1` — one or more failures, or bad arguments

---

## Asset Sidecars

Each converted `.md` file gets a `{stem}_assets/` sidecar directory in the same folder (or the destination directory when one is set):

```
report.md
report_assets/
    meta.json       ← source_format, source_filename, converted_at, image/table counts
    images/
        report_p1.png
        report_p2.png
```

A marker near the top of each `.md` links back to the sidecar:

```
<!-- assets: report_assets/meta.json -->
```

Reverse conversion reads this marker to determine the target format and locate images.

---

## Project Structure

```
everything2md/
├── src/
│   ├── batch.py              # Recursive directory walker; run_batch()
│   ├── cli.py                # argparse CLI entry point
│   ├── config.py             # ROOT_DIR, SUPPORTED_EXTENSIONS
│   ├── logging_setup.py      # Rolling daily log
│   ├── mover.py              # Copy/move by extension; run_mover()
│   ├── schemas.py            # ConversionResult, BatchResult dataclasses
│   ├── converter/
│   │   ├── assets.py         # Sidecar read/write helpers
│   │   ├── core.py           # Single dispatch point; convert()
│   │   ├── naming.py         # Output path resolution
│   │   └── formats/
│   │       ├── docx.py
│   │       ├── epub.py
│   │       ├── html.py
│   │       ├── pdf.py
│   │       ├── rtf.py
│   │       └── txt.py
│   └── gui/
│       ├── __main__.py       # python -m src.gui entry point
│       ├── main_window.py    # PySide6 MainWindow (Convert + Mover tabs)
│       └── workers.py        # BatchWorker, MoverWorker (QThread)
├── tests/
│   ├── fixtures/             # sample.txt, sample.html
│   ├── conftest.py
│   ├── test_assets.py
│   ├── test_batch.py
│   ├── test_html.py
│   ├── test_mover.py
│   └── test_txt.py
├── .env.example
├── requirements.txt
└── run.ps1                   # Windows launcher (creates venv, installs deps, launches GUI)
```

---

## Running Tests

```powershell
pytest
```

75 tests covering assets, batch processing, HTML conversion, TXT conversion, mover operations, and path resolution. DOCX, PDF, RTF, and EPUB tests require a full `pip install -r requirements.txt`.

---

## License

MIT
