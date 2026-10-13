"""Command-line interface for nd2-preview."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from nd2_preview import __version__
from nd2_preview.contrast import normalize_and_composite
from nd2_preview.core import read_preview_frame
from nd2_preview.macos import (
    install_finder_action,
    show_preview,
    uninstall_finder_action,
)
from nd2_preview.metadata import inspect_metadata, print_metadata
from nd2_preview.viewer import get_finder_selected_path, launch_viewer

app = typer.Typer(
    name="nd2-preview",
    help=(
        "⚡ Instant macOS Quick Look preview and metadata inspector for Nikon .nd2 "
        "microscopy files."
    ),
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold cyan]nd2-preview[/] version [bold white]{__version__}[/]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """nd2-preview CLI: Instant microscopy inspection without Fiji overhead."""
    pass


def collect_nd2_files(targets: list[Path], gallery: bool = False) -> list[Path]:
    """Expand list of files and directories into a sorted list of .nd2 files."""
    collected: list[Path] = []
    for t in targets:
        if t.is_dir():
            collected.extend(sorted(t.glob("*.nd2")))
            collected.extend(sorted(t.glob("*.ND2")))
        elif t.is_file() and t.suffix.lower() == ".nd2":
            collected.append(t)

    # If only 1 file was given and gallery is requested, expand to all files in that directory
    if len(collected) == 1 and gallery:
        parent = collected[0].parent
        all_in_dir = sorted(parent.glob("*.nd2")) + sorted(parent.glob("*.ND2"))
        if all_in_dir:
            return sorted(list(set(all_in_dir)))

    return collected


@app.command("view")
def view_cmd(
    files: list[Path] = typer.Argument(
        ...,
        help="Path(s) to Nikon .nd2 file(s) or directories.",
    ),
    mip: bool = typer.Option(
        False,
        "--mip",
        help="Compute Maximum Intensity Projection along the Z-axis.",
    ),
    z: Optional[int] = typer.Option(
        None,
        "--z",
        "-z",
        help="Z-slice index (defaults to middle slice).",
    ),
    t: int = typer.Option(
        0,
        "--t",
        "-t",
        help="Timepoint index (default: 0).",
    ),
    position: int = typer.Option(
        0,
        "--position",
        "-p",
        help="Stage position index for multipoint files (default: 0).",
    ),
    channel: Optional[str] = typer.Option(
        None,
        "--channel",
        "-c",
        help="Channel index or name. Default: composite.",
    ),
    pmin: float = typer.Option(
        1.0,
        "--pmin",
        help="Lower percentile for contrast stretch (default: 1.0).",
    ),
    pmax: float = typer.Option(
        99.8,
        "--pmax",
        help="Upper percentile for contrast stretch (default: 99.8).",
    ),
    palette: str = typer.Option(
        "auto",
        "--palette",
        help="Color palette for 2-channel overlay ('auto', 'green-magenta', 'red-green').",
    ),
    gallery: bool = typer.Option(
        False,
        "--gallery",
        "-g",
        help="Include all sister .nd2 files in directory for sequential arrow navigation.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Open interactive desktop viewer with arrow-key navigation.",
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        help="Block until preview window is closed.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to also export the rendered image (PNG/TIFF/JPEG).",
    ),
) -> None:
    """Preview ND2 file(s) in macOS Quick Look or interactive desktop viewer."""
    try:
        nd2_files = collect_nd2_files(files, gallery=gallery)
        if not nd2_files:
            err_console.print("[bold red]Error:[/] No .nd2 files found matching input paths.")
            raise typer.Exit(code=1)

        # If interactive mode requested, launch the desktop viewer
        if interactive:
            launch_viewer(
                files=nd2_files,
                mip=mip,
                pmin=pmin,
                pmax=pmax,
                palette=palette,
            )
            return

        rendered_images = []
        titles = []

        for f in nd2_files:
            frame = read_preview_frame(
                f,
                z=z,
                t=t,
                position=position,
                channel=channel,
                mip=mip,
            )
            img = normalize_and_composite(
                frame.data,
                p_low=pmin,
                p_high=pmax,
                palette=palette,
            )
            rendered_images.append(img)

            title_tag = f.stem
            if frame.is_mip:
                title_tag += "_MIP"
            elif frame.z_index is not None:
                title_tag += f"_z{frame.z_index}"
            titles.append(title_tag)

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            rendered_images[0].save(output)
            console.print(f"✨ Saved preview image to [bold green]{output}[/]")

        show_preview(rendered_images, title=titles, wait=wait)

    except Exception as exc:
        err_console.print(f"[bold red]Error previewing file:[/] {exc}")
        raise typer.Exit(code=1)


@app.command("live")
def live_cmd(
    directory: Optional[Path] = typer.Argument(
        None,
        help="Optional directory to monitor. Defaults to current Finder directory.",
    ),
    mip: bool = typer.Option(
        False,
        "--mip",
        help="Compute Maximum Intensity Projection along the Z-axis.",
    ),
    pmin: float = typer.Option(
        1.0,
        "--pmin",
        help="Lower percentile for contrast stretch (default: 1.0).",
    ),
    pmax: float = typer.Option(
        99.8,
        "--pmax",
        help="Upper percentile for contrast stretch (default: 99.8).",
    ),
    palette: str = typer.Option(
        "auto",
        "--palette",
        help="Color palette for 2-channel overlay ('auto', 'green-magenta', 'red-green').",
    ),
) -> None:
    """Live Finder companion: updates preview as you navigate with arrow keys in Finder."""
    files: list[Path] = []
    current_idx = 0

    # Check currently selected file in Finder
    initial_sel = get_finder_selected_path()
    if directory and directory.is_dir():
        files = sorted(directory.glob("*.nd2")) + sorted(directory.glob("*.ND2"))
    elif initial_sel:
        files = sorted(initial_sel.parent.glob("*.nd2")) + sorted(initial_sel.parent.glob("*.ND2"))
        if initial_sel in files:
            current_idx = files.index(initial_sel)

    if not files and initial_sel:
        files = [initial_sel]

    console.print("🚀 [bold green]Live Finder Preview started![/]")
    console.print(
        "   [dim]Navigate through files in macOS Finder with [bold white]↑ / ↓ arrow keys[/]. "
        "The preview window updates automatically.[/]"
    )

    launch_viewer(
        files=files,
        current_index=current_idx,
        watch_finder=True,
        mip=mip,
        pmin=pmin,
        pmax=pmax,
        palette=palette,
    )


@app.command("browse")
def browse_cmd(
    target: Path = typer.Argument(
        Path("."),
        help="Directory or .nd2 file to browse sequentially.",
    ),
    mip: bool = typer.Option(
        False,
        "--mip",
        help="Compute Maximum Intensity Projection along the Z-axis.",
    ),
    pmin: float = typer.Option(
        1.0,
        "--pmin",
        help="Lower percentile for contrast stretch (default: 1.0).",
    ),
    pmax: float = typer.Option(
        99.8,
        "--pmax",
        help="Upper percentile for contrast stretch (default: 99.8).",
    ),
    palette: str = typer.Option(
        "auto",
        "--palette",
        help="Color palette for 2-channel overlay ('auto', 'green-magenta', 'red-green').",
    ),
) -> None:
    """Browse a folder of .nd2 files sequentially with arrow keys and Z-stepping."""
    start_idx = 0
    if target.is_file():
        folder = target.parent
        files = sorted(folder.glob("*.nd2")) + sorted(folder.glob("*.ND2"))
        if target in files:
            start_idx = files.index(target)
    else:
        files = sorted(target.glob("*.nd2")) + sorted(target.glob("*.ND2"))

    if not files:
        err_console.print(f"[bold red]No .nd2 files found in[/] {target}")
        raise typer.Exit(code=1)

    launch_viewer(
        files=files,
        current_index=start_idx,
        watch_finder=False,
        mip=mip,
        pmin=pmin,
        pmax=pmax,
        palette=palette,
    )


@app.command("info")
def info_cmd(
    file: Path = typer.Argument(
        ...,
        help="Path to the Nikon .nd2 file.",
        exists=True,
        readable=True,
        dir_okay=False,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print raw metadata summary formatted as JSON.",
    ),
) -> None:
    """Inspect and display rich metadata (dimensions, channels, voxel size, optics)."""
    try:
        summary = inspect_metadata(file)
        if as_json:
            console.print(json.dumps(summary.to_dict(), indent=2))
        else:
            print_metadata(summary, console=console)
    except Exception as exc:
        err_console.print(f"[bold red]Error inspecting metadata:[/] {exc}")
        raise typer.Exit(code=1)


@app.command("export")
def export_cmd(
    file: Path = typer.Argument(
        ...,
        help="Path to the Nikon .nd2 file.",
        exists=True,
        readable=True,
        dir_okay=False,
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Destination path for exported image (e.g. preview.png, snapshot.tif).",
    ),
    mip: bool = typer.Option(
        False,
        "--mip",
        help="Compute Maximum Intensity Projection along the Z-axis.",
    ),
    z: Optional[int] = typer.Option(
        None,
        "--z",
        "-z",
        help="Z-slice index (defaults to middle slice).",
    ),
    t: int = typer.Option(
        0,
        "--t",
        "-t",
        help="Timepoint index (default: 0).",
    ),
    position: int = typer.Option(
        0,
        "--position",
        "-p",
        help="Stage position index (default: 0).",
    ),
    channel: Optional[str] = typer.Option(
        None,
        "--channel",
        "-c",
        help="Channel index or name. Default: composite.",
    ),
    pmin: float = typer.Option(
        1.0,
        "--pmin",
        help="Lower percentile for contrast stretch (default: 1.0).",
    ),
    pmax: float = typer.Option(
        99.8,
        "--pmax",
        help="Upper percentile for contrast stretch (default: 99.8).",
    ),
    palette: str = typer.Option(
        "auto",
        "--palette",
        help="Color palette for 2-channel overlay ('auto', 'green-magenta', 'red-green').",
    ),
) -> None:
    """Export a normalized 2D slice or Z-MIP to PNG, TIFF, or JPEG."""
    try:
        frame = read_preview_frame(
            file,
            z=z,
            t=t,
            position=position,
            channel=channel,
            mip=mip,
        )

        image = normalize_and_composite(
            frame.data,
            p_low=pmin,
            p_high=pmax,
            palette=palette,
        )

        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output)
        console.print(f"✨ Successfully exported to [bold green]{output}[/]")
    except Exception as exc:
        err_console.print(f"[bold red]Error exporting image:[/] {exc}")
        raise typer.Exit(code=1)


@app.command("install-finder-action")
def install_action_cmd(
    name: str = typer.Option(
        "Preview with nd2-preview",
        "--name",
        help="Name of the macOS Finder Quick Action.",
    ),
    uninstall: bool = typer.Option(
        False,
        "--uninstall",
        help="Remove the Quick Action from ~/Library/Services/.",
    ),
) -> None:
    """Install or remove the macOS Finder Quick Action / Service workflow."""
    if sys.platform != "darwin":
        err_console.print("[bold red]Error:[/] Finder Quick Actions are only supported on macOS.")
        raise typer.Exit(code=1)

    try:
        if uninstall:
            removed = uninstall_finder_action(name)
            if removed:
                console.print(f"🗑️ Successfully removed Quick Action '[bold yellow]{name}[/]'.")
            else:
                console.print(f"ℹ️ Quick Action '[bold yellow]{name}[/]' was not installed.")
        else:
            workflow_path = install_finder_action(name)
            console.print("🚀 [bold green]Finder Quick Action installed successfully![/]")
            console.print(f"   Location: [cyan]{workflow_path}[/]")
            console.print("\n[bold white]How to use in macOS Finder:[/]")
            console.print("  1. Select one or multiple [bold cyan].nd2[/] files.")
            console.print(f"  2. Right-click ➔ [bold white]Quick Actions[/] ➔ [bold cyan]{name}[/]")
            console.print(
                "  3. In Quick Look, use [bold white]← / → arrow keys[/] to flip through files!"
            )
            console.print("\n[bold white]To assign a keyboard shortcut:[/]")
            console.print(
                "  System Settings ➔ Keyboard ➔ Keyboard Shortcuts ➔ Services ➔ Files and Folders."
            )
    except Exception as exc:
        err_console.print(f"[bold red]Error configuring Finder action:[/] {exc}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
