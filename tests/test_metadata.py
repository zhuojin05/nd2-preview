"""Tests for metadata inspection and summary generation."""

from unittest.mock import patch

import pytest
from rich.console import Console

from nd2_preview.metadata import (
    ND2Summary,
    format_file_size,
    inspect_metadata,
    print_metadata,
)


def test_format_file_size():
    assert format_file_size(500) == "500.0 B"
    assert format_file_size(2048) == "2.0 KB"
    assert format_file_size(5 * 1024 * 1024) == "5.0 MB"
    assert format_file_size(10 * 1024 * 1024 * 1024) == "10.0 GB"


def test_inspect_metadata(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "sample.nd2"
    mock_file.write_bytes(b"0" * 4096)

    mock_nd2 = mock_nd2_generator(
        sizes={"T": 2, "Z": 10, "C": 3, "Y": 512, "X": 512},
        channel_names=["DAPI", "FITC", "Cy5"],
    )

    with patch("nd2.ND2File", return_value=mock_nd2):
        summary = inspect_metadata(mock_file)

        assert isinstance(summary, ND2Summary)
        assert summary.file_size_bytes == 4096
        assert summary.dimensions == {"T": 2, "Z": 10, "C": 3, "Y": 512, "X": 512}
        assert summary.dim_order == "TZCYX"
        assert summary.voxel_size_um == {"x": 0.065, "y": 0.065, "z": 0.2}
        assert summary.objective_name == "Plan Apo 60x/1.40 Oil"
        assert summary.objective_magnification == 60.0
        assert summary.numerical_aperture == 1.40
        assert summary.bits_in_memory == 16
        assert summary.bits_significant == 14
        assert len(summary.channels) == 3
        assert summary.channels[0].name == "DAPI"
        assert summary.channels[1].name == "FITC"
        assert summary.channels[2].name == "Cy5"


def test_summary_to_dict_json_serializable(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "sample.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator()
    with patch("nd2.ND2File", return_value=mock_nd2):
        summary = inspect_metadata(mock_file)
        data_dict = summary.to_dict()

        assert isinstance(data_dict, dict)
        assert "dimensions" in data_dict
        assert "channels" in data_dict


def test_print_metadata_console(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "sample.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator()
    with patch("nd2.ND2File", return_value=mock_nd2):
        summary = inspect_metadata(mock_file)
        console = Console(record=True)
        print_metadata(summary, console=console)
        output = console.export_text()

        assert "Nikon ND2 Metadata" in output
        assert "sample.nd2" in output
        assert "Voxel Size" in output
        assert "Channels & Optics" in output


def test_inspect_metadata_file_not_found():
    with pytest.raises(FileNotFoundError):
        inspect_metadata("/non/existent/sample.nd2")
