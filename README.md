## Upscale Drone Processing:
## RGB and Multispectral Imagery Processing in Agisoft Metashape Pro

## Table of Contents
- [Introduction](#introduction)
- [Installation](#installation)
- [Usage](#usage)
  - [Automated Processing Workflow](#automated-processing-workflow)
  - [Step-by-Step Processing Using the Metashape GUI](#step-by-step-processing-using-the-metashape-gui)
  - [Other Examples](#other-examples)
- [Funding](#funding)
- [Authors](#authors)
- [Acknowledgements](#acknowledgements)
- [Contributing](#contributing)

## Introduction
These workflows were developed for RGB and multispectral imagery collected simultaneously on the DJI Matrice 300 platform. These scripts are designed for use with RGB imagery acquired with DJI Zenmuse P1 and MicaSense RedEdge-MX/Dual.

**Note:** The images are expected to be loaded into the Metashape project already, and the projects are created by the `CreateMultispectralProjects` and `CreateProjectsUpscale` scripts.

## Repository Structure

| Script / Folder | Description |
|---|---|
| `CreateMultispectralProjects.py` | Create Metashape projects for multispectral campaigns |
| `CreateProjectsUpscale.py` | Create Metashape projects from a CSV input file |
| `OpenProjectsfromCSV.py` | Metashape GUI script to open projects listed in a CSV; place in Metashape scripts folder |
| `UpscaleRunScript.py` | Main run script for the full Upscale processing workflow |
| `metashape_proc_upscale_main.py` | Core Metashape processing logic for Upscale campaigns |
| `metashape_proc.py` | Core Metashape processing logic (original/general) |
| `batch_processor.py` | Batch processing driver for multiple projects |
| `UpscaleProjectCreation2025.py` | Project creation for 2025 Upscale campaigns |
| `UpscaleProjectCreation_ExtraMode.py` | Project creation with extra-mode support |
| `UpscaleMultispecProcessing.py` | Multispectral processing for Upscale campaigns |
| `EnhancedUpscaleProcessor.py` | Enhanced processor with additional features |
| `upd_micasense_pos.py` | Update MicaSense camera positions in Metashape project |
| `upd_micasense_pos_filename.py` | Update MicaSense positions using filenames |
| `upd_micasense_pos_from_chunk.py` | Update MicaSense positions from chunk data |
| `ret_micasense_pos_exiftool.py` | Retrieve MicaSense positions using ExifTool |
| `InterpolateCameraPositions.py` | Interpolate camera positions for MicaSense |
| `TransformHeight.py` | Transform height values (geoid conversion) |
| `initiate_project.py` | Project initialisation helpers |
| `validate_projects.py` | Validate Metashape project files |
| `LocatePanels.py` | Locate reflectance panels in imagery |
| `examples/` | Example scripts (blockshift, P1-only processing) |
| `micasense/` | MicaSense Python library (capture, image, metadata, etc.) |
| `testing/` | Widget testing script for Metashape GUI prototype |
| `archive/` | Archived/deprecated scripts kept for reference — safe to delete once functionality is verified |

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/JajjusZiegler/drone_metashape.git
   ```
2. Install required dependencies:
   ```bash
   cd drone_metashape
   pip install -r requirements.txt  # to be added
   ```

## Usage

### Automated Processing Workflow
Uses scripts `UpscaleRunScript.py`, `metashape_proc_upscale_main.py`, `upd_micasense_pos_filename.py` and `CreateProjectsUpscale.py`.
- Run `CreateProjectsUpscale.py` to create Metashape projects from a CSV input file.
- Place `OpenProjectsfromCSV.py` in `C:\Program Files\Agisoft\Metashape Pro\scripts\`. Open Metashape and run *Scripts → Select Project from CSV*. Select the reflectance panel images and detect the panel masks. Click on a new project to open the next project.
- Run `UpscaleRunScript.py` to complete the processing workflow.
- Inspect the output.

### Step-by-Step Processing Using the Metashape GUI
Refer to the [Drone RGB and Multispectral Processing Protocol](https://www.tern.org.au/field-survey-apps-and-protocols/).

### Other Examples
- `examples/metashape_blockshift.py` — perform blockshift of images in a Metashape chunk using AUSPOS results.
- `examples/metashape_proc_p1.py` — process only RGB images captured with Zenmuse P1 on **gimbal 1 of dual mount** (remove GPS/INS offset code for single-mount gimbal).

### Extra Mode / Advanced Features
See `EXTRA_MODE_README.md`, `UPSCALE_PROJECT_CREATION_EXTRAMODE_README.md`, and `QUICK_REFERENCE_EXTRA_MODE.md` for details on extra-mode project creation and advanced processing options.

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

## Contributing
Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests.
