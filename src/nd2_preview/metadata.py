"""Rich metadata inspection and formatting for ND2 microscopy files."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import nd2
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


@dataclass
class ChannelInfo:
    """Channel summary details."""

    index: int
    name: str
    excitation_nm: float | None
    emission_nm: float | None
    color_rgb: tuple[int, int, int] | None


@dataclass
class ND2Summary:
    """Comprehensive summary of an ND2 microscopy file."""

    path: str
    file_size_bytes: int
    file_size_str: str
    dimensions: dict[str, int]
    dim_order: str
    voxel_size_um: dict[str, float | None]
    objective_name: str | None
    objective_magnification: float | None
    numerical_aperture: float | None
    bits_in_memory: int | None
    bits_significant: int | None
    pixel_dtype: str | None
    compression: str | None
    date: str | None
    channels: list[ChannelInfo]

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary for JSON serialization."""
        return asdict(self)


def format_file_size(num_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0  # type: ignore
    return f"{num_bytes:.1f} PB"


def inspect_metadata(path: str | Path) -> ND2Summary:
    """Inspect and extract structured metadata from an ND2 file.

    Args:
        path: Path to the .nd2 file.

    Returns:
        ND2Summary containing all extracted dimensions, optics, calibration, and channels.
    """
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"ND2 file not found: {file_path}")

    size_bytes = file_path.stat().st_size
    size_str = format_file_size(size_bytes)

    with nd2.ND2File(file_path) as f:
        sizes: dict[str, int] = dict(f.sizes)
        dim_order = "".join(sizes.keys())

        # Voxel calibration
        voxel_dict: dict[str, float | None] = {"x": None, "y": None, "z": None}
        try:
            vox = f.voxel_size()
            voxel_dict["x"] = round(float(vox.x), 4) if vox.x is not None else None
            voxel_dict["y"] = round(float(vox.y), 4) if vox.y is not None else None
            voxel_dict["z"] = round(float(vox.z), 4) if vox.z is not None else None
        except Exception:
            pass

        # Attributes
        bits_mem: int | None = None
        bits_sig: int | None = None
        pixel_dt: str | None = None
        compression: str | None = None
        if hasattr(f, "attributes") and f.attributes:
            bits_mem = getattr(f.attributes, "bitsPerComponentInMemory", None)
            bits_sig = getattr(f.attributes, "bitsPerComponentSignificant", None)
            pixel_dt = getattr(f.attributes, "pixelDataType", None)
            compression = getattr(f.attributes, "compressionType", None)

        # Text info & acquisition date
        date_str: str | None = None
        if hasattr(f, "text_info") and f.text_info:
            date_str = getattr(f.text_info, "date", None)
            if not date_str and isinstance(f.text_info, dict):
                date_str = f.text_info.get("date")

        # Optics & Channels
        obj_name: str | None = None
        obj_mag: float | None = None
        obj_na: float | None = None
        channels_info: list[ChannelInfo] = []

        raw_channels = getattr(f.metadata, "channels", None) if f.metadata else None
        if hasattr(f, "metadata") and raw_channels:
            for i, ch in enumerate(raw_channels):
                meta = getattr(ch, "channel", None)
                ch_name = getattr(meta, "name", f"Channel {i}") if meta else f"Channel {i}"
                ex_nm = getattr(meta, "excitationLambdaNm", None) if meta else None
                em_nm = getattr(meta, "emissionLambdaNm", None) if meta else None

                color_rgb: tuple[int, int, int] | None = None
                if meta and hasattr(meta, "color") and meta.color:
                    c = meta.color
                    # color might have r, g, b or as_rgb tuple
                    if hasattr(c, "r") and hasattr(c, "g") and hasattr(c, "b"):
                        color_rgb = (int(c.r), int(c.g), int(c.b))

                # Extract objective details from first channel with microscope info
                microscope = getattr(ch, "microscope", None)
                if microscope and obj_name is None:
                    obj_name = getattr(microscope, "objectiveName", None)
                    obj_mag = getattr(microscope, "objectiveMagnification", None)
                    obj_na = getattr(microscope, "objectiveNumericalAperture", None)

                channels_info.append(
                    ChannelInfo(
                        index=i,
                        name=str(ch_name),
                        excitation_nm=round(float(ex_nm), 1) if ex_nm else None,
                        emission_nm=round(float(em_nm), 1) if em_nm else None,
                        color_rgb=color_rgb,
                    )
                )

        # Fallback if no channels metadata existed
        if not channels_info and "C" in sizes:
            for i in range(sizes["C"]):
                channels_info.append(
                    ChannelInfo(
                        index=i,
                        name=f"Channel {i}",
                        excitation_nm=None,
                        emission_nm=None,
                        color_rgb=None,
                    )
                )

        return ND2Summary(
            path=str(file_path),
            file_size_bytes=size_bytes,
            file_size_str=size_str,
            dimensions=sizes,
            dim_order=dim_order,
            voxel_size_um=voxel_dict,
            objective_name=obj_name,
            objective_magnification=obj_mag,
            numerical_aperture=obj_na,
            bits_in_memory=bits_mem,
            bits_significant=bits_sig,
            pixel_dtype=pixel_dt,
            compression=compression,
            date=date_str,
            channels=channels_info,
        )


