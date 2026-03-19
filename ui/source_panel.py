from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.image_manager import ImageManager, SpriteEntry
from core.packer import LAYOUT_GRID, LAYOUT_HORIZONTAL, LAYOUT_VERTICAL
from core.sprite_detector import detect_irregular, detect_regular

SUPPORTED = "Images (*.png *.jpg *.jpeg)"


class SourcePanel(QWidget):
    """Left panel: load a spritesheet and run sprite detection."""

    sprites_detected = pyqtSignal(list)   # list[SpriteEntry]
    layout_changed   = pyqtSignal(str)    # "horizontal" | "vertical" | "grid"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_image: Optional[Image.Image] = None
        self._source_path: str = ""
        self._bg_color: tuple = (0, 255, 0)
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        layout.addWidget(QLabel("<b>Source Sheet</b>"))

        self.btn_load = QPushButton("Load Sheet...")
        self.btn_load.clicked.connect(self._load_sheet)
        layout.addWidget(self.btn_load)

        self.lbl_file = QLabel("No file loaded")
        self.lbl_file.setWordWrap(True)
        self.lbl_file.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.lbl_file)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedHeight(80)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setStyleSheet("border: 1px solid #666; background: #333;")
        layout.addWidget(self.lbl_thumb)

        layout.addWidget(self._build_layout_group())
        layout.addWidget(self._build_mode_group())
        layout.addWidget(self._build_bg_group())
        layout.addStretch()

        self.chk_auto_trim = QCheckBox("Auto-trim on detect")
        layout.addWidget(self.chk_auto_trim)

        self.btn_detect = QPushButton("Detect Sprites")
        self.btn_detect.setEnabled(False)
        self.btn_detect.clicked.connect(self._detect)
        layout.addWidget(self.btn_detect)

    def _build_layout_group(self) -> QGroupBox:
        group = QGroupBox("Layout")
        lay = QHBoxLayout(group)

        self.radio_horizontal = QRadioButton("Horizontal")
        self.radio_vertical   = QRadioButton("Vertical")
        self.radio_grid       = QRadioButton("Grid")
        self.radio_horizontal.setChecked(True)

        lg = QButtonGroup(self)
        for r in (self.radio_horizontal, self.radio_vertical, self.radio_grid):
            lg.addButton(r)
            lay.addWidget(r)

        self.radio_horizontal.toggled.connect(self._on_layout_toggled)
        self.radio_vertical.toggled.connect(self._on_layout_toggled)
        self.radio_grid.toggled.connect(self._on_layout_toggled)
        return group

    def _build_mode_group(self) -> QGroupBox:
        group = QGroupBox("Detection Mode")
        layout = QVBoxLayout(group)

        self.radio_regular   = QRadioButton("Regular Grid")
        self.radio_irregular = QRadioButton("Irregular / Auto-Detect")
        self.radio_regular.setChecked(True)

        dg = QButtonGroup(self)
        dg.addButton(self.radio_regular)
        dg.addButton(self.radio_irregular)
        layout.addWidget(self.radio_regular)
        layout.addWidget(self.radio_irregular)

        self.stack = QStackedWidget()

        # Regular page
        reg_page = QWidget()
        rp = QVBoxLayout(reg_page)
        rp.setContentsMargins(0, 0, 0, 0)

        row_r = QHBoxLayout()
        row_r.addWidget(QLabel("Rows:"))
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 512)
        self.spin_rows.setValue(1)
        row_r.addWidget(self.spin_rows)
        rp.addLayout(row_r)

        row_c = QHBoxLayout()
        row_c.addWidget(QLabel("Cols:"))
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 512)
        self.spin_cols.setValue(6)
        row_c.addWidget(self.spin_cols)
        rp.addLayout(row_c)
        self.stack.addWidget(reg_page)

        # Irregular page
        irr_page = QWidget()
        ip = QVBoxLayout(irr_page)
        ip.setContentsMargins(0, 0, 0, 0)
        row_m = QHBoxLayout()
        row_m.addWidget(QLabel("Min pixels:"))
        self.spin_min_px = QSpinBox()
        self.spin_min_px.setRange(1, 500)
        self.spin_min_px.setValue(4)
        row_m.addWidget(self.spin_min_px)
        ip.addLayout(row_m)
        self.stack.addWidget(irr_page)

        layout.addWidget(self.stack)
        self.radio_regular.toggled.connect(
            lambda checked: self.stack.setCurrentIndex(0 if checked else 1)
        )
        # Apply initial lock state for rows/cols based on current layout
        self._apply_layout_lock()
        return group

    def _build_bg_group(self) -> QGroupBox:
        group = QGroupBox("Background")
        layout = QVBoxLayout(group)

        self.radio_transparent = QRadioButton("Transparent")
        self.radio_solid       = QRadioButton("Solid Color")
        self.radio_transparent.setChecked(True)

        bg_grp = QButtonGroup(self)
        bg_grp.addButton(self.radio_transparent)
        bg_grp.addButton(self.radio_solid)
        layout.addWidget(self.radio_transparent)

        solid_row = QHBoxLayout()
        solid_row.addWidget(self.radio_solid)
        self.btn_color = QPushButton()
        self.btn_color.setFixedWidth(32)
        self.btn_color.setEnabled(False)
        self._refresh_color_btn()
        solid_row.addWidget(self.btn_color)
        layout.addLayout(solid_row)

        self.radio_solid.toggled.connect(self.btn_color.setEnabled)
        self.btn_color.clicked.connect(self._pick_color)
        return group

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def auto_trim(self) -> bool:
        return self.chk_auto_trim.isChecked()

    @property
    def layout_mode(self) -> str:
        if self.radio_horizontal.isChecked():
            return LAYOUT_HORIZONTAL
        if self.radio_vertical.isChecked():
            return LAYOUT_VERTICAL
        return LAYOUT_GRID

    # ------------------------------------------------------------------
    # Public: sync from toolbar
    # ------------------------------------------------------------------

    def set_layout(self, mode: str):
        """Called by main_window to sync with the toolbar radio."""
        self.radio_horizontal.blockSignals(True)
        self.radio_vertical.blockSignals(True)
        self.radio_grid.blockSignals(True)
        if mode == LAYOUT_HORIZONTAL:
            self.radio_horizontal.setChecked(True)
        elif mode == LAYOUT_VERTICAL:
            self.radio_vertical.setChecked(True)
        else:
            self.radio_grid.setChecked(True)
        self.radio_horizontal.blockSignals(False)
        self.radio_vertical.blockSignals(False)
        self.radio_grid.blockSignals(False)
        self._apply_layout_lock()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_layout_toggled(self):
        self._apply_layout_lock()
        self.layout_changed.emit(self.layout_mode)

    def _apply_layout_lock(self):
        """Lock rows=1 for Horizontal, cols=1 for Vertical in Regular Grid."""
        mode = self.layout_mode
        if mode == LAYOUT_HORIZONTAL:
            self.spin_rows.setValue(1)
            self.spin_rows.setEnabled(False)
            self.spin_cols.setEnabled(True)
        elif mode == LAYOUT_VERTICAL:
            self.spin_cols.setValue(1)
            self.spin_cols.setEnabled(False)
            self.spin_rows.setEnabled(True)
        else:
            self.spin_rows.setEnabled(True)
            self.spin_cols.setEnabled(True)

    def _load_sheet(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Spritesheet", "", SUPPORTED)
        if not path:
            return
        try:
            self._source_image = Image.open(path).convert("RGBA")
            self._source_path  = path
            self.lbl_file.setText(Path(path).name)
            thumb = self._source_image.copy()
            thumb.thumbnail((240, 76), Image.Resampling.NEAREST)
            self.lbl_thumb.setPixmap(ImageManager.to_qpixmap(thumb))
            self.btn_detect.setEnabled(True)
        except Exception as e:
            self.lbl_file.setText(f"Error: {e}")
            self._source_image = None
            self.btn_detect.setEnabled(False)

    def _pick_color(self):
        r, g, b = self._bg_color[:3]
        color = QColorDialog.getColor(QColor(r, g, b), self, "Select Background Color")
        if color.isValid():
            self._bg_color = (color.red(), color.green(), color.blue())
            self._refresh_color_btn()

    def _refresh_color_btn(self):
        r, g, b = self._bg_color[:3]
        self.btn_color.setStyleSheet(f"background-color: rgb({r},{g},{b});")

    def _detect(self):
        if self._source_image is None:
            return

        bg_mode    = "solid" if self.radio_solid.isChecked() else "transparent"
        bg_color   = self._bg_color if bg_mode == "solid" else None
        source_name = Path(self._source_path).stem

        if self.radio_regular.isChecked():
            detected = detect_regular(
                self._source_image,
                rows=self.spin_rows.value(),
                cols=self.spin_cols.value(),
                bg_mode=bg_mode,
                bg_color=bg_color,
            )
        else:
            detected = detect_irregular(
                self._source_image,
                bg_mode=bg_mode,
                bg_color=bg_color,
                min_pixels=self.spin_min_px.value(),
            )

        entries = [
            SpriteEntry(
                name=f"{source_name}_{i:03d}",
                image=d.image,
                source_file=self._source_path,
            )
            for i, d in enumerate(detected)
        ]
        self.sprites_detected.emit(entries)

    def load_from_path(self, path: str) -> bool:
        try:
            self._source_image = Image.open(path).convert("RGBA")
            self._source_path  = path
            self.lbl_file.setText(Path(path).name)
            thumb = self._source_image.copy()
            thumb.thumbnail((240, 76), Image.Resampling.NEAREST)
            self.lbl_thumb.setPixmap(ImageManager.to_qpixmap(thumb))
            self.btn_detect.setEnabled(True)
            return True
        except Exception:
            return False
