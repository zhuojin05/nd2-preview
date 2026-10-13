# nd2-preview 🔬⚡

[![PyPI version](https://img.shields.io/pypi/v/nd2-preview.svg?color=blue)](https://pypi.org/project/nd2-preview/)
[![Python versions](https://img.shields.io/pypi/pyversions/nd2-preview.svg)](https://pypi.org/project/nd2-preview/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/zhuojin/nd2-preview/actions/workflows/test.yml/badge.svg)](https://github.com/zhuojin/nd2-preview/actions/workflows/test.yml)

> **Instant macOS Quick Look preview and metadata inspector for Nikon `.nd2` microscopy files.**  
> Preview 20 GB+ files in **<300 ms** with **<50 MB RAM**, zero JVM startup delay, percentile auto-contrast, and native macOS Finder integration.

---

## 💡 Why `nd2-preview`?

| Feature | `nd2-preview` | Fiji / Bio-Formats |
| :--- | :--- | :--- |
| **Startup Time** | **< 300 ms** (native macOS Quick Look) | 10 – 30 seconds (JVM bootstrap) |
| **Memory Footprint** | **< 50 MB** (lazy slice reading via Dask) | 2 – 16 GB+ (often crashes on large stacks) |
| **Finder Integration** | **Native Quick Action** (Right-click in Finder) | Manual file open dialog |
| **Auto-Contrast** | Smart 1st–99.8th percentile stretch | Raw 16-bit often renders completely black |
| **Dependencies** | Pure lightweight Python (`nd2`, `numpy`, `pillow`) | Java 8+ Runtime Environment |

---

## 🚀 Installation

### Using `uv` (Recommended)
```bash
uv tool install nd2-preview
```

### Using `pip`
```bash
pip install nd2-preview
```

### Using Homebrew
```bash
brew install zhuojin/tools/nd2-preview
```

---

## 🍎 macOS Finder Integration

Turn any `.nd2` file in macOS Finder into an instant preview:

```bash
nd2-preview install-finder-action
```

1. Right-click any `.nd2` file in Finder.
2. Select **Quick Actions** ➔ **Preview with nd2-preview**.
3. The image instantly pops up in macOS's native Quick Look preview window!

> **Tip (Keyboard Shortcut):** Bind this Quick Action to a hotkey (e.g. `Cmd+Shift+Space` or `Option+Space`) in:  
> *System Settings* ➔ *Keyboard* ➔ *Keyboard Shortcuts* ➔ *Services* ➔ *Files and Folders*.

To remove the Quick Action:
```bash
nd2-preview install-finder-action --uninstall
```

---

## 📖 CLI Usage

### 1. Sequential Arrow-Key Browsing (`live` & `browse`)
```bash
# 🎯 Live Finder Follow-Mode: Stay in Finder, press ↑ / ↓ arrow keys, preview updates automatically!
nd2-preview live

# 🔍 Interactive Desktop Browser: Flip through files with [← / →], step Z with [[ / ]], toggle MIP with [M]
nd2-preview browse /path/to/folder
```

### 2. Multi-File Quick Look Carousel (`view`)
```bash
# Preview single file
nd2-preview view sample.nd2

# Preview all files in folder with Left/Right Arrow navigation in native Quick Look
nd2-preview view *.nd2
# or auto-expand sister files in the same directory:
nd2-preview view sample.nd2 --gallery

# Maximum Intensity Projection (MIP) along Z
nd2-preview view sample.nd2 --mip

# Specific slice, timepoint, or channel
nd2-preview view sample.nd2 -z 15 -t 2 -c "GFP"
```

### 3. Inspect Rich Metadata (`info`)
```bash
nd2-preview info sample.nd2
```

Displays a styled terminal summary formatted with Rich:
- **Dimensions:** XYZCT coordinate shape & dimension ordering
- **Voxel Size Calibration:** Micron voxel spacing ($dx, dy, dz$)
- **Optics & Objective:** Objective magnification, NA, and lens name
- **Channels Table:** Channel names, excitation & emission wavelengths, color assignments
- **Bit Depth & Compression:** Significant bits, data type, compression method, acquisition date

For programmatic pipelines, output JSON:
```bash
nd2-preview info sample.nd2 --json
```

### 4. Export Normalized Image (`export`)
```bash
# Export middle Z-slice to PNG
nd2-preview export sample.nd2 -o snapshot.png

# Export Z Maximum Intensity Projection
nd2-preview export sample.nd2 --mip -o mip.png

# Export specific channel with red-green palette
nd2-preview export sample.nd2 --channel 0 --palette red-green -o ch0.png
```

---

## 🎨 Smart Color Compositing

Raw microscope cameras capture 12-bit, 14-bit, or 16-bit unnormalized integers. Linear 8-bit division usually renders the image solid black. `nd2-preview` applies percentile-based histogram normalization:

- **1 Channel:** 8-bit grayscale.
- **2 Channels:** **Green / Magenta** overlay (color-blind friendly standard used in scientific publications; overlapping signals appear white).
- **3+ Channels:** First 3 channels mapped directly to **RGB**.
- **RGB native images:** Preserves native color channels with balanced contrast.

---

## 🛠️ Architecture & Memory Safety

Microscopy datasets easily exceed 20 GB. `nd2-preview` guarantees low memory usage:
- **Zero Full Loads:** Never calls `f.asarray()`.
- **Dask Chunk Streaming:** Uses `nd2.ND2File.to_dask()` to read *only* the single 2D plane or the single Z-column needed for MIP.
- **Async Quick Look Bridge:** Streams the normalized 8-bit composite to a temporary cache in `/tmp/nd2_preview/` and spawns `qlmanage -p` asynchronously.
- **Cross-Platform Graceful Fallback:** On Linux and Windows, automatically falls back to `xdg-open` or Pillow's image viewer.

---

## 🧪 Development & Testing

```bash
# Clone repository
git clone https://github.com/zhuojin/nd2-preview.git
cd nd2-preview

# Install development dependencies
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest -v
```

---

## 📄 License

MIT License. Built with ❤️ for the scientific microscopy community.
