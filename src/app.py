from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import Qt, QSize, QSettings, Signal
from PySide6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QToolButton,
    QAbstractSpinBox,
    QApplication, QAbstractItemView, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QComboBox, QSpinBox, QCheckBox, QVBoxLayout,
    QWidget, QTabWidget, QFrame, QSplitter, QStackedWidget, QTextEdit
)

from pdf_generator import (
    MAX_IMAGES, SUPPORTED_EXTENSIONS, collect_images, create_pdf, open_safe
)
from document_tools import (
    compress_pdf, delete_pages, docx_to_pdf, extract_pages, extract_text_to_docx,
    find_libreoffice, merge_docx, merge_pdfs, pdf_info, pdf_to_images, reorder_pdf,
    rotate_pdf, split_pdf
)
from image_tools import convert_images, compress_images, resize_images

VERSION = "3.2.0"
APP_NAME = "FileForge"


class DropList(QListWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(115, 82))
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Snap)
        self.setSpacing(9)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAcceptDrops(True)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.changed.emit()


class WordFileList(QListWidget):
    """DOCX list with drag/drop support for files from anywhere on the PC."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setAcceptDrops(True)
        self.setMinimumHeight(220)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        paths = [Path(u.toLocalFile()) for u in urls]
        docx = [p for p in paths if p.suffix.lower() == ".docx"]
        if docx and self.parent() and hasattr(self.parent(), "add_paths"):
            self.parent().add_paths(docx)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class WordMergerDialog(QDialog):
    """Professional multi-location DOCX merger."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Merge Word Documents")
        self.resize(820, 600)
        self.setMinimumSize(700, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        title = QLabel("Merge Word Documents")
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        desc = QLabel(
            "Add DOCX files from any folder, arrange them in the exact order you want, "
            "then merge them into one Word document."
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        root.addWidget(desc)

        self.files = WordFileList(self)
        root.addWidget(self.files, 1)

        buttons = QHBoxLayout()
        add = QPushButton("+ Add Word Files")
        add.clicked.connect(self.choose_multiple)
        add_one = QPushButton("Add From Another Folder")
        add_one.clicked.connect(self.choose_one)
        remove = QPushButton("Remove Selected")
        remove.clicked.connect(self.remove_selected)
        clear = QPushButton("Clear All")
        clear.clicked.connect(self.clear_all)
        buttons.addWidget(add)
        buttons.addWidget(add_one)
        buttons.addWidget(remove)
        buttons.addWidget(clear)
        root.addLayout(buttons)

        order = QHBoxLayout()
        up = QPushButton("↑ Move Up")
        up.clicked.connect(lambda: self.move_selected(-1))
        down = QPushButton("↓ Move Down")
        down.clicked.connect(lambda: self.move_selected(1))
        order.addWidget(up)
        order.addWidget(down)
        order.addStretch()
        self.count_label = QLabel("0 Word files")
        order.addWidget(self.count_label)
        root.addLayout(order)

        hint = QLabel("Tip: You can also drag DOCX files directly into the list.")
        hint.setObjectName("muted")
        root.addWidget(hint)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        merge = QPushButton("MERGE DOCUMENTS")
        merge.clicked.connect(self.merge)
        footer.addWidget(cancel)
        footer.addWidget(merge)
        root.addLayout(footer)

    def choose_multiple(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Word documents", str(Path.home()),
            "Word Documents (*.docx)"
        )
        self.add_paths([Path(p) for p in files])

    def choose_one(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Add Word document", str(Path.home()),
            "Word Documents (*.docx)"
        )
        if file:
            self.add_paths([Path(file)])

    def add_paths(self, paths):
        existing = {
            str(self.files.item(i).data(Qt.UserRole)).lower()
            for i in range(self.files.count())
        }
        for path in paths:
            if path.suffix.lower() != ".docx":
                continue
            resolved = str(path.resolve())
            if resolved.lower() in existing:
                continue
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, resolved)
            item.setToolTip(resolved)
            self.files.addItem(item)
            existing.add(resolved.lower())
        self.update_count()

    def remove_selected(self):
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))
        self.update_count()

    def clear_all(self):
        self.files.clear()
        self.update_count()

    def move_selected(self, direction):
        rows = sorted(
            {self.files.row(item) for item in self.files.selectedItems()},
            reverse=(direction > 0)
        )
        for row in rows:
            target = row + direction
            if target < 0 or target >= self.files.count():
                continue
            item = self.files.takeItem(row)
            self.files.insertItem(target, item)
            item.setSelected(True)
        self.update_count()

    def update_count(self):
        count = self.files.count()
        self.count_label.setText(
            f"{count} Word file{'s' if count != 1 else ''}"
        )

    def merge(self):
        if self.files.count() < 2:
            QMessageBox.warning(
                self, "Word Merger",
                "Add at least two Word documents before merging."
            )
            return

        paths = [
            Path(self.files.item(i).data(Qt.UserRole))
            for i in range(self.files.count())
        ]

        output, _ = QFileDialog.getSaveFileName(
            self, "Save merged Word document",
            str(paths[0].with_name("Merged_Document.docx")),
            "Word Documents (*.docx)"
        )
        if not output:
            return

        output_path = Path(output)
        if output_path.suffix.lower() != ".docx":
            output_path = output_path.with_suffix(".docx")

        if not self.owner.confirm_overwrite(output_path):
            return

        try:
            merge_docx(
                paths,
                output_path,
                lambda d, t: self.owner.progress(
                    self.owner.convert_progress_bar(), d, t
                )
            )
            self.owner.done(output_path)
            self.accept()
        except Exception as exc:
            self.owner.error(str(exc))



