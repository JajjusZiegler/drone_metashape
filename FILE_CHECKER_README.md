# Drone Processing File Checker Tools

This directory contains tools to check for expected output files from drone processing workflows. These tools help identify where additional processing work might be needed.

## 🎯 What These Tools Check For

The file checkers scan all sites and dates looking for these important exported files:

### Essential Files:
- **Orthophotos (.tif format)**
  - RGB orthomosaics
  - Multispectral orthomosaics  
- **Processing Reports (.pdf format)**
  - RGB processing reports
  - Multispectral processing reports
- **3D Models (.obj format)**
  - 3D mesh models from processing

### Additional Files (comprehensive checker):
- DEM files (.tif)
- Reference marker files
- Camera position files
- Processing status markers

## 🚀 Quick Start

### Option 1: Simple Check (Recommended)
```bash
# Windows
double-click: quick_check.bat

# Or from command line
python simple_file_checker.py "E:\Share"
```

### Option 2: Comprehensive Check
```bash
# Windows  
double-click: run_file_checker.bat

# Or from command line
python comprehensive_file_checker.py "E:\Share"
```

## 📁 Expected Directory Structure

The tools expect your data to be organized like this:
```
Base Directory/
├── Site1/
│   ├── 20240815/
│   │   ├── exports/
│   │   │   ├── 20240815_Site1_rgb_ortho_1cm.tif
│   │   │   ├── 20240815_Site1_multispec_ortho_5cm.tif
│   │   │   ├── 20240815_Site1_rgb_report.pdf
│   │   │   ├── 20240815_Site1_multispec_report.pdf
│   │   │   └── 20240815_Site1_model.obj
│   │   └── references/
│   └── 20240816/
│       └── exports/
├── Site2/
│   └── 20240820/
│       └── exports/
└── Site3/
    ├── 20240825/
    └── 20240826/
```

## 📊 Output Files

Both tools generate reports showing:

### Console Output:
- ✅ Complete sites (≥90% of expected files)
- 🟡 Mostly complete sites (70-89%)
- 🟠 Partial sites (40-69%)
- ❌ Incomplete sites (<40%)

### CSV Report:
- Detailed spreadsheet with all results
- File-by-file status for each site/date
- Can be opened in Excel for analysis

### Text Report (comprehensive only):
- Detailed summary report
- Lists specific missing files
- Highlights sites needing attention

## 🛠️ Tools Description

### simple_file_checker.py
- **Fast and focused** - checks only essential files
- **Easy to read output** with emojis and color coding
- **Perfect for daily checks** and quick overviews
- Generates CSV report for Excel analysis

### comprehensive_file_checker.py  
- **Detailed analysis** of all file types
- **Advanced reporting** with statistics and completion metrics
- **Flexible configuration** for different file patterns
- **Command-line options** for specific sites/dates

## 🔧 Configuration

### Change Default Directory
Edit the batch files to change the default search directory:
```batch
REM In quick_check.bat or run_file_checker.bat
set "DEFAULT_DIRS=E:\Share;YOUR_PATH_HERE;D:\Share"
```

### Customize File Patterns
Edit the Python scripts to look for different file patterns:
```python
# In simple_file_checker.py
rgb_ortho_patterns = ["*rgb*ortho*.tif", "*your_pattern*.tif"]
```

## 💡 Usage Tips

### For Daily Monitoring:
- Use `quick_check.bat` for fast daily checks
- Focus on the "Needs Attention" section

### For Detailed Analysis:
- Use `run_file_checker.bat` for comprehensive reports
- Open the CSV file in Excel for sorting/filtering
- Use the text report for management summaries

### For Specific Sites:
```bash
# Check only one site
python comprehensive_file_checker.py "E:\Share" --site "YourSite" --date "20240815"
```

### For Automation:
```bash
# Run without interactive prompts
python simple_file_checker.py "E:\Share" > daily_check.log 2>&1
```

## 🐛 Troubleshooting

### "Directory not found" errors:
- Check that your base directory path is correct
- Ensure you have read permissions to the directory
- Try using the full absolute path

### "No sites found" warnings:
- Verify your directory structure matches the expected format
- Check that site folders contain date subdirectories
- Look for exports/export folders within date directories

### Python errors:
- Ensure Python 3.6+ is installed
- The scripts handle missing optional libraries gracefully
- For enhanced features, install: `pip install pandas humanize`

## 📈 Understanding the Results

### Completion Percentages:
- **90-100%**: Complete ✅ - All essential files present
- **70-89%**: Mostly Done 🟡 - Minor files missing  
- **40-69%**: Partial 🟠 - Some major files missing
- **0-39%**: Incomplete ❌ - Significant work needed

### Common Issues:
- **Missing exports folder**: Processing may not have started
- **Missing orthophotos**: Orthomosaic generation failed
- **Missing reports**: Processing completed but reports not generated
- **Missing 3D models**: Model export step was skipped

## 🔄 Integration with Processing Workflow

These tools are designed to work with the existing drone processing scripts:
- `metashape_proc_Upscale.py`
- `DEMtests.py`
- Processing workflow scripts

Run the file checker after batch processing to identify any failed or incomplete jobs.

---

*For questions or issues, check the detailed error messages in the console output or generated log files.*
