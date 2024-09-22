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
    QGridLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QHeaderView,
)
from PyQt5.QtGui import QImage, QPixmap, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtCore import QRectF, Qt, QPointF


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

        self.font = QFont("Consolas", 12)
        self.char_width = self.calculate_char_width(self.font)
        self.char_height = self.calculate_char_height(self.font)

        self.init_ui()

    def cleanup(self):
        """Clean up resources."""
        if self.image_item:
            self.scene.removeItem(self.image_item)
            self.image_item = None
        if self.roi_item:
            self.scene.removeItem(self.roi_item)
            self.roi_item = None
        self.scene.clear()
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

        # Top row for file path and load image button
        top_row_layout = QHBoxLayout()
        main_layout.addLayout(top_row_layout)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("File Path")
        self.file_path_edit.setReadOnly(True)
        top_row_layout.addWidget(self.file_path_edit)

        self.load_button = QPushButton("Load Image")
        top_row_layout.addWidget(self.load_button)

        # Layout for image display and info
        display_layout = QHBoxLayout()
        main_layout.addLayout(display_layout)

        # Left side for image display
        self.image_view = QGraphicsView()
        self.scene = QGraphicsScene()  # Initialize scene here
        self.image_view.setScene(self.scene)
        display_layout.addWidget(self.image_view)

        # Right side layout (using QVBoxLayout for the right side information and table)
        right_side_layout = QVBoxLayout()
        display_layout.addLayout(right_side_layout)

        # Input fields for image info
        textbox_width = 7 * self.char_width

        self.height_edit = self.create_readonly_line_edit(self.font, textbox_width)
        self.width_edit = self.create_readonly_line_edit(self.font, textbox_width)
        self.pattern_edit = self.create_readonly_line_edit(self.font, textbox_width)
        self.bit_depth_edit = self.create_readonly_line_edit(self.font, textbox_width)

        # Create a QGridLayout for the image info
        info_grid_layout = QGridLayout()
        right_side_layout.addLayout(info_grid_layout)

        # Add labels and input fields to the right side layout
        info_grid_layout.addWidget(QLabel("Height:"), 0, 0)
        info_grid_layout.addWidget(self.height_edit, 0, 1)
        info_grid_layout.addWidget(QLabel("Width:"), 0, 2)
        info_grid_layout.addWidget(self.width_edit, 0, 3)
        info_grid_layout.addWidget(QLabel("Pattern:"), 1, 0)
        info_grid_layout.addWidget(self.pattern_edit, 1, 1)
        info_grid_layout.addWidget(QLabel("Bitdepth:"), 1, 2)
        info_grid_layout.addWidget(self.bit_depth_edit, 1, 3)

        # Initialize table for ROIs
        self.roi_table = QTableWidget(0, 5)
        self.roi_table.setHorizontalHeaderLabels(["", "tlX", "tlY", "brX", "brY"])

        # Set column resize mode: fixed for checkbox column, stretch for the others
        self.roi_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        for i in range(1, 5):
            self.roi_table.horizontalHeader().setSectionResizeMode(
                i, QHeaderView.Stretch
            )

        # Set checkbox column width based on the checkbox's size hint
        dummy_checkbox = QCheckBox()
        checkbox_width = dummy_checkbox.sizeHint().width()  # Optional padding
        self.roi_table.setColumnWidth(0, checkbox_width)

        # Set fixed width for coordinate columns
        for i in range(1, 5):
            self.roi_table.setColumnWidth(
                i, self.char_width * 4
            )  # Adjust as needed for coordinate display

        # Add the table and buttons to the right side layout
        right_side_layout.addWidget(self.roi_table)

        buttons_layout = QHBoxLayout()
        right_side_layout.addLayout(buttons_layout)

        self.clean_button = QPushButton("Clean")
        self.save_button = QPushButton("Save")
        buttons_layout.addWidget(self.clean_button)
        buttons_layout.addWidget(self.save_button)

        # Set button width based on label and textbox width
        button_width = (
            max(
                self.char_width * len(label)
                for label in ["Load Image", "Clean", "Save"]
            )
            + textbox_width
        )
        self.load_button.setFixedWidth(button_width)
        self.clean_button.setFixedWidth(button_width)
        self.save_button.setFixedWidth(button_width)

        # Set button actions
        self.load_button.clicked.connect(self.load_image)
        self.clean_button.clicked.connect(self.clean_table)
        self.save_button.clicked.connect(self.save_to_csv)

    def create_readonly_line_edit(self, font, width):
        line_edit = QLineEdit()
        line_edit.setFont(font)
        line_edit.setReadOnly(True)
        line_edit.setFixedWidth(width)
        return line_edit

    def calculate_char_width(self, font):
        return QFontMetrics(font).horizontalAdvance("0")

    def calculate_char_height(self, font):
        return QFontMetrics(font).height()

    def load_image(self):
        # Save any existing ROI records if needed
        if self.roi_table.rowCount() > 0:
            save_reply = QMessageBox.question(
                self,
                "Save Records",
                "There are unsaved ROI records. Do you want to save them?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )

            if save_reply == QMessageBox.Yes:
                default_path = str(
                    Path(__file__).parent / f"{self.image_path.stem}.csv"
                )
                try:
                    numpy_array = self.table_to_numpy()
                    self.save_numpy_to_csv(numpy_array, default_path)
                    self.roi_table.setRowCount(0)
                    QMessageBox.information(
                        self, "Success", f"Records saved to {default_path}."
                    )
                except Exception as e:
                    self.show_error_message(f"Error saving file: {str(e)}")

                # Clear the table after saving
                self.roi_table.setRowCount(0)

            elif save_reply == QMessageBox.No:
                # If user selects No, just clear the table
                self.roi_table.setRowCount(0)
            else:
                return  # If the user cancels, stop further execution

        # Proceed to load the image
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
                    self.image_info = self.parse_filename(self.image_path)
                    self.height_edit.setText(str(self.image_info[1]))
                    self.width_edit.setText(str(self.image_info[0]))
                    self.pattern_edit.setText(self.image_info[2])
                    self.bit_depth_edit.setText(str(self.image_info[3]))

                    width, height, pattern, bit_depth, title = self.image_info
                    dtype = self.get_numpy_dtype(bit_depth)

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
                    self.show_error_message(f"ValueError: {str(e)}")
                except Exception as e:
                    self.show_error_message(f"Error loading image: {str(e)}")

    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)

    def eventFilter(self, source, event):
        if source is self.image_view.viewport():
            if event.type() == event.MouseButtonPress:
                self.handle_mouse_press(event)
            elif event.type() == event.MouseMove:
                self.handle_mouse_move(event)
            elif event.type() == event.MouseButtonRelease:
                self.handle_mouse_release(event)
        return super().eventFilter(source, event)

    def handle_mouse_press(self, event):
        scene_pos = self.image_view.mapToScene(event.pos())
        self.selection_start = QPointF(scene_pos.x(), scene_pos.y())

    def handle_mouse_move(self, event):
        scene_pos = self.image_view.mapToScene(event.pos())
        self.selection_end = QPointF(scene_pos.x(), scene_pos.y())

        if self.selection_start and self.selection_end:
            rect = QRectF(self.selection_start, self.selection_end).normalized()
            self.update_roi_preview(rect)

    def handle_mouse_release(self, event):
        scene_pos = self.image_view.mapToScene(event.pos())
        self.selection_end = QPointF(scene_pos.x(), scene_pos.y())

        if self.selection_start and self.selection_end:
            rect = QRectF(self.selection_start, self.selection_end).normalized()
            self.update_roi_selection(rect)
            self.selection_start = self.selection_end = None

    def clip_roi_coordinates(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(self.image_info[0], x2), min(self.image_info[1], y2)
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def update_roi(self, rect, pen_style):
        if self.roi_item:
            self.scene.removeItem(self.roi_item)
        self.roi_item = self.scene.addRect(rect, QPen(pen_style))

    def update_roi_preview(self, rect):
        self.update_roi(rect, QPen(Qt.green, 2, Qt.DashLine))

    def update_roi_selection(self, rect):
        self.update_roi(rect, QPen(Qt.red, 2, Qt.SolidLine))
        self.roi_tl_x, self.roi_tl_y, self.roi_br_x, self.roi_br_y = (
            self.clip_roi_coordinates(
                rect.topLeft().toPoint().x(),
                rect.topLeft().toPoint().y(),
                rect.bottomRight().toPoint().x(),
                rect.bottomRight().toPoint().y(),
            )
        )
        self.add_roi_to_table()

    def add_roi_to_table(self):
        row_count = self.roi_table.rowCount()
        if row_count >= 256:
            self.roi_table.removeRow(
                0
            )  # Remove the oldest row if table exceeds 256 rows

        row_position = self.roi_table.rowCount()
        self.roi_table.insertRow(row_position)

        select_checkbox = QCheckBox()
        select_checkbox.setEnabled(True)
        self.roi_table.setCellWidget(row_position, 0, select_checkbox)

        # Add ROI coordinates
        self.roi_table.setItem(row_position, 1, QTableWidgetItem(f"{self.roi_tl_x:04}"))
        self.roi_table.setItem(row_position, 2, QTableWidgetItem(f"{self.roi_tl_y:04}"))
        self.roi_table.setItem(row_position, 3, QTableWidgetItem(f"{self.roi_br_x:04}"))
        self.roi_table.setItem(row_position, 4, QTableWidgetItem(f"{self.roi_br_y:04}"))

    def clean_table(self):
        # 检查表格是否有数据
        if self.roi_table.rowCount() > 0:
            # 检查是否有勾选的行
            selected_rows = [
                row
                for row in range(self.roi_table.rowCount())
                if self.roi_table.cellWidget(row, 0).isChecked()
            ]

            if not selected_rows:  # 如果没有勾选的行
                reply = QMessageBox.question(
                    self,
                    "Clear Confirmation",
                    "Are you sure to clean up all records?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self.roi_table.setRowCount(0)  # 清空所有记录
            else:  # 如果有选中的行，删除选中行
                for row in reversed(selected_rows):
                    self.roi_table.removeRow(row)

    def table_to_numpy(self):
        """Convert Qt table data to a NumPy 2D array, ignoring the first column."""
        num_rows = self.roi_table.rowCount()
        data = []

        for row in range(num_rows):
            row_data = [row]  # Start with the index
            for col in range(1, 5):  # Skip the first column and get the rest
                item = self.roi_table.item(row, col)
                row_data.append(item.text() if item else "")
            data.append(row_data)

        return np.array(data)

    def save_numpy_to_csv(self, numpy_array, file_path):
        try:
            np.savetxt(
                file_path,
                numpy_array,
                delimiter=",",
                fmt="%s",
                header="index,tlX,tlY,brX,brY",
                comments="",
            )
        except Exception as e:
            self.show_error_message(f"Error saving file: {str(e)}")

    def save_to_csv(self):
        # Check if the table is empty
        if self.roi_table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No ROI records to save.")
            return

        # Check if at least one row is selected
        selected_rows = [
            row
            for row in range(self.roi_table.rowCount())
            if self.roi_table.cellWidget(row, 0).isChecked()
        ]

        if selected_rows:
            QMessageBox.warning(self, "Warning", "Remaining records to clean up.")
            return

        # Get directory for saving CSV
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if not directory:
            return  # User cancelled the directory selection

        # Construct the CSV file path
        csv_filename = f"{self.image_path.stem}.csv"
        csv_path = Path(directory, csv_filename).resolve()

        try:
            numpy_array = self.table_to_numpy()
            self.save_numpy_to_csv(numpy_array, csv_path)
            QMessageBox.information(self, "Success", f"Data saved to {csv_path}.")
        except Exception as e:
            self.show_error_message(f"Error saving file: {str(e)}")

    def parse_filename(self, path: Path) -> tuple[int, int, str, int, str]:
        stem = path.stem
        temp, title = stem.split("-", maxsplit=1)
        ptn_cfa_sfd = re.compile(
            r"([1-9]\d*)x([1-9]\d*)_(\w+)_(8|10|12|14|16|20|24|32)bit"
        )
        result = ptn_cfa_sfd.match(temp)
        if result:
            width, height, pattern, bit_depth = result.groups()
            return int(width), int(height), pattern.upper(), int(bit_depth), title
        else:
            raise ValueError(f"Failed to parse filename: {path}")

    def get_numpy_dtype(self, bit_depth: int) -> np.dtype:
        if bit_depth <= 8:
            return np.uint8
        elif bit_depth <= 16:
            return np.uint16
        elif bit_depth <= 32:
            return np.uint32
        else:
            raise ValueError(f"Unsupported bit depth: {bit_depth}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
