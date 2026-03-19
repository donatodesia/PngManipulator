from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView

from core.image_manager import ImageManager
from PIL import Image


def _make_checker_brush() -> QBrush:
    tile = QPixmap(16, 16)
    tile.fill(QColor(200, 200, 200))
    p = QPainter(tile)
    p.fillRect(0, 0, 8, 8, QColor(155, 155, 155))
    p.fillRect(8, 8, 8, 8, QColor(155, 155, 155))
    p.end()
    return QBrush(tile)


class SpritesheetCanvas(QGraphicsView):
    zoom_changed = pyqtSignal(int)  # zoom %

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.setBackgroundBrush(_make_checker_brush())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        self._cell_w: int = 32
        self._cell_h: int = 32
        self._padding: int = 0
        self._sprite_count: int = 0
        self._zoom_factor: float = 1.0
        self._content_rects: list[tuple[int, int, int, int]] = []  # (x, y, w, h) in sheet coords
        self._pixmap_item = None

        self._grid_pen = QPen(QColor(220, 60, 60, 160))
        self._grid_pen.setCosmetic(True)

        self._content_pen = QPen(QColor(80, 160, 255, 180))
        self._content_pen.setCosmetic(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_sheet(
        self,
        sheet: Optional[Image.Image],
        cell_w: int,
        cell_h: int,
        padding: int = 0,
        sprite_count: int = 0,
        content_rects: Optional[list[tuple[int, int, int, int]]] = None,
    ):
        self._cell_w = cell_w
        self._cell_h = cell_h
        self._padding = padding
        self._sprite_count = sprite_count
        self._content_rects = content_rects or []

        had_content = self._pixmap_item is not None
        old_center = (
            self.mapToScene(self.viewport().rect().center()) if had_content else None
        )
        old_transform = self.transform() if had_content else None

        self._scene.clear()
        self._pixmap_item = None

        if sheet is not None:
            pixmap = ImageManager.to_qpixmap(sheet)
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._scene.setSceneRect(QRectF(0, 0, pixmap.width(), pixmap.height()))

            if old_transform is not None:
                self.setTransform(old_transform)
                self.centerOn(old_center)
            else:
                self.fitInView(
                    self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
                )
                self._zoom_factor = self.transform().m11()
                self.zoom_changed.emit(int(self._zoom_factor * 100))

        self.viewport().update()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def drawForeground(self, painter: QPainter, rect: QRectF):
        if self._pixmap_item is None:
            return
        sr = self._pixmap_item.boundingRect()
        w, h = int(sr.width()), int(sr.height())

        # Red grid — cell boundaries
        painter.setPen(self._grid_pen)
        p = self._padding
        cw = self._cell_w
        ch = self._cell_h
        if p == 0:
            for x in range(0, w + 1, cw):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h + 1, ch):
                painter.drawLine(0, y, w, y)
        else:
            x = p
            while x <= w:
                painter.drawLine(x, 0, x, h)
                painter.drawLine(x + cw, 0, x + cw, h)
                x += cw + p
            y = p
            while y <= h:
                painter.drawLine(0, y, w, y)
                painter.drawLine(0, y + ch, w, y + ch)
                y += ch + p

        # Blue outlines — trimmed content bounds per sprite
        if self._content_rects:
            painter.setPen(self._content_pen)
            for (cx, cy, cw2, ch2) in self._content_rects:
                if cw2 > 0 and ch2 > 0:
                    painter.drawRect(cx, cy, cw2 - 1, ch2 - 1)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._pixmap_item is not None:
            p = QPainter(self.viewport())
            self._draw_info_overlay(p)
            p.end()

    def _draw_info_overlay(self, painter: QPainter):
        lines = [
            f"Cell: {self._cell_w} \u00d7 {self._cell_h} px",
            f"Sprites: {self._sprite_count}",
            f"Zoom: {int(self._zoom_factor * 100)}%",
        ]
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = painter.fontMetrics()
        line_h = fm.height()
        pad = 7
        max_w = max(fm.horizontalAdvance(l) for l in lines)
        box_w = max_w + pad * 2
        box_h = line_h * len(lines) + pad * 2
        x = self.viewport().width() - box_w - 10
        y = 10
        painter.fillRect(x, y, box_w, box_h, QColor(0, 0, 0, 170))
        painter.setPen(QColor(255, 255, 255, 230))
        for i, line in enumerate(lines):
            painter.drawText(x + pad, y + pad + (i + 1) * line_h - 2, line)

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1.0 / 1.2
        self.scale(factor, factor)
        self._zoom_factor = self.transform().m11()
        self.zoom_changed.emit(int(self._zoom_factor * 100))
        event.accept()
