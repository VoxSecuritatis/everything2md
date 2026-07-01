# everything2md

Batch document converter for Markdown workflows.

`everything2md` converts PDF, DOCX, TXT, HTML, RTF, and EPUB files to Markdown. It can also convert Markdown back to a target document format on a best-effort basis. The project includes both a PySide6 desktop GUI and a command-line interface.

---

## Features

- Forward conversion from source documents to `.md` files with YAML front matter
- Reverse conversion from `.md` files back to a document format where supported
- Asset sidecars for extracted images and metadata
- Recursive batch processing across a root folder and subfolders
- Optional destination folder with mirrored source directory structure
- GUI Mover tab for copying or moving files by extension
- Optional OCR for image-only PDF pages using RapidOCR
- PySide6 GUI plus a full `argparse` CLI

---

## Supported Formats

| Extension | Forward Library | Reverse Library |
|---|---|---|
| `.pdf` | PyMuPDF + pdfplumber | WeasyPrint |
| `.docx` | mammoth + python-docx | python-docx |
| `.txt` | stdlib | stdlib |
| `.html` / `.htm` | markdownify | markdown |
| `.rtf` | striprtf | plain-text RTF wrapper |
| `.epub` | ebooklib + markdownify | ebooklib |

---

## Installation

### Step 1: Verify Python 3.12

Python 3.12 is required.

The `rapidocr-onnxruntime` package, used for optional PDF OCR, does not currently have a build for Python 3.13 or later.

```powershell
python --version
````

Expected output:

```text
Python 3.12.x
```

If you have multiple Python versions installed, use the full path to Python 3.12 when creating the virtual environment.

Example:

```powershell
D:\Python312\python.exe
```

---

### Step 2: Get the project

Clone or download the repository.

Then open PowerShell in the project root folder.

---

### Step 3: Create a virtual environment

```powershell
python -m venv .venv
```

To target a specific Python 3.12 install:

```powershell
D:\Python312\python.exe -m venv .venv
```

---

### Step 4: Activate the virtual environment

```powershell
.venv\Scripts\Activate.ps1
```

Your prompt should show `(.venv)` when the environment is active.

---

### Step 5: Install dependencies

```powershell
pip install -r requirements.txt
```

This installs the conversion libraries and the PySide6 GUI toolkit.

---

### Step 6: Configure environment variables

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Most users can leave `.env` as-is.

Edit `.env` only if you need local configuration changes or Markdown-to-PDF support.

---

### Step 7: Optional Markdown-to-PDF support on Windows

Reverse conversion from `.md` to `.pdf` uses WeasyPrint.

On Windows, WeasyPrint depends on GTK/Pango DLLs that are not installed by `pip`.

Skip this step if you do not need Markdown-to-PDF output.

1. Download and install MSYS2:

   ```text
   https://www.msys2.org/
   ```

   The default install path is:

   ```text
   C:\msys64
   ```

2. Open the `MSYS2 MINGW64` shell.

   Do not use the default `MSYS2` shell.

3. Install Pango:

   ```bash
   pacman -S mingw-w64-x86_64-pango
   ```

4. Open `.env` and set:

   ```text
   WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin
   ```

Adjust the path if MSYS2 was installed somewhere else.

---

## Quick Start

Launch the GUI directly:

```powershell
python -m src.gui
```

Or use the included launcher:

```powershell
.\run.ps1
```

`run.ps1` creates `.venv`, installs dependencies, and launches the GUI.

---

## GUI

The GUI has two tabs:

* Convert
* Mover

---

## Convert Tab

| Control               | Description                                                                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Root directory        | Folder to scan for source files                                                                                                                         |
| Destination directory | Optional output folder. When Recursive is enabled, the source tree is mirrored under this folder. Leave blank to write output next to each source file. |
| Direction             | Forward converts source files to Markdown. Reverse converts Markdown files back to a document format.                                                   |
| Formats               | Include or exclude PDF, DOCX, TXT, HTML, RTF, and EPUB                                                                                                  |
| Enable OCR            | Enables OCR for image-only PDF pages. Applies only to Forward + PDF.                                                                                    |
| Recursive             | Includes subdirectories. Enabled by default.                                                                                                            |
| Convert               | Runs the batch job in a background thread and reports results per file.                                                                                 |

---

## Mover Tab

The Mover tab copies or moves files by extension into a destination folder while recreating the source directory structure.

| Control               | Description                                                                                           |
| --------------------- | ----------------------------------------------------------------------------------------------------- |
| Source directory      | Root folder to scan                                                                                   |
| Destination directory | Required destination folder                                                                           |
| Mode                  | Copy leaves source files in place. Move deletes source files after copying and requires confirmation. |
| File types            | TXT, PDF, DOCX, MD, RTF, and HTML. All are checked by default.                                        |
| Recursive             | Includes subdirectories. Enabled by default.                                                          |
| Copy/Move             | Runs the operation in a background thread.                                                            |

### Sidecar behavior

When a `.md` file is copied or moved and a matching `{stem}_assets/` folder exists next to it, the sidecar folder is copied or moved with the Markdown file.

Destination conflicts are overwritten.

---

## CLI

```text
python -m src.cli <command> --root <directory> [options]
```

---

## Commands

### forward

Convert source files to Markdown.

```powershell
python -m src.cli forward --root .\docs\
python -m src.cli forward --root .\docs\ --format pdf docx --ocr
python -m src.cli forward --root .\docs\ --no-recursive --dry-run
```

---

### reverse

Convert Markdown files back to a document format.

```powershell
python -m src.cli reverse --root .\docs\
python -m src.cli reverse --root .\docs\ --format txt
```

---

### status

Report how many source files have, or do not have, a `.md` sibling.

```powershell
python -m src.cli status --root .\docs\
```

---

## Shared CLI Options

| Flag             | Description                                                           |
| ---------------- | --------------------------------------------------------------------- |
| `--root`, `-r`   | Root directory to scan. Required.                                     |
| `--format`, `-f` | Limit processing to one or more formats: `pdf docx txt html rtf epub` |
| `--no-recursive` | Do not walk subdirectories                                            |
| `--dry-run`      | List files that would be processed without converting anything        |

### forward-only option

| Flag    | Description                         |
| ------- | ----------------------------------- |
| `--ocr` | Enable OCR for image-only PDF pages |

### reverse-only option

| Flag                     | Description                                                |
| ------------------------ | ---------------------------------------------------------- |
| `--target-format FORMAT` | Target format to use when a `.md` file has no asset marker |

---

## Exit Codes

| Code | Meaning                                                     |
| ---- | ----------------------------------------------------------- |
| `0`  | All files succeeded                                         |
| `1`  | One or more files failed, or the command used bad arguments |

---

## Asset Sidecars

Each converted `.md` file gets a sidecar directory named `{stem}_assets/`.

The sidecar is created next to the Markdown file, or in the destination folder when one is set.

Example:

```text
report.md
report_assets/
    meta.json
    images/
        report_p1.png
        report_p2.png
