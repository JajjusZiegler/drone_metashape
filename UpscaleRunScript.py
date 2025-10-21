import csv
import subprocess
import sys
import os
from pathlib import Path
import logging
import glob
import datetime
import threading
import time

# Configuration - CSV file input with smart defaults
def get_csv_file_path():
    """Get CSV file path with smart defaults for unprocessed projects"""
    
    # Default directory for UPSCALE projects
    default_dir = Path(r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects")
    
    # Look for recent unprocessed projects CSV files
    recent_unprocessed = []
    if default_dir.exists():
        pattern = "unprocessed_projects_*.csv"
        recent_unprocessed = sorted(default_dir.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
    
    print("🚁 UPSCALE Batch Processing")
    print("=" * 40)
    
    if recent_unprocessed:
        print(f"📋 Found recent unprocessed projects files:")
        for i, file_path in enumerate(recent_unprocessed[:5], 1):  # Show top 5
            mod_time = datetime.datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            print(f"  {i}. {file_path.name} ({mod_time})")
        
        print(f"\n💡 Press Enter to use most recent: {recent_unprocessed[0].name}")
        print("   Or enter full path to different CSV file:")
        
        csv_input = input("> ").strip().strip('"').strip("'")
        
        if not csv_input:  # Use most recent if empty
            return str(recent_unprocessed[0])
        elif csv_input.isdigit() and 1 <= int(csv_input) <= len(recent_unprocessed):
            return str(recent_unprocessed[int(csv_input) - 1])
        else:
            return csv_input
    else:
        print("📂 Enter the path to the CSV file:")
        return input("> ").strip().strip('"').strip("'")

csv_file_path = get_csv_file_path()

# Validate CSV file path
if not os.path.exists(csv_file_path):
    print(f"❌ Error: CSV file not found: {csv_file_path}")
    print("Please check the path and try again.")
    sys.exit(1)
    
print(f"✅ Using CSV file: {csv_file_path}")

target_script_path = r"C:\Users\admin\Documents\Python Scripts\drone_metashape\DEMtests.py"
metashape_python_path = r"C:\Program Files\Agisoft\Metashape Pro\python\python.exe"
HARDCODED_CRS = "2056"

# Validate Metashape Python interpreter
if not os.path.exists(metashape_python_path):
    print(f"❌ Error: Metashape Python interpreter not found at: {metashape_python_path}")
    print("Please check your Metashape installation or update the path in the script.")
    sys.exit(1)

print(f"✅ Using Metashape Python: {metashape_python_path}")

# Validate target script
if not os.path.exists(target_script_path):
    print(f"❌ Error: Target script not found: {target_script_path}")
    sys.exit(1)

print(f"✅ Target script found: {target_script_path}")
TEST_FLAG_ENABLED = False

# Timeout duration in seconds (50 minutes)
TIMEOUT_DURATION = 60 * 60

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

def monitor_subprocess(process, project_logger, timeout_event):
    """Monitor the subprocess for timeout."""
    last_output_time = time.time()

    def update_last_output_time():
        nonlocal last_output_time
        last_output_time = time.time()

    # Read stdout and stderr in separate threads
    def read_stdout():
        for line in process.stdout:
            print(line, end='')
            project_logger.info(line.strip())
            update_last_output_time()
            if line.startswith('OUTPUT_ORTHO_RGB:'):
                output_paths['ortho_rgb'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_ORTHO_MS:'):
                output_paths['ortho_ms'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_REPORT_RGB:'):
                output_paths['report_rgb'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_REPORT_MS:'):
                output_paths['report_ms'] = line.split(':', 1)[1].strip()

    def read_stderr():
        for line in process.stderr:
            print(line, end='', file=sys.stderr)
            project_logger.error(line.strip())
            update_last_output_time()

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)

    stdout_thread.start()
    stderr_thread.start()

    # Monitor for timeout
    while process.poll() is None:  # While the process is running
        if time.time() - last_output_time > TIMEOUT_DURATION:
            project_logger.error(f"Timeout reached for project. Terminating process.")
            process.terminate()
            timeout_event.set()  # Signal timeout
            break
        time.sleep(1)  # Check every second

    stdout_thread.join()
    stderr_thread.join()

# Main processing
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    rows = list(csv_reader)
    fieldnames = csv_reader.fieldnames + ['ortho_rgb', 'ortho_ms', 'report_rgb', 'report_ms', 'status']

print(f"\n📊 BATCH PROCESSING SUMMARY")
print(f"{'='*50}")
print(f"Projects to process: {len(rows)}")
print(f"Target script: {target_script_path}")
print(f"Python interpreter: {metashape_python_path}")
print(f"CRS: {HARDCODED_CRS}")
print(f"Test mode: {'Enabled' if TEST_FLAG_ENABLED else 'Disabled'}")
print(f"Timeout: {TIMEOUT_DURATION//60} minutes")

if len(rows) > 0:
    print(f"\nFirst few projects:")
    for i, row in enumerate(rows[:3], 1):
        print(f"  {i}. {row.get('site', 'Unknown')} - {row.get('date', 'Unknown')}")
    if len(rows) > 3:
        print(f"  ... and {len(rows)-3} more")

print(f"\n⚠️  This will start processing {len(rows)} projects.")
confirm = input("Continue? (y/N): ").strip().lower()
if confirm not in ['y', 'yes']:
    print("❌ Processing cancelled.")
    sys.exit(0)

print(f"\n🚀 Starting batch processing...")

# Main processing loop (modified to include timeout logic)
for row in rows:
    project_path = row.get('project_path', '').strip()
    site = row.get('site', '').strip()
    date = row.get('date', '').strip()

    if not project_path or not site or not date:
        main_logger.warning(f"Skipping row with missing project_path, site, or date: {row}")
        continue

    project_logger = setup_project_logger(project_path, site, date)
    
    # Debug: Log available columns and values
    project_logger.info(f"CSV columns available: {list(row.keys())}")
    project_logger.info(f"Processing project: {site} - {date}")
    project_logger.info(f"Project path: {project_path}")
    project_logger.info(f"RGB data path: {row.get('rgb_data_path', 'N/A')} (fallback: {row.get('rgb', 'N/A')})")
    project_logger.info(f"Multispec data path: {row.get('multispec_data_path', 'N/A')} (fallback: {row.get('multispec', 'N/A')})")
    
    # Validate project file exists
    if not os.path.exists(project_path):
        project_logger.error(f"Project file does not exist: {project_path}")
        continue

    if check_output_files_exist(project_path, project_logger):
        project_logger.info(f"Skipping already processed project: {project_path}")
        continue

    missing_args = [arg for arg in ['project_path', 'date', 'site'] if not row.get(arg)]
    if missing_args:
        project_logger.warning(f"Skipping row due to missing arguments: {missing_args}")
        continue

    # Use Metashape Python interpreter directly
    cmd = [metashape_python_path, target_script_path, "-proj_path", row['project_path'], "-date", row['date'], "-site", row['site'], "-crs", HARDCODED_CRS, "-smooth", "medium"]
    
    # Add RGB and multispec paths if available
    if row.get('rgb_data_path'):  # Updated to match the column name from status checker
        rgb_path = row['rgb_data_path']
        if os.path.exists(rgb_path):
            cmd.extend(["-rgb", rgb_path])
            project_logger.info(f"Using RGB path: {rgb_path}")
        else:
            project_logger.warning(f"RGB path does not exist: {rgb_path}")
    elif row.get('rgb'):  # Fallback to original column name
        rgb_path = row['rgb']
        if os.path.exists(rgb_path):
            cmd.extend(["-rgb", rgb_path])
            project_logger.info(f"Using RGB path (fallback): {rgb_path}")
        else:
            project_logger.warning(f"RGB path (fallback) does not exist: {rgb_path}")
    
    if row.get('multispec_data_path'):  # Updated to match the column name from status checker
        multispec_path = row['multispec_data_path']
        if os.path.exists(multispec_path):
            cmd.extend(["-multispec", multispec_path])
            project_logger.info(f"Using multispec path: {multispec_path}")
        else:
            project_logger.warning(f"Multispec path does not exist: {multispec_path}")
    elif row.get('multispec'):  # Fallback to original column name
        multispec_path = row['multispec']
        if os.path.exists(multispec_path):
            cmd.extend(["-multispec", multispec_path])
            project_logger.info(f"Using multispec path (fallback): {multispec_path}")
        else:
            project_logger.warning(f"Multispec path (fallback) does not exist: {multispec_path}")
    
    if row.get('sunsens', '').lower() == 'true': cmd.append("-sunsens")
    if TEST_FLAG_ENABLED: cmd.append("-test")

    project_logger.info(f"Executing: {' '.join(cmd)}")
    output_paths = {}
    timeout_event = threading.Event()

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        monitor_thread = threading.Thread(target=monitor_subprocess, args=(process, project_logger, timeout_event), daemon=True)
        monitor_thread.start()
        monitor_thread.join()  # Wait for the monitor thread to finish

        if timeout_event.is_set():
            continue

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)

        project_logger.info(f"Project processed successfully: {project_path}")

    except subprocess.CalledProcessError as e:
        project_logger.error(f"Error processing {project_path}: {e}")

print("Script execution completed.")