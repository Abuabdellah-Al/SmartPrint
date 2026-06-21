import ctypes
import sys
import os
from xmlrpc.client import boolean

import win32print
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QCheckBox, QGroupBox, QListWidget,
    QFileDialog, QMessageBox, QSizePolicy, QFrame, QSlider
)
from PySide6.QtGui import (
    QPixmap, QFont, QColor, QIcon, QImage, QPainter, QTransform, QPageSize
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtCore import Qt, QSize, QMarginsF, QSettings, QRectF, QSizeF
from PySide6.QtGui import QPageLayout
from PySide6.QtGui import QPageSize, QPageLayout

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class SmartPrintApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))  # or .png
        self.printer_count = None
        self.setWindowTitle("Smart Print")
        self.setMinimumSize(760, 832)
        self.settings = QSettings("SmartPrint", "Settings")
        self.image_files = []
        self.current_image_index = 0
        self.image_rotations = {}  # Stores rotation per image

        # Main Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)  # Reduced margins
        main_layout.setSpacing(5)  # Tight spacing

        # ===== HEADER =====
        header_layout = QVBoxLayout()
        header_layout.setSpacing(0)  # No space between header elements

        header = QLabel("Smart Print")
        header.setStyleSheet("""
            font-family: akira expanded;
            font-size: 35px; 
            font-weight: bold; 
            color: dodgerblue;
            margin-bottom: 0px;
        """)
        header.setAlignment(Qt.AlignCenter)

        subheader = QLabel("Made with DeepSeek℗")
        subheader.setStyleSheet("""
            font-size: 11px; 
            color: gray;
            margin-top: 0px;
            margin-bottom: 5px;
        """)
        subheader.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(header)
        header_layout.addWidget(subheader)
        main_layout.addLayout(header_layout)

        # ===== MAIN CONTENT =====
        content_layout = QHBoxLayout()
        content_layout.setSpacing(5)
        main_layout.addLayout(content_layout)

        # === LEFT SIDE (Preview) ===
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        content_layout.addLayout(left_panel, stretch=2)

        # Preview Frame - Set to A4 dimensions from start
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet("""
                border: 2px dashed #ccc;
                background: white;
                margin: 5px;
            """)
        # Set initial size to A4 dimensions (matches loaded state)
        self.preview_frame.setFixedSize(595, 842)  # A4 at 72 DPI (210x297mm)

        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignCenter)
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.addWidget(self.image_preview)
        left_panel.setAlignment(Qt.AlignCenter)
        left_panel.addWidget(self.preview_frame)



        # Image Slider
        self.image_slider = QSlider(Qt.Horizontal)
        self.image_slider.setRange(0, 0)
        self.image_slider.valueChanged.connect(self.show_image_at_index)
        left_panel.addWidget(self.image_slider)

        self.load_btn = QPushButton("🖼️ Load Images")
        self.load_btn.setStyleSheet("""
                font-size: 14px; 
                padding: 6px;
                margin-top: 5px;
            """)
        self.load_btn.clicked.connect(self.load_individual_images)  # Changed connection
        left_panel.addWidget(self.load_btn)

        # === RIGHT SIDE (Controls) ===
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)
        content_layout.addLayout(right_panel, stretch=1)

        # Printer Settings Group
        printer_group = QGroupBox("Printer Settings")
        printer_layout = QVBoxLayout()
        printer_layout.setSpacing(8)

        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumHeight(30)
        self.load_printers()
        printer_layout.addWidget(QLabel("Select Printer:"))
        printer_layout.addWidget(self.printer_combo)

        self.duplex_combo = QComboBox()
        self.duplex_combo.setMinimumHeight(30)
        self.duplex_combo.addItems(["Single-Sided", "Double-Sided (Long Edge)", "Double-Sided (Short Edge)"])
        printer_layout.addWidget(QLabel("Print Mode:"))
        printer_layout.addWidget(self.duplex_combo)

        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 99)
        printer_layout.addWidget(QLabel("Copies:"))
        printer_layout.addWidget(self.copies_spin)

        printer_group.setLayout(printer_layout)
        right_panel.addWidget(printer_group)

        # Image Adjustments Group
        adjust_group = QGroupBox("Image Adjustments")
        adjust_layout = QVBoxLayout()
        adjust_layout.setSpacing(8)

        # Rotation Control
        rotation_layout = QHBoxLayout()
        rotation_layout.addWidget(QLabel("Rotation (°):"))
        self.rotate_spin = QSpinBox()
        self.rotate_spin.setRange(0, 359)
        self.rotate_spin.valueChanged.connect(self.update_current_rotation)
        rotation_layout.addWidget(self.rotate_spin)
        adjust_layout.addLayout(rotation_layout)

        # Scale Control
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale (%):"))
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(10, 200)
        self.scale_spin.setValue(100)
        self.scale_spin.valueChanged.connect(self.update_preview)
        scale_layout.addWidget(self.scale_spin)
        adjust_layout.addLayout(scale_layout)

        # Grayscale Checkbox
        self.grayscale_check = QCheckBox("Grayscale")
        self.grayscale_check.stateChanged.connect(self.update_preview)
        adjust_layout.addWidget(self.grayscale_check)

        adjust_group.setLayout(adjust_layout)
        right_panel.addWidget(adjust_group)

        # Paper Settings Group
        paper_group = QGroupBox("Paper & Quality")
        paper_layout = QVBoxLayout()
        paper_layout.setSpacing(8)

        self.paper_combo = QComboBox()
        self.paper_combo.addItems(["A4 (210x297mm)"])  # Only A4 option
        self.paper_combo.setEnabled(False)  # Disable the combobox
        paper_layout.addWidget(QLabel("Paper Size:"))
        paper_layout.addWidget(self.paper_combo)

        self.orient_combo = QComboBox()
        self.orient_combo.addItems(["Portrait", "Landscape"])
        self.orient_combo.currentIndexChanged.connect(self.update_preview)
        paper_layout.addWidget(QLabel("Orientation:"))
        paper_layout.addWidget(self.orient_combo)

        self.dpi_combo = QComboBox()
        self.dpi_combo.addItems(["600 DPI", "300 DPI", "1200 DPI"])
        paper_layout.addWidget(QLabel("Quality:"))
        paper_layout.addWidget(self.dpi_combo)

        paper_group.setLayout(paper_layout)
        right_panel.addWidget(paper_group)

        # Print Button
        print_btn = QPushButton("🖨️ Print")
        print_btn.setStyleSheet("""
            font-size: 16px; 
            padding: 10px; 
            background: dodgerblue; 
            color: white;
            margin-top: 10px;
        """)
        print_btn.clicked.connect(self.print_images)
        right_panel.addWidget(print_btn)
        self.update_paper_preview_size()

    def load_printers(self):
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL, None, 1)
        """self.printer_combo.addItem("Save as PDF")"""
        for printer in printers:
            self.printer_combo.addItem(printer[2])
        self.printer_count = self.printer_combo.count()
        self.printer_combo.setCurrentIndex(self.printer_count-1)

    def load_individual_images(self):
        """Select multiple individual image files"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)"
        )
        if files:
            self._load_images([f for f in files if os.path.isfile(f)])

    def _load_images(self, file_paths):
        """Common loading logic"""
        self.image_files = file_paths
        if self.image_files:
            self.image_rotations = {img: 0 for img in self.image_files}
            self.image_slider.setRange(0, len(self.image_files) - 1)
            self.show_image_at_index(0)
            self.update_preview()
        else:
            QMessageBox.warning(self, "No Images", "No valid images selected!")

    def show_image_at_index(self, index):
        if 0 <= index < len(self.image_files):
            self.current_image_index = index
            current_image = self.image_files[index]
            # Safely get rotation value
            rotation = self.image_rotations.get(current_image, 0)
            self.rotate_spin.blockSignals(True)
            self.rotate_spin.setValue(rotation)
            self.rotate_spin.blockSignals(False)
            self.update_preview()

    def update_current_rotation(self):
        if self.image_files:
            current_image = self.image_files[self.current_image_index]
            self.image_rotations[current_image] = self.rotate_spin.value()
            self.update_preview()

    def update_paper_preview_size(self):
        """Adjust preview frame to match selected paper aspect ratio"""
        paper_sizes = {
            "A4 (210x297mm)": (210, 297),
            "Letter (216x279mm)": (216, 279),
            "Legal (216x356mm)": (216, 356)
        }

        paper = self.paper_combo.currentText()
        width_mm, height_mm = paper_sizes.get(paper, (210, 297))

        # Calculate aspect ratio
        if self.orient_combo.currentText() == "Landscape":
            width_mm, height_mm = height_mm, width_mm

        aspect_ratio = width_mm / height_mm

        # Calculate maximum possible size within the window
        max_width = 500  # Adjust based on your UI
        max_height = 650

        # Calculate size maintaining aspect ratio
        if max_width / max_height > aspect_ratio:
            height = max_height
            width = int(height * aspect_ratio)
        else:
            width = max_width
            height = int(width / aspect_ratio)

        self.preview_frame.setFixedSize(width, height)
        self.update_preview()

    def update_preview(self):
        if not self.image_files:
            return

        current_image = self.image_files[self.current_image_index]
        pixmap = QPixmap(current_image)
        if pixmap.isNull():
            return

        # Apply transformations
        rotation = self.image_rotations.get(current_image, 0)
        transform = QTransform()
        transform.rotate(rotation)

        # Scale to fit A4 preview
        scaled_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation).scaled(
            self.preview_frame.width() - 20,
            self.preview_frame.height() - 20,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_preview.setPixmap(scaled_pixmap)

    def print_images(self):
        if not self.image_files:
            QMessageBox.warning(self, "No Images", "Please load images first!")
            return

        printer = QPrinter()
        printer.setFullPage(True)

        # Set A4 paper size
        from PySide6.QtGui import QPageSize
        printer.setPageSize(QPageSize(QPageSize.A4))

        # Set orientation
        from PySide6.QtGui import QPageLayout
        printer.setPageOrientation(
            QPageLayout.Portrait if self.orient_combo.currentText() == "Portrait"
            else QPageLayout.Landscape
        )

        # Set duplex mode (works with PDF too)
        duplex_mode = {
            1: QPrinter.DuplexLongSide,
            2: QPrinter.DuplexShortSide
        }.get(self.duplex_combo.currentIndex(), QPrinter.DuplexNone)
        printer.setDuplex(duplex_mode)

        # Handle output destination
        if self.printer_combo.currentText() == "Save as PDF":
            pdf_path, _ = QFileDialog.getSaveFileName(
                self, "Save PDF", "", "PDF Files (*.pdf)"
            )
            if not pdf_path:
                return
            printer.setOutputFileName(pdf_path)
            printer.setOutputFormat(QPrinter.PdfFormat)
        else:
            printer.setOutputFileName("")  # Direct printing

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.warning(self, "Error", "Failed to initialize printer")
            return

        try:
            for i, img_path in enumerate(self.image_files):
                if i > 0:
                    printer.newPage()

                pixmap = QPixmap(img_path)
                if pixmap.isNull():
                    continue

                # Apply transformations
                rotation = self.image_rotations.get(img_path, 0)
                transform = QTransform().rotate(rotation)
                pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)

                # Get page dimensions as integers
                page_rect = printer.pageRect(QPrinter.DevicePixel)
                page_width = int(page_rect.width())
                page_height = int(page_rect.height())

                # Scale to fit page (fixed integer dimensions)
                scaled_pixmap = pixmap.scaled(
                    page_width,
                    page_height,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

                # Center on page
                x = (page_width - scaled_pixmap.width()) // 2
                y = (page_height - scaled_pixmap.height()) // 2
                painter.drawPixmap(x, y, scaled_pixmap)

            QMessageBox.information(self, "Success", f"Printed {len(self.image_files)} pages")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Printing failed:\n{str(e)}")
        finally:
            painter.end()

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/icon.ico"))

    window = SmartPrintApp()
    window.show()
    sys.exit(app.exec())

