import csv
import subprocess
import sys
import os
from pathlib import Path
import logging
import glob

# Configuration (same as before)
csv_file_path = input("Enter the path to the CSV file: ")
target_script_path = r"C:\Users\admin\Documents\Python Scripts\drone_metashape\DEMtests.py"
HARDCODED_CRS = "2056"
TEST_FLAG_ENABLED = False
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add console logging
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

def check_output_files_exist(project_path):

    project_dir = Path(project_path)

    output_file_patterns = ["**_rgb_ortho_**.tif", "**_multispec_ortho_**.tif", "*_rgb_report.pdf", "*_multispec_report.pdf", "**.psx"]

    all_patterns_found = True

    

    print(f"DEBUG: Checking output for project: {project_path}")

    for pattern in output_file_patterns:

        search_path = str(project_dir / pattern)

        matching_files = glob.glob(search_path)

        if matching_files:

            print(f"  FOUND: {pattern} -> {matching_files[0]}")

        else:

            print(f"  MISSING: {pattern}")

            all_patterns_found = False

    

    return all_patterns_found


def update_csv_row(csv_file_path, project_path, output_paths, status, fieldnames):

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
# Read CSV into memory
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    rows = list(csv_reader)
    fieldnames = csv_reader.fieldnames + ['ortho_rgb', 'ortho_ms', 'report_rgb', 'report_ms', 'status']

# Process each row
for row in rows:
    project_path = row.get('project_path', '').strip()
    if not project_path:
        logging.warning(f"Skipping row with missing project_path: {row}")
        continue

    if check_output_files_exist(project_path):
        logging.info(f"Skipping already processed project: {project_path}")
        continue

    missing_args = [arg for arg in ['project_path', 'date', 'site'] if not row.get(arg)]
    if missing_args:
        logging.warning(f"Skipping row due to missing arguments: {missing_args}")
        update_csv_row(csv_file_path, project_path, {}, 'error_missing_args', fieldnames)
        continue

    cmd = [sys.executable, target_script_path, "-proj_path", row['project_path'], "-date", row['date'], "-site", row['site'], "-crs", HARDCODED_CRS, "-smooth", "medium"]

    if row.get('multispec'):
        cmd.extend(["-multispec", row['multispec']])
    if row.get('rgb'):
        cmd.extend(["-rgb", row['rgb']])
    if row.get('sunsens', '').lower() == 'true':
        cmd.append("-sunsens")
    if TEST_FLAG_ENABLED:
        cmd.append("-test")

    logging.info(f"Executing: {' '.join(cmd)}")
    output_paths = {}

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1) # bufsize=1 for line-buffering.

        for line in process.stdout:
            print(line, end='')  # Print stdout in real-time
            if line.startswith('OUTPUT_ORTHO_RGB:'):
                output_paths['ortho_rgb'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_ORTHO_MS:'):
                output_paths['ortho_ms'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_REPORT_RGB:'):
                output_paths['report_rgb'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_REPORT_MS:'):
                output_paths['report_ms'] = line.split(':', 1)[1].strip()

        for line in process.stderr:
            print(line, end='', file=sys.stderr) # Print stderr in real-time.

        process.wait() # Wait for the subprocess to finish.

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)

        update_csv_row(csv_file_path, project_path, output_paths, 'success', fieldnames)
        logging.info(f"Project processed successfully: {project_path}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error processing {project_path}: {e}")
        update_csv_row(csv_file_path, project_path, {}, 'error_subprocess', fieldnames)

print("Script execution completed.")