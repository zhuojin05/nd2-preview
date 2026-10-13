from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from PIL import Image

from nd2_preview.viewer import InteractiveViewer, get_finder_selected_path, pil_to_tk


def test_pil_to_tk():
    """Verify that pil_to_tk converts PIL images to Tk PhotoImage using PPM buffer."""
    img = Image.new("RGB", (32, 32), color=(255, 0, 0))
    with patch("tkinter.PhotoImage") as mock_photo:
        mock_photo.return_value = "mock_tk_image"
        res = pil_to_tk(img)
        assert res == "mock_tk_image"
        mock_photo.assert_called_once()
        _, kwargs = mock_photo.call_args
        assert "data" in kwargs
        assert kwargs["data"].startswith(b"P6")  # PPM binary header


def test_get_finder_selected_path_non_darwin(monkeypatch):
    """Ensure get_finder_selected_path returns None on non-macOS platforms."""
    monkeypatch.setattr(sys, "platform", "linux")
    assert get_finder_selected_path() is None


def test_get_finder_selected_path_darwin_success(monkeypatch, tmp_path):
    """Test get_finder_selected_path parsing an existing .nd2 file."""
    monkeypatch.setattr(sys, "platform", "darwin")
    fake_nd2 = tmp_path / "sample.nd2"
    fake_nd2.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=str(fake_nd2) + "\n")
        assert get_finder_selected_path() == fake_nd2


def test_get_finder_selected_path_darwin_non_nd2(monkeypatch, tmp_path):
    """Test get_finder_selected_path filtering out non-nd2 files."""
    monkeypatch.setattr(sys, "platform", "darwin")
    fake_txt = tmp_path / "sample.txt"
    fake_txt.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=str(fake_txt) + "\n")
        assert get_finder_selected_path() is None


def test_viewer_init_empty_files_watch_finder():
    """Ensure InteractiveViewer initializes smoothly with no initial files in live mode."""
    with patch("tkinter.Tk") as mock_tk_cls:
        mock_tk = MagicMock()
        mock_tk_cls.return_value = mock_tk

        with patch.object(InteractiveViewer, "_schedule_finder_poll") as mock_poll:
            viewer = InteractiveViewer(files=[], watch_finder=True)
            assert viewer.files == []
            assert viewer.watch_finder is True
            mock_poll.assert_called_once()


def test_viewer_check_finder_selection(tmp_path):
    """Test adding a file detected via Finder polling when file list was initially empty."""
    fake_nd2 = tmp_path / "experiment.nd2"
    fake_nd2.touch()

    with patch("tkinter.Tk") as mock_tk_cls:
        mock_tk = MagicMock()
        mock_tk_cls.return_value = mock_tk

        with patch.object(InteractiveViewer, "_schedule_finder_poll"):
            viewer = InteractiveViewer(files=[], watch_finder=True)

            with patch("nd2_preview.viewer.get_finder_selected_path", return_value=fake_nd2):
                with patch.object(viewer, "load_current_file") as mock_load:
                    viewer._check_finder_selection()
                    assert viewer.files == [fake_nd2]
                    assert viewer.index == 0
                    mock_load.assert_called_once()
