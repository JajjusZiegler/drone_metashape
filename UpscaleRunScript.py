import csv
import subprocess
import sys
import os
from pathlib import Path
import logging
import glob
import datetime

# Configuration (same as before)
csv_file_path = input("Enter the path to the CSV file: ")
target_script_path = r"C:\Users\admin\Documents\Python Scripts\drone_metashape\DEMtests.py"
HARDCODED_CRS = "2056"
TEST_FLAG_ENABLED = False

# --- Basic Logging Setup (for the main script's actions) ---
main_logger = logging.getLogger(__name__)
main_logger.setLevel(logging.INFO)
main_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s')
main_console_handler = logging.StreamHandler(sys.stdout)
main_console_handler.setLevel(logging.INFO)
main_console_handler.setFormatter(main_formatter)
main_logger.addHandler(main_console_handler)
# --- End of Basic Logging Setup ---

def setup_project_logger(project_file_path, site, date):
    """Sets up a separate logger for each project."""
    project_file = Path(project_file_path)
    project_dir = project_file.parent
    logs_dir = project_dir / 'logs'
    consolelog_dir = logs_dir / 'consolelog'
    logs_dir.mkdir(parents=True, exist_ok=True)
    consolelog_dir.mkdir(parents=True, exist_ok=True)
    log_file_name = f"consolelog_{site}_{date}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file_path = consolelog_dir / log_file_name
    project_logger = logging.getLogger(f"project_{project_dir.name}_{site}_{date}")
    project_logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(str(log_file_path), mode='w')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    project_logger.addHandler(file_handler)
    project_logger.propagate = False  # Prevent messages from going to the root logger
    return project_logger

def check_output_files_exist(project_path, project_logger):
    project_dir = Path(project_path)
    output_file_patterns = ["**_rgb_ortho_**.tif", "**_multispec_ortho_**.tif", "*_rgb_report.pdf", "*_multispec_report.pdf", "**.psx"]
    all_patterns_found = True
    project_logger.debug(f"Checking output for project: {project_path}")
    for pattern in output_file_patterns:
        search_path = str(project_dir / pattern)
        matching_files = glob.glob(search_path)
        if not matching_files:
            project_logger.debug(f"  MISSING: {pattern}")
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
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csv_file_out:
        writer = csv.DictWriter(csv_file_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

# Main processing
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    rows = list(csv_reader)
    fieldnames = csv_reader.fieldnames + ['ortho_rgb', 'ortho_ms', 'report_rgb', 'report_ms', 'status']

for row in rows:
    project_path = row.get('project_path', '').strip()
    site = row.get('site', '').strip()
    date = row.get('date', '').strip()

    if not project_path or not site or not date:
        main_logger.warning(f"Skipping row with missing project_path, site, or date: {row}")
        continue

    project_logger = setup_project_logger(project_path, site, date)

    if check_output_files_exist(project_path, project_logger):
        project_logger.info(f"Skipping already processed project: {project_path}")
        continue

    missing_args = [arg for arg in ['project_path', 'date', 'site'] if not row.get(arg)]
    if missing_args:
        project_logger.warning(f"Skipping row due to missing arguments: {missing_args}")
        update_csv_row(csv_file_path, project_path, {}, 'error_missing_args', fieldnames)
        continue

    cmd = [sys.executable, target_script_path, "-proj_path", row['project_path'], "-date", row['date'], "-site", row['site'], "-crs", HARDCODED_CRS, "-smooth", "medium"]
    if row.get('multispec'): cmd.extend(["-multispec", row['multispec']])
    if row.get('rgb'): cmd.extend(["-rgb", row['rgb']])
    if row.get('sunsens', '').lower() == 'true': cmd.append("-sunsens")
    if TEST_FLAG_ENABLED: cmd.append("-test")

    project_logger.info(f"Executing: {' '.join(cmd)}")
    output_paths = {}

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        for line in process.stdout:
            print(line, end='')
            project_logger.info(line.strip())  # Log to project log
            if line.startswith('OUTPUT_ORTHO_RGB:'):
                output_paths['ortho_rgb'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_ORTHO_MS:'):
                output_paths['ortho_ms'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_REPORT_RGB:'):
                output_paths['report_rgb'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_REPORT_MS:'):
                output_paths['report_ms'] = line.split(':', 1)[1].strip()

        for line in process.stderr:
            print(line, end='', file=sys.stderr)
            project_logger.error(line.strip())  # Log to project log

        process.wait()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)

        update_csv_row(csv_file_path, project_path, output_paths, 'success', fieldnames)
        project_logger.info(f"Project processed successfully: {project_path}")

    except subprocess.CalledProcessError as e:
        project_logger.error(f"Error processing {project_path}: {e}")
        update_csv_row(csv_file_path, project_path, {}, 'error_subprocess', fieldnames)

print("Script execution completed.")