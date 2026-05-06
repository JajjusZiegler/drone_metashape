@echo off
REM Simple Drone File Checker
REM Quick check for orthophotos, reports, and 3D models

echo 🚁 Simple Drone Processing File Checker
echo ==========================================

REM Check if Python script exists
if not exist "%~dp0simple_file_checker.py" (
    echo ❌ Error: simple_file_checker.py not found in current directory!
    pause
    exit /b 1
)

REM Try default directories first
set "DEFAULT_DIRS=E:\Share;M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects;D:\Share;F:\Share"

echo 📁 Looking for data directories...
for %%D in (%DEFAULT_DIRS%) do (
    if exist "%%D" (
        echo ✅ Found: %%D
        set "BASE_DIR=%%D"
        goto :found_dir
    )
)

REM If no default directory found, ask user
echo ⚠️  No default directories found.
set /p BASE_DIR="📂 Enter base directory containing site folders: "

:found_dir
if not exist "%BASE_DIR%" (
    echo ❌ Error: Directory does not exist: %BASE_DIR%
    pause
    exit /b 1
)

echo.
echo 🔍 Checking files in: %BASE_DIR%
echo.

REM Run the Python script
python "%~dp0simple_file_checker.py" "%BASE_DIR%"

echo.
echo ✅ File check complete!
echo.
pause
