# UpscaleProjectCreation_ExtraMode - Enhanced Project Creation Script

This script extends the original `UpscaleProjectCreation2025.py` with flexible "extra mode" functionality that allows processing new sites and custom project directories while maintaining all original capabilities.

## Key Features

### Standard Mode (Original Functionality)
- Uses predefined site mappings from the SITE_MAPPING dictionary
- Automatic path correction for known site name mismatches
- Project directories follow the established Upscale campaign structure
- Full backward compatibility with existing workflows

### Extra Mode (New Functionality)
- **New Site Support**: Process any site names, not limited to predefined mappings
- **Custom Project Directories**: Specify custom project folder names via CSV column
- **Flexible Base Paths**: Override default RGB, Multispec, and Project base paths
- **Auto-Generated Names**: Automatically create project directories for new sites
- **Enhanced Fuzzy Matching**: Improved path resolution for mismatched names

## Usage Examples

### Basic Usage (Standard Mode)
```bash
# Process with original functionality
python UpscaleProjectCreation_ExtraMode.py input.csv

# Dry run to validate without creating projects
python UpscaleProjectCreation_ExtraMode.py input.csv --dry-run
```

### Extra Mode Usage
```bash
# Enable extra mode for new sites
python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode

# Extra mode with custom project directory
python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode --project-path "D:/MyProjects"

# Complete custom setup
python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode \
    --rgb-path "E:/RGB_Data" \
    --multispec-path "E:/Multispec_Data" \
    --project-path "E:/Projects"

# Dry run in extra mode
python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode --dry-run
```

## CSV Format

### Standard CSV Format
```csv
date,site,rgb,multispec,sunsens
2024-07-15,wangen_zh,M:/data/P1/wangen_zh/2024-07-15,M:/data/Micasense/wangen_zh/2024-07-15,true
```

### Extra Mode CSV Format (with optional custom_project_dir column)
```csv
date,site,rgb,multispec,sunsens,custom_project_dir
2024-07-15,New Research Forest,M:/data/P1/new_forest/2024-07-15,M:/data/Micasense/new_forest/2024-07-15,true,Forest_Research_2024
2024-07-16,Coastal Site,M:/data/P1/coastal/2024-07-16,M:/data/Micasense/coastal/2024-07-16,false,Marine_Study
2024-07-17,Urban Analysis,M:/data/P1/urban/2024-07-17,M:/data/Micasense/urban/2024-07-17,true,
2024-07-18,wangen_zh,M:/data/P1/wangen_zh/2024-07-18,M:/data/Micasense/wangen_zh/2024-07-18,false,
```

### Column Descriptions
- **date**: Flight date (YYYY-MM-DD format) - Required
- **site**: Site name - can be any name in extra mode - Required  
- **rgb**: Path to RGB image data - Required
- **multispec**: Path to multispectral image data - Required
- **sunsens**: Sun sensor usage (true/false) - Required
- **custom_project_dir**: Custom project directory name (optional, extra mode only)

## Project Directory Behavior

### Standard Mode
1. Uses SITE_MAPPING to find predefined project folder
2. Falls back to fuzzy matching if mapping not found
3. Creates projects in existing Upscale campaign structure

### Extra Mode
1. **With custom_project_dir**: Uses exact custom directory name
2. **Without custom_project_dir**: 
   - First tries predefined site mappings
   - Then tries fuzzy matching with existing folders
   - Finally creates auto-generated directory: `{sanitized_site}_project`

### Project File Naming
- **Standard mode**: `metashape_project_{site_folder_name}_{date}.psx`
- **Extra mode (custom dir)**: `metashape_project_{custom_project_dir}_{date}.psx`
- **Extra mode (auto-generated)**: `metashape_project_{sanitized_site}_{date}.psx`

## Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `input_csv` | Input CSV file path | Required |
| `--extra-mode` | Enable extra mode functionality | False |
| `--dry-run` | Validate without creating projects | False |
| `--output` | Custom output CSV path | Auto-generated |
| `--rgb-path` | Custom RGB base path | M:/working_package_2/2024_dronecampaign/01_data/P1 |
| `--multispec-path` | Custom Multispec base path | M:/working_package_2/2024_dronecampaign/01_data/Micasense |
| `--project-path` | Custom project base path | M:/working_package_2/2024_dronecampaign/02_processing/metashape_projects/Upscale_Metashapeprojects |

## Output CSV Format

The output CSV includes all input columns plus:
- **project_path**: Full path to the created/planned project file
- **image_load_status**: Status of project creation (success, error, skipped, etc.)
- **custom_project_dir**: Custom directory used (extra mode only)

## Error Handling & Path Correction

The script includes robust error handling and automatic path correction:

1. **Path Validation**: Checks if RGB and Multispec paths exist
2. **Automatic Correction**: Uses predefined corrections for known mismatches
3. **Fuzzy Matching**: Finds similar folder names when exact matches fail
4. **Graceful Fallback**: Creates meaningful error messages for unresolvable paths

## Examples

### Example 1: University Research Project
```bash
python UpscaleProjectCreation_ExtraMode.py university_data.csv --extra-mode \
    --project-path "C:/University_Research/Drone_Projects"
```

### Example 2: Multi-Site Campaign with Custom Paths
```bash
python UpscaleProjectCreation_ExtraMode.py campaign_2025.csv --extra-mode \
    --rgb-path "D:/DroneData/RGB" \
    --multispec-path "D:/DroneData/Multispec" \
    --project-path "D:/Analysis/Metashape_Projects"
```

### Example 3: Validation Run for New Dataset
```bash
python UpscaleProjectCreation_ExtraMode.py new_sites.csv --extra-mode --dry-run
```

## Dependencies

- **Required**: Python 3.7+, pathlib, csv, argparse, logging
- **Optional**: Metashape Pro (for project creation), exifread (for EXIF validation)
- **Note**: Script runs in validation-only mode if Metashape is not available

## Migration from Original Script

The new script is fully backward compatible:

1. **Direct replacement**: Can replace `UpscaleProjectCreation2025.py` without changes to existing workflows
2. **Same output format**: Produces identical results in standard mode
3. **Enhanced capabilities**: Adds extra mode functionality when needed

## Logging and Debugging

The script provides comprehensive logging:
- **INFO level**: General progress and path corrections
- **WARNING level**: Missing paths and fallback operations  
- **ERROR level**: Critical failures and validation errors
- **Summary**: Final status counts for all processed projects

## Notes

- Extra mode maintains all original functionality (site mappings, path corrections, etc.)
- Custom paths override default Upscale campaign paths completely
- Output files include mode indicators (`_extra` suffix for extra mode)
- All path resolution uses the same robust algorithms as the original script
- Dry-run mode works in both standard and extra modes for validation
