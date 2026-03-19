"""
AI upscaling via Real-ESRGAN ONNX models.

Requires:  pip install onnxruntime numpy scipy
Models are downloaded automatically on first use.
"""
from __future__ import annotations

import urllib.request
import urllib.error
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

_WEIGHTS_DIR = Path(__file__).parent.parent / "weights"

_ESRGAN_MODELS: dict[str, dict] = {
    "photo": {
        "filename": "Real-ESRGAN-x4plus.onnx",
        "url": (
            "https://huggingface.co/qualcomm/Real-ESRGAN-x4plus/resolve/"
            "01179a4da7bf5ac91faca650e6afbf282ac93933/"
            "Real-ESRGAN-x4plus.onnx?download=true"
        ),
        "tile_size": 128,
        "bgr": False,
        "scale": 4,
    },
    "anime": {
        "filename": "RealESRGAN-anime-4B32F.onnx",
        "url": (
            "https://huggingface.co/xiongjie/lightweight-real-ESRGAN-anime/"
            "resolve/main/RealESRGAN_x4plus_anime_4B32F.onnx?download=true"
        ),
        "tile_size": None,
        "bgr": True,
        "scale": 4,
    },
    "swinir": {
        "filename": "003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.onnx",
        "url": (
            "https://huggingface.co/rocca/swin-ir-onnx/resolve/main/"
            "003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.onnx"
        ),
        "tile_size": 64,
        "bgr": False,
        "scale": 4,
    },
}

_DEFAULT_TILE = 256
_OVERLAP = 32   # px overlap on each side for feather blending


def is_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def model_names() -> list[str]:
    return list(_ESRGAN_MODELS.keys())


