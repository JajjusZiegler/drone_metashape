@echo off
echo === Installing Metashape in upscale-drone environment ===
echo.

REM Activate the environment
call conda activate upscale-drone

echo Current Python version:
python --version

echo.
echo Installing requirements...
pip install -r requirements.txt

echo.
echo Installing Metashape wheel...
pip install "wheels\Metashape-2.1.4-cp37.cp38.cp39.cp310.cp311-none-win_amd64.whl"

echo.
echo Testing Metashape import...
python scripts\testing\quick_metashape_check.py

echo.
echo Installation complete!
pause
