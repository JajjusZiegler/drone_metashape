# Robust Project Creation Tools

This document explains how to use the improved project creation tools that handle naming mismatches between CSV site names and actual folder structures.

## Problem Statement

Your original project creation scripts had issues with inconsistent naming between:
- CSV site names (e.g., "Wangen Brüttisellen", "Sanasilva-50845") 
- Actual folder names (e.g., "wangen_zh", "sanasilva_50845")

This caused projects to fail when trying to find the correct RGB and Multispec image folders.

## Solution Overview

Two new scripts have been created to handle this robustly:

1. **`fix_project_paths.py`** - Validates and corrects paths in existing CSV files
2. **`robust_project_creator.py`** - Creates Metashape projects with automatic path correction

## Script Details

### 1. fix_project_paths.py

**Purpose**: Validates and corrects paths in existing CSV files without creating projects.

**Usage**:
```bash
python fix_project_paths.py input.csv [--output output.csv]
```

**Features**:
- Automatically maps site names to correct folder names
- Uses fuzzy matching for unknown site names
- Creates a corrected CSV with both original and corrected paths
- Provides detailed logging of path corrections

**Example**:
```bash
python fix_project_paths.py "20250717_RGBandMulti_data_project_created.csv"
```
Output: `20250717_RGBandMulti_data_project_created_corrected.csv`

### 2. robust_project_creator.py

**Purpose**: Creates Metashape projects with automatic path correction and validation.

**Usage**:
```bash
# Dry run (validation only)
python robust_project_creator.py input.csv --dry-run

# Create projects
python robust_project_creator.py input.csv [--output output.csv]
```

**Features**:
- Same path resolution as fix_project_paths.py
- Can run without Metashape (validation mode)
- Actually creates Metashape projects when Metashape is available
- Handles all sensor offset configurations
- Comprehensive error handling

**Examples**:
```bash
# Validate paths only
python robust_project_creator.py "input.csv" --dry-run

# Create projects
python robust_project_creator.py "input.csv"
```

## Site Name Mappings

The scripts include comprehensive site name mappings for all known variations:

| CSV Site Name | RGB Folder | Multispec Folder | Project Folder |
|---------------|------------|------------------|----------------|
| Wangen Brüttisellen | wangen_zh | wangen_zh | WangenBrüttisellen_treenet |
| Sanasilva-50845 | sanasilva_50845 | sanasilva_50845 | Brüttelen_sanasilva50845 |
| Sanasilva-50877 | sanasilva_50877 | sanasilva_50877 | Schüpfen_sanasilva50877 |
| Martelloskop | marteloskop | marteloskop | Marteloskop |
| LWF-Davos | lwf_davos | lwf_davos | Davos_LWF |
| Stillberg | Stillberg | stillberg | Stillberg |

And many more...

## Path Resolution Strategy

The scripts use a multi-level approach to resolve paths:

1. **Direct Mapping**: Check predefined mappings first
2. **Fuzzy Matching**: Use normalized name matching (lowercase, underscore conversion)
3. **Partial Matching**: Find folders containing parts of the site name
4. **Word-based Matching**: Match individual words in site names

This ensures maximum compatibility with different naming conventions.

## Configuration

### Base Paths
The scripts are configured with these base paths:
```python
base_rgb_path = Path(r"M:/working_package_2/2024_dronecampaign/01_data/P1")
base_multispec_path = Path(r"M:/working_package_2/2024_dronecampaign/01_data/Micasense")
project_base_path = Path(r"M:/working_package_2/2024_dronecampaign/02_processing/metashape_projects/Upscale_Metashapeprojects")
```

### Adding New Site Mappings
To add new site mappings, edit the `_create_comprehensive_site_mappings()` method:

```python
"New Site Name": {
    "rgb": "actual_rgb_folder",
    "multispec": "actual_multispec_folder",
    "project": "actual_project_folder"
},
```

## CSV Output Format

Both scripts create CSV files with these columns:
- `date`: Original date
- `site`: Original site name
- `rgb`: Corrected RGB path
- `multispec`: Corrected Multispec path
- `sunsens`: Sun sensor flag
- `project_path`: Full project file path
- `image_load_status`: Status (success/error/skipped)
- `original_rgb`: Original RGB path (fix_project_paths.py only)
- `original_multispec`: Original Multispec path (fix_project_paths.py only)

## Logging and Error Handling

Both scripts provide comprehensive logging:
- Path corrections are logged with before/after values
- Missing folders are clearly identified
- Error conditions are properly handled and reported

## Usage Recommendations

1. **First Time Setup**: Use `fix_project_paths.py` to validate your CSV and understand path corrections
2. **Project Creation**: Use `robust_project_creator.py --dry-run` first, then run without dry-run to create projects
3. **Regular Use**: Use `robust_project_creator.py` directly for new datasets

## Error Handling

Common error scenarios and their handling:

| Error | Handling |
|-------|----------|
| RGB folder not found | Try fuzzy matching, report specific error |
| Multispec folder not found | Try fuzzy matching, report specific error |
| Project folder not resolved | Use mapping, create directory if needed |
| Invalid paths | Skip project, report error in CSV |
| Metashape license issues | Graceful degradation to validation mode |

## Troubleshooting

### Path Not Found Errors
1. Check if the base paths are correct
2. Verify folder names match available folders
3. Add new mappings if needed

### Project Creation Failures
1. Ensure Metashape license is activated
2. Check if image folders contain valid files
3. Verify project directory permissions

### New Site Names
1. Run with `--dry-run` first to see path resolution
2. Add explicit mappings for consistent results
3. Check fuzzy matching results in logs

This robust solution should eliminate the naming error issues you were experiencing with the WangenBrüttisellen site and any similar naming mismatches in the future.
