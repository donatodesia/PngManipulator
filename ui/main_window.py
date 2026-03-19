from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.exporter import Exporter
from core.image_manager import ImageManager, SpriteEntry
from core.packer import GridPacker
from core.trimmer import get_content_bbox, compute_safe_margins, apply_trim
from ui.canvas import SpritesheetCanvas
from ui.resize_tab import ResizeTab
from ui.source_panel import SourcePanel
from ui.sprites_panel import SpritesPanel
from ui.toolbar import OutputToolbar

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spritesheet Editor")
        self.resize(1400, 800)

        self.manager = ImageManager()
        self.packer = GridPacker()
        self.exporter = Exporter()
        self._current_sheet = None

        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self.setAcceptDrops(True)
        self._update_status()

    # ------------------------------------------------------------------
    # UI layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.source_panel = SourcePanel()
        self.canvas = SpritesheetCanvas()
        self.sprites_panel = SpritesPanel(self.manager)
        self.toolbar = OutputToolbar()

        # Spritesheet tab
        spritesheet_widget = QWidget()
        ss_layout = QVBoxLayout(spritesheet_widget)
        ss_layout.setContentsMargins(0, 0, 0, 0)
        ss_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.source_panel)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self.sprites_panel)
        splitter.setSizes([260, 880, 240])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(2, False)

        ss_layout.addWidget(splitter, stretch=1)
        ss_layout.addWidget(self.toolbar)

        # Resize tab
        self.resize_tab = ResizeTab()

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(spritesheet_widget, "Spritesheet")
        self.tabs.addTab(self.resize_tab, "Resize")

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        act_export_png  = QAction("Export PNG…",  self)
        act_export_json = QAction("Export JSON…", self)
        act_export_both = QAction("Export Both…", self)
        act_export_png.triggered.connect(self._export_png)
        act_export_json.triggered.connect(self._export_json)
        act_export_both.triggered.connect(self._export_both)
        file_menu.addAction(act_export_png)
        file_menu.addAction(act_export_json)
        file_menu.addAction(act_export_both)

        edit_menu = menu_bar.addMenu("Edit")
        self.act_undo = QAction("Undo", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.setEnabled(False)
        self.act_undo.triggered.connect(self._undo)

        self.act_redo = QAction("Redo", self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.setEnabled(False)
        self.act_redo.triggered.connect(self._redo)

        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.source_panel.sprites_detected.connect(self._on_sprites_detected)
        self.source_panel.layout_changed.connect(self._on_source_layout_changed)
        self.sprites_panel.sprites_changed.connect(self._on_sprites_changed)
        self.sprites_panel.trim_requested.connect(self._on_trim_requested)
        self.sprites_panel.trim_all_requested.connect(self._on_trim_all)
        self.toolbar.settings_changed.connect(self.refresh)
        self.toolbar.layout_changed.connect(self._on_toolbar_layout_changed)
        self.toolbar.export_png_requested.connect(self._export_png)
        self.toolbar.export_json_requested.connect(self._export_json)
        self.toolbar.export_both_requested.connect(self._export_both)
        self.canvas.zoom_changed.connect(self._on_zoom_changed)
        self.resize_tab.status_message.connect(self.status_bar.showMessage)

    # ------------------------------------------------------------------
    # Core workflow
    # ------------------------------------------------------------------

    def _on_sprites_detected(self, entries: list[SpriteEntry]):
        if self.source_panel.auto_trim and entries:
            margins = compute_safe_margins(entries)
            if margins != (0, 0, 0, 0):
                entries = apply_trim(entries, margins)
        self.manager.add_sprites(entries)
        self.sprites_panel.refresh_list()
        self._auto_cell_size()
        self.refresh()

    def _on_sprites_changed(self):
        self._update_undo_redo()
        self.refresh()

    def _auto_cell_size(self):
        if not self.manager.sprites:
            return
        max_w = max(s.image.width  for s in self.manager.sprites)
        max_h = max(s.image.height for s in self.manager.sprites)
        self.toolbar.set_cell_size(max_w, max_h)

    def refresh(self):
        cell_w = self.toolbar.cell_w
        cell_h = self.toolbar.cell_h
        cols   = self.toolbar.columns
        pad    = self.toolbar.padding
        layout = self.toolbar.layout_mode

        self._current_sheet = self.packer.pack(
            self.manager, cols, cell_w, cell_h, pad, layout
        )
        content_rects = self._compute_content_rects(cols, cell_w, cell_h, pad, layout)
        self.canvas.load_sheet(
            self._current_sheet,
            cell_w, cell_h, pad,
            len(self.manager.sprites),
            content_rects,
        )
        self._update_status()
        self._update_undo_redo()

    # ------------------------------------------------------------------
    # Layout sync
    # ------------------------------------------------------------------

    def _on_source_layout_changed(self, mode: str):
        self.toolbar.set_layout(mode)
        self.refresh()

    def _on_toolbar_layout_changed(self, mode: str):
        self.source_panel.set_layout(mode)
        # refresh already triggered by toolbar.settings_changed

    # ------------------------------------------------------------------
    # Trim
    # ------------------------------------------------------------------

    def _on_trim_requested(self, indices: list[int]):
        if self.manager.trim_sprites(indices):
            self.sprites_panel.refresh_list()
            self._auto_cell_size()
            self.refresh()

    def _on_trim_all(self):
        all_indices = list(range(len(self.manager.sprites)))
        if self.manager.trim_sprites(all_indices):
            self.sprites_panel.refresh_list()
            self._auto_cell_size()
            self.refresh()

    # ------------------------------------------------------------------
    # Content rects for blue outlines
    # ------------------------------------------------------------------

    def _compute_content_rects(
        self, cols: int, cell_w: int, cell_h: int, pad: int, layout: str = "grid"
    ) -> list[tuple[int, int, int, int]]:
        sprites = self.manager.sprites
        if not sprites:
            return []
        rects: list[tuple[int, int, int, int]] = []
        positions = self.packer.get_positions(
            self.manager, cols, cell_w, cell_h, pad, layout
        )

        for entry, (cell_x, cell_y) in zip(sprites, positions):

            img = entry.image
            fitted_w = min(img.width,  cell_w)
            fitted_h = min(img.height, cell_h)
            offset_x = (cell_w - fitted_w) // 2
            offset_y = (cell_h - fitted_h) // 2
            sprite_x = cell_x + offset_x
            sprite_y = cell_y + offset_y

            bbox = get_content_bbox(img)
            if bbox:
                l, t, r, b = bbox
                l = min(l, fitted_w)
                t = min(t, fitted_h)
                r = min(r, fitted_w)
                b = min(b, fitted_h)
                rects.append((sprite_x + l, sprite_y + t, r - l, b - t))

        return rects

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    def _undo(self):
        if self.manager.undo():
            self.sprites_panel.refresh_list()
            self._auto_cell_size()
            self.refresh()

    def _redo(self):
        if self.manager.redo():
            self.sprites_panel.refresh_list()
            self._auto_cell_size()
            self.refresh()

    def _update_undo_redo(self):
        self.act_undo.setEnabled(self.manager.can_undo)
        self.act_redo.setEnabled(self.manager.can_redo)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _require_sheet(self) -> bool:
        if self._current_sheet is None:
            QMessageBox.warning(
                self, "Nothing to Export",
                "Load a spritesheet and detect sprites first."
            )
            return False
        return True

    def _export_png(self):
        if not self._require_sheet():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Spritesheet", "spritesheet_packed.png", "PNG (*.png)"
        )
        if path:
            self.exporter.export_png(self._current_sheet, path)
            self.status_bar.showMessage(f"Saved: {path}")

    def _export_json(self):
        if not self._require_sheet():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Metadata", "spritesheet_packed.json", "JSON (*.json)"
        )
        if path:
            meta = self._build_metadata(Path(path).with_suffix(".png").name)
            self.exporter.export_json(meta, path)
            self.status_bar.showMessage(f"Saved: {path}")

    def _export_both(self):
        if not self._require_sheet():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Spritesheet + Metadata", "spritesheet_packed.png", "PNG (*.png)"
        )
        if path:
            meta = self._build_metadata(Path(path).name)
            self.exporter.export_both(self._current_sheet, meta, path)
            self.status_bar.showMessage(f"Saved: {path} + .json")

    def _build_metadata(self, image_filename: str) -> dict:
        return self.packer.metadata(
            self.manager,
            self.toolbar.columns,
            self.toolbar.cell_w,
            self.toolbar.cell_h,
            self.toolbar.padding,
            image_filename,
            self.toolbar.layout_mode,
        )

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _update_status(self):
        count = len(self.manager.sprites)
        if self._current_sheet:
            w, h = self._current_sheet.size
            self.status_bar.showMessage(
                f"{count} sprite(s)  |  Output: {w} \u00d7 {h} px"
            )
        else:
            self.status_bar.showMessage(
                "Load a spritesheet, configure detection, then click Detect Sprites."
            )

    def _on_zoom_changed(self, pct: int):
        count = len(self.manager.sprites)
        if self._current_sheet:
            w, h = self._current_sheet.size
            self.status_bar.showMessage(
                f"{count} sprite(s)  |  Output: {w} \u00d7 {h} px  |  Zoom: {pct}%"
            )

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if any(path.lower().endswith(e) for e in SUPPORTED_EXTS):
                if self.source_panel.load_from_path(path):
                    break