```

`meta.json` stores details such as:

* Source format
* Source file name
* Conversion timestamp
* Image count
* Table count

Each `.md` file includes an asset marker near the top:

```text
<!-- assets: report_assets/meta.json -->
```

Reverse conversion reads this marker to determine the target format and locate related assets.

---

## Project Structure

```text
everything2md/
|-- src/
|   |-- batch.py              # Recursive directory walker; run_batch()
|   |-- cli.py                # argparse CLI entry point
|   |-- config.py             # ROOT_DIR, SUPPORTED_EXTENSIONS
|   |-- logging_setup.py      # Rolling daily log
|   |-- mover.py              # Copy/move by extension; run_mover()
|   |-- schemas.py            # ConversionResult, BatchResult dataclasses
|   |-- converter/
|   |   |-- assets.py         # Sidecar read/write helpers
|   |   |-- core.py           # Single dispatch point; convert()
|   |   |-- naming.py         # Output path resolution
|   |   |-- formats/
|   |       |-- docx.py
|   |       |-- epub.py
|   |       |-- html.py
|   |       |-- pdf.py
|   |       |-- rtf.py
|   |       |-- txt.py
|   |-- gui/
|       |-- __main__.py       # python -m src.gui entry point
|       |-- main_window.py    # PySide6 MainWindow with Convert and Mover tabs
|       |-- workers.py        # BatchWorker, MoverWorker
|-- tests/
|   |-- fixtures/
|   |   |-- sample.txt
|   |   |-- sample.html
|   |-- conftest.py
|   |-- test_assets.py
|   |-- test_batch.py
|   |-- test_html.py
|   |-- test_mover.py
|   |-- test_txt.py
|-- .env.example
|-- requirements.txt
|-- run.ps1
```

---

## Running Tests

```powershell
pytest
```

The test suite covers:

* Asset sidecars
* Batch processing
* HTML conversion
* TXT conversion
* Mover operations
* Path resolution

DOCX, PDF, RTF, and EPUB tests require a full dependency install:

```powershell
pip install -r requirements.txt
```

---

© 2026 Brock Frary. All rights reserved.
