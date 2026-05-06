# Scripts Directory

Utility scripts for setting up and testing the drone_metashape environment.

## Setup Scripts (`setup/`)

| Script | Description |
|---|---|
| `setup_conda_env.ps1` | PowerShell — create conda environment with Python 3.11 |
| `setup_conda_env.bat` | Windows batch version of environment setup |
| `setup_environment.py` | Python — validate installation requirements |
| `install_metashape.bat` | Install Metashape Python API wheel |
| `activate_environment.ps1` | Quick activation script for future sessions |

### First-time Setup

```powershell
# Run from repository root in PowerShell
scripts\setup\setup_conda_env.ps1
```

Then in a new PowerShell window:

```bash
conda activate upscale-drone
pip install -r requirements.txt
# optionally install Metashape wheel:
# pip install wheels\Metashape-2.1.4-...-win_amd64.whl
python scripts\setup\setup_environment.py
```

---

## Testing Scripts (`testing/`)

| Script | Description |
|---|---|
| `test_metashape_installation.py` | Comprehensive Metashape installation test |
| `quick_metashape_check.py` | Quick Metashape availability check |
| `metashape_proc_widget_testing.py` | GUI widget prototype testing (requires Metashape GUI) |
| `run_tests_with_metashape.bat` | Run all tests in the conda environment |
| `final_test.bat` | End-to-end test suite |
| `confirm_success.bat` | Simple success confirmation |

### Run Tests

```bash
python scripts\testing\test_metashape_installation.py
python tests\test_setup_paths.py
```

---

## Notes

- All `.bat` / `.ps1` scripts target Windows.
- Conda/Anaconda must be installed before running setup scripts.
- Python 3.11 is recommended (Metashape 2.1.4 does not support 3.12+).
