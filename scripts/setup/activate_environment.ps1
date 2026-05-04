# Activate drone_metashape processing environment
conda activate upscale-drone
Write-Host "upscale-drone environment activated!" -ForegroundColor Green
Write-Host "Python version: $(python --version)"
Write-Host ""
Write-Host "Available commands:"
Write-Host "  python scripts\testing\test_metashape_installation.py   # Test Metashape"
Write-Host "  python scripts\setup\setup_environment.py               # Check setup"
Write-Host "  python src\core\batch_processor.py input.csv            # Batch processing"
Write-Host "  python src\core\UpscaleRunScript.py                     # Single-run launcher"
Write-Host ""
