from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QDragEnterEvent, QDropEvent, QPainter
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import core.ai_upscaler as ai_upscaler
from core.resizer import output_size, resize_image, save_resized

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}


class AIUpscaleWorker(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal(int, int)  # saved, errors

    def __init__(self, images: list, out_dir: Path, scale: int,
                 model: str = "photo", sharpness: int = 0, detail_blend: int = 0):
        super().__init__()
        self._images = images
        self._out_dir = out_dir
        self._scale = scale
        self._model = model
        self._sharpness = sharpness
        self._detail_blend = detail_blend

    def run(self):
        import datetime
        import time

        def ts():
            return datetime.datetime.now().strftime("%H:%M:%S")

        scale = self._scale
        total_images = len(self._images)
        self.log.emit(
            f"[{ts()}] Starting AI upscale ({scale}x | model={self._model} | "
            f"sharpness={self._sharpness} | detail={self._detail_blend}) "
            f"— {total_images} image(s)"
        )

        saved = 0
        errors = 0
        t_start = time.time()

        for idx, (path, img) in enumerate(self._images, 1):
            self.log.emit(
                f"[{ts()}] Processing ({idx}/{total_images}): {path.name} "
                f"({img.width}×{img.height})"
            )
            t_img = time.time()

            def on_tile(done, total, _ts=ts, _idx=idx):
                pct = int(done / total * 100)
                if done == 1 or done == total or done % max(1, total // 10) == 0:
                    self.log.emit(f"[{_ts()}]   Tile {done}/{total} ({pct}%)")

            try:
                result = ai_upscaler.upscale(
                    img, model=self._model, sharpness=self._sharpness,
                    detail_blend=self._detail_blend, on_tile=on_tile
                )
                out_file = self._out_dir / (path.stem + f"_ai{scale}x.png")
                result.save(out_file, format="PNG")
                elapsed = time.time() - t_img
                self.log.emit(
                    f"[{ts()}]   Saved: {out_file.name} "
                    f"({result.width}×{result.height}) — {elapsed:.1f}s"
                )
                saved += 1
            except Exception as e:
                self.log.emit(f"[{ts()}]   ERROR: {path.name}: {e}")
                errors += 1

        total_elapsed = time.time() - t_start
        self.log.emit(
            f"[{ts()}] Done — {saved} saved, {errors} errors "
            f"— total {total_elapsed:.1f}s"
        )
        self.finished.emit(saved, errors)


def _pil_to_pixmap(img: Image.Image) -> QPixmap:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    qimg = QImage()
    qimg.loadFromData(buf.read())
    return QPixmap.fromImage(qimg)


class ResizeTab(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._images: list[tuple[Path, Image.Image]] = []
        self._selected_idx: int = -1
        self._aspect_locked = True
        self._ai_scale = 4
        self._w_changing = False
        self._h_changing = False
        self._ai_available = ai_upscaler.is_available()

        self._build_ui()
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_file_panel())
        splitter.addWidget(self._build_controls_panel())
        splitter.setSizes([260, 900])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        root.addWidget(splitter)

    # ---- left: file list ----

    def _build_file_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        self._btn_load = QPushButton("Load PNG(s)…")
        self._btn_remove = QPushButton("Remove")
        self._btn_clear = QPushButton("Clear")
        self._btn_remove.setEnabled(False)
        self._btn_clear.setEnabled(False)
        btn_row.addWidget(self._btn_load)
        btn_row.addWidget(self._btn_remove)
        btn_row.addWidget(self._btn_clear)
        lay.addLayout(btn_row)

        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._file_list.setAcceptDrops(False)
        lay.addWidget(self._file_list)

        hint = QLabel("or drag & drop PNG files here")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(hint)

        self._btn_load.clicked.connect(self._load_files)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_clear.clicked.connect(self._clear_all)
        self._file_list.currentRowChanged.connect(self._on_selection_changed)

        return w

    # ---- right: controls + preview ----

    def _build_controls_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # --- scale mode ---
        mode_frame = QFrame()
        mode_frame.setFrameShape(QFrame.Shape.StyledPanel)
        mode_lay = QVBoxLayout(mode_frame)
        mode_lay.setContentsMargins(8, 6, 8, 6)

        mode_label = QLabel("Scale mode")
        mode_label.setStyleSheet("font-weight: bold;")
        mode_lay.addWidget(mode_label)

        radio_row = QHBoxLayout()
        self._rb_factor = QRadioButton("Factor")
        self._rb_percent = QRadioButton("Percent")
        self._rb_dims = QRadioButton("Dimensions")
        self._rb_ai = QRadioButton("AI Upscale")
        self._rb_factor.setChecked(True)
        for rb in (self._rb_factor, self._rb_percent, self._rb_dims, self._rb_ai):
            radio_row.addWidget(rb)
        radio_row.addStretch()
        mode_lay.addLayout(radio_row)

        bg = QButtonGroup(self)
        bg.addButton(self._rb_factor)
        bg.addButton(self._rb_percent)
        bg.addButton(self._rb_dims)
        bg.addButton(self._rb_ai)

        # factor row
        self._factor_widget = QWidget()
        flay = QHBoxLayout(self._factor_widget)
        flay.setContentsMargins(0, 0, 0, 0)
        flay.addWidget(QLabel("Factor:"))
        self._spin_factor = QDoubleSpinBox()
        self._spin_factor.setRange(0.1, 64.0)
        self._spin_factor.setSingleStep(0.25)
        self._spin_factor.setValue(2.0)
        self._spin_factor.setDecimals(2)
        flay.addWidget(self._spin_factor)
        flay.addWidget(QLabel("  Presets:"))
        for label, val in [("½x", 0.5), ("1x", 1.0), ("2x", 2.0), ("4x", 4.0), ("8x", 8.0)]:
            btn = QPushButton(label)
            btn.setFixedWidth(38)
            btn.clicked.connect(lambda _, v=val: self._spin_factor.setValue(v))
            flay.addWidget(btn)
        flay.addStretch()
        mode_lay.addWidget(self._factor_widget)

        # percent row
        self._percent_widget = QWidget()
        play = QHBoxLayout(self._percent_widget)
        play.setContentsMargins(0, 0, 0, 0)
        play.addWidget(QLabel("Percent:"))
        self._spin_percent = QSpinBox()
        self._spin_percent.setRange(1, 10000)
        self._spin_percent.setValue(200)
        self._spin_percent.setSuffix(" %")
        play.addWidget(self._spin_percent)
        play.addWidget(QLabel("  Presets:"))
        for label, val in [("25%", 25), ("50%", 50), ("100%", 100), ("200%", 200), ("400%", 400)]:
            btn = QPushButton(label)
            btn.setFixedWidth(46)
            btn.clicked.connect(lambda _, v=val: self._spin_percent.setValue(v))
            play.addWidget(btn)
        play.addStretch()
        self._percent_widget.setVisible(False)
        mode_lay.addWidget(self._percent_widget)

        # dims row
        self._dims_widget = QWidget()
        dlay = QHBoxLayout(self._dims_widget)
        dlay.setContentsMargins(0, 0, 0, 0)
        dlay.addWidget(QLabel("Width:"))
        self._spin_w = QSpinBox()
        self._spin_w.setRange(1, 65535)
        self._spin_w.setValue(128)
        dlay.addWidget(self._spin_w)

        self._btn_lock = QToolButton()
        self._btn_lock.setCheckable(True)
        self._btn_lock.setChecked(True)
        self._btn_lock.setText("🔒")
        self._btn_lock.setToolTip("Lock aspect ratio")
        self._btn_lock.toggled.connect(self._on_lock_toggled)
        dlay.addWidget(self._btn_lock)

        dlay.addWidget(QLabel("Height:"))
        self._spin_h = QSpinBox()
        self._spin_h.setRange(1, 65535)
        self._spin_h.setValue(128)
        dlay.addWidget(self._spin_h)
        dlay.addStretch()
        self._dims_widget.setVisible(False)
        mode_lay.addWidget(self._dims_widget)

        # AI upscale row
        self._ai_widget = QWidget()
        ailay = QVBoxLayout(self._ai_widget)
        ailay.setContentsMargins(0, 4, 0, 0)
        ailay.setSpacing(6)

        if self._ai_available:
            # Row 1: scale + model
            row1 = QHBoxLayout()
            row1.addWidget(QLabel("Scale:"))
            self._btn_ai_2x = QPushButton("2×")
            self._btn_ai_4x = QPushButton("4×")
            self._btn_ai_2x.setFixedWidth(48)
            self._btn_ai_4x.setFixedWidth(48)
            self._btn_ai_4x.setStyleSheet("font-weight: bold;")
            self._btn_ai_2x.clicked.connect(lambda: self._set_ai_scale(2))
            self._btn_ai_4x.clicked.connect(lambda: self._set_ai_scale(4))
            row1.addWidget(self._btn_ai_2x)
            row1.addWidget(self._btn_ai_4x)
            row1.addSpacing(16)
            row1.addWidget(QLabel("Model:"))
            self._combo_ai_model = QComboBox()
            self._combo_ai_model.addItem("Photos / Real world", "photo")
            self._combo_ai_model.addItem("Anime / Illustrations", "anime")
            self._combo_ai_model.addItem("SwinIR (high quality)", "swinir")
            row1.addWidget(self._combo_ai_model)
            row1.addStretch()
            ailay.addLayout(row1)

            # Row 2: sharpness
            row2 = QHBoxLayout()
            row2.addWidget(QLabel("Sharpness:"))
            self._slider_sharpness = QSlider(Qt.Orientation.Horizontal)
            self._slider_sharpness.setRange(0, 100)
            self._slider_sharpness.setValue(0)
            self._slider_sharpness.setFixedWidth(150)
            self._label_sharpness = QLabel("0")
            self._label_sharpness.setFixedWidth(24)
            self._slider_sharpness.valueChanged.connect(
                lambda v: self._label_sharpness.setText(str(v))
            )
            row2.addWidget(self._slider_sharpness)
            row2.addWidget(self._label_sharpness)
            row2.addSpacing(16)
            row2.addWidget(QLabel("Detail preservation:"))
            self._slider_detail = QSlider(Qt.Orientation.Horizontal)
            self._slider_detail.setRange(0, 100)
            self._slider_detail.setValue(0)
            self._slider_detail.setFixedWidth(150)
            self._label_detail = QLabel("0")
            self._label_detail.setFixedWidth(24)
            self._slider_detail.valueChanged.connect(
                lambda v: self._label_detail.setText(str(v))
            )
            row2.addWidget(self._slider_detail)
            row2.addWidget(self._label_detail)
            row2.addStretch()
            ailay.addLayout(row2)

            warn = QLabel("Models download automatically on first use. CPU processing may be slow.")
            warn.setStyleSheet("color: #b8860b; font-size: 11px;")
            ailay.addWidget(warn)
        else:
            msg = QLabel(
                "Real-ESRGAN not installed.  Run in your terminal:\n"
                "    pip install realesrgan basicsr torch torchvision\n"
                "then restart the app."
            )
            msg.setStyleSheet(
                "background: #fff3cd; border: 1px solid #ffc107; "
                "border-radius: 4px; padding: 8px; font-family: monospace; font-size: 11px;"
            )
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            ailay.addWidget(msg)

        self._ai_widget.setVisible(False)
        mode_lay.addWidget(self._ai_widget)

        lay.addWidget(mode_frame)

        # --- resampling (hidden when AI mode active) ---
        self._resample_row_widget = QWidget()
        rrow = QHBoxLayout(self._resample_row_widget)
        rrow.setContentsMargins(0, 0, 0, 0)
        rrow.addWidget(QLabel("Resampling:"))
        self._combo_resample = QComboBox()
        self._combo_resample.addItem("Lanczos (smooth, best for photos)", "lanczos")
        self._combo_resample.addItem("Bicubic (smooth, faster)", "bicubic")
        self._combo_resample.addItem("Bilinear (smooth, fastest)", "bilinear")
        self._combo_resample.addItem("Nearest (sharp pixels, pixel art)", "nearest")
        self._combo_resample.currentIndexChanged.connect(self._refresh_preview)
        rrow.addWidget(self._combo_resample)
        rrow.addStretch()
        lay.addWidget(self._resample_row_widget)

        # --- preview + log side by side ---
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        preview_lay = QVBoxLayout(preview_frame)
        preview_lay.setContentsMargins(8, 6, 8, 6)

        preview_label = QLabel("Preview")
        preview_label.setStyleSheet("font-weight: bold;")
        preview_lay.addWidget(preview_label)

        self._preview_view = QGraphicsView()
        self._preview_scene = QGraphicsScene()
        self._preview_view.setScene(self._preview_scene)
        self._preview_view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self._preview_view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._preview_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._preview_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_lay.addWidget(self._preview_view, stretch=1)

        self._info_label = QLabel("No image loaded")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet("color: gray; font-size: 11px;")
        preview_lay.addWidget(self._info_label)

        # log terminal — right of preview, visible only in AI mode
        log_frame = QFrame()
        log_frame.setFrameShape(QFrame.Shape.StyledPanel)
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(8, 6, 8, 6)
        log_layout.setSpacing(4)

        log_header = QLabel("AI Upscale Log")
        log_header.setStyleSheet("font-weight: bold;")
        log_layout.addWidget(log_header)

        self._log_widget = QTextEdit()
        self._log_widget.setReadOnly(True)
        self._log_widget.setStyleSheet(
            "background: #1e1e1e; color: #d4d4d4; "
            "font-family: Consolas, monospace; font-size: 11px; border: none;"
        )
        log_layout.addWidget(self._log_widget, stretch=1)

        self._preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._preview_splitter.addWidget(preview_frame)
        self._preview_splitter.addWidget(log_frame)
        self._preview_splitter.setSizes([600, 300])
        log_frame.setVisible(False)
        self._log_frame = log_frame

        lay.addWidget(self._preview_splitter, stretch=1)

        # --- export row ---
        export_row = QHBoxLayout()
        self._btn_export = QPushButton("Export All to Folder…")
        self._btn_export.setEnabled(False)
        self._btn_export.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        export_row.addWidget(self._btn_export)
        export_row.addStretch()
        lay.addLayout(export_row)

        # connect signals
        self._rb_factor.toggled.connect(self._on_mode_changed)
        self._rb_percent.toggled.connect(self._on_mode_changed)
        self._rb_dims.toggled.connect(self._on_mode_changed)
        self._rb_ai.toggled.connect(self._on_mode_changed)
        self._spin_factor.valueChanged.connect(self._refresh_preview)
        self._spin_percent.valueChanged.connect(self._refresh_preview)
        self._spin_w.valueChanged.connect(self._on_w_changed)
        self._spin_h.valueChanged.connect(self._on_h_changed)
        self._btn_export.clicked.connect(self._export_all)

        return w

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _on_mode_changed(self):
        is_factor = self._rb_factor.isChecked()
        is_percent = self._rb_percent.isChecked()
        is_dims = self._rb_dims.isChecked()
        is_ai = self._rb_ai.isChecked()
        self._factor_widget.setVisible(is_factor)
        self._percent_widget.setVisible(is_percent)
        self._dims_widget.setVisible(is_dims)
        self._ai_widget.setVisible(is_ai)
        self._resample_row_widget.setVisible(not is_ai)
        self._log_frame.setVisible(is_ai)
        self._refresh_preview()

    # ------------------------------------------------------------------
    # AI scale selector
    # ------------------------------------------------------------------

    def _set_ai_scale(self, scale: int):
        self._ai_scale = scale
        if self._ai_available:
            self._btn_ai_2x.setStyleSheet("font-weight: bold;" if scale == 2 else "")
            self._btn_ai_4x.setStyleSheet("font-weight: bold;" if scale == 4 else "")
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Aspect ratio lock
    # ------------------------------------------------------------------

    def _on_lock_toggled(self, locked: bool):
        self._aspect_locked = locked
        self._btn_lock.setText("🔒" if locked else "🔓")

    def _on_w_changed(self, value: int):
        if self._w_changing:
            return
        if self._aspect_locked and self._selected_idx >= 0:
            _, img = self._images[self._selected_idx]
            if img.width:
                ratio = img.height / img.width
                new_h = max(1, round(value * ratio))
                self._h_changing = True
                self._spin_h.setValue(new_h)
                self._h_changing = False
        self._refresh_preview()

    def _on_h_changed(self, value: int):
        if self._h_changing:
            return
        if self._aspect_locked and self._selected_idx >= 0:
            _, img = self._images[self._selected_idx]
            if img.height:
                ratio = img.width / img.height
                new_w = max(1, round(value * ratio))
                self._w_changing = True
                self._spin_w.setValue(new_w)
                self._w_changing = False
        self._refresh_preview()

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    def _load_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Load Images", "", "Images (*.png *.jpg *.jpeg)"
        )
        for p in paths:
            self._add_file(Path(p))

    def _add_file(self, path: Path):
        if path.suffix.lower() not in SUPPORTED_EXTS:
            return
        if any(p == path for p, _ in self._images):
            return
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return
        self._images.append((path, img))
        item = QListWidgetItem(f"{path.name}  ({img.width}×{img.height})")
        self._file_list.addItem(item)
        self._btn_clear.setEnabled(True)
        self._btn_export.setEnabled(True)
        if self._file_list.currentRow() < 0:
            self._file_list.setCurrentRow(0)

    def _remove_selected(self):
        row = self._file_list.currentRow()
        if row < 0:
            return
        self._file_list.takeItem(row)
        self._images.pop(row)
        if not self._images:
            self._btn_remove.setEnabled(False)
            self._btn_clear.setEnabled(False)
            self._btn_export.setEnabled(False)
            self._selected_idx = -1
            self._clear_preview()

    def _clear_all(self):
        self._file_list.clear()
        self._images.clear()
        self._selected_idx = -1
        self._btn_remove.setEnabled(False)
        self._btn_clear.setEnabled(False)
        self._btn_export.setEnabled(False)
        self._clear_preview()

    def _on_selection_changed(self, row: int):
        self._selected_idx = row
        self._btn_remove.setEnabled(row >= 0)
        if row >= 0:
            _, img = self._images[row]
            self._w_changing = True
            self._h_changing = True
            self._spin_w.setValue(img.width)
            self._spin_h.setValue(img.height)
            self._w_changing = False
            self._h_changing = False
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _current_mode(self) -> str:
        if self._rb_factor.isChecked():
            return "factor"
        if self._rb_percent.isChecked():
            return "percent"
        if self._rb_ai.isChecked():
            return "ai"
        return "dims"

    def _current_kwargs(self) -> dict:
        return dict(
            factor=self._spin_factor.value(),
            percent=float(self._spin_percent.value()),
            target_w=self._spin_w.value(),
            target_h=self._spin_h.value(),
            resample=self._combo_resample.currentData(),
        )

    def _refresh_preview(self):
        if self._selected_idx < 0 or self._selected_idx >= len(self._images):
            self._clear_preview()
            return

        path, img = self._images[self._selected_idx]
        mode = self._current_mode()

        if mode == "ai":
            if not self._ai_available:
                self._clear_preview()
                self._info_label.setText("Install Real-ESRGAN to enable AI upscaling.")
                return
            # AI preview: show original (upscaling is slow, don't run live)
            new_w = img.width * self._ai_scale
            new_h = img.height * self._ai_scale
            px = _pil_to_pixmap(img)
            self._preview_scene.clear()
            self._preview_scene.addPixmap(px)
            self._preview_scene.setSceneRect(0, 0, px.width(), px.height())
            self._preview_view.fitInView(
                self._preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )
            self._info_label.setText(
                f"{path.name}  |  {img.width}×{img.height} → {new_w}×{new_h} px"
                "  (preview shows original — AI runs on export)"
            )
            return

        kw = self._current_kwargs()
        new_w, new_h = output_size(img.width, img.height, mode, **kw)

        try:
            resized = resize_image(img, mode, **kw)
            px = _pil_to_pixmap(resized)
            self._preview_scene.clear()
            self._preview_scene.addPixmap(px)
            self._preview_scene.setSceneRect(0, 0, px.width(), px.height())
            self._preview_view.fitInView(
                self._preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )
        except Exception as e:
            self._clear_preview()
            self._info_label.setText(f"Preview error: {e}")
            return

        self._info_label.setText(
            f"{path.name}  |  {img.width}×{img.height} → {new_w}×{new_h} px"
        )

    def _clear_preview(self):
        self._preview_scene.clear()
        self._info_label.setText("No image loaded")

    # ------------------------------------------------------------------
    # AI log
    # ------------------------------------------------------------------

    def _append_log(self, text: str):
        self._log_widget.append(text)
        self._log_widget.verticalScrollBar().setValue(
            self._log_widget.verticalScrollBar().maximum()
        )

    def _on_ai_finished(self, saved: int, errors: int):
        self._btn_export.setEnabled(True)
        msg = f"AI upscale complete — {saved} saved"
        if errors:
            msg += f", {errors} error(s)"
        self.status_message.emit(msg)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_all(self):
        if not self._images:
            return
        mode = self._current_mode()

        if mode == "ai" and not self._ai_available:
            self.status_message.emit(
                "AI upscaling not available. Run: pip install onnxruntime numpy"
            )
            return

        out_dir = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if not out_dir:
            return
        out_path = Path(out_dir)

        saved = []
        errors = []

        if mode == "ai":
            self._log_widget.clear()
            self._btn_export.setEnabled(False)
            self._worker = AIUpscaleWorker(
                list(self._images), out_path, self._ai_scale,
                model=self._combo_ai_model.currentData(),
                sharpness=self._slider_sharpness.value(),
                detail_blend=self._slider_detail.value(),
            )
            self._worker.log.connect(self._append_log)
            self._worker.finished.connect(self._on_ai_finished)
            self._worker.start()
            return
        else:
            kw = self._current_kwargs()
            for path, img in self._images:
                try:
                    result = save_resized(img, path, out_path, mode, **kw)
                    saved.append(result)
                except Exception as e:
                    errors.append(f"{path.name}: {e}")

        msg = f"Saved {len(saved)} file(s) to {out_dir}"
        if errors:
            msg += f"  |  {len(errors)} error(s): " + "; ".join(errors)
        self.status_message.emit(msg)

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            self._add_file(Path(url.toLocalFile()))
