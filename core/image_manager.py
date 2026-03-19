from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image
from PyQt6.QtGui import QImage, QPixmap


@dataclass
class SpriteEntry:
    name: str
    image: Image.Image   # RGBA PIL image (cropped sprite)
    source_file: str = ""


class ImageManager:
    """
    Ordered list of sprites to be packed.
    Every mutation saves an undo snapshot; redo stack is cleared on new edits.
    """

    MAX_HISTORY = 50

    def __init__(self) -> None:
        self._sprites: list[SpriteEntry] = []
        self._undo_stack: list[list[SpriteEntry]] = []
        self._redo_stack: list[list[SpriteEntry]] = []

    # ------------------------------------------------------------------
    # Read-only access
    # ------------------------------------------------------------------

    @property
    def sprites(self) -> list[SpriteEntry]:
        return self._sprites

    def __len__(self) -> int:
        return len(self._sprites)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_sprites(self, entries: list[SpriteEntry]) -> None:
        self._snapshot()
        self._sprites.extend(entries)

    def remove(self, index: int) -> None:
        if 0 <= index < len(self._sprites):
            self._snapshot()
            self._sprites.pop(index)

    def move(self, index: int, direction: int) -> None:
        """direction: -1 = up, +1 = down."""
        target = index + direction
        if 0 <= index < len(self._sprites) and 0 <= target < len(self._sprites):
            self._snapshot()
            self._sprites[index], self._sprites[target] = (
                self._sprites[target],
                self._sprites[index],
            )

    def reorder(self, from_index: int, to_index: int) -> None:
        n = len(self._sprites)
        if from_index == to_index or not (0 <= from_index < n) or not (0 <= to_index < n):
            return
        self._snapshot()
        item = self._sprites.pop(from_index)
        self._sprites.insert(to_index, item)

    def clear(self) -> None:
        if self._sprites:
            self._snapshot()
            self._sprites.clear()

    def replace_all(self, entries: list[SpriteEntry]) -> None:
        """Replace the full list (used after drag-drop reorder)."""
        self._snapshot()
        self._sprites = list(entries)

    def trim_sprites(self, indices: list[int]) -> bool:
        """
        Trim the sprites at the given indices uniformly:
        compute the largest safe crop across those sprites, apply to all of them.
        Returns True if any trimming was performed.
        """
        from core.trimmer import compute_safe_margins, apply_trim
        valid = sorted({i for i in indices if 0 <= i < len(self._sprites)})
        if not valid:
            return False
        targets = [self._sprites[i] for i in valid]
        margins = compute_safe_margins(targets)
        if margins == (0, 0, 0, 0):
            return False
        trimmed = apply_trim(targets, margins)
        self._snapshot()
        for idx, entry in zip(valid, trimmed):
            self._sprites[idx] = entry
        return True

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(_copy_list(self._sprites))
        self._sprites = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(_copy_list(self._sprites))
        self._sprites = self._redo_stack.pop()
        return True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _snapshot(self) -> None:
        self._redo_stack.clear()
        self._undo_stack.append(_copy_list(self._sprites))
        if len(self._undo_stack) > self.MAX_HISTORY:
            self._undo_stack.pop(0)

    # ------------------------------------------------------------------
    # Static utility
    # ------------------------------------------------------------------

    @staticmethod
    def to_qpixmap(img: Image.Image) -> QPixmap:
        buf = BytesIO()
        img.convert("RGBA").save(buf, format="PNG")
        buf.seek(0)
        qimg = QImage()
        qimg.loadFromData(buf.read())
        return QPixmap.fromImage(qimg)


def _copy_list(sprites: list[SpriteEntry]) -> list[SpriteEntry]:
    """Shallow-copy list with new SpriteEntry wrappers (PIL images are shared)."""
    return [SpriteEntry(name=s.name, image=s.image, source_file=s.source_file)
            for s in sprites]
