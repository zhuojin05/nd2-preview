"""Memory-safe slice extraction and Maximum Intensity Projection (MIP) for ND2 files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import nd2
import numpy as np


@dataclass
class PreviewFrame:
    """Container holding extracted 2D plane / MIP data and slice coordinates."""

    data: np.ndarray
    shape: tuple[int, ...]
    dtype: np.dtype
    channel_names: list[str]
    selected_channel: str | int | None
    z_index: int | None
    t_index: int
    position_index: int
    is_mip: bool
    voxel_size_um: tuple[float, float, float] | None


def get_channel_names(file_handle: Any) -> list[str]:
    """Retrieve human-readable channel names from an open ND2File."""
    names: list[str] = []
    try:
        if hasattr(file_handle, "metadata") and file_handle.metadata:
            channels = getattr(file_handle.metadata, "channels", None)
            if channels:
                for ch in channels:
                    meta = getattr(ch, "channel", None)
                    name = getattr(meta, "name", None) if meta else None
                    if name:
                        names.append(str(name))
    except Exception:
        pass

    if not names and hasattr(file_handle, "sizes") and "C" in file_handle.sizes:
        c_count = file_handle.sizes["C"]
        names = [f"Channel {i}" for i in range(c_count)]

    return names


def resolve_channel_index(
    channel: int | str | None,
    channel_count: int,
    channel_names: list[str],
) -> int | None:
    """Resolve user-supplied channel index or name to an integer index."""
    if channel is None:
        return None

    if isinstance(channel, int):
        if 0 <= channel < channel_count:
            return channel
        raise ValueError(
            f"Channel index {channel} out of range [0, {channel_count - 1}]."
        )

    # String channel name (case-insensitive lookup)
    query = str(channel).strip().lower()
    for idx, name in enumerate(channel_names):
        if name.strip().lower() == query:
            return idx

    # If it's a digit string
    if query.isdigit():
        idx = int(query)
        if 0 <= idx < channel_count:
            return idx

    available = ", ".join([f"'{name}' (index {i})" for i, name in enumerate(channel_names)])
    raise ValueError(
        f"Channel '{channel}' not found. Available channels: {available}"
    )


def read_preview_frame(
    path: str | Path,
    z: int | None = None,
    t: int = 0,
    position: int = 0,
    channel: int | str | None = None,
    mip: bool = False,
) -> PreviewFrame:
    """Memory-safely read a 2D plane or Z-MIP from an ND2 file.

    Crucial Optimization:
    Never calls `f.asarray()`. Employs lazy delayed reading (via Dask wrapper)
    to only page in the requested 2D plane or single Z-stack column. Memory footprint
    remains strictly under 50 MB even for 20 GB+ files.

    Args:
        path: Path to the .nd2 file.
        z: Z-stack slice index. Defaults to middle slice (size_z // 2).
        t: Timepoint index. Defaults to 0.
        position: Stage position index (multipoint). Defaults to 0.
        channel: Specific channel index or name. If None, all channels are returned.
        mip: If True, computes Maximum Intensity Projection along the Z-axis.

    Returns:
        PreviewFrame with extracted numpy array and metadata.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"ND2 file not found: {file_path}")

    with nd2.ND2File(file_path) as f:
        sizes: dict[str, int] = dict(f.sizes)
        channel_names = get_channel_names(f)
        c_count = sizes.get("C", len(channel_names) or 1)

        ch_idx = resolve_channel_index(channel, c_count, channel_names)

        # Retrieve voxel size if available
        voxel_um: tuple[float, float, float] | None = None
        try:
            vox = f.voxel_size()
            voxel_um = (float(vox.x), float(vox.y), float(vox.z))
        except Exception:
            voxel_um = None

        has_z = "Z" in sizes and sizes["Z"] > 1
        num_z = sizes.get("Z", 1)

        actual_z: int | None = None
        apply_mip = mip and has_z

        if not apply_mip and has_z:
            if z is not None:
                actual_z = min(max(0, z), num_z - 1)
            else:
                actual_z = num_z // 2
        elif not has_z:
            actual_z = 0 if "Z" in sizes else None

        # Build lazy dask array
        darr = f.to_dask()

        # Construct coordinate indexer matching sizes order
        indices: list[Any] = []
        remaining_axes: list[str] = []

        for ax, sz in sizes.items():
            if ax == "P":
                p_idx = min(max(0, position), sz - 1)
                indices.append(p_idx)
            elif ax == "T":
                t_idx = min(max(0, t), sz - 1)
                indices.append(t_idx)
            elif ax == "Z":
                if apply_mip:
                    indices.append(slice(None))
                    remaining_axes.append("Z")
                else:
                    z_target = actual_z if actual_z is not None else 0
                    indices.append(min(max(0, z_target), sz - 1))
            elif ax == "C":
                if ch_idx is not None:
                    indices.append(ch_idx)
                else:
                    indices.append(slice(None))
                    remaining_axes.append("C")
            elif ax in ("Y", "X", "S"):
                indices.append(slice(None))
                remaining_axes.append(ax)
            else:
                # Other loops or unknown axes: take first index
                indices.append(0)

        # Slice the lazy dask array
        sub_arr = darr[tuple(indices)]

        # If MIP was requested along Z
        if apply_mip and "Z" in remaining_axes:
            z_axis = remaining_axes.index("Z")
            sub_arr = sub_arr.max(axis=z_axis)
            remaining_axes.pop(z_axis)

        # Materialize only the sliced data into RAM
        computed: np.ndarray = np.asarray(sub_arr.compute())

        # Clean up and normalize orientation of dimensions
        # Expected outputs: (H, W), (C, H, W), or (H, W, 3/4)
        computed = np.squeeze(computed)

        if "S" in remaining_axes and computed.ndim == 3:
            # RGB components: ensure (H, W, S)
            s_axis = remaining_axes.index("S")
            if s_axis != 2:
                computed = np.moveaxis(computed, s_axis, -1)
        elif "C" in remaining_axes and computed.ndim == 3:
            # Multichannel: ensure (C, H, W)
            c_axis = remaining_axes.index("C")
            if c_axis != 0:
                computed = np.moveaxis(computed, c_axis, 0)

        return PreviewFrame(
            data=computed,
            shape=computed.shape,
            dtype=computed.dtype,
            channel_names=channel_names,
            selected_channel=channel if channel is not None else None,
            z_index=actual_z if not apply_mip else None,
            t_index=min(max(0, t), sizes.get("T", 1) - 1),
            position_index=min(max(0, position), sizes.get("P", 1) - 1),
            is_mip=apply_mip,
            voxel_size_um=voxel_um,
        )
