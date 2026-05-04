@echo off
call conda activate upscale-drone
python -c "import Metashape; print('SUCCESS: Metashape ' + Metashape.app.version + ' is ready!')"
pause
