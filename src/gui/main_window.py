# ================================================================
# gui/main_window
# ================================================================
# Objective:
#       Two-tab PySide6 GUI for everything2md.
#       "Convert" tab: pick a root directory, choose direction and
#       formats, hit Convert, see per-file results in a monospace
#       list. Conversion runs in a QThread (BatchWorker).
#       "Mover" tab: pick a source root and destination directory,
#       choose copy or move, select file extensions, hit Run, see
#       per-file results. Operation runs in a QThread (MoverWorker).
# Inputs:
#       - user interaction (directory pickers, checkboxes, buttons)
# Outputs:
#       - Launches BatchWorker / MoverWorker; results displayed in
#         per-tab results lists; shared status bar updated throughout
# Notes:
#       - No settings panel, no navigation sidebar.
#       - OCR toggle visible only when PDF is included and
#         direction is Forward (Convert tab).
#       - Footer row provides Help, About, and Exit actions.
# ================================================================

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt  # type: ignore
from PySide6.QtGui import QColor, QFont  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.batch import EXT_TO_FORMAT
from src.gui.workers import BatchWorker, MoverWorker
from src.logging_setup import setup_logging
from src.mover import MOVER_EXTENSIONS, MoveResult, MoveBatchResult, collect_mover_files
from src.schemas import BatchResult, ConversionResult

setup_logging()

ALL_FORMATS = sorted(set(EXT_TO_FORMAT.values()))
MOVER_FORMAT_KEYS = sorted(MOVER_EXTENSIONS.keys())
WINDOW_TITLE = "everything2md"
WINDOW_MIN_WIDTH = 720
WINDOW_MIN_HEIGHT = 580

APP_NAME = "everything2md"
APP_VERSION = "1.0"
APP_RELEASE_DATE = "2026-06-30"
APP_DEVELOPER = "Brock Frary"

# Colors (burnt orange accent on dark background)
COLOR_OK = "#7fc97f"
COLOR_FAIL = "#e06c75"
COLOR_WARN = "#e5c07b"
COLOR_ACCENT = "#BF5700"

