#! python3
# -*- encoding: utf-8 -*-
"""
@File    :   selectROI.py
@Time    :   2024/09/20 00:38:41
@Author  :   for13to1
@Version :   1.0
@Contact :   for13to1@outlook.com
"""

import sys
import re
import numpy as np
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QTextEdit,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QMessageBox,
)
from PyQt5.QtGui import QImage, QPixmap, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtCore import QRectF, Qt, QPointF


def cfa_parse_filename(path: Path) -> tuple[int, int, str, int, str]:
    stem = path.stem
    temp, title = stem.split("-", maxsplit=1)
    ptn_cfa_sfd = re.compile(r"([1-9]\d*)x([1-9]\d*)_(\w+)_(8|10|12|14|16|20|24|32)bit")
    result = ptn_cfa_sfd.match(temp)
    if result:
        width, height, pattern, bit_depth = result.groups()
        return int(width), int(height), pattern.upper(), int(bit_depth), title
    else:
        raise ValueError(f"Failed to parse filename: {path}")


def get_numpy_dtype(bit_depth: int) -> np.dtype:
    byte_depth = (bit_depth + 7) // 8
    dtype_mapping = {
        1: np.uint8,
        2: np.uint16,
        3: np.uint32,
        4: np.uint32,
    }
    if byte_depth not in dtype_mapping:
        raise ValueError(f"Unsupported bit depth: {bit_depth}")
    return dtype_mapping[byte_depth]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("selectROI")

        self.image_path = None
        self.image_info = None
        self.image_size = None
        self.selection_start = None
        self.selection_end = None

        self.roi_tl_x = None
        self.roi_tl_y = None
        self.roi_br_x = None
        self.roi_br_y = None

        self.qimage = None
        self.qpixmap = None
        self.image_item = None
        self.roi_item = None
        self.screen_geom = QApplication.primaryScreen().availableGeometry()
        self.init_ui()

    def cleanup(self):
        """Clean up resources."""
        if self.image_item:
            self.scene.removeItem(self.image_item)
            self.image_item = None
        if self.roi_item:
            self.scene.removeItem(self.roi_item)
            self.roi_item = None
        # Clear all items from the scene
        self.scene.clear()
        # Optionally, remove the scene from the view
        self.image_view.setScene(None)
        self.scene = None

    def closeEvent(self, event):
        """Handle the close event to clean up resources."""
        self.cleanup()
        super().closeEvent(event)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top row for file path
        file_path_layout = QHBoxLayout()
        main_layout.addLayout(file_path_layout)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("File Path")
        self.file_path_edit.setReadOnly(True)
        file_path_layout.addWidget(self.file_path_edit)

        # Layout for image display and info
        display_layout = QHBoxLayout()
        main_layout.addLayout(display_layout)

        # Left side for image display
        self.image_view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.image_view.setScene(self.scene)
        display_layout.addWidget(self.image_view)

        # Right side for image info and load button (vertical layout)
        right_side_layout = QVBoxLayout()
        display_layout.addLayout(right_side_layout)

        # Add Load Image button at the top
        self.load_button = QPushButton("Load Image")
        right_side_layout.addWidget(self.load_button)

        # Input fields for image info
        font = QFont("Consolas", 12)
        textbox_width = 7 * self.calculate_char_width(font)
        textbox_height = 5 * self.calculate_char_height(font)

        self.height_edit = self.create_readonly_line_edit(font, textbox_width)
        self.width_edit = self.create_readonly_line_edit(font, textbox_width)
        self.pattern_edit = self.create_readonly_line_edit(font, textbox_width)
        self.bit_depth_edit = self.create_readonly_line_edit(font, textbox_width)
        self.roi_info_edit = self.create_readonly_text_edit(
            font, textbox_width, textbox_height
        )

        # Add labels and input fields to the right side layout
        label_length_max = max(
            len(label) for label in ["Height:", "Width:", "Pattern:", "Bitdepth:"]
        ) * self.calculate_char_width(font)
        for label_text, edit in [
            ("Height:", self.height_edit),
            ("Width:", self.width_edit),
            ("Pattern:", self.pattern_edit),
            ("Bitdepth:", self.bit_depth_edit),
            ("ROI:", self.roi_info_edit),
        ]:
            right_side_layout.addLayout(
                self.create_info_row(label_text, edit, label_length_max)
            )

        # Set button width based on label and textbox width
        button_width = (
            label_length_max + textbox_width + self.calculate_char_width(font) * 4
        )
        self.load_button.setFixedWidth(button_width)

        # Set button action
        self.load_button.clicked.connect(self.load_image)

    def create_readonly_line_edit(self, font, width):
        line_edit = QLineEdit()
        line_edit.setFont(font)
        line_edit.setReadOnly(True)
        line_edit.setFixedWidth(width)
        return line_edit

    def create_readonly_text_edit(self, font, width, height):
        text_edit = QTextEdit()
        text_edit.setFont(font)
        text_edit.setReadOnly(True)
        text_edit.setFixedWidth(width)
        text_edit.setFixedHeight(height)
        text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        return text_edit

    def create_info_row(self, label_text, input_field, label_width=None):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        if label_width:
            label.setFixedWidth(label_width)
        layout.addWidget(label)
        layout.addWidget(input_field)
        return layout

    def calculate_char_width(self, font):
        return QFontMetrics(font).horizontalAdvance("0")

    def calculate_char_height(self, font):
        return QFontMetrics(font).height()

    def load_image(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("CFA Files (*.raw)")
        file_dialog.setViewMode(QFileDialog.List)
        if file_dialog.exec_():
            file_paths = file_dialog.selectedFiles()
            if file_paths:
                self.image_path = Path(file_paths[0])
                self.file_path_edit.setText(str(self.image_path))

                if not self.image_path.exists():
                    self.show_error_message("Selected file does not exist.")
                    return

                try:
                    self.image_info = cfa_parse_filename(self.image_path)
                    self.height_edit.setText(str(self.image_info[1]))
                    self.width_edit.setText(str(self.image_info[0]))
                    self.pattern_edit.setText(self.image_info[2])
                    self.bit_depth_edit.setText(str(self.image_info[3]))

                    width, height, pattern, bit_depth, title = self.image_info
                    dtype = get_numpy_dtype(bit_depth)

                    image_data = np.memmap(
                        self.image_path, dtype=dtype, mode="r", shape=(height, width)
                    )
                    if image_data.size == 0:
                        raise ValueError("Image data is empty or not properly mapped.")
                    image_data = (image_data >> (bit_depth - 8)).astype(np.uint8)

                    self.qimage = QImage(
                        image_data.data, width, height, width, QImage.Format_Grayscale8
                    )
                    if self.qimage.isNull():
                        raise ValueError("Failed to create QImage from image data")

                    self.qpixmap = QPixmap.fromImage(self.qimage)
                    if self.qpixmap.isNull():
                        raise ValueError("Failed to create QPixmap from QImage")

                    if self.image_item:
                        self.scene.removeItem(self.image_item)
                    self.image_item = QGraphicsPixmapItem(self.qpixmap)
                    self.scene.addItem(self.image_item)

                    self.image_size = self.qpixmap.size()
                    self.image_view.setSceneRect(QRectF(self.qpixmap.rect()))

                    if (
                        self.image_size.width() <= self.screen_geom.width() * 3 // 4
                        and self.image_size.height()
                        <= self.screen_geom.height() * 3 // 4
                    ):
                        self.image_view.setFixedSize(
                            self.image_size.width(), self.image_size.height()
                        )
                    else:
                        self.resize(
                            self.screen_geom.width() * 3 // 4,
                            self.screen_geom.height() * 3 // 4,
                        )

                    self.image_view.setRenderHint(QPainter.Antialiasing, True)
                    self.image_view.setRenderHint(QPainter.SmoothPixmapTransform, True)
                    self.image_view.viewport().installEventFilter(self)

                except ValueError as e:
                    self.show_error_message(f"Value Error: {str(e)}")
                except Exception as e:
                    self.show_error_message(f"Unexpected Error: {str(e)}")

    def eventFilter(self, obj, event):
        if obj == self.image_view.viewport():
            if (
                event.type() == event.MouseButtonPress
                and event.button() == Qt.LeftButton
            ):
                self.handle_mouse_press(event)
            elif event.type() == event.MouseMove and self.selection_start:
                self.handle_mouse_move(event)
            elif (
                event.type() == event.MouseButtonRelease
                and event.button() == Qt.LeftButton
                and self.selection_start
            ):
                self.handle_mouse_release(event)
        return super().eventFilter(obj, event)

    def handle_mouse_press(self, event):
        scene_pos = self.image_view.mapToScene(event.pos())
        self.selection_start = QPointF(scene_pos.x(), scene_pos.y())
        if self.roi_item:
            self.scene.removeItem(self.roi_item)
            self.roi_item = None

    def handle_mouse_move(self, event):
        scene_pos = self.image_view.mapToScene(event.pos())
        self.selection_end = QPointF(scene_pos.x(), scene_pos.y())
        rect = QRectF(self.selection_start, self.selection_end).normalized()
        self.update_roi_preview(rect)

    def handle_mouse_release(self, event):
        scene_pos = self.image_view.mapToScene(event.pos())
        self.selection_end = QPointF(scene_pos.x(), scene_pos.y())
        rect = QRectF(self.selection_start, self.selection_end).normalized()
        self.update_roi_selection(rect)
        self.selection_start = self.selection_end = None

    def update_roi_preview(self, rect):
        self.update_roi(rect, QPen(Qt.green, 2, Qt.DashLine))

    def update_roi_selection(self, rect):
        self.update_roi(rect, QPen(Qt.red, 2, Qt.SolidLine))
        self.roi_tl_x, self.roi_tl_y = (
            rect.topLeft().toPoint().x(),
            rect.topLeft().toPoint().y(),
        )
        self.roi_br_x, self.roi_br_y = (
            rect.bottomRight().toPoint().x(),
            rect.bottomRight().toPoint().y(),
        )
        self.roi_info_edit.setPlainText(
            f"{self.roi_tl_x:04},{self.roi_tl_y:04},{self.roi_br_x:04},{self.roi_br_y:04}"
        )

    def update_roi(self, rect, pen_style):
        if self.roi_item:
            self.scene.removeItem(self.roi_item)
        self.roi_item = self.scene.addRect(rect, QPen(pen_style))

    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