class NumericControl(QWidget):
    """Reliable numeric input with explicit + / - buttons.

    Native QSpinBox arrow hitboxes can behave inconsistently with custom Qt
    styles on Windows. This control removes the native arrows and provides
    real QToolButtons, while keeping a QSpinBox underneath for typing,
    keyboard and mouse-wheel support.
    """

    def __init__(self, value=0, minimum=1, maximum=20000, parent=None):
        super().__init__(parent)

        self._spin = QSpinBox()
        self._spin.setRange(minimum, maximum)
        self._spin.setValue(value)
        self._spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self._spin.setKeyboardTracking(True)
        self._spin.setAccelerated(True)
        self._spin.setSingleStep(1)
        self._spin.setMinimumHeight(34)

        self._up = QToolButton()
        self._up.setText("▲")
        self._up.setToolTip("Increase")
        self._up.setAutoRaise(False)
        self._up.clicked.connect(self._spin.stepUp)

        self._down = QToolButton()
        self._down.setText("▼")
        self._down.setToolTip("Decrease")
        self._down.setAutoRaise(False)
        self._down.clicked.connect(self._spin.stepDown)

        buttons = QVBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(1)
        buttons.addWidget(self._up)
        buttons.addWidget(self._down)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(self._spin, 1)
        button_box = QWidget()
        button_box.setLayout(buttons)
        button_box.setFixedWidth(28)
        layout.addWidget(button_box)

        self.setMinimumHeight(34)
        self.setMinimumWidth(145)

    def value(self):
        return self._spin.value()

    def setValue(self, value):
        self._spin.setValue(value)

    def setRange(self, minimum, maximum):
        self._spin.setRange(minimum, maximum)

    def setSuffix(self, suffix):
        self._spin.setSuffix(suffix)

    def setSingleStep(self, step):
        self._spin.setSingleStep(step)

    def stepUp(self):
        self._spin.stepUp()

    def stepDown(self):
        self._spin.stepDown()


def _configure_spinbox(box, value: int):
    """Configure the FileForge numeric control."""
    box.setRange(1, 20000)
    box.setValue(value)
    box.setSingleStep(1)
    return box


