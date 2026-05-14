# drone_metashape — Upscale Drone Processing

RGB and Multispectral Imagery Processing in Agisoft Metashape Pro.

## Overview

These workflows process imagery collected simultaneously on the **DJI Matrice 300 RTK** platform using:
- **DJI Zenmuse P1** (RGB, gimbal 1)
- **MicaSense RedEdge-MX / Dual** (multispectral, gimbal 2)

The pipeline produces co-registered RGB and multispectral orthomosaics, DEMs, and processing reports with Swiss coordinate system (EPSG:2056) support.

## Key Features

- **Batch Processing**: Process multiple campaigns from a single CSV
- **Robust Path Resolution**: Handles naming mismatches between CSV and file system
- **Swiss Coordinate Support**: Swisstopo API integration for coordinate transformation
- **Quality Control**: Per-project logging and output validation

## Project Structure

```
src/
├── core/                        # Main processing scripts
│   ├── batch_processor.py           # Batch orchestrator (reads CSV, calls processor)
│   ├── UpscaleRunScript.py          # Simple single-run launcher
│   ├── metashape_proc_upscale_main.py  # Full processing pipeline (Upscale)
│   ├── metashape_proc.py            # Processing pipeline (generic/TERN)
│   ├── upd_micasense_pos_filename.py   # MicaSense position interpolation
│   └── TransformHeight.py           # Height/geoid transformation
│
├── project_management/          # Project creation and validation
│   ├── UpscaleProjectCreation_ExtraMode.py  # Standard project creation (--extra-mode for new sites)
│   ├── CreateMultispectralProjects.py  # Multispectral-only project creation
│   ├── initiate_project.py          # Low-level project initialisation
│   ├── validate_projects.py         # Validate Metashape project paths
│   └── OpenProjectsfromCSV.py       # Metashape GUI script (open from CSV)
│
├── utilities/                   # Helper scripts
│   ├── InterpolateCameraPositions.py   # MicaSense position interpolation (fallback)
│   ├── upd_micasense_pos.py         # Update positions in Metashape project
│   ├── upd_micasense_pos_from_chunk.py # Update positions from chunk data
│   ├── ret_micasense_pos_exiftool.py   # Retrieve positions via ExifTool
│   ├── LocatePanels.py              # Locate reflectance panels
│   └── UpscaleMultispecProcessing.py   # Multispectral-only processing
│
└── micasense/                   # MicaSense Python library
    └── (capture, image, imageset, metadata, panel, dls, utils)

scripts/
├── setup/                       # Environment setup scripts
│   ├── setup_conda_env.ps1          # PowerShell: create conda env (Python 3.11)
│   ├── setup_conda_env.bat          # Batch: create conda env
│   ├── setup_environment.py         # Python: validate installation
│   ├── install_metashape.bat        # Install Metashape Python API wheel
│   └── activate_environment.ps1    # Quick environment activation
└── testing/                     # Testing and validation
    ├── test_metashape_installation.py  # Comprehensive Metashape tests
    ├── quick_metashape_check.py        # Quick Metashape check
    ├── metashape_proc_widget_testing.py # GUI widget prototype
    ├── run_tests_with_metashape.bat    # Test runner
    ├── final_test.bat                  # End-to-end test suite
    └── confirm_success.bat             # Success confirmation

docs/                            # Documentation
├── USAGE_GUIDE.md                   # Detailed usage instructions
├── METASHAPE_INSTALLATION.md        # Metashape setup guide
├── EXTRA_MODE_README.md             # Extra-mode documentation
├── ROBUST_PROJECT_TOOLS_README.md   # Robust project tools guide
└── metashape_python_api_2_1_0.pdf   # Metashape API reference

examples/                        # Example scripts
├── metashape_blockshift.py          # Blockshift using AUSPOS results
└── metashape_proc_p1.py             # RGB-only (P1 single-mount) processing

tests/
└── test_setup_paths.py          # Setup path validation test

archive/                         # Deprecated scripts (reference only)

geoid_audit.py                   # Standalone Swiss geoid / height audit tool
```

## Installation

### Prerequisites

- **Agisoft Metashape Pro** license (required for processing)
- **Python 3.8–3.11** ⚠️ Python 3.12+ is NOT supported by Metashape 2.1.4
- **Anaconda / Miniconda** (recommended)

### Quick Setup

```powershell
# 1. Clone
git clone https://github.com/JajjusZiegler/drone_metashape.git
cd drone_metashape

# 2. Create compatible Python environment
scripts\setup\setup_conda_env.ps1

# 3. (In a new shell) Activate and install
conda activate upscale-drone
pip install -r requirements.txt

# 4. Verify
python scripts\setup\setup_environment.py
python tests\test_setup_paths.py
```

### Metashape Python API

See `docs/METASHAPE_INSTALLATION.md` for full details.

```bash
pip install wheels/Metashape-2.1.4-cp37.cp38.cp39.cp310.cp311-none-win_amd64.whl
python scripts\testing\test_metashape_installation.py
```

## Usage

### Automated Processing Workflow

1. **Create projects** from CSV:
   ```bash
   # Standard sites (in SITE_MAPPING):
   python src/project_management/UpscaleProjectCreation_ExtraMode.py input.csv
   # New / test sites not in the mapping:
   python src/project_management/UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode
   ```
