# Setup script for drone_metashape with Python 3.11
Write-Host "=== Setting up drone_metashape Environment ===" -ForegroundColor Green
Write-Host ""

# Check if conda is available
try {
    $condaVersion = conda --version 2>$null
    Write-Host "Found conda: $condaVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Conda not found. Please install Anaconda or Miniconda first." -ForegroundColor Red
    exit 1
}

# Check if environment already exists
$envExists = conda info --envs | Select-String "upscale-drone"

if (-not $envExists) {
    Write-Host "Creating conda environment with Python 3.11..." -ForegroundColor Yellow
    conda create -n upscale-drone python=3.11 -y

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create conda environment" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Conda environment 'upscale-drone' already exists" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Next Steps ===" -ForegroundColor Cyan
Write-Host "1. Open a new PowerShell window"
Write-Host "2. Navigate to the repository:"
Write-Host "   cd '<path-to>\drone_metashape'"
Write-Host "3. Activate the environment:"
Write-Host "   conda activate upscale-drone"
Write-Host "4. Install dependencies:"
Write-Host "   pip install -r requirements.txt"
Write-Host "5. (Optional) Install Metashape wheel:"
Write-Host "   pip install wheels\Metashape-2.1.4-cp37.cp38.cp39.cp310.cp311-none-win_amd64.whl"
Write-Host "6. Verify setup:"
Write-Host "   python scripts\setup\setup_environment.py"
Write-Host ""
Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
