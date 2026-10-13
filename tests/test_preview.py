"""End-to-end tests for preview pipeline across various microscopy configurations."""

from unittest.mock import patch

from PIL import Image

from nd2_preview.contrast import normalize_and_composite
from nd2_preview.core import read_preview_frame


def test_preview_pipeline_multichannel_zstack(mock_nd2_generator, tmp_path):
    """Test full preview pipeline on a multi-channel Z-stack with MIP."""
    mock_file = tmp_path / "zstack.nd2"
    mock_file.touch()

    # 3-channel, 10 Z-slices, 128x128
    mock_nd2 = mock_nd2_generator(
        sizes={"Z": 10, "C": 3, "Y": 128, "X": 128},
        channel_names=["DAPI", "GFP", "Cy5"],
    )

    with patch("nd2.ND2File", return_value=mock_nd2):
        # 1. Read MIP
        frame = read_preview_frame(mock_file, mip=True)
        assert frame.is_mip
        assert frame.shape == (3, 128, 128)

        # 2. Composite
        img = normalize_and_composite(frame.data)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.size == (128, 128)


def test_preview_pipeline_twocolor_green_magenta(mock_nd2_generator, tmp_path):
    """Test two-color green/magenta overlay."""
    mock_file = tmp_path / "twocolor.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator(
        sizes={"C": 2, "Y": 64, "X": 64},
        channel_names=["GFP", "mCherry"],
    )

    with patch("nd2.ND2File", return_value=mock_nd2):
        frame = read_preview_frame(mock_file)
        assert frame.shape == (2, 64, 64)

        img = normalize_and_composite(frame.data, palette="green-magenta")
        assert img.mode == "RGB"
        assert img.size == (64, 64)


def test_preview_pipeline_single_channel_grayscale(mock_nd2_generator, tmp_path):
    """Test single-channel grayscale preview."""
    mock_file = tmp_path / "single.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator(sizes={"Y": 100, "X": 100})

    with patch("nd2.ND2File", return_value=mock_nd2):
        frame = read_preview_frame(mock_file)
        assert frame.shape == (100, 100)

        img = normalize_and_composite(frame.data)
        assert img.mode == "RGB"
        assert img.size == (100, 100)
