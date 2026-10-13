"""Shared test fixtures and synthetic mock ND2 file generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import dask.array as da
import numpy as np
import pytest


@dataclass
class MockVoxelSize:
    x: float
    y: float
    z: float


@dataclass
class MockColor:
    r: int
    g: int
    b: int


@dataclass
class MockChannelMeta:
    name: str
    index: int
    excitationLambdaNm: float | None
    emissionLambdaNm: float | None
    color: MockColor | None


@dataclass
class MockMicroscope:
    objectiveName: str | None = "Plan Apo 60x/1.40 Oil"
    objectiveMagnification: float | None = 60.0
    objectiveNumericalAperture: float | None = 1.40


@dataclass
class MockChannel:
    channel: MockChannelMeta
    microscope: MockMicroscope = field(default_factory=MockMicroscope)


@dataclass
class MockAttributes:
    bitsPerComponentInMemory: int = 16
    bitsPerComponentSignificant: int = 14
    pixelDataType: str = "unsigned"
    compressionType: str = "lossless"


@dataclass
class MockTextInfo:
    date: str = "2026-03-15 14:30:00"


class MockND2File:
    """Simulates an open nd2.ND2File for testing without requiring 20GB real binary files."""

    def __init__(
        self,
        sizes: dict[str, int],
        dtype: np.dtype = np.dtype(np.uint16),
        channel_names: list[str] | None = None,
        is_rgb: bool = False,
    ):
        self.sizes = sizes
        self.dtype = dtype
        self.is_rgb = is_rgb
        self.shape = tuple(sizes.values())

        # Generate synthetic array
        np.random.seed(42)
        raw = np.random.randint(100, 4000, size=self.shape, dtype=dtype)
        # Create dask array with chunk size 1 on outer dimensions
        chunks = tuple((1,) * s if ax not in ("Y", "X") else (s,) for ax, s in sizes.items())
        self._dask_arr = da.from_array(raw, chunks=chunks)

        # Setup channel metadata
        c_count = sizes.get("C", 1)
        if channel_names is None:
            channel_names = [f"Channel {i}" for i in range(c_count)]

        channels: list[MockChannel] = []
        for i, name in enumerate(channel_names[:c_count]):
            meta = MockChannelMeta(
                name=name,
                index=i,
                excitationLambdaNm=405.0 + i * 80.0,
                emissionLambdaNm=450.0 + i * 80.0,
                color=MockColor(r=50 * (i + 1), g=100, b=200),
            )
            channels.append(MockChannel(channel=meta))

        self.metadata = MagicMock()
        self.metadata.channels = channels
        self.attributes = MockAttributes()
        self.text_info = MockTextInfo()

    def __enter__(self) -> "MockND2File":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def voxel_size(self) -> MockVoxelSize:
        return MockVoxelSize(x=0.065, y=0.065, z=0.200)

    def to_dask(self) -> da.Array:
        return self._dask_arr


@pytest.fixture
def mock_nd2_generator():
    """Factory fixture to create MockND2File instances with custom dimension shapes."""
    def _create(
        sizes: dict[str, int] | None = None,
        channel_names: list[str] | None = None,
        is_rgb: bool = False,
    ) -> MockND2File:
        if sizes is None:
            sizes = {"T": 2, "Z": 5, "C": 3, "Y": 64, "X": 64}
        return MockND2File(sizes=sizes, channel_names=channel_names, is_rgb=is_rgb)

    return _create
