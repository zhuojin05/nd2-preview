"""Tests for Typer CLI commands (view, info, export, install-finder-action)."""

from unittest.mock import patch

from typer.testing import CliRunner

from nd2_preview import __version__
from nd2_preview.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Instant macOS Quick Look preview" in result.stdout
    assert "view" in result.stdout
    assert "info" in result.stdout
    assert "export" in result.stdout
    assert "install-finder-action" in result.stdout


def test_cli_info_command(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "sample.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator()
    with patch("nd2.ND2File", return_value=mock_nd2):
        result = runner.invoke(app, ["info", str(mock_file)])
        assert result.exit_code == 0
        assert "Nikon ND2 Metadata" in result.stdout
        assert "sample.nd2" in result.stdout


def test_cli_info_json(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "sample.nd2"
    mock_file.touch()

    mock_nd2 = mock_nd2_generator()
    with patch("nd2.ND2File", return_value=mock_nd2):
        result = runner.invoke(app, ["info", str(mock_file), "--json"])
        assert result.exit_code == 0
        assert '"dimensions"' in result.stdout
        assert '"voxel_size_um"' in result.stdout


def test_cli_view_command(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "sample.nd2"
    mock_file.touch()
    out_file = tmp_path / "rendered.png"

    mock_nd2 = mock_nd2_generator()
    with patch("nd2.ND2File", return_value=mock_nd2), \
         patch("nd2_preview.cli.show_preview") as mock_show:

        result = runner.invoke(
            app,
            ["view", str(mock_file), "--mip", "-o", str(out_file)],
        )
        assert result.exit_code == 0
        assert mock_show.called
        assert out_file.exists()


def test_cli_export_command(mock_nd2_generator, tmp_path):
    mock_file = tmp_path / "sample.nd2"
    mock_file.touch()
    export_file = tmp_path / "exported.png"

    mock_nd2 = mock_nd2_generator()
    with patch("nd2.ND2File", return_value=mock_nd2):
        result = runner.invoke(
            app,
            ["export", str(mock_file), "-o", str(export_file), "--mip"],
        )
        assert result.exit_code == 0
        assert export_file.exists()
        assert "Successfully exported" in result.stdout


def test_cli_install_finder_action(tmp_path):
    with patch("sys.platform", "darwin"), \
         patch("nd2_preview.macos.get_services_dir", return_value=tmp_path):

        # Install
        result = runner.invoke(app, ["install-finder-action"])
        assert result.exit_code == 0
        assert "Finder Quick Action installed successfully" in result.stdout

        # Uninstall
        result_un = runner.invoke(app, ["install-finder-action", "--uninstall"])
        assert result_un.exit_code == 0
        assert "Successfully removed Quick Action" in result_un.stdout


def test_cli_file_not_found():
    result = runner.invoke(app, ["view", "missing.nd2"])
    assert result.exit_code != 0
