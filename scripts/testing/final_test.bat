@echo off
echo === Final Comprehensive Test — drone_metashape ===
echo.

REM Activate the environment
call conda activate upscale-drone

echo ✅ Environment: Python 3.11 with Metashape 2.1.4
python -c "import sys; print('Python: ' + sys.version.split()[0])"
python -c "import Metashape; print('Metashape: ' + Metashape.app.version)"

echo.
echo === Test 1: File Structure ===
python tests\test_setup_paths.py

echo.
echo === Test 2: Metashape Installation ===
python scripts\testing\test_metashape_installation.py

echo.
echo === Test 3: Core Module Imports ===
python -c "
import sys
sys.path.insert(0, 'src')
try:
    import core.upd_micasense_pos_filename as m
    print('PASS core.upd_micasense_pos_filename')
except Exception as e:
    print('FAIL core.upd_micasense_pos_filename:', e)
try:
    import core.TransformHeight as m
    print('PASS core.TransformHeight')
except Exception as e:
    print('FAIL core.TransformHeight:', e)
"

echo.
echo === FINAL RESULT ===
echo All tests run. Review output above for any FAIL lines.
echo.
pause
