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
from nd2_preview.macos import install_finder_action, show_preview, uninstall_finder_action
from nd2_preview.metadata import inspect_metadata, print_metadata

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


@app.command("view")
def view_cmd(
    file: Path = typer.Argument(
        ...,
        help="Path to the Nikon .nd2 file.",
        exists=True,
        readable=True,
        dir_okay=False,
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
        help="Channel index (0, 1, ...) or channel name (e.g. 'DAPI', 'GFP'). Default: composite.",
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
    """Preview an ND2 file instantly in macOS Quick Look (or system viewer)."""
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

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            image.save(output)
            console.print(f"✨ Saved preview image to [bold green]{output}[/]")

        # Descriptive title for the preview cache
        title_tag = f"{file.stem}"
        if frame.is_mip:
            title_tag += "_MIP"
        elif frame.z_index is not None:
            title_tag += f"_z{frame.z_index}"
        if frame.t_index > 0:
            title_tag += f"_t{frame.t_index}"
        if frame.selected_channel is not None:
            title_tag += f"_ch{frame.selected_channel}"

        show_preview(image, title=title_tag, wait=wait)

    except Exception as exc:
        err_console.print(f"[bold red]Error previewing file:[/] {exc}")
        raise typer.Exit(code=1)


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
            console.print("  1. Right-click any [bold cyan].nd2[/] file.")
            console.print(f"  2. Select [bold white]Quick Actions[/] ➔ [bold cyan]{name}[/].")
            console.print("\n[bold white]To assign a keyboard shortcut:[/]")
            console.print(
                "  System Settings ➔ Keyboard ➔ Keyboard Shortcuts ➔ Services ➔ Files and Folders."
            )
    except Exception as exc:
        err_console.print(f"[bold red]Error configuring Finder action:[/] {exc}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
