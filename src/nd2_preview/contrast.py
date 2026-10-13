"""Image normalization and color compositing for raw microscopy data."""

from __future__ import annotations

import numpy as np
from PIL import Image


def stretch_percentile(
    plane: np.ndarray,
    p_low: float = 1.0,
    p_high: float = 99.8,
) -> np.ndarray:
    """Normalize a 2D single-channel image plane to 8-bit [0, 255] using percentile clipping.

    Raw microscopy images (12-bit, 14-bit, 16-bit) frequently have high dynamic
    range and low background intensity. Slicing with naive linear scaling produces
    virtually black images. Percentile stretching clips extreme noise/hot pixels
    while boosting the real fluorescent signal.

    Args:
        plane: 2D array of intensity values.
        p_low: Lower percentile cutoff (default: 1.0).
        p_high: Upper percentile cutoff (default: 99.8).

    Returns:
        np.ndarray of uint8 values in range [0, 255].
    """
    if plane.size == 0:
        return np.zeros_like(plane, dtype=np.uint8)

    # Sanitize any potential NaNs or Infs
    clean = np.nan_to_num(plane, nan=0.0, posinf=0.0, neginf=0.0)

    vmin = float(np.percentile(clean, p_low))
    vmax = float(np.percentile(clean, p_high))

    if vmax <= vmin:
        # Uniform or black image - avoid division by zero
        vmax = vmin + 1.0

    clipped = np.clip(clean, vmin, vmax)
    normalized = (clipped - vmin) / (vmax - vmin)
    res: np.ndarray = (normalized * 255.0).astype(np.uint8)
    return res


def normalize_and_composite(
    data: np.ndarray,
    p_low: float = 1.0,
    p_high: float = 99.8,
    palette: str = "auto",
) -> Image.Image:
    """Convert raw multi-channel / single-channel microscopy arrays to a displayable PIL RGB Image.

    Rules:
    - 1 channel (H, W) or (1, H, W): Grayscale stretched to 8-bit RGB.
    - 2 channels (2, H, W): Green/Magenta overlay (ch0=Green, ch1=Magenta).
    - 3+ channels (C, H, W): RGB mapping using the first 3 channels.
    - Native RGB (H, W, 3): Channel-wise stretch to uint8 RGB.

    Args:
        data: Numpy array with shape (H, W), (C, H, W), or (H, W, 3).
        p_low: Lower percentile cutoff for contrast stretch.
        p_high: Upper percentile cutoff for contrast stretch.
        palette: Color palette preference ('auto', 'green-magenta', 'red-green', 'grayscale').

    Returns:
        PIL.Image in 'RGB' mode.
    """
    arr = np.asarray(data)

    # Handle native RGB images (H, W, 3) or (H, W, 4)
    if arr.ndim == 3 and arr.shape[-1] in (3, 4):
        rgb_channels = [
            stretch_percentile(arr[..., c], p_low=p_low, p_high=p_high)
            for c in range(3)
        ]
        rgb = np.stack(rgb_channels, axis=-1)
        return Image.fromarray(rgb, mode="RGB")

    # If 3D with leading dimension C: (C, H, W)
    if arr.ndim == 3:
        channels_count = arr.shape[0]

        if channels_count == 1:
            ch0 = stretch_percentile(arr[0], p_low=p_low, p_high=p_high)
            rgb = np.stack([ch0, ch0, ch0], axis=-1)
            return Image.fromarray(rgb, mode="RGB")

        if channels_count == 2:
            ch0 = stretch_percentile(arr[0], p_low=p_low, p_high=p_high)
            ch1 = stretch_percentile(arr[1], p_low=p_low, p_high=p_high)

            if palette == "red-green":
                # Channel 0 -> Red, Channel 1 -> Green
                h, w = ch0.shape
                zeros = np.zeros((h, w), dtype=np.uint8)
                rgb = np.stack([ch0, ch1, zeros], axis=-1)
            else:
                # Default: Green/Magenta overlay
                # ch0 -> Green: (0, ch0, 0)
                # ch1 -> Magenta: (ch1, 0, ch1)
                # Result: R = ch1, G = ch0, B = ch1
                rgb = np.stack([ch1, ch0, ch1], axis=-1)
            return Image.fromarray(rgb, mode="RGB")

        # 3 or more channels: map first 3 channels to R, G, B
        ch0 = stretch_percentile(arr[0], p_low=p_low, p_high=p_high)
        ch1 = stretch_percentile(arr[1], p_low=p_low, p_high=p_high)
        ch2 = stretch_percentile(arr[2], p_low=p_low, p_high=p_high)
        rgb = np.stack([ch0, ch1, ch2], axis=-1)
        return Image.fromarray(rgb, mode="RGB")

    # 2D single channel image (H, W)
    if arr.ndim == 2:
        gray = stretch_percentile(arr, p_low=p_low, p_high=p_high)
        rgb = np.stack([gray, gray, gray], axis=-1)
        return Image.fromarray(rgb, mode="RGB")

    raise ValueError(f"Unsupported array shape for image normalization: {arr.shape}")