HELP_HTML = """
<h2>everything2md -- Help</h2>
<p>everything2md has two tabs: <b>Convert</b> and <b>Mover</b>.</p>

<h2>Convert Tab</h2>
<p>Scans a folder, converts documents to Markdown (.md), and can convert
Markdown back to the original format.</p>

<h3>Root Directory</h3>
<p>Click <b>Browse...</b> to choose the folder to scan. All matching files inside it
(and its subfolders, if Recursive is checked) will be processed.</p>

<h3>Destination Directory</h3>
<p>Optional. Leave blank to write each output file next to its source file (default
behavior). If set, output files (and their <code>{filename}_assets/</code> sidecars) are
written into this folder instead. When Recursive is checked, each file's subfolder
structure relative to the root directory is mirrored under the destination.</p>

<h3>Direction</h3>
<ul>
<li><b>Forward</b> (source -&gt; .md): Converts source documents to Markdown.</li>
<li><b>Reverse</b> (.md -&gt; source): Converts .md files back to their original format.</li>
</ul>

<h3>Formats to Include</h3>
<p>Check the formats to process: PDF, DOCX, TXT, HTML, RTF, EPUB. Unchecked formats
are skipped during the scan.</p>

<h3>Options</h3>
<ul>
<li><b>Enable OCR for image-only PDF pages</b>: Only shown for Forward + PDF. Runs
OCR on pages with little or no extractable text.</li>
<li><b>Recursive</b>: Include subdirectories when scanning the root directory.</li>
</ul>

<h3>Convert Button</h3>
<p>Runs the batch conversion in the background. Progress appears in the results list
below; the status bar shows the file currently being processed.</p>

<h3>Results List</h3>
<ul>
<li><b>OK</b> -- file converted successfully, with output filename and timing/stats.</li>
<li><b>WARNING</b> -- a non-fatal issue during conversion (e.g. OCR returned no text).</li>
<li><b>FAIL</b> -- conversion failed, with the error message.</li>
</ul>
<p>A summary line (total / succeeded / failed / skipped) appears at the end of each batch.</p>

<h3>Asset Sidecars</h3>
<p>Images and metadata extracted during conversion are saved to a
<code>{filename}_assets/</code> folder next to the output file (the source file's
folder by default, or the destination directory if one is set). A marker comment near
the top of each .md file links back to its sidecar for reverse conversion.</p>

<h2>Mover Tab</h2>
<p>Copies or moves files by extension from a source directory tree into a destination
directory, recreating the source's subfolder structure filtered to only the selected
file types.</p>

<h3>Source Directory</h3>
<p>The root folder to scan. Files are collected from this folder and (when Recursive
is checked) all subfolders.</p>

<h3>Destination Directory</h3>
<p>Required. The folder where matched files are placed. The source's subfolder
structure is mirrored: a file at <code>root/sub/a.txt</code> goes to
<code>dest/sub/a.txt</code>. Only subfolders containing at least one matched file
are created at the destination.</p>

<h3>Mode</h3>
<ul>
<li><b>Copy</b>: Source files are left untouched; copies are written to the destination.
Runs immediately.</li>
<li><b>Move</b>: Files are removed from the source after being written to the
destination. A confirmation dialog appears before the operation starts because
this is irreversible.</li>
</ul>

<h3>File Types</h3>
<p>Check the extensions to include: TXT, PDF, DOCX, MD, RTF, HTML (which covers
both .html and .htm). Only files with the checked extensions are moved or copied;
all other files are ignored.</p>

<h3>Sidecar Folders</h3>
<p>When a <b>.md</b> file is selected and has a matching <code>{stem}_assets/</code>
sidecar folder (images and metadata from a prior conversion), the sidecar is
automatically carried along to the destination directory alongside the .md file.
<code>_assets/</code> folders are never picked up independently as a top-level match.</p>

<h3>Conflicts</h3>
<p>If a file already exists at the destination it is overwritten. The same applies
to sidecar folders.</p>

<h3>Run Button</h3>
<p>Runs the copy/move operation in the background. Progress appears in the results
list; the status bar shows the current file.</p>

<h2>Help / About / Exit</h2>
<ul>
<li><b>Help</b>: Opens this dialog.</li>
<li><b>About</b>: Shows version and developer information.</li>
<li><b>Exit</b>: Closes the application.</li>
</ul>
"""


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.worker: BatchWorker | None = None
        self.mover_worker: MoverWorker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_convert_tab(), "Convert")
        self.tabs.addTab(self.build_mover_tab(), "Mover")
        outer.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.update_ocr_visibility()

    # ------------------------------------------------
    # Tab builders
    # ------------------------------------------------

    def build_convert_tab(self) -> QWidget:
        """Build the Convert tab widget (existing single-screen layout)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addLayout(self.build_root_row())
        layout.addLayout(self.build_dest_row())
        layout.addLayout(self.build_direction_row())
        layout.addWidget(self.build_format_group())
        layout.addWidget(self.build_options_group())
        layout.addWidget(self.build_convert_button())
        layout.addWidget(self.build_results_list())
        layout.addLayout(self.build_footer_row())

        return tab

    def build_mover_tab(self) -> QWidget:
        """Build the Mover tab widget."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addLayout(self.build_mover_root_row())
        layout.addLayout(self.build_mover_dest_row())
        layout.addLayout(self.build_mover_mode_row())
        layout.addWidget(self.build_mover_format_group())
        layout.addWidget(self.build_mover_options_group())
        layout.addWidget(self.build_mover_run_button())
        layout.addWidget(self.build_mover_results_list())
        layout.addLayout(self.build_footer_row())

        return tab

    # ------------------------------------------------
    # Convert tab widget builders
    # ------------------------------------------------

    def build_root_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Root directory:"))
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("Select a directory to scan...")
        row.addWidget(self.root_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.on_browse)
        row.addWidget(browse_btn)
        return row

    def build_dest_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Destination directory:"))
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Leave blank to write output next to each source file")
        row.addWidget(self.dest_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.on_browse_dest)
        row.addWidget(browse_btn)
        return row

    def build_direction_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Direction:"))
        self.radio_forward = QRadioButton("Forward  (source -> .md)")
        self.radio_forward.setChecked(True)
        self.radio_reverse = QRadioButton("Reverse  (.md -> source)")
        self.radio_forward.toggled.connect(self.update_ocr_visibility)
        row.addWidget(self.radio_forward)
        row.addWidget(self.radio_reverse)
        row.addStretch()
        return row

    def build_format_group(self) -> QGroupBox:
        group = QGroupBox("Formats to include")
        layout = QHBoxLayout(group)
        self.format_checks: dict[str, QCheckBox] = {}
        for fmt in ALL_FORMATS:
            cb = QCheckBox(fmt.upper())
            cb.setChecked(True)
            if fmt == "pdf":
                cb.toggled.connect(self.update_ocr_visibility)
            self.format_checks[fmt] = cb
            layout.addWidget(cb)
        layout.addStretch()
        return group

    def build_options_group(self) -> QGroupBox:
        group = QGroupBox("Options")
        layout = QHBoxLayout(group)
        self.ocr_check = QCheckBox("Enable OCR for image-only PDF pages")
        self.recursive_check = QCheckBox("Recursive (include subdirectories)")
        self.recursive_check.setChecked(True)
        layout.addWidget(self.ocr_check)
        layout.addWidget(self.recursive_check)
        layout.addStretch()
        return group

    def build_convert_button(self) -> QPushButton:
        self.convert_btn = QPushButton("Convert")
        self.convert_btn.setFixedHeight(36)
        font = self.convert_btn.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.convert_btn.setFont(font)
        self.convert_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_ACCENT}; color: white; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: #a04600; }}"
            f"QPushButton:disabled {{ background-color: #888; }}"
        )
        self.convert_btn.clicked.connect(self.on_convert)
        return self.convert_btn

    def build_results_list(self) -> QListWidget:
        self.results_list = QListWidget()
        mono_font = QFont("Courier New", 9)
        self.results_list.setFont(mono_font)
        self.results_list.setAlternatingRowColors(False)
        return self.results_list

    def build_footer_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        help_btn = QPushButton("Help")
        help_btn.clicked.connect(self.on_help)
        row.addWidget(help_btn)
        about_btn = QPushButton("About")
        about_btn.clicked.connect(self.on_about)
        row.addWidget(about_btn)
        row.addStretch()
        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(self.close)
        row.addWidget(exit_btn)
        return row

    # ------------------------------------------------
    # Mover tab widget builders
    # ------------------------------------------------

    def build_mover_root_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Source directory:"))
        self.mover_root_edit = QLineEdit()
        self.mover_root_edit.setPlaceholderText("Select the source directory to scan...")
        row.addWidget(self.mover_root_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.on_browse_mover_root)
        row.addWidget(browse_btn)
        return row

    def build_mover_dest_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Destination directory:"))
        self.mover_dest_edit = QLineEdit()
        self.mover_dest_edit.setPlaceholderText("Select the destination directory (required)...")
        row.addWidget(self.mover_dest_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.on_browse_mover_dest)
        row.addWidget(browse_btn)
        return row

    def build_mover_mode_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Mode:"))
        self.mover_radio_copy = QRadioButton("Copy  (source files kept)")
        self.mover_radio_copy.setChecked(True)
        self.mover_radio_move = QRadioButton("Move  (source files deleted)")
        row.addWidget(self.mover_radio_copy)
        row.addWidget(self.mover_radio_move)
        row.addStretch()
        return row

    def build_mover_format_group(self) -> QGroupBox:
        group = QGroupBox("File types to include")
        layout = QHBoxLayout(group)
        self.mover_format_checks: dict[str, QCheckBox] = {}
        for key in MOVER_FORMAT_KEYS:
            label = "HTML (.html/.htm)" if key == "html" else key.upper()
            cb = QCheckBox(label)
            cb.setChecked(True)
            self.mover_format_checks[key] = cb
            layout.addWidget(cb)
        layout.addStretch()
        return group

    def build_mover_options_group(self) -> QGroupBox:
        group = QGroupBox("Options")
        layout = QHBoxLayout(group)
        self.mover_recursive_check = QCheckBox("Recursive (include subdirectories)")
        self.mover_recursive_check.setChecked(True)
        layout.addWidget(self.mover_recursive_check)
        layout.addStretch()
        return group

    def build_mover_run_button(self) -> QPushButton:
        self.mover_run_btn = QPushButton("Copy/Move")
        self.mover_run_btn.setFixedHeight(36)
        font = self.mover_run_btn.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.mover_run_btn.setFont(font)
        self.mover_run_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_ACCENT}; color: white; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: #a04600; }}"
            f"QPushButton:disabled {{ background-color: #888; }}"
        )
        self.mover_run_btn.clicked.connect(self.on_run_mover)
        return self.mover_run_btn

    def build_mover_results_list(self) -> QListWidget:
        self.mover_results_list = QListWidget()
        mono_font = QFont("Courier New", 9)
        self.mover_results_list.setFont(mono_font)
        self.mover_results_list.setAlternatingRowColors(False)
        return self.mover_results_list

    # ------------------------------------------------
    # Convert tab event handlers
    # ------------------------------------------------

    def on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select root directory")
        if directory:
            self.root_edit.setText(directory)

    def on_browse_dest(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select destination directory")
        if directory:
            self.dest_edit.setText(directory)

    def on_convert(self) -> None:
        root_text = self.root_edit.text().strip()
        if not root_text:
            self.status_bar.showMessage("Please select a root directory.")
            return

        root = Path(root_text)
        if not root.is_dir():
            self.status_bar.showMessage(f"Directory not found: {root}")
            return

        selected_formats = {
            fmt for fmt, cb in self.format_checks.items() if cb.isChecked()
        }
        if not selected_formats:
            self.status_bar.showMessage("Please select at least one format.")
            return

        direction = "forward" if self.radio_forward.isChecked() else "reverse"
        options: dict = {}
        if direction == "forward" and self.ocr_check.isChecked():
            options["ocr"] = True

        dest_text = self.dest_edit.text().strip()
        dest_dir = Path(dest_text) if dest_text else None

        self.results_list.clear()
        self.convert_btn.setEnabled(False)
        self.status_bar.showMessage("Converting...")

        self.worker = BatchWorker(
            root_dir=root,
            direction=direction,
            formats=selected_formats,
            options=options,
            recursive=self.recursive_check.isChecked(),
            dest_dir=dest_dir,
        )
        self.worker.file_done.connect(self.on_file_done)
        self.worker.batch_done.connect(self.on_batch_done)
        self.worker.start()

    def on_file_done(self, result: ConversionResult) -> None:
        if result.status == "success":
            out_name = result.output_path.name if result.output_path else "?"
            stats = f"{result.duration_ms:.0f}ms"
            if result.table_count:
                stats += f", {result.table_count} tbl"
            if result.image_count:
                stats += f", {result.image_count} img"
            line = f"OK   {result.input_path.name} -> {out_name} ({stats})"
            self.add_result_item(line, COLOR_OK, self.results_list)
            for w in result.warnings:
                self.add_result_item(f"     WARNING: {w}", COLOR_WARN, self.results_list)
        else:
            self.add_result_item(
                f"FAIL {result.input_path.name} -- {result.error}",
                COLOR_FAIL,
                self.results_list,
            )
        self.status_bar.showMessage(f"Converting... {result.input_path.name}")

    def on_batch_done(self, batch: BatchResult) -> None:
        self.convert_btn.setEnabled(True)
        summary = (
            f"Done: {batch.total} total, "
            f"{batch.succeeded} succeeded, "
            f"{batch.failed} failed, "
            f"{batch.skipped} skipped"
        )
        self.status_bar.showMessage(summary)
        self.add_result_item("", None, self.results_list)
        self.add_result_item(summary, None, self.results_list)
        self.worker = None

    def on_help(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{APP_NAME} Help")
        dialog.resize(580, 520)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setHtml(HELP_HTML)
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons)
        dialog.exec()

    def on_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b><br>"
            f"Version {APP_VERSION} ({APP_RELEASE_DATE})<br><br>"
            f"Developer: {APP_DEVELOPER}<br><br>"
            "A bidirectional batch file converter for PDF, DOCX, TXT, HTML, RTF, "
            "and EPUB to and from Markdown.",
        )

    # ------------------------------------------------
    # Mover tab event handlers
    # ------------------------------------------------

    def on_browse_mover_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select source directory")
        if directory:
            self.mover_root_edit.setText(directory)

    def on_browse_mover_dest(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select destination directory")
        if directory:
            self.mover_dest_edit.setText(directory)

    def on_run_mover(self) -> None:
        root_text = self.mover_root_edit.text().strip()
        if not root_text:
            self.status_bar.showMessage("Mover: please select a source directory.")
            return

        root = Path(root_text)
        if not root.is_dir():
            self.status_bar.showMessage(f"Mover: directory not found: {root}")
            return

        dest_text = self.mover_dest_edit.text().strip()
        if not dest_text:
            self.status_bar.showMessage("Mover: please select a destination directory.")
            return

        dest = Path(dest_text)

        selected_exts = {
            key for key, cb in self.mover_format_checks.items() if cb.isChecked()
        }
        if not selected_exts:
            self.status_bar.showMessage("Mover: please select at least one file type.")
            return

        recursive = self.mover_recursive_check.isChecked()
        mode = "move" if self.mover_radio_move.isChecked() else "copy"

        files = collect_mover_files(root, selected_exts, recursive)
        if not files:
            self.status_bar.showMessage("Mover: no matching files found.")
            return

        if mode == "move":
            answer = QMessageBox.question(
                self,
                "Confirm Move",
                f"Move {len(files)} file(s) from\n  {root}\nto\n  {dest}?\n\n"
                "Source files will be permanently deleted after copying.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.status_bar.showMessage("Move cancelled.")
                return

        self.mover_results_list.clear()
        self.mover_run_btn.setEnabled(False)
        self.status_bar.showMessage(f"Mover: starting {mode} of {len(files)} file(s)...")

        self.mover_worker = MoverWorker(
            root_dir=root,
            dest_dir=dest,
            extensions=selected_exts,
            mode=mode,
            recursive=recursive,
            files=files,
        )
        self.mover_worker.file_done.connect(self.on_mover_file_done)
        self.mover_worker.batch_done.connect(self.on_mover_done)
        self.mover_worker.start()

    def on_mover_file_done(self, result: MoveResult) -> None:
        if result.status == "success":
            out_name = result.output_path.name if result.output_path else "?"
            line = f"OK   {result.input_path.name} -> {out_name}"
            self.add_result_item(line, COLOR_OK, self.mover_results_list)
        else:
            self.add_result_item(
                f"FAIL {result.input_path.name} -- {result.error}",
                COLOR_FAIL,
                self.mover_results_list,
            )
        if result.input_path:
            self.status_bar.showMessage(f"Mover: {result.input_path.name}")

    def on_mover_done(self, batch: MoveBatchResult) -> None:
        self.mover_run_btn.setEnabled(True)
        summary = (
            f"Done: {batch.total} total, "
            f"{batch.succeeded} succeeded, "
            f"{batch.failed} failed"
        )
        self.status_bar.showMessage(summary)
        self.add_result_item("", None, self.mover_results_list)
        self.add_result_item(summary, None, self.mover_results_list)
        self.mover_worker = None

    # ------------------------------------------------
    # Helpers
    # ------------------------------------------------

    def add_result_item(
        self, text: str, color: str | None, list_widget: QListWidget
    ) -> None:
        item = QListWidgetItem(text)
        if color:
            item.setForeground(QColor(color))
        list_widget.addItem(item)
        list_widget.scrollToBottom()

    def update_ocr_visibility(self) -> None:
        """Show OCR checkbox only when direction is forward and PDF is selected."""
        show = (
            self.radio_forward.isChecked()
            and self.format_checks.get("pdf", QCheckBox()).isChecked()
        )
        self.ocr_check.setVisible(show)


def run_app() -> None:
    """Launch the GUI application."""
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
