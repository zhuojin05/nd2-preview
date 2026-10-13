"""Tests for macOS Quick Look bridge and Finder Quick Action installer."""

import plistlib
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from nd2_preview.macos import (
    get_cache_dir,
    install_finder_action,
    show_preview,
    uninstall_finder_action,
)


def test_get_cache_dir():
    cache_dir = get_cache_dir()
    assert cache_dir.exists()
    assert cache_dir.is_dir()
    assert "nd2_preview" in str(cache_dir)


def test_show_preview_macos_qlmanage():
    img = Image.new("RGB", (50, 50), color=(100, 150, 200))

    mock_proc = MagicMock(spec=subprocess.Popen)
    with patch("sys.platform", "darwin"), \
         patch("shutil.which", return_value="/usr/bin/qlmanage"), \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen:

        proc = show_preview(img, title="test_sample", wait=False)

        assert proc is mock_proc
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "qlmanage"
        assert args[1] == "-p"
        assert "test_sample.png" in args[2]


def test_show_preview_linux_fallback():
    img = Image.new("RGB", (20, 20))

    mock_proc = MagicMock(spec=subprocess.Popen)

    def mock_which(cmd: str) -> str | None:
        return "/usr/bin/xdg-open" if cmd == "xdg-open" else None

    with patch("sys.platform", "linux"), \
         patch("shutil.which", side_effect=mock_which), \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen:

        proc = show_preview(img, title="linux_test", wait=False)
        assert proc is mock_proc
        mock_popen.assert_called_once()
        assert mock_popen.call_args[0][0][0] == "xdg-open"


def test_show_preview_pil_fallback():
    img = Image.new("RGB", (20, 20))

    with patch("sys.platform", "win32"), \
         patch("shutil.which", return_value=None), \
         patch.object(Image.Image, "show") as mock_show:

        proc = show_preview(img, title="fallback_test")
        assert proc is None
        mock_show.assert_called_once()


def test_install_and_uninstall_finder_action(tmp_path):
    action_name = "Test Preview Quick Action"

    with patch("sys.platform", "darwin"), \
         patch("nd2_preview.macos.get_services_dir", return_value=tmp_path):

        # Install
        workflow_path = install_finder_action(action_name)
        assert workflow_path.exists()
        assert workflow_path.is_dir()

        info_plist = workflow_path / "Contents" / "Info.plist"
        doc_wflow = workflow_path / "Contents" / "document.wflow"
        assert info_plist.exists()
        assert doc_wflow.exists()

        # Validate plists are valid
        with open(info_plist, "rb") as f:
            info_data = plistlib.load(f)
            assert "NSServices" in info_data

        with open(doc_wflow, "rb") as f:
            wflow_data = plistlib.load(f)
            assert "actions" in wflow_data

        # Uninstall
        removed = uninstall_finder_action(action_name)
        assert removed is True
        assert not workflow_path.exists()

        # Uninstall again returns False
        assert uninstall_finder_action(action_name) is False


def test_install_finder_action_non_macos_error():
    with patch("sys.platform", "linux"):
        with pytest.raises(OSError, match="only be installed on macOS"):
            install_finder_action()
