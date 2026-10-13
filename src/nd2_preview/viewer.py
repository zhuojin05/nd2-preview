"""Interactive desktop previewer with keyboard navigation and live Finder synchronization."""

from __future__ import annotations

import io
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from nd2_preview.contrast import normalize_and_composite
from nd2_preview.core import PreviewFrame, read_preview_frame


def pil_to_tk(image: Image.Image) -> tk.PhotoImage:
    """Convert PIL Image to tk.PhotoImage using uncompressed PPM buffer.

    Completely bypasses PIL's _imagingtk C extension, avoiding PyImagingPhoto
    symbol lookup errors across standalone Python environments on macOS.
    """
    buf = io.BytesIO()
    image.save(buf, format="PPM")
    return tk.PhotoImage(data=buf.getvalue())


def get_finder_selected_path() -> Optional[Path]:
    """Retrieve the POSIX path of the currently selected file in macOS Finder."""
    if sys.platform != "darwin":
        return None

    script = (
        'tell application "Finder"\n'
        "    set sel to selection as alias list\n"
        "    if (count of sel) > 0 then\n"
        "        return POSIX path of (item 1 of sel)\n"
        "    end if\n"
        "end tell"
    )
    try:
        res = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=0.3,
        )
        if res.returncode == 0:
            out = res.stdout.strip()
            if out:
                p = Path(out)
                if p.suffix.lower() == ".nd2" and p.exists():
                    return p
    except Exception:
        pass
    return None