2. *(Optional)* Place `src/project_management/OpenProjectsfromCSV.py` in
   `C:\Program Files\Agisoft\Metashape Pro\scripts\` and use
   *Scripts → Select Project from CSV* to set reflectance panels.
3. **Run batch processing**:
   ```bash
   python src/core/batch_processor.py input.csv
   python src/core/batch_processor.py input.csv --test           # dry-run / validation
   python src/core/batch_processor.py input.csv --crs 2056       # override CRS (default: 2056)
   python src/core/batch_processor.py input.csv --timeout 7200   # 2-hour timeout
   python src/core/batch_processor.py input.csv --smooth high
   ```

   > **Note:** `batch_processor.py` spawns `metashape_proc_upscale_main.py` using
   > the **Metashape Python interpreter** (default:
   > `C:\Program Files\Agisoft\Metashape Pro\python\python.exe`).
   > If Metashape is installed elsewhere, edit the `METASHAPE_PYTHON_PATH` constant
   > near the top of `src/core/batch_processor.py`.

### CSV Format

Required columns: `date`, `site`, `project_path`  
Image-path columns (either form is accepted): `rgb` / `rgb_data_path`, `multispec` / `multispec_data_path`  
Optional column: `sunsens` (set to `true` to enable sun-sensor reflectance calibration)

### Coordinate and Height Transformation (Switzerland)

This is a critical step in the Swiss processing workflow. The pipeline performs
two independent transformations for every P1 camera position:

#### 1. Horizontal: WGS84 → LV95 (EPSG:2056)

The Swisstopo `wgs84tolv95` REST API transforms WGS84 geographic coordinates
(lat/lon from MRK file or DJI XMP `GpsLatitude`/`GpsLongitude`) into
CH1903+/LV95 easting/northing. The API also returns an altitude (LN02), but
this is discarded — the height is handled separately (see below).

#### 2. Vertical: ETRS89 ellipsoidal → LHN95 orthometric

The DJI P1 records heights as **ETRS89 ellipsoidal** in the MRK file and in
the XMP tag `drone-dji:AbsoluteAltitude`. These are **not** orthometric heights
and must be converted before use in Metashape.

The conversion uses the swisstopo CHGeo2004 geoid grid (`ETRS.tif`):

```
H_LHN95 = h_ETRS89 - N
```

where `N` is the geoid undulation (≈ 47–54 m for Switzerland) sampled from
the grid using **bilinear interpolation** at the camera's WGS84 position.
Bilinear interpolation is essential — nearest-neighbour sampling produces
errors up to ~260 mm.

**Accuracy** (verified against swisstopo Reframe GeoSuite):
- Central Switzerland (e.g. lwf_lens, ~1160 m): **~7 mm** mean offset
- Southern border / Ticino: **~58 mm** (grid accuracy limit at coverage edge)

**Fallback chain** (applied per-point, in order):
1. `ETRS.tif` (swisstopo CHGeo2004, LHN95) — pass with `--htrans`
2. `ExtendedGeoid.tif` (EGM2008, global) — pass with `--htrans-fallback`
3. ETRS89 ellipsoidal unchanged (logged as warning)

**CLI usage:**
```bash
python src/core/batch_processor.py input.csv \
    --htrans   "M:/geoid/Swisstopo/ETRS.tif" \
    --htrans-fallback "M:/geoid/ExtendedGeoid.tif"
```

#### 3. MRK validity and EXIF fallback

Before using MRK positions the pipeline validates the file:
1. Checks every entry has a valid GPS fix (non-zero coordinates)
2. Spot-checks a sample of MRK positions against the DJI XMP fields
   `GpsLatitude`, `GpsLongitude`, and `AbsoluteAltitude` from the JPG headers

If the MRK is all-zeros (no RTK fix) **or** its positions disagree with EXIF,
the pipeline falls back to reading positions and timestamps directly from the
XMP block of each P1 JPG (`drone-dji:UTCAtExposure` for timing,
`drone-dji:AbsoluteAltitude` for height). This ensures MicaSense position
interpolation still works even when the MRK file is faulty.

---

### Geoid / Height Audit

`geoid_audit.py` at the repo root is a standalone diagnostic that verifies the
height pipeline for a specific flight.  It requires an internet connection (for
the Swisstopo reframe API) but does **not** require Metashape:

```bash
python geoid_audit.py --image path/to/P1_image.JPG --geoid_ln02 path/to/chgeo2004_ETRS89_LN02.tif
# optional extras:
python geoid_audit.py --image ... --mrk path/to/flight.MRK --dsm path/to/dsm.tif \
    --geoid_ln02 path/to/LN02.tif --geoid_lhn95 path/to/LHN95.tif
```

### Other Examples

- `examples/metashape_blockshift.py` — blockshift images using AUSPOS results
- `examples/metashape_proc_p1.py` — process RGB-only (P1 single-mount)

### Extra Mode / Advanced Features

See `docs/EXTRA_MODE_README.md`, `docs/UPSCALE_PROJECT_CREATION_EXTRAMODE_README.md`,
and `docs/QUICK_REFERENCE_EXTRA_MODE.md`.

## Funding

This project was funded by TERN Landscapes.

## Authors

- Poornima Sivanandam (Original Author)
- Darren Turner (Original Author)
- Arko Lucieer (Original Author), School of Geography, Planning, and Spatial Sciences, University of Tasmania
- Jan Ziegler (Modifying Author)

## Acknowledgements

- TERN Landscapes
- TERN Surveillance
- TERN Data Services
- Swiss Federal Office of Topography (Swisstopo)

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.