def print_metadata(summary: ND2Summary, console: Console | None = None) -> None:
    """Print beautifully formatted Rich summary table for an ND2 file."""
    if console is None:
        console = Console()

    # Overview panel
    filename = Path(summary.path).name
    dim_str = " × ".join([f"{k}:{v}" for k, v in summary.dimensions.items()])

    overview_table = Table.grid(padding=(0, 2))
    overview_table.add_column(style="bold cyan", justify="right")
    overview_table.add_column(style="white")

    overview_table.add_row("File:", f"[bold white]{filename}[/] ({summary.file_size_str})")
    overview_table.add_row("Dimensions:", f"[green]{dim_str}[/] [dim]({summary.dim_order})[/]")

    # Voxel sizes
    vx = summary.voxel_size_um.get("x")
    vy = summary.voxel_size_um.get("y")
    vz = summary.voxel_size_um.get("z")
    vox_parts = []
    if vx is not None and vy is not None:
        vox_parts.append(f"XY: {vx:.4f} µm")
    if vz is not None:
        vox_parts.append(f"Z: {vz:.4f} µm")
    vox_text = ", ".join(vox_parts) if vox_parts else "[dim]Uncalibrated[/]"
    overview_table.add_row("Voxel Size:", vox_text)

    # Objective
    obj_parts = []
    if summary.objective_name:
        obj_parts.append(str(summary.objective_name))
    elif summary.objective_magnification:
        obj_parts.append(f"{summary.objective_magnification:.0f}×")
    if summary.numerical_aperture:
        obj_parts.append(f"NA {summary.numerical_aperture:.2f}")
    overview_table.add_row("Objective:", " ".join(obj_parts) if obj_parts else "[dim]Unknown[/]")

    # Bit depth & Compression
    bit_info = []
    if summary.bits_significant:
        bit_info.append(f"{summary.bits_significant}-bit significant")
    if summary.bits_in_memory:
        bit_info.append(f"({summary.bits_in_memory}-bit in memory)")
    if summary.pixel_dtype:
        bit_info.append(summary.pixel_dtype)
    if summary.compression and summary.compression != "none":
        bit_info.append(f"[yellow]{summary.compression}[/]")
    overview_table.add_row("Data Type:", " ".join(bit_info) if bit_info else "[dim]N/A[/]")

    if summary.date:
        overview_table.add_row("Acquisition Date:", summary.date)

    console.print(
        Panel(
            overview_table,
            title=f"🔬 [bold]Nikon ND2 Metadata[/bold] — [cyan]{filename}[/]",
            border_style="cyan",
            expand=False,
        )
    )

    # Channels table
    if summary.channels:
        ch_table = Table(
            title="Channels & Optics",
            title_style="bold magenta",
            border_style="dim",
            show_header=True,
            header_style="bold",
        )
        ch_table.add_column("#", justify="center", style="dim", width=4)
        ch_table.add_column("Channel Name", style="bold")
        ch_table.add_column("Excitation", justify="right")
        ch_table.add_column("Emission", justify="right")
        ch_table.add_column("Display Color", justify="center")

        for ch in summary.channels:
            ex_str = f"{ch.excitation_nm:.0f} nm" if ch.excitation_nm else "—"
            em_str = f"{ch.emission_nm:.0f} nm" if ch.emission_nm else "—"

            color_str = "—"
            if ch.color_rgb:
                r, g, b = ch.color_rgb
                color_str = f"[rgb({r},{g},{b})]■ rgb({r},{g},{b})[/]"

            ch_table.add_row(str(ch.index), ch.name, ex_str, em_str, color_str)

        console.print(ch_table)
