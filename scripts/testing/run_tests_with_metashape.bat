@echo off
echo === Running drone_metashape Tests with Metashape ===
echo.

REM Activate the environment
call conda activate upscale-drone

echo Current environment:
python --version
python -c "import Metashape; print('Metashape ' + Metashape.app.version + ' available')"

echo.
echo === Running Metashape Installation Test ===
python scripts\testing\test_metashape_installation.py

echo.
echo === Running Setup Path Test ===
python tests\test_setup_paths.py

echo.
echo Tests complete!
pause