def _ensure_model(model: str) -> Path:
    info = _ESRGAN_MODELS[model]
    path = _WEIGHTS_DIR / info["filename"]
    if path.exists():
        return path
    _WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    url = info["url"]
    print(f"[ai_upscaler] Downloading {model} model from {url} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(path, "wb") as f:
            f.write(response.read())
        print(f"[ai_upscaler] Saved to {path}")
    except Exception as exc:
        if path.exists():
            path.unlink()
        raise RuntimeError(
            f"Failed to download {model} model.\nURL: {url}\nError: {exc}\n\n"
            f"Place an ONNX Real-ESRGAN model manually at:\n  {path}"
        ) from exc
    return path


# ---------------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------------

def _gamma_to_linear(img: np.ndarray) -> np.ndarray:
    """sRGB → linear light (remove gamma ~2.2)."""
    f = img.astype(np.float32) / 255.0
    return np.where(f <= 0.04045, f / 12.92, ((f + 0.055) / 1.055) ** 2.4)


def _linear_to_gamma(img: np.ndarray) -> np.ndarray:
    """Linear light → sRGB (apply gamma ~2.2)."""
    f = np.clip(img, 0.0, 1.0)
    out = np.where(f <= 0.0031308, f * 12.92, 1.055 * (f ** (1.0 / 2.4)) - 0.055)
    return (np.clip(out, 0.0, 1.0) * 255.0).round().astype(np.uint8)


def _denoise(img: np.ndarray) -> np.ndarray:
    """Light bilateral-style denoising via scipy. Falls back to PIL median if unavailable."""
    try:
        from scipy.ndimage import uniform_filter, median_filter
        # Gentle median filter — removes impulse noise while preserving edges
        return median_filter(img, size=(2, 2, 1)).astype(np.uint8)
    except ImportError:
        pil = Image.fromarray(img)
        return np.array(pil.filter(ImageFilter.MedianFilter(3)))


# ---------------------------------------------------------------------------
# Tiled inference with overlap + Gaussian feathering
# ---------------------------------------------------------------------------

def _make_weight_map(h: int, w: int) -> np.ndarray:
    """Gaussian-shaped 2-D weight map (H, W) that tapers to ~0 at edges."""
    wy = np.hanning(h).astype(np.float32)
    wx = np.hanning(w).astype(np.float32)
    return np.outer(wy, wx)


def _run_tile(session, input_name: str, tile: np.ndarray,
              tile_size: int, bgr: bool) -> np.ndarray:
    """Run one padded tile through the session. Returns float32 [0,1] H'xW'x3."""
    h, w = tile.shape[:2]
    padded = np.zeros((tile_size, tile_size, 3), dtype=np.float32)
    # tile is already float32 [0,1] after gamma removal
    padded[:h, :w] = tile

    x = padded.copy()
    if bgr:
        x = x[:, :, ::-1]
    x = np.transpose(x, (2, 0, 1))[np.newaxis, ...]

    out = session.run(None, {input_name: x})[0]
    out = np.clip(out[0], 0.0, 1.0)
    out = np.transpose(out, (1, 2, 0))
    if bgr:
        out = out[:, :, ::-1]

    scale = out.shape[0] // tile_size
    return out[:h * scale, :w * scale]


def _upscale_rgb(session, img_rgb: np.ndarray, info: dict,
                 on_tile: callable | None = None) -> np.ndarray:
    """
    Tile-based upscale with overlap and Gaussian feather blending.
    Eliminates seam artifacts at tile boundaries.
    img_rgb: uint8 HxWx3
    """
    tile_size = info["tile_size"] or _DEFAULT_TILE
    scale     = info["scale"]
    bgr       = info["bgr"]
    overlap   = min(_OVERLAP, tile_size // 4)
    step      = tile_size - 2 * overlap
    input_name = session.get_inputs()[0].name

    # Convert to linear float for processing
    linear = _gamma_to_linear(img_rgb)          # float32 [0,1]

    h, w = linear.shape[:2]
    out_h, out_w = h * scale, w * scale

    accum   = np.zeros((out_h, out_w, 3), dtype=np.float64)
    weights = np.zeros((out_h, out_w),    dtype=np.float64)

    ys = list(range(0, h - overlap, step)) if h > tile_size else [0]
    xs = list(range(0, w - overlap, step)) if w > tile_size else [0]
    # Ensure last tile covers the bottom/right edge
    if ys[-1] + tile_size < h:
        ys.append(max(0, h - tile_size))
    if xs[-1] + tile_size < w:
        xs.append(max(0, w - tile_size))

    total = len(ys) * len(xs)
    done  = 0

    for y in ys:
        y1 = min(y + tile_size, h)
        th = y1 - y
        for x in xs:
            x1 = min(x + tile_size, w)
            tw = x1 - x

            tile    = linear[y:y1, x:x1]
            up_tile = _run_tile(session, input_name, tile, tile_size, bgr)

            wmap = _make_weight_map(th * scale, tw * scale)

            oy, ox = y * scale, x * scale
            accum  [oy:oy + th * scale, ox:ox + tw * scale] += up_tile * wmap[:, :, np.newaxis]
            weights[oy:oy + th * scale, ox:ox + tw * scale] += wmap

            done += 1
            if on_tile:
                on_tile(done, total)

    weights = np.maximum(weights, 1e-8)
    result_linear = (accum / weights[:, :, np.newaxis]).astype(np.float32)
    return _linear_to_gamma(result_linear)


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def _histogram_match(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """
    Match the per-channel histogram of *source* to *reference*.
    Ensures output brightness/contrast is tonally identical to the original.
    """
    out = np.empty_like(source)
    for c in range(source.shape[2]):
        src_ch = source[:, :, c].ravel()
        ref_ch = reference[:, :, c].ravel()
        src_cdf = np.cumsum(np.bincount(src_ch, minlength=256)).astype(np.float32)
        ref_cdf = np.cumsum(np.bincount(ref_ch, minlength=256)).astype(np.float32)
        src_cdf /= src_cdf[-1]
        ref_cdf /= ref_cdf[-1]
        lut = np.interp(src_cdf, ref_cdf, np.arange(256)).astype(np.uint8)
        out[:, :, c] = lut[source[:, :, c]]
    return out


def _apply_sharpness(img: Image.Image, amount: int) -> Image.Image:
    """
    Guided-filter-style sharpening: extracts high-freq from a Gaussian blur
    and adds it back scaled by amount, preventing halos and noise amplification.
    """
    if amount <= 0:
        return img
    arr  = np.array(img.convert("RGB"), dtype=np.float32)
    blur = np.array(
        Image.fromarray(arr.clip(0, 255).astype(np.uint8))
             .filter(ImageFilter.GaussianBlur(1.5)),
        dtype=np.float32,
    )
    strength = amount / 100.0 * 0.8   # max 80% high-freq boost
    sharpened = arr + (arr - blur) * strength
    result = np.clip(sharpened, 0, 255).astype(np.uint8)
    out = Image.fromarray(result, mode="RGB")
    if img.mode == "RGBA":
        out = out.convert("RGBA")
        out.putalpha(img.getchannel("A"))
    return out


def _apply_detail_blend(ai: Image.Image, original: Image.Image,
                        scale: int, amount: int) -> Image.Image:
    """
    Laplacian frequency-split + edge-aware Sobel mask + histogram match.

    Low freq  → 100% Lanczos (colour/lighting faithful to original)
    High freq → AI × edge_mask × alpha + Lanczos × (1 − above)
    Final     → histogram-matched to Lanczos reference
    """
    if amount <= 0:
        return ai

    alpha       = amount / 100.0
    target_size = ai.size
    lanczos     = original.resize(target_size, Image.Resampling.LANCZOS)

    ai_arr      = np.array(ai.convert("RGB"),      dtype=np.float32)
    lanczos_arr = np.array(lanczos.convert("RGB"),  dtype=np.float32)

    # --- Laplacian frequency separation ---
    blur_r      = 3
    ai_low      = np.array(
        Image.fromarray(ai_arr.clip(0, 255).astype(np.uint8))
             .filter(ImageFilter.GaussianBlur(blur_r)), dtype=np.float32)
    lanczos_low = np.array(
        Image.fromarray(lanczos_arr.clip(0, 255).astype(np.uint8))
             .filter(ImageFilter.GaussianBlur(blur_r)), dtype=np.float32)

    ai_high      = ai_arr      - ai_low
    lanczos_high = lanczos_arr - lanczos_low

    # --- Sobel edge mask ---
    gray = (0.299 * lanczos_arr[:, :, 0] +
            0.587 * lanczos_arr[:, :, 1] +
            0.114 * lanczos_arr[:, :, 2])
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = (gray[:, 2:] - gray[:, :-2]) / 2.0
    gy[1:-1, :]  = (gray[2:, :] - gray[:-2, :]) / 2.0
    magnitude    = np.sqrt(gx ** 2 + gy ** 2)
    mask = (magnitude / magnitude.max()) if magnitude.max() > 0 else magnitude
    mask = np.array(
        Image.fromarray((mask * 255).astype(np.uint8))
             .filter(ImageFilter.GaussianBlur(5)), dtype=np.float32) / 255.0
    mask = mask[:, :, np.newaxis]

    # --- Combine frequencies ---
    effective_alpha = alpha * mask
    result_high     = ai_high * effective_alpha + lanczos_high * (1.0 - effective_alpha)
    result          = np.clip(lanczos_low + result_high, 0, 255).astype(np.uint8)

    # --- Histogram match to Lanczos reference ---
    ref = lanczos_arr.clip(0, 255).astype(np.uint8)
    result = _histogram_match(result, ref)

    out = Image.fromarray(result, mode="RGB")
    if ai.mode == "RGBA":
        out = out.convert("RGBA")
        out.putalpha(ai.getchannel("A"))
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upscale(img: Image.Image, model: str = "photo",
            sharpness: int = 0, detail_blend: int = 0,
            on_tile: callable | None = None) -> Image.Image:
    """
    Full pipeline:
      1. Mild denoising (removes source noise/JPEG artifacts)
      2. Gamma linearisation (accurate signal for the model)
      3. Tiled inference with overlap + Gaussian feather blending (no seams)
      4. Gamma re-encoding
      5. Laplacian blend + edge-aware mask + histogram match (detail_blend)
      6. Guided high-freq sharpening (sharpness)
    """
    import onnxruntime as ort

    if model not in _ESRGAN_MODELS:
        raise ValueError(f"Unknown model '{model}'. Choose from: {list(_ESRGAN_MODELS)}")

    info       = _ESRGAN_MODELS[model]
    model_path = _ensure_model(model)

    sess_options = ort.SessionOptions()
    sess_options.log_severity_level = 3
    available = ort.get_available_providers()
    providers = [p for p in ["CUDAExecutionProvider", "CPUExecutionProvider"] if p in available]
    session   = ort.InferenceSession(str(model_path), sess_options=sess_options, providers=providers)

    has_alpha = img.mode == "RGBA"
    original  = img.copy()
    rgb       = np.array(img.convert("RGB"))
    alpha     = np.array(img.convert("RGBA"))[:, :, 3] if has_alpha else None

    # 1. Denoise source
    rgb = _denoise(rgb)

    # 2+3+4 handled inside _upscale_rgb (gamma in/out + feathered tiling)
    upscaled_rgb = _upscale_rgb(session, rgb, info, on_tile=on_tile)
    result = Image.fromarray(upscaled_rgb, mode="RGB")

    # 5. Laplacian blend + edge mask + histogram match
    if detail_blend > 0:
        result = _apply_detail_blend(result, original.convert("RGB"), info["scale"], detail_blend)

    # 6. Guided sharpening
    if sharpness > 0:
        result = _apply_sharpness(result, sharpness)

    if has_alpha and alpha is not None:
        alpha_img = Image.fromarray(alpha).resize(result.size, Image.Resampling.LANCZOS)
        result    = result.convert("RGBA")
        result.putalpha(alpha_img)

    return result
