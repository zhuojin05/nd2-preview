"""Tests for core slice extraction and projection logic."""

from unittest.mock import patch

import pytest

from nd2_preview.core import (
    PreviewFrame,
    read_preview_frame,
    resolve_channel_index,
)


def test_resolve_channel_index():
    names = ["DAPI", "GFP", "Cy5"]
    assert resolve_channel_index(None, 3, names) is None
    assert resolve_channel_index(0, 3, names) == 0
    assert resolve_channel_index(2, 3, names) == 2
    assert resolve_channel_index("gfp", 3, names) == 1
    assert resolve_channel_index("CY5", 3, names) == 2
    assert resolve_channel_index("0", 3, names) == 0

    with pytest.raises(ValueError, match="out of range"):
        resolve_channel_index(5, 3, names)

    with pytest.raises(ValueError, match="not found"):
        resolve_channel_index("mCherry", 3, names)


def test_read_preview_frame_default_middle_z(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "test.nd2"
    mock_file.touch()

    # Sizes: T=2, Z=5, C=3, Y=64, X=64
    mock_nd2 = mock_nd2_generator({"T": 2, "Z": 5, "C": 3, "Y": 64, "X": 64})

    with patch("nd2.ND2File", return_value=mock_nd2):
        frame = read_preview_frame(mock_file)

        assert isinstance(frame, PreviewFrame)
        # Default Z should be middle: 5 // 2 = 2
        assert frame.z_index == 2
        assert frame.t_index == 0
        assert not frame.is_mip
        # Shape should be (C, Y, X) = (3, 64, 64)
        assert frame.shape == (3, 64, 64)
        assert frame.voxel_size_um == (0.065, 0.065, 0.200)


def test_read_preview_frame_specific_z(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "test.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator({"Z": 10, "C": 2, "Y": 32, "X": 32})

    with patch("nd2.ND2File", return_value=mock_nd2):
        frame = read_preview_frame(mock_file, z=8)
        assert frame.z_index == 8
        assert not frame.is_mip
        assert frame.shape == (2, 32, 32)


def test_read_preview_frame_mip(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "test.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator({"Z": 5, "C": 2, "Y": 32, "X": 32})

    with patch("nd2.ND2File", return_value=mock_nd2):
        frame = read_preview_frame(mock_file, mip=True)
        assert frame.is_mip is True
        assert frame.z_index is None
        assert frame.shape == (2, 32, 32)


def test_read_preview_frame_select_channel(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "test.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator(
        {"Z": 3, "C": 3, "Y": 32, "X": 32},
        channel_names=["DAPI", "GFP", "TexasRed"],
    )

    with patch("nd2.ND2File", return_value=mock_nd2):
        # Select by name
        frame = read_preview_frame(mock_file, channel="GFP")
        assert frame.selected_channel == "GFP"
        # Selecting single channel squeezes to 2D (Y, X)
        assert frame.shape == (32, 32)

        # Select by index
        frame_idx = read_preview_frame(mock_file, channel=0)
        assert frame_idx.selected_channel == 0
        assert frame_idx.shape == (32, 32)


def test_read_preview_frame_multipoint_and_time(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "test.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator({"P": 4, "T": 10, "Z": 3, "C": 1, "Y": 20, "X": 20})

    with patch("nd2.ND2File", return_value=mock_nd2):
        frame = read_preview_frame(mock_file, t=5, position=2)
        assert frame.t_index == 5
        assert frame.position_index == 2
        assert frame.shape == (20, 20)


def test_read_preview_frame_2d_no_z(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "test.nd2"
    mock_file.touch()

    # 2D single plane without Z
    mock_nd2 = mock_nd2_generator({"Y": 50, "X": 50})

    with patch("nd2.ND2File", return_value=mock_nd2):
        frame = read_preview_frame(mock_file, mip=True)
        # MIP requested on 2D file should safely result in is_mip=False
        assert frame.is_mip is False
        assert frame.shape == (50, 50)


def test_read_preview_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_preview_frame("/non/existent/path/file.nd2")
