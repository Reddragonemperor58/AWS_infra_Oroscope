"""Optical (red vs blue light) comparison: SSIM on equalized grayscale images.

Same algorithm as the original analysis.py calculate_ssim(), re-implemented with
numpy + Pillow so the Lambda zip stays small (OpenCV + scikit-image = 441 MB, over
Lambda's 250 MB limit). See docs/adr/0012. Verified equal to the original:
  - SSIM maths: identical to skimage (max diff ~5e-16).
  - same-size image pairs: identical end-to-end score.
  - different-size pairs: resize interpolation differs from OpenCV by up to ~0.004.
"""
import io

import numpy as np
from PIL import Image, ImageOps

MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # decompression-bomb guard (raises above 2x this)


class OpticalImageError(ValueError):
    """Raised when an uploaded image cannot be decoded."""


def _decode(img_bytes: bytes) -> Image.Image:
    try:
        im = Image.open(io.BytesIO(img_bytes))
        im.load()
    except Exception as exc:
        raise OpticalImageError("Could not decode image") from exc
    if im.width * im.height > MAX_PIXELS:
        raise OpticalImageError("Image too large")
    # OpenCV's imdecode applies EXIF orientation; Pillow does not, so do it here.
    return ImageOps.exif_transpose(im).convert("RGB")


def _gray_u8(im: Image.Image) -> np.ndarray:
    """OpenCV's COLOR_BGR2GRAY fixed-point formula (14-bit), not Pillow's 'L'."""
    a = np.asarray(im, dtype=np.uint32)
    return ((a[..., 0] * 4899 + a[..., 1] * 9617 + a[..., 2] * 1868 + 8192) >> 14).astype(np.uint8)


def _equalize_hist(g: np.ndarray) -> np.ndarray:
    """Same as cv2.equalizeHist for uint8."""
    hist = np.bincount(g.ravel(), minlength=256)
    cdf = hist.cumsum()
    nz = np.nonzero(hist)[0][0]
    cdf_min, total = cdf[nz], cdf[-1]
    if total == cdf_min:
        return g.copy()
    lut = np.round((cdf - cdf_min) * 255.0 / (total - cdf_min)).clip(0, 255).astype(np.uint8)
    return lut[g]


def _box(a: np.ndarray, w: int) -> np.ndarray:
    """Mean over a w x w window with reflect padding (uniform filter)."""
    p = w // 2
    padded = np.pad(a, p, mode="reflect")
    c = padded.cumsum(axis=0).cumsum(axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    h, wd = a.shape
    s = c[w:w + h, w:w + wd] - c[0:h, w:w + wd] - c[w:w + h, 0:wd] + c[0:h, 0:wd]
    return s / (w * w)


def ssim_gray(g1: np.ndarray, g2: np.ndarray) -> float:
    """skimage.metrics.structural_similarity defaults for 2-D uint8 (7x7 uniform window,
    K1=0.01, K2=0.03, sample covariance, data_range=255, 3-px border cropped)."""
    x, y = g1.astype(np.float64), g2.astype(np.float64)
    w = 7
    cov_norm = (w * w) / (w * w - 1)
    ux, uy = _box(x, w), _box(y, w)
    vx = cov_norm * (_box(x * x, w) - ux * ux)
    vy = cov_norm * (_box(y * y, w) - uy * uy)
    vxy = cov_norm * (_box(x * y, w) - ux * uy)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    s = ((2 * ux * uy + c1) * (2 * vxy + c2)) / ((ux ** 2 + uy ** 2 + c1) * (vx + vy + c2))
    p = (w - 1) // 2
    return float(s[p:-p, p:-p].mean())


def calculate_ssim(img1_bytes: bytes, img2_bytes: bytes) -> dict:
    im1, im2 = _decode(img1_bytes), _decode(img2_bytes)
    resized = im2.size != im1.size
    if resized:
        im2 = im2.resize(im1.size, Image.BILINEAR)  # original: cv2.resize(img2, (w, h))
    g1 = _equalize_hist(_gray_u8(im1))
    g2 = _equalize_hist(_gray_u8(im2))
    return {"ssim_score": ssim_gray(g1, g2), "resized": resized}