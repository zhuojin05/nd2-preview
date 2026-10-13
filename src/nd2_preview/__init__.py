"""nd2-preview: Instant macOS Quick Look preview and metadata inspector for Nikon .nd2 files."""

__version__ = "0.1.0"

from nd2_preview.contrast import normalize_and_composite, stretch_percentile
from nd2_preview.core import PreviewFrame, read_preview_frame
from nd2_preview.metadata import ND2Summary, inspect_metadata

__all__ = [
    "__version__",
    "PreviewFrame",
    "read_preview_frame",
    "normalize_and_composite",
    "stretch_percentile",
    "ND2Summary",
    "inspect_metadata",
]
