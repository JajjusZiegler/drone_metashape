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
│   ├── CreateProjectsUpscale.py     # Create projects from CSV (standard)
│   ├── CreateMultispectralProjects.py  # Multispectral-only project creation
│   ├── UpscaleProjectCreation2025.py   # 2025 campaign project creation
│   ├── UpscaleProjectCreation_ExtraMode.py  # Extra-mode project creation
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
   python src/project_management/CreateProjectsUpscale.py input.csv
   ```
2. *(Optional)* Place `src/project_management/OpenProjectsfromCSV.py` in
   `C:\Program Files\Agisoft\Metashape Pro\scripts\` and use
   *Scripts → Select Project from CSV* to set reflectance panels.
3. **Run batch processing** (interactive — the script will prompt for the CSV path):
   ```bash
   python src/core/batch_processor.py
   ```
   If recent `unprocessed_projects_*.csv` files are found in the default project
   directory the script lists them and lets you pick one; otherwise it prompts for
   a full path.

   > **Note:** `batch_processor.py` spawns `metashape_proc_upscale_main.py` using
   > the **Metashape Python interpreter** (default:
   > `C:\Program Files\Agisoft\Metashape Pro\python\python.exe`).
   > If Metashape is installed elsewhere, edit the `metashape_python_path` constant
   > near the top of `src/core/batch_processor.py`.
   > The target CRS (default `2056` — Swiss LV95) is set via the `HARDCODED_CRS`
   > constant in the same file.

### CSV Format

Required columns: `date`, `site`, `project_path`  
Image-path columns (either form is accepted): `rgb` / `rgb_data_path`, `multispec` / `multispec_data_path`  
Optional column: `sunsens` (set to `true` to enable sun-sensor reflectance calibration)

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
