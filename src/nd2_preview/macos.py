"""macOS integration: Quick Look bridge and Finder Quick Action installer."""

from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


def get_cache_dir() -> Path:
    """Return the dedicated directory used for caching preview frames."""
    cache_dir = Path(tempfile.gettempdir()) / "nd2_preview"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def show_preview(
    image: Image.Image | list[Image.Image],
    title: str | list[str] = "preview",
    wait: bool = False,
) -> subprocess.Popen[Any] | None:
    """Display image(s) using macOS Quick Look, or gracefully fallback on other OSes.

    When multiple images are provided, macOS Quick Look opens a carousel/gallery
    where users can navigate sequentially using the Left/Right Arrow keys.

    Args:
        image: Single PIL Image or list of PIL Images to display.
        title: Base name or list of base names for the cached preview files.
        wait: If True, blocks until the preview window is closed by the user.

    Returns:
        subprocess.Popen object if spawned asynchronously, or None if fallback was used.
    """
    cache_dir = get_cache_dir()
    imgs = image if isinstance(image, list) else [image]

    if isinstance(title, list):
        titles = title
    else:
        titles = [f"{title}_{i}" if len(imgs) > 1 else title for i in range(len(imgs))]

    cache_paths: list[Path] = []
    for img, t in zip(imgs, titles):
        clean_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in t)
        p = cache_dir / f"{clean_title}.png"
        img.save(p, format="PNG")
        cache_paths.append(p)

    is_macos = sys.platform == "darwin"
    has_qlmanage = shutil.which("qlmanage") is not None

    if is_macos and has_qlmanage:
        proc = subprocess.Popen(
            ["qlmanage", "-p", *[str(p) for p in cache_paths]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if wait:
            proc.wait()
        return proc

    # Graceful fallback for non-macOS or headless environments
    if sys.platform.startswith("linux") and shutil.which("xdg-open"):
        proc = subprocess.Popen(
            ["xdg-open", str(cache_paths[0])],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if wait:
            proc.wait()
        return proc

    # Universal PIL fallback
    for img, t in zip(imgs, titles):
        img.show(title=t)
    return None


def get_services_dir() -> Path:
    """Return the user's macOS Services directory (~/Library/Services)."""
    return Path.home() / "Library" / "Services"


def install_finder_action(action_name: str = "Preview with nd2-preview") -> Path:
    """Generate and install a native macOS Quick Action (.workflow) into ~/Library/Services/.

    Enables right-clicking .nd2 file(s) in Finder -> Quick Actions -> 'Preview with nd2-preview'.
    The action automatically looks up nd2-preview across ~/.local/bin (uv tool), Homebrew, and PATH.

    Args:
        action_name: Name of the workflow service.

    Returns:
        Path to the installed .workflow bundle.
    """
    if sys.platform != "darwin":
        raise OSError("Finder Quick Actions can only be installed on macOS (darwin).")

    services_dir = get_services_dir()
    services_dir.mkdir(parents=True, exist_ok=True)

    workflow_path = services_dir / f"{action_name}.workflow"
    contents_dir = workflow_path / "Contents"
    contents_dir.mkdir(parents=True, exist_ok=True)

    # Shell script executed by Automator when file(s) are selected in Finder
    script = (
        'export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"\n'
        'if command -v nd2-preview >/dev/null 2>&1;\n'
        'then\n'
        '    nd2-preview view "$@"\n'
        'else\n'
        '    python3 -m nd2_preview.cli view "$@"\n'
        'fi\n'
    )

    info_plist_data: dict[str, Any] = {
        "NSServices": [
            {
                "NSBackgroundColorName": "background",
                "NSIconName": "NSActionTemplate",
                "NSMenuItem": {
                    "default": action_name,
                },
                "NSMessage": "runWorkflowAsService",
                "NSSendFileTypes": [
                    "public.item",
                    "public.data",
                ],
            }
        ]
    }

    document_wflow_data: dict[str, Any] = {
        "AMApplicationBuild": "534",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [
            {
                "action": {
                    "AMAccepts": {
                        "Container": "List",
                        "Optional": False,
                        "Types": ["com.apple.cocoa.path"],
                    },
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "AMParameterProperties": {
                        "COMMAND_STRING": {},
                        "CheckedForUserDefaultShell": {},
                        "inputMethod": {},
                        "shell": {},
                        "source": {},
                    },
                    "AMProvides": {
                        "Container": "List",
                        "Types": ["com.apple.cocoa.string"],
                    },
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "ActionParameters": {
                        "COMMAND_STRING": script,
                        "CheckedForUserDefaultShell": True,
                        "inputMethod": 1,  # 1 = arguments passed in "$@"
                        "shell": "/bin/zsh",
                        "source": "",
                    },
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "CFBundleVersion": "2.0.3",
                    "CanShowSelectedItemsWhenRun": False,
                    "CanShowWhenRun": True,
                    "Category": ["AMCategoryUtilities"],
                    "Class Name": "RunShellScriptAction",
                    "InputUUID": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
                    "Keywords": ["Shell", "Script", "Command", "Run", "Unix"],
                    "OutputUUID": "B2C3D4E5-F6A7-8901-BCDE-F12345678901",
                    "UUID": "C3D4E5F6-A7B8-9012-CDEF-123456789012",
                    "UnlocalizedApplications": ["Automator"],
                    "conversionLabel": 0,
                    "isViewVisible": 1,
                    "location": "309.000000:305.000000",
                    "nibPath": (
                        "/System/Library/Automator/Run Shell Script.action/"
                        "Contents/Resources/Base.lproj/main.nib"
                    ),
                },
                "isViewVisible": 1,
            }
        ],
        "connectors": {},
        "workflowMetaData": {
            "applicationBundleIDsByPath": {},
            "applicationPaths": [],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "presentationMode": 15,
            "processesInput": False,
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": False,
            "systemImageName": "NSActionTemplate",
            "useAutomaticInputType": False,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }

    info_path = contents_dir / "Info.plist"
    wflow_path = contents_dir / "document.wflow"

    with open(info_path, "wb") as f:
        plistlib.dump(info_plist_data, f)

    with open(wflow_path, "wb") as f:
        plistlib.dump(document_wflow_data, f)

    return workflow_path


def uninstall_finder_action(action_name: str = "Preview with nd2-preview") -> bool:
    """Remove the installed Quick Action workflow from ~/Library/Services/.

    Args:
        action_name: Name of the workflow service.

    Returns:
        True if the workflow was found and removed, False otherwise.
    """
    workflow_path = get_services_dir() / f"{action_name}.workflow"
    if workflow_path.exists():
        shutil.rmtree(workflow_path)
        return True
    return False
