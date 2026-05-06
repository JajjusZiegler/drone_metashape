@echo off
echo === Setting up drone_metashape Environment ===
echo.

REM Check if conda environment exists
conda info --envs | findstr upscale-drone >nul
if %errorlevel% neq 0 (
    echo Creating conda environment with Python 3.11...
    conda create -n upscale-drone python=3.11 -y
    if %errorlevel% neq 0 (
        echo Failed to create conda environment
        pause
        exit /b 1
    )
) else (
    echo Conda environment 'upscale-drone' already exists
)

echo.
echo Activating environment...
call conda activate upscale-drone

echo.
echo Checking Python version...
python --version

echo.
echo Installing requirements...
pip install -r requirements.txt

echo.
echo === Setup Complete ===
echo To activate in future sessions:
echo   conda activate upscale-drone
echo.
pause
