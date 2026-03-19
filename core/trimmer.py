from __future__ import annotations

from typing import Optional

import numpy as np
from PIL import Image

from .image_manager import SpriteEntry


def get_content_bbox(img: Image.Image) -> Optional[tuple[int, int, int, int]]:
    """
    Return (left, top, right, bottom) pixel bounds of non-transparent content.
    Returns None if the image is fully transparent.
    """
    arr = np.array(img.convert("RGBA"))
    mask = arr[:, :, 3] > 0
    if not mask.any():
        return None
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    top    = int(np.argmax(rows))
    bottom = img.height - int(np.argmax(rows[::-1]))
    left   = int(np.argmax(cols))
    right  = img.width - int(np.argmax(cols[::-1]))
    return (left, top, right, bottom)


def compute_safe_margins(sprites: list[SpriteEntry]) -> tuple[int, int, int, int]:
    """
    Find the largest uniform crop that keeps ALL sprites' content intact.

    Returns (left, top, right, bottom) — pixels to crop from each side.
    Safe = minimum transparent border on each side across all sprites.
    """
    if not sprites:
        return (0, 0, 0, 0)

    margins: list[tuple[int, int, int, int]] = []
    for entry in sprites:
        bbox = get_content_bbox(entry.image)
        if bbox is None:
            margins.append((0, 0, 0, 0))
        else:
            l, t, r, b = bbox
            w, h = entry.image.size
            margins.append((l, t, w - r, h - b))

    safe_left   = min(m[0] for m in margins)
    safe_top    = min(m[1] for m in margins)
    safe_right  = min(m[2] for m in margins)
    safe_bottom = min(m[3] for m in margins)
    return (safe_left, safe_top, safe_right, safe_bottom)


def apply_trim(
    sprites: list[SpriteEntry],
    margins: tuple[int, int, int, int],
) -> list[SpriteEntry]:
    """
    Crop each sprite by the given margins.
    All output images have the same dimensions (original - margins).
    """
    left, top, right, bottom = margins
    result: list[SpriteEntry] = []
    for entry in sprites:
        w, h = entry.image.size
        x0, y0 = left, top
        x1, y1 = w - right, h - bottom
        if x1 > x0 and y1 > y0:
            new_img = entry.image.crop((x0, y0, x1, y1))
        else:
            new_img = entry.image.copy()
        result.append(
            SpriteEntry(name=entry.name, image=new_img, source_file=entry.source_file)
        )
    return result
