from __future__ import annotations

from PIL import Image
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.image_manager import ImageManager, SpriteEntry

THUMB_SIZE = 56
_ENTRY_ROLE = Qt.ItemDataRole.UserRole


class SpritesPanel(QWidget):
    sprites_changed = pyqtSignal()
    trim_requested = pyqtSignal(list)       # list[int] — selected indices
    trim_all_requested = pyqtSignal()

    def __init__(self, manager: ImageManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setMinimumWidth(180)
        self.setMaximumWidth(260)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header row: label | count | Trim All
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Sprites</b>"))
        self.lbl_count = QLabel("0")
        header.addWidget(self.lbl_count)
        header.addStretch()
        self.btn_trim_all = QPushButton("Trim All")
        self.btn_trim_all.setEnabled(False)
        self.btn_trim_all.setFixedHeight(22)
        header.addWidget(self.btn_trim_all)
        layout.addLayout(header)

        # Sprite list — multi-select + drag-reorder
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

        # Action buttons row
        btn_row = QHBoxLayout()
        self.btn_trim_sel = QPushButton("Trim Selected")
        self.btn_trim_sel.setEnabled(False)
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setEnabled(False)
        self.btn_clear = QPushButton("Clear All")
        btn_row.addWidget(self.btn_trim_sel)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        layout.addLayout(btn_row)

        # Connections
        self.btn_trim_sel.clicked.connect(self._trim_selected)
        self.btn_trim_all.clicked.connect(self.trim_all_requested.emit)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_all)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_list(self):
        self.list_widget.clear()
        for entry in self.manager.sprites:
            thumb = entry.image.copy()
            thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.NEAREST)
            pixmap = ImageManager.to_qpixmap(thumb)
            item = QListWidgetItem(QIcon(pixmap), entry.name)
            item.setData(_ENTRY_ROLE, entry)
            self.list_widget.addItem(item)
        self._update_header()

    def selected_indices(self) -> list[int]:
        return sorted(
            self.list_widget.row(item)
            for item in self.list_widget.selectedItems()
        )

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        if not self.list_widget.selectedItems():
            return
        menu = QMenu(self)
        act_trim = QAction("Trim Selected", self)
        act_remove = QAction("Remove", self)
        act_trim.triggered.connect(self._trim_selected)
        act_remove.triggered.connect(self._remove_selected)
        menu.addAction(act_trim)
        menu.addSeparator()
        menu.addAction(act_remove)
        menu.exec(self.list_widget.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        has_sel = bool(self.list_widget.selectedItems())
        self.btn_trim_sel.setEnabled(has_sel)
        self.btn_remove.setEnabled(has_sel)

    def _on_rows_moved(self, _parent, _start, _end, _dest, _dest_row):
        new_order = [
            self.list_widget.item(i).data(_ENTRY_ROLE)
            for i in range(self.list_widget.count())
        ]
        self.manager.replace_all(new_order)
        self._update_header()
        self.sprites_changed.emit()

    def _trim_selected(self):
        indices = self.selected_indices()
        if indices:
            self.trim_requested.emit(indices)

    def _remove_selected(self):
        # Remove highest indices first to preserve lower ones
        for row in sorted(self.selected_indices(), reverse=True):
            self.manager.remove(row)
        self.refresh_list()
        self.sprites_changed.emit()

    def _clear_all(self):
        if self.manager.sprites:
            self.manager.clear()
            self.refresh_list()
            self.sprites_changed.emit()

    def _update_header(self):
        n = len(self.manager.sprites)
        self.lbl_count.setText(str(n))
        self.btn_trim_all.setEnabled(n > 0)
