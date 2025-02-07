import csv
import subprocess
import sys
import os
from pathlib import Path

# Path to the CSV file containing the arguments
csv_file_path = r"U:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\logbook_test_RGBandMulti_dataproject_created.csv"

# Path to the target Python script you want to call
target_script_path = r"C:\Users\Administrator\drone_metashape\metashape_proc_Upscale_copy.py"

# Hardcoded CRS (Modify this to your desired coordinate system)
HARDCODED_CRS = "2056"  # might be issues with swiss coordinates stick to WGS84
def check_output_files_exist(project_path):
    """Check if expected output files exist"""
    project_dir = Path(project_path).parent
    expected_files = [
        project_dir /  f"{Path(project_path).stem}_rgb_ortho_01.tif",
        project_dir /  f"{Path(project_path).stem}_multispec_ortho_05.tif",
        project_dir /  f"{Path(project_path).stem}_rgb_report.pdf",
        project_dir /  f"{Path(project_path).stem}_multispec_report.pdf"
    ]
    return all(f.exists() for f in expected_files)

def ensure_columns_exist(fieldnames):
    """Ensure the new columns are present in the CSV"""
    new_columns = ['ortho_rgb', 'ortho_ms', 'report_rgb', 'report_ms', 'status']
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)
    return fieldnames

def update_csv_row(project_path, output_paths):
    """Update CSV with output paths and status"""
    updated_rows = []
    with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        fieldnames = csv_reader.fieldnames + ['ortho_rgb', 'ortho_ms', 'report_rgb', 'report_ms', 'status']
        
        for row in csv_reader:
            if row['project_path'] == project_path:
                # Update output paths
                row.update({
                    'ortho_rgb': output_paths.get('ortho_rgb', ''),
                    'ortho_ms': output_paths.get('ortho_ms', ''),
                    'report_rgb': output_paths.get('report_rgb', ''),
                    'report_ms': output_paths.get('report_ms', ''),
                    'status': 'success'
                })
            updated_rows.append(row)

    # Write updated CSV
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

# Open the CSV and read rows
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    
    for row in csv_reader:
        project_path = row['project_path']
        
        # Skip processing if outputs exist
        if check_output_files_exist(project_path):
            print(f"Skipping already processed project: {project_path}")
            continue
            
        # Skip if required arguments are missing
        required_args = {'project_path', 'date', 'site'} # Removed 'crs' from required args
        missing_args = [arg for arg in required_args if not row.get(arg)]
        
        if missing_args:
            print(f"Skipping row due to missing required arguments: {missing_args} - Row: {row}")
            continue
        
        cmd = ["python", target_script_path]
        cmd.extend(["-proj_path", row['project_path']])
        cmd.extend(["-date", row['date']])
        cmd.extend(["-site", row['site']])
        cmd.extend(["-crs", HARDCODED_CRS])  # Using hardcoded CRS instead of row['crs']
        
        # Append optional arguments
        if row.get('multispec'):
            cmd.extend(["-multispec", row['multispec']])
        if row.get('rgb'):
            cmd.extend(["-rgb", row['rgb']])
        if row.get('sunsens', '').lower() == 'true':
            cmd.append("-sunsens")
        # Add test flag    
        cmd.append("-test")
        
        # Add test flag
        #cmd.append("-test")

# Print the command for debugging purposes
print("Running command:", " ".join(cmd))

try:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    output_paths = {}
    for line in result.stdout.split('\n'):
        if line.startswith('OUTPUT_ORTHO_RGB:'):
            output_paths['ortho_rgb'] = line.split(':', 1)[1].strip()
        elif line.startswith('OUTPUT_ORTHO_MS:'):
            output_paths['ortho_ms'] = line.split(':', 1)[1].strip()
        elif line.startswith('OUTPUT_REPORT_RGB:'):
            output_paths['report_rgb'] = line.split(':', 1)[1].strip()
        elif line.startswith('OUTPUT_REPORT_MS:'):
            output_paths['report_ms'] = line.split(':', 1)[1].strip()
    
    update_csv_row(project_path, output_paths)
    
except subprocess.CalledProcessError as e:
    print(f"Error processing {project_path}: {e}")
    # Update CSV with error status
    update_csv_row(project_path, {'status': 'error'})