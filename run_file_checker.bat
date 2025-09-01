@echo off
REM Comprehensive File Checker for Drone Processing
REM This batch file runs the Python file checker script

echo Comprehensive File Checker for Drone Metashape Processing
echo ==========================================================

REM Set default base directory - MODIFY THIS PATH TO YOUR DATA LOCATION
set DEFAULT_BASE_DIR=E:\Share

REM Check if default directory exists
if exist "%DEFAULT_BASE_DIR%" (
    echo Using default base directory: %DEFAULT_BASE_DIR%
    set BASE_DIR=%DEFAULT_BASE_DIR%
) else (
    echo Default directory %DEFAULT_BASE_DIR% not found.
    set /p BASE_DIR="Enter base directory containing site folders: "
)

REM Generate timestamp for output files
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "timestamp=%YYYY%%MM%%DD%_%HH%%Min%%Sec%"

REM Set output file names
set "OUTPUT_CSV=drone_file_check_results_%timestamp%.csv"
set "OUTPUT_TXT=drone_file_check_report_%timestamp%.txt"

echo.
echo Running file checker...
echo Output files will be:
echo   CSV: %OUTPUT_CSV%
echo   TXT: %OUTPUT_TXT%
echo.

REM Run the Python script
python "%~dp0comprehensive_file_checker.py" "%BASE_DIR%" --output-csv "%OUTPUT_CSV%" --output-txt "%OUTPUT_TXT%"

if %errorlevel% equ 0 (
    echo.
    echo ===================================
    echo File check completed successfully!
    echo ===================================
    echo.
    echo Results saved to:
    echo   CSV: %OUTPUT_CSV%
    echo   TXT: %OUTPUT_TXT%
    echo.
    echo Opening report files...
    start "" "%OUTPUT_TXT%"
    timeout /t 2 /nobreak >nul
    start "" "%OUTPUT_CSV%"
) else (
    echo.
    echo ===================================
    echo Error occurred during file check!
    echo ===================================
)

echo.
pause
