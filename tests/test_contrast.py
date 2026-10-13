"""Tests for image contrast stretching and multi-channel color compositing."""

import numpy as np
import pytest
from PIL import Image

from nd2_preview.contrast import normalize_and_composite, stretch_percentile


def test_stretch_percentile_normal_range():
    # 16-bit simulated data
    arr = np.linspace(100, 10000, 1000, dtype=np.uint16).reshape((10, 100))
    stretched = stretch_percentile(arr, p_low=1.0, p_high=99.0)

    assert stretched.dtype == np.uint8
    assert stretched.shape == (10, 100)
    assert stretched.min() == 0
    assert stretched.max() == 255


def test_stretch_percentile_zeros():
    arr = np.zeros((20, 20), dtype=np.uint16)
    stretched = stretch_percentile(arr)
    assert stretched.dtype == np.uint8
    assert np.all(stretched == 0)


def test_stretch_percentile_constant_value():
    arr = np.full((15, 15), 500, dtype=np.uint16)
    stretched = stretch_percentile(arr)
    assert stretched.dtype == np.uint8
    assert np.all(stretched == 0)


def test_stretch_percentile_nan_and_inf():
    arr = np.array([[np.nan, 100.0], [np.inf, 200.0]])
    stretched = stretch_percentile(arr)
    assert stretched.dtype == np.uint8
    assert stretched.shape == (2, 2)


def test_normalize_and_composite_single_channel_2d():
    arr = np.arange(100, dtype=np.uint16).reshape((10, 10))
    img = normalize_and_composite(arr)

    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.size == (10, 10)

    # Grayscale RGB should have identical R, G, B channels
    rgb_arr = np.array(img)
    assert np.array_equal(rgb_arr[..., 0], rgb_arr[..., 1])
    assert np.array_equal(rgb_arr[..., 1], rgb_arr[..., 2])


def test_normalize_and_composite_single_channel_3d():
    arr = np.arange(100, dtype=np.uint16).reshape((1, 10, 10))
    img = normalize_and_composite(arr)
    assert img.mode == "RGB"
    assert img.size == (10, 10)


def test_normalize_and_composite_two_channels_green_magenta():
    # ch0: Green, ch1: Magenta
    ch0 = np.full((10, 10), 1000, dtype=np.uint16)
    ch1 = np.full((10, 10), 5000, dtype=np.uint16)
    # Put variation so contrast stretch maps to full range
    ch0[0, 0] = 0
    ch1[0, 0] = 0
    data = np.stack([ch0, ch1], axis=0)

    img = normalize_and_composite(data, palette="green-magenta")
    rgb_arr = np.array(img)

    assert img.mode == "RGB"
    # Magenta is R and B: rgb[..., 0] == rgb[..., 2]
    assert np.array_equal(rgb_arr[..., 0], rgb_arr[..., 2])


def test_normalize_and_composite_two_channels_red_green():
    ch0 = np.arange(100, dtype=np.uint16).reshape((10, 10))
    ch1 = np.arange(100, dtype=np.uint16).reshape((10, 10))
    data = np.stack([ch0, ch1], axis=0)

    img = normalize_and_composite(data, palette="red-green")
    rgb_arr = np.array(img)

    assert img.mode == "RGB"
    # Blue channel should be zero in red-green palette
    assert np.all(rgb_arr[..., 2] == 0)


def test_normalize_and_composite_three_channels_rgb():
    ch0 = np.arange(100, dtype=np.uint16).reshape((10, 10))
    ch1 = (np.arange(100, dtype=np.uint16) * 2).reshape((10, 10))
    ch2 = (np.arange(100, dtype=np.uint16) * 3).reshape((10, 10))
    data = np.stack([ch0, ch1, ch2], axis=0)

    img = normalize_and_composite(data)
    assert img.mode == "RGB"
    assert img.size == (10, 10)


def test_normalize_and_composite_four_channels():
    data = np.ones((4, 10, 10), dtype=np.uint16)
    img = normalize_and_composite(data)
    assert img.mode == "RGB"
    assert img.size == (10, 10)


def test_normalize_and_composite_native_rgb():
    rgb_data = np.zeros((10, 10, 3), dtype=np.uint8)
    rgb_data[..., 0] = 255  # Red
    img = normalize_and_composite(rgb_data)
    assert img.mode == "RGB"
    assert img.size == (10, 10)


def test_normalize_and_composite_invalid_shape():
    invalid_data = np.zeros((2, 2, 2, 2))
    with pytest.raises(ValueError, match="Unsupported array shape"):
        normalize_and_composite(invalid_data)