class ImageToolsDialog(QDialog):
    """Batch image conversion, compression and resizing."""

    def __init__(self, owner, mode="convert"):
        super().__init__(owner)
        self.owner = owner
        self.mode = mode
        self.setWindowTitle({
            "convert": "Convert Images",
            "compress": "Compress Images",
            "resize": "Resize Images",
        }[mode])
        self.resize(820, 620)
        self.setMinimumSize(720, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        titles = {
            "convert": ("Convert Images", "Convert multiple images between JPG, PNG and WebP."),
            "compress": ("Compress Images", "Reduce image file size while keeping quality under your control."),
            "resize": ("Resize Images", "Resize multiple images with optional aspect-ratio preservation."),
        }
        title, desc = titles[mode]
        t = QLabel(title); t.setObjectName("sectionTitle"); root.addWidget(t)
        d = QLabel(desc); d.setWordWrap(True); d.setObjectName("muted"); root.addWidget(d)

        self.files = QListWidget()
        self.files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.files.setDragDropMode(QAbstractItemView.InternalMove)
        root.addWidget(self.files, 1)

        row = QHBoxLayout()
        for label, callback in [
            ("+ Add Images", self.add_files),
            ("Add Folder", self.add_folder),
            ("Remove Selected", self.remove_selected),
            ("Clear All", self.files.clear),
        ]:
            b = QPushButton(label); b.clicked.connect(callback); row.addWidget(b)
        root.addLayout(row)

        controls = QGroupBox("Options")
        form = QHBoxLayout(controls)

        if mode == "convert":
            form.addWidget(QLabel("Output format"))
            self.format_box = QComboBox()
            self.format_box.addItems(["JPG", "PNG", "WEBP"])
            form.addWidget(self.format_box)
            form.addWidget(QLabel("Quality"))
            self.quality = _configure_spinbox(NumericControl(value=92), 92)
            self.quality.setRange(1, 100)
            self.quality.setSuffix("%")
            form.addWidget(self.quality)
        elif mode == "compress":
            form.addWidget(QLabel("Compression"))
            self.compression = QComboBox()
            self.compression.addItems(["High Quality", "Balanced", "Maximum Compression"])
            self.compression.setCurrentText("Balanced")
            form.addWidget(self.compression)
            form.addWidget(QLabel("Output"))
            self.format_box = QComboBox()
            self.format_box.addItems(["Keep original", "JPG", "PNG", "WEBP"])
            self.format_box.setCurrentText("Keep original")
            form.addWidget(self.format_box)
        else:
            form.addWidget(QLabel("Width"))
            self.width = _configure_spinbox(NumericControl(value=1920), 1920)
            form.addWidget(self.width)
            form.addWidget(QLabel("Height"))
            self.height = _configure_spinbox(NumericControl(value=1080), 1080)
            form.addWidget(self.height)
            self.keep_aspect = QCheckBox("Keep aspect ratio"); self.keep_aspect.setChecked(True)
            form.addWidget(self.keep_aspect)

        form.addStretch()
        root.addWidget(controls)

        if mode in ("convert", "resize"):
            hint = QLabel("Tip: use the ▲/▼ buttons, mouse wheel, or type a value directly.")
            hint.setObjectName("muted")
            root.addWidget(hint)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        root.addWidget(self.progress_bar)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        run = QPushButton({
            "convert": "CONVERT IMAGES",
            "compress": "COMPRESS IMAGES",
            "resize": "RESIZE IMAGES",
        }[mode])
        run.setProperty("primary", True)
        run.clicked.connect(self.run)
        footer.addWidget(cancel); footer.addWidget(run)
        root.addLayout(footer)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select images", str(Path.home()),
            "Images (*.jpg *.jpeg *.jfif *.png *.webp *.bmp *.tif *.tiff *.avif)"
        )
        self.add_paths([Path(x) for x in files])

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select image folder", str(Path.home()))
        if folder:
            paths = sorted(
                p for p in Path(folder).rglob("*")
                if p.is_file() and p.suffix.lower() in {
                    ".jpg",".jpeg",".jfif",".png",".webp",".bmp",".tif",".tiff",".avif"
                }
            )
            self.add_paths(paths)

    def add_paths(self, paths):
        existing = {
            str(self.files.item(i).data(Qt.UserRole)).lower()
            for i in range(self.files.count())
        }
        for path in paths:
            try:
                resolved = str(path.resolve())
            except Exception:
                continue
            if path.suffix.lower() not in {
                ".jpg",".jpeg",".jfif",".png",".webp",".bmp",".tif",".tiff",".avif"
            } or resolved.lower() in existing:
                continue
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, resolved)
            item.setToolTip(resolved)
            self.files.addItem(item)
            existing.add(resolved.lower())

    def remove_selected(self):
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))

    def run(self):
        if self.files.count() == 0:
            QMessageBox.warning(self, "FileForge", "Add at least one image.")
            return

        paths = [
            Path(self.files.item(i).data(Qt.UserRole))
            for i in range(self.files.count())
        ]
        folder = QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(Path.home() / "Documents")
        )
        if not folder:
            return
        output_dir = Path(folder)

        try:
            if self.mode == "convert":
                created = convert_images(
                    paths, output_dir, self.format_box.currentText(),
                    self.quality.value()
                )
                message = f"Converted {len(created)} image(s) to {self.format_box.currentText()}."
            elif self.mode == "compress":
                created = compress_images(
                    paths, output_dir,
                    self.compression.currentText(),
                    self.format_box.currentText()
                )
                message = (
                    f"Compressed {len(created)} image(s).\n\n"
                    "Note: PNG kept as PNG uses lossless compression; for substantially smaller files, "
                    "choose WebP or JPG where appropriate."
                )
            else:
                created = resize_images(
                    paths, output_dir,
                    self.width.value(), self.height.value(),
                    self.keep_aspect.isChecked()
                )
                message = f"Resized {len(created)} image(s) to fit within {self.width.value()}×{self.height.value()}."

            for p in created:
                self.owner.add_recent(p)
            self.owner.statusBar().showMessage(f"{message} Output: {output_dir}", 8000)
            self.accept()
            answer = QMessageBox.question(
                self.owner, "Completed",
                f"Finished successfully.\n\n{message}\n\nOutput folder:\n{output_dir}\n\nOpen the output folder now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if answer == QMessageBox.Yes:
                self.owner.open_path(output_dir)
        except Exception as exc:
            QMessageBox.critical(self, "Image operation failed", str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("FileForge", "FileForge")
        self.dark = self.settings.value("dark_mode", False, type=bool)
        self.recent = json.loads(self.settings.value("recent", "[]"))
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.resize(1240, 860)
        self.setMinimumSize(1040, 720)
        self.build_ui()
        self.apply_theme()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(26, 22, 26, 18)
        root.setSpacing(13)

        header = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel("FileForge")
        title.setObjectName("title")
        subtitle = QLabel("A fast, private desktop toolbox for images, PDFs and Word documents")
        subtitle.setObjectName("subtitle")
        left.addWidget(title)
        left.addWidget(subtitle)
        header.addLayout(left)
        header.addStretch()

        self.theme_btn = QPushButton("☾ Dark mode" if not self.dark else "☀ Light mode")
        self.theme_btn.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_btn)

        offline = QLabel("●  LOCAL / OFFLINE")
        offline.setObjectName("badge")
        header.addWidget(offline)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_home(), "  Home  ")
        self.tabs.addTab(self.build_create_tab(), "  Images → PDF  ")
        self.tabs.addTab(self.build_pdf_tab(), "  PDF Tools  ")
        self.tabs.addTab(self.build_convert_tab(), "  Convert  ")
        self.tabs.addTab(self.build_history_tab(), "  History  ")
        root.addWidget(self.tabs, 1)

        footer = QLabel(
            "Privacy first: files are processed on this computer. No telemetry, uploads or cloud processing."
        )
        footer.setObjectName("footer")
        root.addWidget(footer)

    def make_card(self, title, description, button_text, callback):
        box = QFrame()
        box.setObjectName("card")
        lay = QVBoxLayout(box)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        d = QLabel(description)
        d.setObjectName("cardText")
        d.setWordWrap(True)
        b = QPushButton(button_text)
        b.setProperty("primary", True)
        b.clicked.connect(callback)
        lay.addWidget(t)
        lay.addWidget(d)
        lay.addStretch()
        lay.addWidget(b)
        return box

    def build_home(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.addWidget(QLabel("Everything you need for everyday document work", objectName="sectionTitle"))

        cards = QHBoxLayout()
        cards.addWidget(self.make_card(
            "Create PDF", "Turn images into a polished multi-page PDF with ordering, rotation and page sizing.",
            "Open Image → PDF", lambda: self.tabs.setCurrentIndex(1)
        ))
        cards.addWidget(self.make_card(
            "PDF Toolbox", "Merge, split, extract, rotate, reorder, compress and inspect PDF files.",
            "Open PDF Tools", lambda: self.tabs.setCurrentIndex(2)
        ))
        cards.addWidget(self.make_card(
            "Convert", "Convert images, merge Word files, PDF → editable text DOCX, and DOCX → PDF when LibreOffice is installed.",
            "Open Convert", lambda: self.tabs.setCurrentIndex(3)
        ))
        lay.addLayout(cards)

        features = QGroupBox("Included in FileForge")
        fl = QVBoxLayout(features)
        for text in [
            "✓ Drag-and-drop file ordering",
            "✓ Batch image conversion",
            "✓ PDF page extraction and splitting",
            "✓ Lossless PDF structural compression",
            "✓ Recent outputs and one-click open folder",
            "✓ Optional dark mode",
            "✓ No network service required at runtime",
        ]:
            fl.addWidget(QLabel(text))
        lay.addWidget(features)
        lay.addStretch()
        return tab

    # ---------------- Image → PDF ----------------
    def build_create_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(18, 18, 18, 18)

        top = QHBoxLayout()
        for text, cb in [
            ("＋ Add Images", self.add_images),
            ("Add Folder", self.add_image_folder),
            ("Clear", self.clear_images),
        ]:
            b = QPushButton(text); b.clicked.connect(cb); top.addWidget(b)
        top.addStretch()
        self.image_count = QLabel("0 images")
        top.addWidget(self.image_count)
        lay.addLayout(top)

        self.images = DropList()
        self.images.changed.connect(self.refresh_image_count)
        lay.addWidget(self.images, 1)
        lay.addWidget(self.drop_hint("Drop images here • drag thumbnails to reorder"))

        controls = QHBoxLayout()
        for text, cb in [
            ("↑ Up", lambda: self.move_item(self.images, -1)),
            ("↓ Down", lambda: self.move_item(self.images, 1)),
            ("↻ Rotate", self.rotate_images),
            ("Remove", lambda: self.remove_items(self.images)),
        ]:
            b = QPushButton(text); b.clicked.connect(cb); controls.addWidget(b)
        controls.addStretch()
        lay.addLayout(controls)

        settings = QGroupBox("PDF Settings")
        s = QHBoxLayout(settings)
        s.addWidget(QLabel("Page"))
        self.page_size = QComboBox(); self.page_size.addItems(["Original", "A4", "Letter"]); s.addWidget(self.page_size)
        s.addWidget(QLabel("Quality"))
        self.image_quality = QComboBox(); self.image_quality.addItems(["High", "Medium", "Low"]); s.addWidget(self.image_quality)
        self.fit_page = QCheckBox("Fit to page"); self.fit_page.setChecked(True); s.addWidget(self.fit_page)
        s.addStretch()
        lay.addWidget(settings)

        out = QHBoxLayout()
        out.addWidget(QLabel("Output"))
        self.create_output = QLineEdit(str(Path.home() / "Documents" / "Images_to_PDF.pdf"))
        out.addWidget(self.create_output, 1)
        b = QPushButton("Browse"); b.clicked.connect(lambda: self.save_path(self.create_output, "PDF Files (*.pdf)", ".pdf")); out.addWidget(b)
        lay.addLayout(out)

        self.create_progress = QProgressBar(); lay.addWidget(self.create_progress)
        b = QPushButton("CREATE PDF"); b.setProperty("primary", True); b.clicked.connect(self.create_pdf_action); lay.addWidget(b)
        return tab

    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", str(Path.home()),
            "Images (*.jpg *.jpeg *.jfif *.png *.webp *.bmp *.tif *.tiff *.avif);;All Files (*)")
        self.add_image_paths(files)

    def add_image_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            paths = collect_images(Path(folder), recursive=True)
            self.add_image_paths([str(p) for p in paths])

    def add_image_paths(self, paths):
        existing = {self.images.item(i).data(Qt.UserRole) for i in range(self.images.count())}
        for raw in paths[:MAX_IMAGES - self.images.count()]:
            path = Path(raw).resolve()
            if str(path) in existing or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                image = ImageOps.exif_transpose(open_safe(path).convert("RGBA"))
                image.thumbnail((115, 82), Image.Resampling.LANCZOS)
                q = QImage(image.tobytes("raw", "RGBA"), image.width, image.height,
                           QImage.Format_RGBA8888).copy()
                item = QListWidgetItem(QPixmap.fromImage(q), path.name)
                item.setData(Qt.UserRole, str(path))
                item.setData(Qt.UserRole + 1, 0)
                item.setTextAlignment(Qt.AlignHCenter)
                self.images.addItem(item)
                existing.add(str(path))
            except Exception:
                continue
        self.refresh_image_count()

    def refresh_image_count(self):
        n = self.images.count()
        self.image_count.setText(f"{n} image{'s' if n != 1 else ''}")

    def clear_images(self):
        self.images.clear(); self.refresh_image_count(); self.create_progress.setValue(0)

    def rotate_images(self):
        for item in self.images.selectedItems():
            rotation = ((item.data(Qt.UserRole + 1) or 0) + 90) % 360
            item.setData(Qt.UserRole + 1, rotation)
            try:
                image = ImageOps.exif_transpose(open_safe(Path(item.data(Qt.UserRole))).convert("RGBA"))
                image = image.rotate(rotation, expand=True)
                image.thumbnail((115, 82), Image.Resampling.LANCZOS)
                q = QImage(image.tobytes("raw", "RGBA"), image.width, image.height, QImage.Format_RGBA8888).copy()
                item.setIcon(QPixmap.fromImage(q))
            except Exception:
                pass

    def create_pdf_action(self):
        paths = [Path(self.images.item(i).data(Qt.UserRole)) for i in range(self.images.count())]
        if not paths:
            return self.warn("Add at least one image.")
        output = Path(self.create_output.text()).expanduser()
        if output.suffix.lower() != ".pdf": output = output.with_suffix(".pdf")
        if not self.confirm_overwrite(output): return
        rotations = {p: self.images.item(i).data(Qt.UserRole + 1) or 0 for i, p in enumerate(paths)}
        quality = {"High": 95, "Medium": 85, "Low": 70}[self.image_quality.currentText()]
        page = {"A4": (595, 842), "Letter": (612, 792)}.get(self.page_size.currentText())
        try:
            create_pdf(paths, output, page_size=page, fit_to_page=self.fit_page.isChecked(),
                       jpeg_quality=quality, rotations=rotations,
                       progress_callback=lambda d,t: self.progress(self.create_progress,d,t))
            self.done(output)
        except Exception as e: self.error(str(e))

    # ---------------- PDF tools ----------------
    def build_pdf_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(18,18,18,18)

        row = QHBoxLayout()
        b = QPushButton("＋ Add PDF"); b.clicked.connect(self.add_pdf_files); row.addWidget(b)
        b = QPushButton("Clear"); b.clicked.connect(lambda: self.pdf_list.clear()); row.addWidget(b)
        row.addStretch()
        self.pdf_status = QLabel("No PDF selected")
        row.addWidget(self.pdf_status)
        lay.addLayout(row)

        self.pdf_list = QListWidget()
        self.pdf_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.pdf_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.pdf_list.setAlternatingRowColors(True)
        lay.addWidget(self.pdf_list, 1)

        actions = QGroupBox("PDF Operations")
        grid = QHBoxLayout(actions)
        self.pdf_action = QComboBox()
        self.pdf_action.addItems([
            "Merge selected PDFs",
            "Split PDF into single pages",
            "Extract page range",
            "Rotate PDF",
            "Reorder pages",
            "Compress PDF",
            "Delete selected pages",
            "PDF → Images",
            "PDF → DOCX (text extraction)",
        ])
        grid.addWidget(self.pdf_action, 1)
        b = QPushButton("Run Operation"); b.setProperty("primary", True); b.clicked.connect(self.run_pdf_operation); grid.addWidget(b)
        lay.addWidget(actions)

        options = QHBoxLayout()
        options.addWidget(QLabel("Pages / order:"))
        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("Example: 1-3,5,8-10 or 3,1,2,4")
        options.addWidget(self.page_input, 2)
        options.addWidget(QLabel("Rotation:"))
        self.rotation = QComboBox(); self.rotation.addItems(["90°", "180°", "270°"]); options.addWidget(self.rotation)
        lay.addLayout(options)

        self.pdf_progress = QProgressBar(); lay.addWidget(self.pdf_progress)
        return tab

    def add_pdf_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDFs", str(Path.home()), "PDF Files (*.pdf)")
        existing = {self.pdf_list.item(i).data(Qt.UserRole) for i in range(self.pdf_list.count())}
        for f in files:
            p = str(Path(f).resolve())
            if p in existing: continue
            item = QListWidgetItem(Path(p).name)
            item.setData(Qt.UserRole, p)
            try:
                info = pdf_info(Path(p))
                item.setToolTip(f"{p}\nPages: {info['pages']}\nSize: {info['size']/1024/1024:.2f} MB")
            except Exception:
                item.setToolTip(p)
            self.pdf_list.addItem(item)
        self.pdf_status.setText(f"{self.pdf_list.count()} PDF(s)")

    def run_pdf_operation(self):
        selected = self.pdf_list.selectedItems()
        if not selected and self.pdf_list.count():
            selected = [self.pdf_list.item(0)]
        if not selected:
            return self.warn("Add/select a PDF first.")

        op = self.pdf_action.currentText()
        try:
            if op == "Merge selected PDFs":
                paths = [Path(x.data(Qt.UserRole)) for x in selected]
                if len(paths) < 2: return self.warn("Select at least two PDFs.")
                output, _ = QFileDialog.getSaveFileName(self, "Save merged PDF", str(Path.home() / "Merged.pdf"), "PDF Files (*.pdf)")
                if output and self.confirm_overwrite(Path(output)):
                    merge_pdfs(paths, Path(output), lambda d,t: self.progress(self.pdf_progress,d,t))
                    self.done(Path(output))

            elif op == "Split PDF into single pages":
                p = Path(selected[0].data(Qt.UserRole))
                folder = QFileDialog.getExistingDirectory(self, "Choose output folder", str(p.parent))
                if folder:
                    created = split_pdf(p, Path(folder), lambda d,t: self.progress(self.pdf_progress,d,t))
                    self.done(Path(folder), f"Created {len(created)} PDF pages in")

            elif op == "Extract page range":
                p = Path(selected[0].data(Qt.UserRole))
                pages = self.parse_pages(self.page_input.text())
                output, _ = QFileDialog.getSaveFileName(self, "Save extracted PDF", str(p.with_name(p.stem + "_extracted.pdf")), "PDF Files (*.pdf)")
                if output and self.confirm_overwrite(Path(output)):
                    extract_pages(p, pages, Path(output)); self.done(Path(output))

            elif op == "Rotate PDF":
                p = Path(selected[0].data(Qt.UserRole))
                output, _ = QFileDialog.getSaveFileName(self, "Save rotated PDF", str(p.with_name(p.stem + "_rotated.pdf")), "PDF Files (*.pdf)")
                if output and self.confirm_overwrite(Path(output)):
                    rotate_pdf(p, Path(output), int(self.rotation.currentText().replace("°", "").strip())); self.done(Path(output))

            elif op == "Reorder pages":
                p = Path(selected[0].data(Qt.UserRole))
                order = self.parse_pages(self.page_input.text())
                output, _ = QFileDialog.getSaveFileName(self, "Save reordered PDF", str(p.with_name(p.stem + "_reordered.pdf")), "PDF Files (*.pdf)")
                if output and self.confirm_overwrite(Path(output)):
                    reorder_pdf(p, order, Path(output)); self.done(Path(output))

            elif op == "Compress PDF":
                p = Path(selected[0].data(Qt.UserRole))
                output, _ = QFileDialog.getSaveFileName(self, "Save compressed PDF", str(p.with_name(p.stem + "_compressed.pdf")), "PDF Files (*.pdf)")
                if output and self.confirm_overwrite(Path(output)):
                    compress_pdf(p, Path(output)); self.done(Path(output))

            elif op == "Delete selected pages":
                p = Path(selected[0].data(Qt.UserRole))
                pages = self.parse_pages(self.page_input.text())
                output, _ = QFileDialog.getSaveFileName(
                    self, "Save PDF without selected pages",
                    str(p.with_name(p.stem + "_deleted.pdf")), "PDF Files (*.pdf)"
                )
                if output and self.confirm_overwrite(Path(output)):
                    delete_pages(p, pages, Path(output)); self.done(Path(output))

            elif op == "PDF → Images":
                p = Path(selected[0].data(Qt.UserRole))
                folder = QFileDialog.getExistingDirectory(
                    self, "Choose image output folder", str(p.parent)
                )
                if folder:
                    created = pdf_to_images(p, Path(folder), "PNG", 150)
                    self.done(Path(folder), f"Rendered {len(created)} PDF page(s) into")

            elif op == "PDF → DOCX (text extraction)":
                p = Path(selected[0].data(Qt.UserRole))
                output, _ = QFileDialog.getSaveFileName(self, "Save DOCX", str(p.with_suffix(".docx")), "Word Documents (*.docx)")
                if output and self.confirm_overwrite(Path(output)):
                    extract_text_to_docx(p, Path(output))
                    self.done(Path(output), "Extracted text to")

        except Exception as e:
            self.error(str(e))

    def parse_pages(self, value):
        if not value.strip():
            raise ValueError("Enter pages, e.g. 1-3,5,8.")
        nums = []
        for part in value.replace(" ", "").split(","):
            if "-" in part:
                a,b = part.split("-",1)
                a,b = int(a),int(b)
                if a > b: raise ValueError("Invalid page range.")
                nums.extend(range(a,b+1))
            else:
                nums.append(int(part))
        return nums

    # ---------------- Convert ----------------
    def build_convert_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(18,18,18,18)

        cards = QHBoxLayout()
        cards.addWidget(self.make_card(
            "Image Converter", "Batch convert JPG, PNG and WebP with safe transparency handling.",
            "Convert Images", lambda: self.open_image_tools("convert")
        ))
        cards.addWidget(self.make_card(
            "Image Compressor", "Reduce image size with High Quality, Balanced or Maximum Compression modes.",
            "Compress Images", lambda: self.open_image_tools("compress")
        ))
        cards.addWidget(self.make_card(
            "Image Resizer", "Resize batches while keeping the original aspect ratio when desired.",
            "Resize Images", lambda: self.open_image_tools("resize")
        ))
        lay.addLayout(cards)

        cards2 = QHBoxLayout()
        cards2.addWidget(self.make_card(
            "Word Merger", "Combine DOCX files from different folders with ordering and drag-and-drop.",
            "Merge Word Files", self.merge_word_action
        ))
        cards2.addWidget(self.make_card(
            "DOCX → PDF", "Uses locally installed LibreOffice for high-fidelity conversion.",
            "Convert DOCX", self.docx_pdf_action
        ))
        cards2.addStretch()
        lay.addLayout(cards2)

        info = QGroupBox("Conversion notes")
        il = QVBoxLayout(info)
        il.addWidget(QLabel("• PNG → JPG is supported; transparent pixels are safely placed on a white background."))
        il.addWidget(QLabel("• Image compression can use WebP/JPG for significantly smaller files; PNG compression remains lossless."))
        il.addWidget(QLabel("• DOCX → PDF requires LibreOffice; FileForge never sends your document to a server."))
        lay.addWidget(info)
        lay.addStretch()
        return tab

    def open_image_tools(self, mode):
        ImageToolsDialog(self, mode).exec()

    def convert_images_action(self):
        self.open_image_tools("convert")

    def merge_word_action(self):
        dialog = WordMergerDialog(self)
        dialog.exec()

    def docx_pdf_action(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Word documents", str(Path.home()), "Word Documents (*.docx)")
        if not files: return
        if not find_libreoffice():
            return self.warn("LibreOffice is not installed. Install it to enable DOCX → PDF.")
        folder = QFileDialog.getExistingDirectory(self, "Output folder", str(Path.home() / "Documents"))
        if not folder: return
        try:
            created = []
            for f in files:
                created.append(docx_to_pdf(Path(f), Path(folder)))
            self.done(Path(folder), f"Converted {len(created)} Word file(s) into")
        except Exception as e: self.error(str(e))

    # ---------------- History / shared ----------------
    def build_history_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(18,18,18,18)
        lay.addWidget(QLabel("Recent outputs", objectName="sectionTitle"))
        self.history = QListWidget()
        self.history_path = None
        self.history.itemClicked.connect(self.select_history_item)
        self.history.itemDoubleClicked.connect(self.open_history_item)
        lay.addWidget(self.history, 1)
        row = QHBoxLayout()
        self.open_selected_btn = QPushButton("Open Selected")
        self.open_selected_btn.clicked.connect(self.open_history_item)
        self.open_selected_btn.setEnabled(False)
        row.addWidget(self.open_selected_btn)

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.clicked.connect(self.open_history_folder)
        self.open_folder_btn.setEnabled(False)
        row.addWidget(self.open_folder_btn)

        b = QPushButton("Clear History")
        b.clicked.connect(self.clear_history)
        row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)

        self.history.itemSelectionChanged.connect(self.update_history_actions)
        self.update_history_actions()
        self.refresh_history()
        return tab

    def refresh_history(self):
        if not hasattr(self, "history"): return
        self.history_path = None
        self.history.clear()
        for path in self.recent:
            p = Path(path)
            item = QListWidgetItem(p.name)
            item.setToolTip(str(p))
            item.setData(Qt.UserRole, str(p))
            self.history.addItem(item)
        self.update_history_actions()

    def add_recent(self, path):
        p = str(Path(path).resolve())
        self.recent = [x for x in self.recent if x != p]
        self.recent.insert(0, p)
        self.recent = self.recent[:20]
        self.settings.setValue("recent", json.dumps(self.recent))
        self.refresh_history()

    def select_history_item(self, _item=None):
        # PySide/Qt signal overloads can provide a non-item argument on some
        # platforms. Always resolve the actual selected/current QListWidgetItem
        # from the widget itself.
        item = self.history.currentItem()
        if item is None:
            selected = self.history.selectedItems()
            item = selected[0] if selected else None

        if item is None:
            self.history_path = None
        else:
            self.history_path = Path(item.data(Qt.UserRole))

        self.update_history_actions()

    def update_history_actions(self):
        has_selection = self.history_path is not None
        if hasattr(self, "open_selected_btn"):
            self.open_selected_btn.setEnabled(has_selection)
        if hasattr(self, "open_folder_btn"):
            self.open_folder_btn.setEnabled(has_selection)

    def open_history_item(self, _item=None):
        if self.history.currentItem() is not None:
            self.select_history_item(self.history.currentItem())

        if self.history_path is None:
            self.warn("Select a recent output first.")
            return

        path = self.history_path
        if not path.exists():
            self.warn("The selected output no longer exists on disk.")
            return
        self.open_path(path)

    def open_history_folder(self):
        if self.history_path is None and self.history.currentItem() is not None:
            self.select_history_item(self.history.currentItem())

        if self.history_path is None:
            self.warn("Select a recent output first.")
            return

        path = self.history_path
        folder = path.parent
        if not folder.exists():
            self.warn("The output folder no longer exists.")
            return
        self.open_path(folder)

    def clear_history(self):
        self.recent = []
        self.settings.setValue("recent", "[]")
        self.refresh_history()

    def move_item(self, widget, delta):
        row = widget.currentRow()
        new = row + delta
        if row >= 0 and 0 <= new < widget.count():
            item = widget.takeItem(row)
            widget.insertItem(new, item)
            widget.setCurrentRow(new)

    def remove_items(self, widget):
        for item in sorted(widget.selectedItems(), key=widget.row, reverse=True):
            widget.takeItem(widget.row(item))

    def drop_hint(self, text):
        f = QFrame(); f.setObjectName("dropHint")
        l = QVBoxLayout(f); q = QLabel(text); q.setAlignment(Qt.AlignCenter); q.setObjectName("dropText"); l.addWidget(q)
        return f

    def save_path(self, edit, filt, suffix):
        p, _ = QFileDialog.getSaveFileName(self, "Choose output", edit.text(), filt)
        if p:
            if not p.lower().endswith(suffix): p += suffix
            edit.setText(p)

    def confirm_overwrite(self, path):
        if not path.exists(): return True
        return QMessageBox.question(self, "Overwrite file?", f"{path.name} already exists. Replace it?",
            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes

    def progress(self, bar, done, total):
        bar.setValue(int(done / total * 100))
        QApplication.processEvents()

    def convert_progress_bar(self):
        # A transient progress bar is unnecessary for the simple converter.
        if not hasattr(self, "_convert_bar"):
            self._convert_bar = QProgressBar()
            self.statusBar().addPermanentWidget(self._convert_bar)
        return self._convert_bar

    def done(self, path, prefix="Created"):
        p = Path(path)
        self.add_recent(p)
        self.statusBar().showMessage(f"{prefix}: {p}", 8000)
        self.open_after_done(p)

    def open_after_done(self, path):
        answer = QMessageBox.question(self, "Completed",
            f"Finished successfully.\n\n{path}\n\nOpen the output now?",
            QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.open_path(path)

    def open_path(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)], shell=False)
            else:
                subprocess.Popen(["xdg-open", str(path)], shell=False)
        except Exception as e:
            self.error(f"Could not open: {e}")

    def warn(self, text): QMessageBox.warning(self, "FileForge", text)
    def error(self, text): QMessageBox.critical(self, "FileForge", text)

    def choose_option(self, title, options):
        from PySide6.QtWidgets import QInputDialog
        return QInputDialog.getItem(self, title, "Choose:", options, 0, False)

    def toggle_theme(self):
        self.dark = not self.dark
        self.settings.setValue("dark_mode", self.dark)
        self.apply_theme()
        self.theme_btn.setText("☀ Light mode" if self.dark else "☾ Dark mode")

    def apply_theme(self):
        if self.dark:
            bg, panel, text, muted, border = "#101828", "#182230", "#f2f4f7", "#98a2b3", "#344054"
            primary = "#84adff"
        else:
            bg, panel, text, muted, border = "#f5f7fb", "#ffffff", "#172033", "#667085", "#e4e7ec"
            primary = "#175cd3"

        self.setStyleSheet(f"""
            QWidget {{ font-family: "Segoe UI", Arial; font-size: 14px; color: {text}; }}
            QMainWindow, QWidget {{ background: {bg}; }}
            #title {{ font-size: 34px; font-weight: 800; color: {text}; }}
            #subtitle {{ color: {muted}; font-size: 15px; }}
            #sectionTitle {{ font-size: 21px; font-weight: 800; margin: 6px 0; }}
            #card {{ background: {panel}; border: 1px solid {border}; border-radius: 14px; padding: 6px; }}
            #cardTitle {{ font-size: 18px; font-weight: 800; }}
            #cardText, #dropText {{ color: {muted}; }}
            #badge {{ background: #ecfdf3; color: #067647; border: 1px solid #abefc6; border-radius: 14px; padding: 7px 12px; font-weight: 700; }}
            #footer {{ color: {muted}; font-size: 12px; }}
            QTabWidget::pane {{ border: 1px solid {border}; border-radius: 14px; background: {panel}; top: -1px; }}
            QTabBar::tab {{ background: transparent; color: {muted}; padding: 12px 18px; margin-right: 4px; font-weight: 700; }}
            QTabBar::tab:selected {{ color: {primary}; border-bottom: 3px solid {primary}; }}
            QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 9px; padding: 9px 14px; font-weight: 600; }}
            QPushButton:hover {{ background: {bg}; }}
            QPushButton[primary="true"] {{ background: {primary}; color: white; border: none; font-size: 15px; font-weight: 800; padding: 13px; }}
            QLineEdit, QComboBox, QSpinBox {{ background: {panel}; border: 1px solid {border}; border-radius: 8px; padding: 8px; color: {text}; }}
            QListWidget, QTextEdit {{ background: {panel}; border: 1px solid {border}; border-radius: 12px; padding: 10px; color: {text}; }}
            QGroupBox {{ background: {panel}; border: 1px solid {border}; border-radius: 11px; margin-top: 8px; padding: 14px; font-weight: 800; }}
            QProgressBar {{ background: {border}; border: none; border-radius: 6px; height: 10px; }}
            QProgressBar::chunk {{ background: {primary}; border-radius: 6px; }}
            #dropHint {{ background: {panel}; border: 1px dashed {muted}; border-radius: 10px; }}
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = [
            Path(url.toLocalFile()) for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if not paths:
            return

        images = [p for p in paths if p.suffix.lower() in SUPPORTED_EXTENSIONS]
        pdfs = [p for p in paths if p.suffix.lower() == ".pdf"]
        docx = [p for p in paths if p.suffix.lower() == ".docx"]

        if images:
            self.tabs.setCurrentIndex(1)
            self.add_image_paths([str(p) for p in images])
        if pdfs:
            self.tabs.setCurrentIndex(2)
            self.add_pdf_files_from_paths(pdfs)
        if docx:
            self.tabs.setCurrentIndex(3)
            self.statusBar().showMessage(
                f"Dropped {len(docx)} Word file(s). Use Merge Word Files to choose/order them.", 6000
            )
        event.acceptProposedAction()

    def add_pdf_files_from_paths(self, paths):
        existing = {self.pdf_list.item(i).data(Qt.UserRole) for i in range(self.pdf_list.count())}
        for path in paths:
            p = str(path.resolve())
            if p in existing:
                continue
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, p)
            try:
                info = pdf_info(path)
                item.setToolTip(
                    f"{p}\nPages: {info['pages']}\nSize: {info['size']/1024/1024:.2f} MB"
                )
            except Exception:
                item.setToolTip(p)
            self.pdf_list.addItem(item)
            existing.add(p)
        self.pdf_status.setText(f"{self.pdf_list.count()} PDF(s)")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
