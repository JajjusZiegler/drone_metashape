# drone_metashape — Usage Guide

Detailed instructions for processing drone imagery (DJI Zenmuse P1 + MicaSense RedEdge-MX/Dual) with Agisoft Metashape Pro.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/JajjusZiegler/drone_metashape.git
cd drone_metashape
pip install -r requirements.txt
# See docs/METASHAPE_INSTALLATION.md for Metashape wheel installation
```

### 2. Prepare Your Data

Typical project folder layout:
```
<project_dir>/
├── *.psx               # Metashape project file (created by project-creation scripts)
├── exports/            # Output TIFs, OBJs, PDFs written here
├── references/         # Reference CSVs (GCP, interpolated positions)
└── logs/
    └── consolelog/     # Per-project console logs
```

Raw data structure (example):
```
data/
├── P1/                 # RGB imagery (DJI Zenmuse P1)
│   └── <site>/<YYYYMMDD>/
│       ├── *.JPG
│       └── *.MRK       # GPS logs
└── Micasense/          # Multispectral imagery
    └── <site>/<YYYYMMDD>/
        └── *.tif
```

### 3. Create Metashape Projects

```bash
python src/project_management/CreateProjectsUpscale.py input.csv
```

Or use the Metashape GUI script:

```
# Place in C:\Program Files\Agisoft\Metashape Pro\scripts\
src/project_management/OpenProjectsfromCSV.py
# Then: Scripts → Select Project from CSV
```

### 4. Run Batch Processing

```bash
python src/core/batch_processor.py
```

The script is **interactive**: it scans for recent `unprocessed_projects_*.csv`
files in the default project directory and lets you pick one, or prompts for a
full path.  There are no command-line flags — the CRS and test-mode are
controlled by the `HARDCODED_CRS` and `TEST_FLAG_ENABLED` constants at the top
of `src/core/batch_processor.py`.

---

## Core Scripts

### `src/core/batch_processor.py` — Batch Orchestrator

Reads a project CSV, validates paths, and launches `metashape_proc_upscale_main.py`
as a subprocess for each project.  Runs **interactively** — prompts for CSV path at
startup (no command-line arguments).

```bash
python src/core/batch_processor.py
```

**Configurable constants** (edit near the top of the file):

| Constant | Default | Description |
|---|---|---|
| `metashape_python_path` | `C:\Program Files\Agisoft\Metashape Pro\python\python.exe` | Metashape Python interpreter used to invoke the processing script |
| `HARDCODED_CRS` | `"2056"` | EPSG code passed as `-crs` to each processing run |
| `TEST_FLAG_ENABLED` | `False` | Set to `True` to append `-test` flag (lower quality, faster debug runs) |
| `TIMEOUT_DURATION` | `3600` (60 min) | Per-project subprocess timeout in seconds |

**CSV columns accepted:** `date`, `site`, `project_path`, `rgb` (or `rgb_data_path`), `multispec` (or `multispec_data_path`). Optional: `sunsens`.

### `src/core/metashape_proc_upscale_main.py` — Main Processing Pipeline

Invoked as a subprocess by `batch_processor.py`. Performs:

1. P1 alignment → point cloud → mesh → RGB ortho + DEM + PDF report
2. MicaSense position interpolation → multispectral ortho + PDF report

```bash
# Metashape Python interpreter required:
"C:\Program Files\Agisoft\Metashape Pro\python\python.exe" \
    src/core/metashape_proc_upscale_main.py \
    -proj_path /path/to/project.psx \
    -date 20250101 -site test_site -crs 2056
```

### `src/core/UpscaleRunScript.py` — Simple Launcher

Reads a CSV and launches `metashape_proc_upscale_main.py` sequentially (simpler alternative to `batch_processor.py`).

### `src/core/upd_micasense_pos_filename.py` — Position Interpolation

Interpolates MicaSense GPS positions from DJI P1 `.MRK` timestamps and the Swisstopo coordinate transformation API.

### `src/core/TransformHeight.py` — Height Transformation

Converts ellipsoidal heights to orthometric heights using a geoid model.

---

## Project Management Scripts

| Script | Description |
|---|---|
| `src/project_management/CreateProjectsUpscale.py` | Create projects from CSV (standard Upscale) |
| `src/project_management/CreateMultispectralProjects.py` | Create projects for multispectral-only campaigns |
| `src/project_management/UpscaleProjectCreation2025.py` | 2025 campaign project creation |
| `src/project_management/UpscaleProjectCreation_ExtraMode.py` | Extra-mode project creation |
| `src/project_management/initiate_project.py` | Low-level project initialisation helpers |
| `src/project_management/validate_projects.py` | Validate Metashape project paths |
| `src/project_management/OpenProjectsfromCSV.py` | Metashape GUI script — open projects from CSV |

---

## Utilities

| Script | Description |
|---|---|
| `src/utilities/InterpolateCameraPositions.py` | MicaSense position interpolation (fallback method) |
| `src/utilities/upd_micasense_pos.py` | Update MicaSense positions in a Metashape project |
| `src/utilities/upd_micasense_pos_from_chunk.py` | Update positions from chunk data |
| `src/utilities/ret_micasense_pos_exiftool.py` | Retrieve positions via ExifTool |
| `src/utilities/LocatePanels.py` | Locate reflectance panels |
| `src/utilities/UpscaleMultispecProcessing.py` | Multispectral-only processing |

---

## Configuration

### Coordinate Systems

Default is Swiss LV95 (`EPSG:2056`), set via the `HARDCODED_CRS` constant in
`batch_processor.py`.  When invoking `metashape_proc_upscale_main.py` directly,
pass `-crs <EPSG_code>`.

### Processing Quality

Controlled by the `-smooth` flag in `metashape_proc_upscale_main.py`: `low` / `medium` / `high`.

For faster debug runs set `TEST_FLAG_ENABLED = True` in `batch_processor.py`
(appends `-test` to each subprocess call, which uses lower quality settings in
`metashape_proc_upscale_main.py`).

### Sensor Offsets

Lever-arm offsets hardcoded in `metashape_proc_upscale_main.py`:

| Sensor | X (m) | Y (m) | Z (m) |
|---|---|---|---|
| DJI P1 (Gimbal 1) | 0.087 | 0.0 | 0.0 |
| MicaSense RedEdge (Gimbal 2) | −0.097 | −0.03 | −0.06 |
| MicaSense Dual (Gimbal 2) | −0.097 | 0.02 | −0.08 |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` | Activate conda env; check `python scripts\setup\setup_environment.py` |
| Path not found | Verify `project_path` in CSV; check site name mappings |
| Swisstopo API error | Check internet; fallback to `-no_api` flag if available |
| Metashape license error | Activate Metashape Pro GUI license |

Enable debug logging with:

```python
logging.basicConfig(level=logging.DEBUG)
```

---

## Extra Mode / Advanced Features

See dedicated documentation in `docs/`:

- `docs/EXTRA_MODE_README.md`
- `docs/UPSCALE_PROJECT_CREATION_EXTRAMODE_README.md`
- `docs/QUICK_REFERENCE_EXTRA_MODE.md`
- `docs/ROBUST_PROJECT_TOOLS_README.md`
