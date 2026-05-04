# Project Validation and Rebuild Strategy

## Immediate Action Plan

Based on your corrected CSV analysis, here are the projects that **definitely need to be rebuilt** because they were created with incorrect paths:

### 🚨 **High Priority - Projects with Path Corrections**

These projects were created with the wrong folder paths and likely contain incorrect or missing images:

#### 1. **Wangen Brüttisellen** (2 projects)
- `20250514, Wangen Brüttisellen` 
- `20250619, Wangen Brüttisellen`
- **Issue**: Created using `Wangen Brüttisellen` folders, should use `wangen_zh`
- **Action**: Must rebuild with correct paths

#### 2. **Sanasilva Sites** (6 projects)
- `20250409, Sanasilva-50845`
- `20250409, Sanasilva-50877`
- `20250515, Sanasilva-50845`
- `20250515, Sanasilva-50877`
- `20250610, Sanasilva-50845` 
- `20250610, Sanasilva-50877`
- **Issue**: Created using `Sanasilva-XXXXX` folders, should use `sanasilva_XXXXX`
- **Action**: Must rebuild with correct paths

#### 3. **LWF-Davos** (2 projects)
- `20250527, LWF-Davos`
- `20250710, LWF-Davos`
- **Issue**: Created using `LWF-Davos` folder, should use `lwf_davos`
- **Action**: Must rebuild with correct paths

#### 4. **Martelloskop** (2 projects)
- `20250606, Martelloskop`
- `20250710, Martelloskop`
- **Issue**: Created using `Martelloskop` folder, should use `marteloskop`
- **Action**: Must rebuild with correct paths

#### 5. **Stillberg** (2 projects)
- `20250606, Stillberg`
- `20250710, Stillberg`
- **Issue**: Multispec path case mismatch (`Stillberg` vs `stillberg`)
- **Action**: Must rebuild with correct multispec paths

### 📋 **Summary**
- **Total projects needing rebuild**: 14 out of 45
- **Percentage affected**: 31%
- **Main cause**: Site name mismatches between CSV and actual folder structure

## Step-by-Step Rebuild Process

### Step 1: Create Rebuild List
Create a CSV with only the problematic projects:

```csv
date,site,rgb,multispec,sunsens,project_path,image_load_status
20250514,Wangen Brüttisellen,M:\working_package_2\2024_dronecampaign\01_data\P1\wangen_zh\20250514,M:\working_package_2\2024_dronecampaign\01_data\Micasense\wangen_zh\20250514,False,M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\WangenBrüttisellen_treenet\20250514\metashape_project_WangenBrüttisellen_treenet_20250514.psx,needs_rebuild
20250619,Wangen Brüttisellen,M:\working_package_2\2024_dronecampaign\01_data\P1\wangen_zh\20250619,M:\working_package_2\2024_dronecampaign\01_data\Micasense\wangen_zh\20250619,False,M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\WangenBrüttisellen_treenet\20250619\metashape_project_WangenBrüttisellen_treenet_20250619.psx,needs_rebuild
... (continue for all 14 problematic projects)
```

### Step 2: Backup Existing Projects (Optional)
Before rebuilding, you might want to backup the incorrect projects:
```bash
# Create backup folder
mkdir "M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\_BACKUP_INCORRECT_PROJECTS"

# Move problematic projects to backup (do this for each site/date)
move "M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\WangenBrüttisellen_treenet\20250514" "M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\_BACKUP_INCORRECT_PROJECTS\"
```

### Step 3: Rebuild Projects
Use the robust project creator to rebuild only the problematic projects:
```bash
python robust_project_creator.py rebuild_list.csv
```

### Step 4: Verify Rebuilt Projects
After rebuilding, verify that:
- ✅ Projects contain correct RGB images from `wangen_zh`, `sanasilva_50845`, etc.
- ✅ Projects contain correct Multispec images from proper folders
- ✅ Camera counts match expected numbers
- ✅ No missing or extra images

## Checking Your Processing Scripts

Since you mentioned your processing scripts ran over incorrect projects, you should also:

1. **Check processed outputs** from these 14 projects
2. **Delete any orthos/DEMs** generated from incorrect projects
3. **Re-run processing** after rebuilding projects with correct images

## Commands to Execute

1. **Create the rebuild list CSV** (use the corrected paths from your CSV for the 14 problematic projects)

2. **Rebuild projects**:
```bash
python robust_project_creator.py rebuild_list.csv
```

3. **Verify results** by checking a few projects manually in Metashape

## Prevention for Future

- Always use the `robust_project_creator.py` script for new projects
- It automatically handles path mismatches
- Test with a few projects first before batch processing
- Keep naming conventions consistent

This focused approach will fix your immediate issues without unnecessarily rebuilding the 31 projects that were created correctly.
