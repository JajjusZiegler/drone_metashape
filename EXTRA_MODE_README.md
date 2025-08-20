# Robust Project Creator - Extra Mode

The Robust Project Creator now supports an "extra mode" that provides enhanced flexibility for working with new site names and custom project directories while maintaining all existing functionality.

## Standard Mode vs Extra Mode

### Standard Mode (Default)
- Uses predefined site name mappings from the comprehensive site mappings dictionary
- Project directories are determined by the existing mapping system
- Best for processing known Upscale campaign sites

### Extra Mode (--extra-mode flag)
- Handles any site names, even those not in the predefined mappings
- Supports custom project directory names via CSV column
- Falls back to fuzzy matching and auto-generated names when needed
- Ideal for new datasets, different campaigns, or custom project organization

## Usage Examples

### Basic Extra Mode
```bash
python robust_project_creator.py input.csv --extra-mode
```

### Extra Mode with Custom Paths
```bash
python robust_project_creator.py input.csv --extra-mode \
    --rgb-path "D:/my_drone_data/RGB" \
    --multispec-path "D:/my_drone_data/Multispec" \
    --project-path "D:/my_projects"
```

### Extra Mode with Dry Run
```bash
python robust_project_creator.py input.csv --extra-mode --dry-run
```

## CSV Format for Extra Mode

The extra mode supports an optional `custom_project_dir` column in your CSV:

```csv
date,site,rgb,multispec,sunsens,custom_project_dir
2024-07-15,New Forest Site,C:/data/rgb/new_forest,C:/data/multispec/new_forest,redeye,CustomForest_Analysis
2024-07-16,Coastal Research Area,C:/data/rgb/coastal,C:/data/multispec/coastal,dual,Marine_Ecosystem_Study
2024-07-17,Urban Canopy Study,C:/data/rgb/urban,C:/data/multispec/urban,redeye,
2024-07-18,Mountain Vegetation,C:/data/rgb/mountain,C:/data/multispec/mountain,dual,Alpine_Research_Project
```

### Column Descriptions:
- **date**: Flight date (required)
- **site**: Site name - can be any name, not limited to predefined mappings (required)
- **rgb**: RGB data path (required)
- **multispec**: Multispectral data path (required)
- **sunsens**: Sun sensor configuration (required)
- **custom_project_dir**: Custom project directory name (optional)

## Project Directory Behavior

### When `custom_project_dir` is provided:
- Uses the exact custom directory name
- Creates: `project_base_path/custom_project_dir/date/`
- Project file: `metashape_project_custom_project_dir_date.psx`

### When `custom_project_dir` is empty or missing:
1. **First**: Tries predefined site mappings (if site exists in mappings)
2. **Second**: Tries fuzzy matching with existing project folders
3. **Third**: Creates auto-generated directory based on site name
   - Sanitizes site name (spaces → underscores, lowercase)
   - Creates: `project_base_path/sanitized_site_project/date/`
   - Project file: `metashape_project_sanitized_site_date.psx`

## Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `input_csv` | Input CSV file path | Required |
| `--extra-mode` | Enable extra mode | False |
| `--dry-run` | Validate without creating projects | False |
| `--output` | Custom output CSV path | Auto-generated |
| `--rgb-path` | Custom RGB base path | M:/working_package_2/2024_dronecampaign/01_data/P1 |
| `--multispec-path` | Custom Multispec base path | M:/working_package_2/2024_dronecampaign/01_data/Micasense |
| `--project-path` | Custom project base path | M:/working_package_2/2024_dronecampaign/02_processing/metashape_projects/Upscale_Metashapeprojects |

## Output CSV

The output CSV includes all input columns plus:
- **project_path**: Resolved project file path
- **image_load_status**: Processing status
- **custom_project_dir**: Custom directory used (in extra mode)

## Examples

### Example 1: University Research Project
```bash
python robust_project_creator.py university_sites.csv --extra-mode \
    --project-path "C:/University_Research/Metashape_Projects"
```

### Example 2: Custom Data Paths
```bash
python robust_project_creator.py field_study.csv --extra-mode \
    --rgb-path "E:/FieldData/RGB_Images" \
    --multispec-path "E:/FieldData/Multispectral" \
    --project-path "E:/Analysis/Projects"
```

### Example 3: Validation Only
```bash
python robust_project_creator.py new_campaign.csv --extra-mode --dry-run
```

## Benefits of Extra Mode

1. **Flexibility**: Handle any site names without predefined mappings
2. **Organization**: Use meaningful project directory names
3. **Compatibility**: Works with existing standard mode features
4. **Fallback**: Robust fallback mechanisms for missing information
5. **Validation**: Full dry-run support for testing configurations

## Notes

- Extra mode maintains all existing functionality (fuzzy matching, path validation, etc.)
- RGB and Multispec paths still use the same resolution logic as standard mode
- Custom paths override default Upscale campaign paths
- Output filenames include mode indicator (`_extra` for extra mode)
- All logging includes mode information for clarity
