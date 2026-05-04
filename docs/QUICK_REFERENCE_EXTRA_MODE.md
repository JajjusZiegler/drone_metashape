# UpscaleProjectCreation_ExtraMode - Feature Comparison

## Quick Reference: Standard Mode vs Extra Mode

### When to Use Each Mode

| Use Case | Mode | Command |
|----------|------|---------|
| Process known Upscale campaign sites | Standard | `python UpscaleProjectCreation_ExtraMode.py input.csv` |
| Process new/unknown sites | Extra | `python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode` |
| Custom project organization | Extra | `python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode --project-path "D:/MyProjects"` |
| Different data locations | Either | `python UpscaleProjectCreation_ExtraMode.py input.csv --rgb-path "E:/RGB" --multispec-path "E:/MS"` |

### Feature Comparison

| Feature | Standard Mode | Extra Mode |
|---------|---------------|------------|
| **Site Name Support** | Predefined sites only | Any site names |
| **Project Directory** | From site mappings | Custom or auto-generated |
| **Path Correction** | ✅ Built-in corrections | ✅ Enhanced fuzzy matching |
| **CSV Custom Column** | ❌ Not supported | ✅ `custom_project_dir` |
| **New Site Handling** | ❌ Rejected | ✅ Auto-creates directories |
| **Backward Compatibility** | ✅ Original behavior | ✅ Maintains original when possible |

### Examples

#### Standard Mode Processing
```csv
date,site,rgb,multispec,sunsens
2024-07-18,wangen_zh,M:/data/P1/wangen_zh/2024-07-18,M:/data/Micasense/wangen_zh/2024-07-18,false
2024-07-19,lwf_davos,M:/data/P1/lwf_davos/2024-07-19,M:/data/Micasense/lwf_davos/2024-07-19,true
```
**Result**: Uses predefined mappings → `WangenBrüttisellen_treenet` and `Davos_LWF` project folders

#### Extra Mode Processing  
```csv
date,site,rgb,multispec,sunsens,custom_project_dir
2024-07-18,New Forest Site,M:/data/P1/new_forest/2024-07-18,M:/data/Micasense/new_forest/2024-07-18,false,Forest_Study_2024
2024-07-19,Research Plot A,M:/data/P1/plot_a/2024-07-19,M:/data/Micasense/plot_a/2024-07-19,true,
```
**Result**: Uses `Forest_Study_2024` and auto-generates `research_plot_a_project` folders

### Migration Strategy

1. **Start with Standard Mode**: Test existing workflows
2. **Add Extra Mode Gradually**: Use for new sites as needed  
3. **Full Custom Setup**: Migrate to custom paths when ready

### Command Templates

```bash
# Standard workflow
python UpscaleProjectCreation_ExtraMode.py data.csv

# New sites with existing infrastructure  
python UpscaleProjectCreation_ExtraMode.py data.csv --extra-mode

# Complete custom setup
python UpscaleProjectCreation_ExtraMode.py data.csv --extra-mode \
    --rgb-path "E:/DroneData/RGB" \
    --multispec-path "E:/DroneData/Multispec" \
    --project-path "E:/Projects"

# Validation run
python UpscaleProjectCreation_ExtraMode.py data.csv --extra-mode --dry-run
```
