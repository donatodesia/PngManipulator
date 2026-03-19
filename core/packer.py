from __future__ import annotations

from PIL import Image

from .image_manager import ImageManager, SpriteEntry

LAYOUT_HORIZONTAL = "horizontal"
LAYOUT_VERTICAL   = "vertical"
LAYOUT_GRID       = "grid"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _group_by_source(sprites: list[SpriteEntry]) -> list[list[SpriteEntry]]:
    """Group sprites by source_file, preserving insertion order."""
    groups: dict[str, list[SpriteEntry]] = {}
    for sprite in sprites:
        key = sprite.source_file or "__default__"
        if key not in groups:
            groups[key] = []
        groups[key].append(sprite)
    return list(groups.values())


def _fit(img: Image.Image, cell_w: int, cell_h: int) -> Image.Image:
    if img.width <= cell_w and img.height <= cell_h:
        return img
    scale = min(cell_w / img.width, cell_h / img.height)
    return img.resize(
        (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
        Image.Resampling.NEAREST,
    )


# ---------------------------------------------------------------------------
# Packer
# ---------------------------------------------------------------------------

class GridPacker:

    # ------------------------------------------------------------------
    # Public: pack
    # ------------------------------------------------------------------

    def pack(
        self,
        manager: ImageManager,
        columns: int,
        cell_w: int,
        cell_h: int,
        padding: int = 0,
        layout: str = LAYOUT_GRID,
    ) -> Image.Image | None:
        sprites = manager.sprites
        if not sprites:
            return None
        positions, sheet_w, sheet_h = self._layout(
            sprites, columns, cell_w, cell_h, padding, layout
        )
        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        for entry, (fx, fy) in zip(sprites, positions):
            img = _fit(entry.image, cell_w, cell_h)
            cx = fx + (cell_w - img.width)  // 2
            cy = fy + (cell_h - img.height) // 2
            sheet.paste(img, (cx, cy), img)
        return sheet

    # ------------------------------------------------------------------
    # Public: metadata (Phaser JSON Hash)
    # ------------------------------------------------------------------

    def metadata(
        self,
        manager: ImageManager,
        columns: int,
        cell_w: int,
        cell_h: int,
        padding: int = 0,
        image_filename: str = "spritesheet.png",
        layout: str = LAYOUT_GRID,
    ) -> dict:
        sprites = manager.sprites
        if not sprites:
            return {"frames": {}, "meta": {}}
        positions, sheet_w, sheet_h = self._layout(
            sprites, columns, cell_w, cell_h, padding, layout
        )
        frames: dict = {}
        for entry, (fx, fy) in zip(sprites, positions):
            frames[entry.name] = {
                "frame":            {"x": fx,  "y": fy,  "w": cell_w, "h": cell_h},
                "rotated":          False,
                "trimmed":          False,
                "spriteSourceSize": {"x": 0,   "y": 0,   "w": cell_w, "h": cell_h},
                "sourceSize":       {"w": cell_w, "h": cell_h},
            }
        return {
            "frames": frames,
            "meta": {
                "app":     "PngManipulator",
                "version": "1.0",
                "image":   image_filename,
                "format":  "RGBA8888",
                "size":    {"w": sheet_w, "h": sheet_h},
                "scale":   "1",
            },
        }

    # ------------------------------------------------------------------
    # Public: sprite positions (used by main_window for canvas overlays)
    # ------------------------------------------------------------------

    def get_positions(
        self,
        manager: ImageManager,
        columns: int,
        cell_w: int,
        cell_h: int,
        padding: int = 0,
        layout: str = LAYOUT_GRID,
    ) -> list[tuple[int, int]]:
        if not manager.sprites:
            return []
        positions, _, _ = self._layout(
            manager.sprites, columns, cell_w, cell_h, padding, layout
        )
        return positions

    # ------------------------------------------------------------------
    # Core layout engine — returns (positions, sheet_w, sheet_h)
    # ------------------------------------------------------------------

    def _layout(
        self,
        sprites: list[SpriteEntry],
        columns: int,
        cell_w: int,
        cell_h: int,
        padding: int,
        layout: str,
    ) -> tuple[list[tuple[int, int]], int, int]:
        if layout == LAYOUT_HORIZONTAL:
            return self._layout_horizontal(sprites, cell_w, cell_h, padding)
        if layout == LAYOUT_VERTICAL:
            return self._layout_vertical(sprites, cell_w, cell_h, padding)
        return self._layout_grid(sprites, columns, cell_w, cell_h, padding)

    def _layout_grid(self, sprites, columns, cell_w, cell_h, padding):
        count = len(sprites)
        cols  = min(columns, count)
        rows  = (count + cols - 1) // cols
        sheet_w = cols * cell_w + (cols + 1) * padding
        sheet_h = rows * cell_h + (rows + 1) * padding
        positions = [
            (padding + (i % cols) * (cell_w + padding),
             padding + (i // cols) * (cell_h + padding))
            for i in range(count)
        ]
        return positions, sheet_w, sheet_h

    def _layout_horizontal(self, sprites, cell_w, cell_h, padding):
        """One row per source sheet, padded to the widest row."""
        groups   = _group_by_source(sprites)
        max_cols = max(len(g) for g in groups)
        num_rows = len(groups)
        sheet_w  = max_cols * cell_w + (max_cols + 1) * padding
        sheet_h  = num_rows * cell_h + (num_rows + 1) * padding
        positions: list[tuple[int, int]] = []
        for row, group in enumerate(groups):
            for col, _ in enumerate(group):
                positions.append((
                    padding + col * (cell_w + padding),
                    padding + row * (cell_h + padding),
                ))
        return positions, sheet_w, sheet_h

    def _layout_vertical(self, sprites, cell_w, cell_h, padding):
        """One column per source sheet, padded to the tallest column."""
        groups   = _group_by_source(sprites)
        max_rows = max(len(g) for g in groups)
        num_cols = len(groups)
        sheet_w  = num_cols * cell_w + (num_cols + 1) * padding
        sheet_h  = max_rows * cell_h + (max_rows + 1) * padding
        positions: list[tuple[int, int]] = []
        for col_idx, group in enumerate(groups):
            for row_idx, _ in enumerate(group):
                positions.append((
                    padding + col_idx * (cell_w + padding),
                    padding + row_idx * (cell_h + padding),
                ))
        return positions, sheet_w, sheet_h
