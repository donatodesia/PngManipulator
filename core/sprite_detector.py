from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image


@dataclass
class DetectedSprite:
    image: Image.Image
    source_rect: tuple[int, int, int, int]  # x, y, w, h in source sheet


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------

def auto_bg_color(img: Image.Image) -> tuple[int, int, int]:
    """Guess background color by sampling the four corners (most common)."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    corners = [
        rgba.getpixel((0, 0))[:3],
        rgba.getpixel((w - 1, 0))[:3],
        rgba.getpixel((0, h - 1))[:3],
        rgba.getpixel((w - 1, h - 1))[:3],
    ]
    from collections import Counter
    return Counter(corners).most_common(1)[0][0]


def _make_mask(arr: np.ndarray, bg_mode: str, bg_color: Optional[tuple]) -> np.ndarray:
    """Return boolean mask: True = pixel has content."""
    if bg_mode == "solid" and bg_color is not None:
        r, g, b = bg_color[:3]
        return ~(
            (arr[:, :, 0] == r) &
            (arr[:, :, 1] == g) &
            (arr[:, :, 2] == b)
        )
    else:
        return arr[:, :, 3] > 0


def _replace_bg_with_alpha(cell: Image.Image, bg_color: tuple) -> Image.Image:
    arr = np.array(cell.convert("RGBA"))
    r, g, b = bg_color[:3]
    bg_mask = (arr[:, :, 0] == r) & (arr[:, :, 1] == g) & (arr[:, :, 2] == b)
    arr[bg_mask, 3] = 0
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------------------
# Regular grid detection
# ---------------------------------------------------------------------------

def detect_regular(
    img: Image.Image,
    rows: int,
    cols: int,
    bg_mode: str = "transparent",
    bg_color: Optional[tuple] = None,
    strip_empty: bool = True,
) -> list[DetectedSprite]:
    """Slice sheet into rows×cols cells; skip empty cells if strip_empty."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    cell_w = w // cols
    cell_h = h // rows

    if bg_mode == "solid" and bg_color is None:
        bg_color = auto_bg_color(rgba)

    sprites: list[DetectedSprite] = []
    arr = np.array(rgba)

    for row in range(rows):
        for col in range(cols):
            x = col * cell_w
            y = row * cell_h
            cell_arr = arr[y:y + cell_h, x:x + cell_w]
            mask = _make_mask(cell_arr, bg_mode, bg_color)
            if strip_empty and not mask.any():
                continue
            cell = rgba.crop((x, y, x + cell_w, y + cell_h))
            if bg_mode == "solid" and bg_color is not None:
                cell = _replace_bg_with_alpha(cell, bg_color)
            sprites.append(DetectedSprite(image=cell, source_rect=(x, y, cell_w, cell_h)))

    return sprites


# ---------------------------------------------------------------------------
# Irregular (auto-detect) detection — projection-based, no extra deps
# ---------------------------------------------------------------------------

def _find_bands(has_content: np.ndarray) -> list[tuple[int, int]]:
    """Return list of (start, end) index ranges where has_content is True."""
    bands: list[tuple[int, int]] = []
    in_band = False
    start = 0
    for i, v in enumerate(has_content.tolist()):
        if v and not in_band:
            in_band = True
            start = i
        elif not v and in_band:
            in_band = False
            bands.append((start, i))
    if in_band:
        bands.append((start, len(has_content)))
    return bands


def detect_irregular(
    img: Image.Image,
    bg_mode: str = "transparent",
    bg_color: Optional[tuple] = None,
    min_pixels: int = 4,
) -> list[DetectedSprite]:
    """
    Auto-detect sprites by finding bounding boxes of non-empty regions.

    Strategy: project onto rows to find horizontal bands, then within each
    band project onto columns to find individual sprites. This covers the
    vast majority of real-world spritesheets (rows of sprites with gaps).
    """
    rgba = img.convert("RGBA")
    if bg_mode == "solid" and bg_color is None:
        bg_color = auto_bg_color(rgba)

    arr = np.array(rgba)
    mask = _make_mask(arr, bg_mode, bg_color)  # shape (H, W)

    row_has_content = mask.any(axis=1)
    row_bands = _find_bands(row_has_content)

    sprites: list[DetectedSprite] = []

    for r_start, r_end in row_bands:
        row_mask = mask[r_start:r_end, :]
        col_has_content = row_mask.any(axis=0)
        col_bands = _find_bands(col_has_content)

        for c_start, c_end in col_bands:
            region = mask[r_start:r_end, c_start:c_end]
            rows_with = np.where(region.any(axis=1))[0]
            cols_with = np.where(region.any(axis=0))[0]

            if len(rows_with) < min_pixels or len(cols_with) < min_pixels:
                continue

            y0 = r_start + int(rows_with[0])
            y1 = r_start + int(rows_with[-1]) + 1
            x0 = c_start + int(cols_with[0])
            x1 = c_start + int(cols_with[-1]) + 1

            crop = rgba.crop((x0, y0, x1, y1))
            if bg_mode == "solid" and bg_color is not None:
                crop = _replace_bg_with_alpha(crop, bg_color)

            sprites.append(DetectedSprite(image=crop, source_rect=(x0, y0, x1 - x0, y1 - y0)))

    # Sort left-to-right, top-to-bottom
    sprites.sort(key=lambda s: (s.source_rect[1], s.source_rect[0]))
    return sprites