class InteractiveViewer:
    """Lightweight GUI viewer with arrow-key browsing, Z-stepping, and live Finder tracking."""

    def __init__(
        self,
        files: list[Path],
        current_index: int = 0,
        watch_finder: bool = False,
        mip: bool = False,
        pmin: float = 1.0,
        pmax: float = 99.8,
        palette: str = "auto",
    ) -> None:
        self.files = files
        self.index = max(0, min(current_index, len(files) - 1)) if files else 0
        self.watch_finder = watch_finder
        self.is_mip = mip
        self.pmin = pmin
        self.pmax = pmax
        self.palette = palette
        self.current_z: Optional[int] = None
        self.selected_channel: Optional[int] = None

        self._current_frame: Optional[PreviewFrame] = None
        self._current_pil: Optional[Image.Image] = None
        self._tk_img: Optional[tk.PhotoImage] = None

        # Setup Tkinter UI
        self.root = tk.Tk()
        self.root.title("nd2-preview")
        self.root.geometry("900x900")
        self.root.configure(bg="#121212")

        # Top Header Bar
        self.header_frame = tk.Frame(self.root, bg="#1a1a1a", height=40)
        self.header_frame.pack(fill=tk.X, side=tk.TOP)

        self.title_label = tk.Label(
            self.header_frame,
            text="Loading...",
            fg="#ffffff",
            bg="#1a1a1a",
            font=("Helvetica", 14, "bold"),
            anchor="w",
            padx=12,
            pady=6,
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.mode_label = tk.Label(
            self.header_frame,
            text="",
            fg="#00e5ff",
            bg="#1a1a1a",
            font=("Helvetica", 11),
            padx=12,
        )
        self.mode_label.pack(side=tk.RIGHT)

        # Main Canvas
        self.canvas = tk.Canvas(
            self.root,
            bg="#121212",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bottom Status / Shortcuts Bar
        self.footer_frame = tk.Frame(self.root, bg="#1a1a1a")
        self.footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        hints = (
            " [← / → or ↑ / ↓] Navigate Files   "
            "[M] MIP   [[ / ]] Z-Slice   [C] Cycle Channels   [F] Fullscreen   [Q] Quit"
        )
        self.footer_label = tk.Label(
            self.footer_frame,
            text=hints,
            fg="#888888",
            bg="#1a1a1a",
            font=("Helvetica", 10),
            pady=4,
        )
        self.footer_label.pack(side=tk.LEFT, padx=10)

        # Key Bindings
        self.root.bind("<Left>", self._prev_file)
        self.root.bind("<Up>", self._prev_file)
        self.root.bind("<Right>", self._next_file)
        self.root.bind("<Down>", self._next_file)
        self.root.bind("<space>", self._next_file)
        self.root.bind("<BackSpace>", self._prev_file)
        self.root.bind("<bracketleft>", self._prev_z)
        self.root.bind("<bracketright>", self._next_z)
        self.root.bind("<m>", self._toggle_mip)
        self.root.bind("<M>", self._toggle_mip)
        self.root.bind("<c>", self._cycle_channel)
        self.root.bind("<C>", self._cycle_channel)
        self.root.bind("<f>", self._toggle_fullscreen)
        self.root.bind("<F>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._close)
        self.root.bind("<q>", self._close)
        self.root.bind("<Q>", self._close)
        self.root.bind("<Configure>", self._on_resize)

        self._is_fullscreen = False
        self._resize_job: Optional[str] = None
        self._last_polled_path: Optional[Path] = None

        if self.files:
            self.load_current_file()
        elif self.watch_finder:
            self.title_label.config(text="Live Finder Mode: Select any .nd2 file in Finder")

        if self.watch_finder:
            self._schedule_finder_poll()

    def _schedule_finder_poll(self) -> None:
        """Poll macOS Finder for selection updates every 150 ms."""
        try:
            self._check_finder_selection()
        except Exception:
            pass
        self.root.after(150, self._schedule_finder_poll)

    def _check_finder_selection(self) -> None:
        sel_path = get_finder_selected_path()
        if sel_path and sel_path != self._last_polled_path:
            self._last_polled_path = sel_path
            # Check if it's already in files or add it
            if sel_path in self.files:
                self.index = self.files.index(sel_path)
            else:
                if not self.files:
                    self.files = [sel_path]
                    self.index = 0
                else:
                    self.files.insert(self.index + 1, sel_path)
                    self.index += 1
            self.current_z = None
            self.load_current_file()

    def load_current_file(self) -> None:
        """Render and display the currently selected ND2 file."""
        if not self.files:
            return

        target_file = self.files[self.index]
        try:
            self._current_frame = read_preview_frame(
                target_file,
                z=self.current_z,
                channel=self.selected_channel,
                mip=self.is_mip,
            )

            # Update current z if returned
            if self._current_frame.z_index is not None:
                self.current_z = self._current_frame.z_index

            self._current_pil = normalize_and_composite(
                self._current_frame.data,
                p_low=self.pmin,
                p_high=self.pmax,
                palette=self.palette,
            )

            # Update header text
            count_str = f"[{self.index + 1}/{len(self.files)}]"
            self.title_label.config(text=f"{count_str}  {target_file.name}")

            mode_info = []
            if self._current_frame.is_mip:
                mode_info.append("Z: MIP")
            elif self._current_frame.z_index is not None:
                mode_info.append(f"Z: {self._current_frame.z_index}")

            dims_str = "×".join(str(d) for d in self._current_frame.shape)
            mode_info.append(f"({dims_str})")

            ch_name = (
                f"Ch: {self._current_frame.selected_channel}"
                if self._current_frame.selected_channel is not None
                else "Composite"
            )
            mode_info.append(ch_name)

            self.mode_label.config(text="  |  ".join(mode_info))
            self.render_image()

        except Exception as exc:
            self.title_label.config(text=f"Error: {exc}")

    def render_image(self) -> None:
        """Scale and draw the PIL Image onto the Tkinter canvas."""
        if not self._current_pil:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        if cw <= 1 or ch <= 1:
            cw, ch = 800, 800

        iw, ih = self._current_pil.size
        scale = min(cw / iw, ch / ih, 2.0)  # max zoom 2x
        nw = max(1, int(iw * scale))
        nh = max(1, int(ih * scale))

        resized = self._current_pil.resize((nw, nh), Image.Resampling.BILINEAR)
        self._tk_img = pil_to_tk(resized)

        self.canvas.delete("all")
        # Center image in canvas
        x = (cw - nw) // 2
        y = (ch - nh) // 2
        self.canvas.create_image(x, y, anchor=tk.NW, image=self._tk_img)

    def _on_resize(self, event: Any) -> None:
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(50, self.render_image)

    def _next_file(self, event: Optional[Any] = None) -> None:
        if self.files and self.index < len(self.files) - 1:
            self.index += 1
            self.current_z = None
            self.load_current_file()

    def _prev_file(self, event: Optional[Any] = None) -> None:
        if self.files and self.index > 0:
            self.index -= 1
            self.current_z = None
            self.load_current_file()

    def _next_z(self, event: Optional[Any] = None) -> None:
        self.is_mip = False
        z = 0 if self.current_z is None else self.current_z + 1
        self.current_z = z
        self.load_current_file()

    def _prev_z(self, event: Optional[Any] = None) -> None:
        self.is_mip = False
        z = 0 if self.current_z is None else max(0, self.current_z - 1)
        self.current_z = z
        self.load_current_file()

    def _toggle_mip(self, event: Optional[Any] = None) -> None:
        self.is_mip = not self.is_mip
        self.load_current_file()

    def _cycle_channel(self, event: Optional[Any] = None) -> None:
        if not self._current_frame or not self._current_frame.channel_names:
            return

        c_count = len(self._current_frame.channel_names)
        if self.selected_channel is None:
            self.selected_channel = 0
        elif self.selected_channel + 1 < c_count:
            self.selected_channel += 1
        else:
            self.selected_channel = None  # back to composite
        self.load_current_file()

    def _toggle_fullscreen(self, event: Optional[Any] = None) -> None:
        self._is_fullscreen = not self._is_fullscreen
        self.root.attributes("-fullscreen", self._is_fullscreen)

    def _close(self, event: Optional[Any] = None) -> None:
        self.root.destroy()

    def run(self) -> None:
        """Start the viewer event loop."""
        self.root.mainloop()


def launch_viewer(
    files: list[Path],
    current_index: int = 0,
    watch_finder: bool = False,
    mip: bool = False,
    pmin: float = 1.0,
    pmax: float = 99.8,
    palette: str = "auto",
) -> None:
    """Launch the interactive viewer."""
    viewer = InteractiveViewer(
        files=files,
        current_index=current_index,
        watch_finder=watch_finder,
        mip=mip,
        pmin=pmin,
        pmax=pmax,
        palette=palette,
    )
    viewer.run()
