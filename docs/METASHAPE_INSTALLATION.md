# Metashape Python API Installation Guide

This guide covers the installation and setup of the Agisoft Metashape Python API for the drone_metashape toolkit.

## Overview

The Metashape Python API (wheel file) provides access to Agisoft Metashape Pro's photogrammetry capabilities from Python. Metashape 2.1.4 supports **Python 3.7–3.11** (Windows x64).

> **⚠️ Python 3.12+ is NOT supported by Metashape 2.1.4.** Use Python 3.11 or earlier.

---

## Quick Setup (Recommended)

```powershell
# Run in PowerShell from the repository root:
scripts\setup\setup_conda_env.ps1
```

Follow the instructions to create a compatible conda environment, then install dependencies and the Metashape wheel.

---

## Manual Installation Steps

### 1. Create Compatible Python Environment

```bash
conda create -n upscale-drone python=3.11 -y
conda activate upscale-drone
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install the Metashape Python API

```bash
pip install wheels/Metashape-2.1.4-cp37.cp38.cp39.cp310.cp311-none-win_amd64.whl
```

Or download the wheel from the [Agisoft website](https://www.agisoft.com/downloads/installer/) and install locally.

### 4. Verify Installation

```bash
python scripts\testing\quick_metashape_check.py
python scripts\testing\test_metashape_installation.py
```

---

## License Requirements

A valid **Metashape Pro** license is required for full processing functionality.

- ✅ Basic operations and validation work without a license.
- ❌ Processing operations (alignment, dense cloud, orthomosaics) require a license.

### License Activation

1. Install the Metashape Pro GUI application.
2. Activate your license through the GUI.
3. The Python API automatically uses the activated license.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ImportError: DLL load failed` | Install Microsoft Visual C++ Redistributable |
| License not found | Activate Metashape Pro GUI license first |
| Wrong Python version | Use `conda create -n upscale-drone python=3.11` |

---

## API Documentation

- **Local PDF**: `docs/metashape_python_api_2_1_0.pdf`
- **Online**: [Agisoft Metashape Python Reference](https://www.agisoft.com/pdf/metashape_python_api_2_1_0.pdf)
