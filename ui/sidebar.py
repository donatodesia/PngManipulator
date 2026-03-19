from PIL import Image
from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.image_manager import ImageManager

SUPPORTED = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
THUMB_SIZE = 48


class Sidebar(QWidget):
    images_changed = pyqtSignal()

    def __init__(self, manager: ImageManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setMinimumWidth(160)
        self.setMaximumWidth(260)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(QLabel("<b>Sprites</b>"))

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.list_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.list_widget)

        row1 = QHBoxLayout()
        self.btn_add = QPushButton("Add")
        self.btn_remove = QPushButton("Remove")
        row1.addWidget(self.btn_add)
        row1.addWidget(self.btn_remove)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_up = QPushButton("Up")
        self.btn_down = QPushButton("Down")
        row2.addWidget(self.btn_up)
        row2.addWidget(self.btn_down)
        layout.addLayout(row2)

        self.btn_add.clicked.connect(self._add_images)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down.clicked.connect(lambda: self._move(1))

    def _add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open Images", "", SUPPORTED
        )
        for path in paths:
            self.manager.load(path)
        if paths:
            self.refresh_list()
            self.images_changed.emit()

    def _remove_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.manager.remove(row)
            self.refresh_list()
            self.images_changed.emit()

    def _move(self, direction: int):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        new_row = self.manager.move(row, direction)
        self.refresh_list()
        self.list_widget.setCurrentRow(new_row)
        self.images_changed.emit()

    def refresh_list(self):
        self.list_widget.clear()
        for entry in self.manager.sprites:
            thumb = entry.original.copy()
            thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.NEAREST)
            pixmap = ImageManager.to_qpixmap(thumb)
            item = QListWidgetItem(QIcon(pixmap), entry.name)
            self.list_widget.addItem(item)
