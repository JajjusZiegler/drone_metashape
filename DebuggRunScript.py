import csv
import sys
import logging
import glob
from pathlib import Path

# Configuration
csv_file_path = input("Enter the path to the CSV file: ")
target_script_path = r"C:\Users\admin\Documents\Python Scripts\drone_metashape\DEMtests.py"
HARDCODED_CRS = "2056"
TEST_FLAG_ENABLED = False
SIMULATION_MODE = True  # Set to True to simulate instead of running subprocess

# Logging setup
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def check_output_files_exist(project_path):
    project_dir = Path(project_path)
    output_file_patterns = ["*_rgb_ortho_*.tif", "*_multispec_ortho_*.tif", "*_rgb_report.pdf", "*_multispec_report.pdf", "*.psx"]
    all_patterns_found = True
    
    logging.debug(f"Checking output files for project: {project_path}")
    for pattern in output_file_patterns:
        search_path = str(project_dir / pattern)
        matching_files = glob.glob(search_path)
        if matching_files:
            logging.debug(f"  FOUND: {pattern} -> {matching_files[0]}")
        else:
            logging.warning(f"  MISSING: {pattern}")
            all_patterns_found = False
    
    return all_patterns_found

def update_csv_row(csv_file_path, project_path, output_paths, status, fieldnames):
    logging.debug(f"Updating CSV for project: {project_path}, Status: {status}")
    updated_rows = []
    with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file_in:
        csv_reader = csv.DictReader(csv_file_in)
        for row in csv_reader:
            if row['project_path'] == project_path:
                row.update({
                    'ortho_rgb': output_paths.get('ortho_rgb', ''),
                    'ortho_ms': output_paths.get('ortho_ms', ''),
                    'report_rgb': output_paths.get('report_rgb', ''),
                    'report_ms': output_paths.get('report_ms', ''),
                    'status': status
                })
            updated_rows.append(row)

    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csv_file_out:
        writer = csv.DictWriter(csv_file_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    logging.debug("CSV update completed.")

# Read CSV into memory
logging.info(f"Reading CSV file: {csv_file_path}")
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    rows = list(csv_reader)
    fieldnames = csv_reader.fieldnames + ['ortho_rgb', 'ortho_ms', 'report_rgb', 'report_ms', 'status']

# Process each row
for row in rows:
    project_path = row.get('project_path', '').strip()
    logging.debug(f"Processing project: {project_path}")

    if not project_path:
        logging.warning(f"Skipping row with missing project_path: {row}")
        continue
    
    if check_output_files_exist(project_path):
        logging.info(f"Skipping already processed project: {project_path}")
        continue
    
    missing_args = [arg for arg in ['project_path', 'date', 'site'] if not row.get(arg)]
    if missing_args:
        logging.error(f"Skipping row due to missing arguments: {missing_args}")
        update_csv_row(csv_file_path, project_path, {}, 'error_missing_args', fieldnames)
        continue
    
    cmd = [sys.executable, target_script_path, "-proj_path", row['project_path'], "-date", row['date'], "-site", row['site'], "-crs", HARDCODED_CRS, "-smooth", "low"]
    
    if row.get('multispec'):
        cmd.extend(["-multispec", row['multispec']])
    if row.get('rgb'):
        cmd.extend(["-rgb", row['rgb']])
    if row.get('sunsens', '').lower() == 'true':
        cmd.append("-sunsens")
    if TEST_FLAG_ENABLED:
        cmd.append("-test")
    
    logging.info(f"Simulated Execution: {' '.join(cmd)}")

    # Simulated output from the subprocess
    output_paths = {
        'ortho_rgb': f"{project_path}/simulated_rgb_ortho.tif",
        'ortho_ms': f"{project_path}/simulated_multispec_ortho.tif",
        'report_rgb': f"{project_path}/simulated_rgb_report.pdf",
        'report_ms': f"{project_path}/simulated_multispec_report.pdf"
    }

    logging.info(f"Simulated Outputs: {output_paths}")
    update_csv_row(csv_file_path, project_path, output_paths, 'success', fieldnames)

logging.info("Script execution (simulation mode) completed.")
