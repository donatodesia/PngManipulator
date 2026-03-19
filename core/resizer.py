from __future__ import annotations

from pathlib import Path

from PIL import Image


RESAMPLE_MODES = {
    "nearest": Image.Resampling.NEAREST,
    "lanczos": Image.Resampling.LANCZOS,
    "bicubic": Image.Resampling.BICUBIC,
    "bilinear": Image.Resampling.BILINEAR,
}


def _resample(resample: str) -> Image.Resampling:
    return RESAMPLE_MODES.get(resample, Image.Resampling.LANCZOS)


def resize_by_factor(img: Image.Image, factor: float,
                     resample: str = "lanczos") -> Image.Image:
    new_w = max(1, round(img.width * factor))
    new_h = max(1, round(img.height * factor))
    return img.resize((new_w, new_h), _resample(resample))


def resize_by_percent(img: Image.Image, percent: float,
                      resample: str = "lanczos") -> Image.Image:
    return resize_by_factor(img, percent / 100.0, resample)


def resize_by_dims(img: Image.Image, w: int, h: int,
                   resample: str = "lanczos") -> Image.Image:
    return img.resize((max(1, w), max(1, h)), _resample(resample))


def output_size(orig_w: int, orig_h: int, mode: str, factor: float = 2.0,
                percent: float = 100.0, target_w: int = 0, target_h: int = 0,
                **_) -> tuple[int, int]:
    """Return (new_w, new_h) without actually resizing."""
    if mode == "factor":
        return max(1, round(orig_w * factor)), max(1, round(orig_h * factor))
    if mode == "percent":
        f = percent / 100.0
        return max(1, round(orig_w * f)), max(1, round(orig_h * f))
    return max(1, target_w or orig_w), max(1, target_h or orig_h)


def resize_image(img: Image.Image, mode: str, factor: float = 2.0,
                 percent: float = 100.0, target_w: int = 0, target_h: int = 0,
                 resample: str = "lanczos") -> Image.Image:
    if mode == "factor":
        return resize_by_factor(img, factor, resample)
    if mode == "percent":
        return resize_by_percent(img, percent, resample)
    return resize_by_dims(img, target_w or img.width, target_h or img.height, resample)


def save_resized(img: Image.Image, source_path: Path, out_dir: Path,
                 mode: str, **kwargs) -> Path:
    resized = resize_image(img, mode, **kwargs)
    suffix = _suffix(mode, **kwargs)
    out_name = source_path.stem + suffix + ".png"
    out_path = out_dir / out_name
    resized.save(out_path, format="PNG")
    return out_path


def _suffix(mode: str, factor: float = 2.0, percent: float = 100.0,
            target_w: int = 0, target_h: int = 0, **_) -> str:
    if mode == "factor":
        f = factor
        if f == int(f):
            return f"_{int(f)}x"
        return f"_{f:.2g}x"
    if mode == "percent":
        return f"_{int(percent)}pct"
    return f"_{target_w}x{target_h}"
