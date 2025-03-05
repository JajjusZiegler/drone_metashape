import csv
import subprocess
import sys
import os
from pathlib import Path
import logging
import glob

# Configuration (rest of your configuration remains the same)
csv_file_path = input("Enter the path to the CSV file: ")
target_script_path = r"C:\Users\admin\Documents\Python Scripts\drone_metashape\DEMtests.py"
HARDCODED_CRS = "2056"
TEST_FLAG_ENABLED = False
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_output_files_exist(project_path):
    """
    Checks if expected output files (using glob patterns) exist in the project path.
    Includes detailed debug prints.
    """
    project_dir = Path(project_path) # Use Path object directly
    output_file_patterns = [
        "*_rgb_ortho_*.tif",
        "*_multispec_ortho_*.tif",
        "*_rgb_report.pdf",
        "*_multispec_report.pdf",
        "*.psx" # Added PSX file check as it was in your initial scraping example
    ]
    all_patterns_found = True  # Assume all patterns are found initially

    print(f"  DEBUG: Checking output files using patterns for project: {project_path}")

    for pattern in output_file_patterns:
        search_path = str(project_dir / pattern) # Construct search path for glob
        matching_files = glob.glob(search_path)

        if matching_files:
            print(f"   DEBUG: Pattern FOUND: {pattern} - Matches: {matching_files[0]}") # Show first match
        else:
            print(f"   DEBUG: Pattern MISSING: {pattern} - No files found.")
            all_patterns_found = False  # If any pattern has no matches, set to False

    return all_patterns_found

def update_csv_row(csv_file_path, project_path, output_paths, status, initial_fieldnames): # Added initial_fieldnames
    """Updates a row in the CSV with output paths and status, using a consistent header."""
    updated_rows = []
    fieldnames = list(initial_fieldnames) # Start with the initial fieldnames

    # Ensure the new columns exist in the fieldnames list, but only once
    new_columns = ['ortho_rgb', 'ortho_ms', 'report_rgb', 'report_ms', 'status']
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)

    with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file_in:
        csv_reader = csv.DictReader(csv_file_in)

        for row in csv_reader:
            if row['project_path'] == project_path:
                # Update output paths and status
                row.update({
                    'ortho_rgb': output_paths.get('ortho_rgb', ''),
                    'ortho_ms': output_paths.get('ortho_ms', ''),
                    'report_rgb': output_paths.get('report_rgb', ''),
                    'report_ms': output_paths.get('report_ms', ''),
                    'status': status
                })
            updated_rows.append(row)

    # Write updated CSV back with the consistent fieldnames
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csv_file_out:
        writer = csv.DictWriter(csv_file_out, fieldnames=fieldnames)
        writer.writeheader() # Write the header with all fieldnames
        writer.writerows(updated_rows)


# Main processing
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    initial_fieldnames = csv_reader.fieldnames # Get the initial fieldnames *once* here

# Main processing loop - now outside the initial CSV open block
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file: # Re-open CSV for reading data rows
    csv_reader = csv.DictReader(csv_file)

    for row in csv_reader:
        project_path = row.get('project_path')

        if not project_path:
            logging.warning(f"Skipping row due to missing 'project_path'. Row: {row}")
            continue

        if check_output_files_exist(project_path):
            logging.info(f"Skipping already processed project: {project_path}")
            continue

        cmd = [sys.executable, target_script_path]
        required_args = {'project_path', 'date', 'site'}
        missing_args = [arg for arg in required_args if not row.get(arg)]

        if missing_args:
            logging.warning(f"Skipping row due to missing required arguments: {missing_args} - Row: {row}")
            update_csv_row(csv_file_path, project_path, {}, 'error_missing_args', initial_fieldnames) # Pass initial_fieldnames
            continue

        cmd.extend(["-proj_path", row['psx_file']]) # Pass project path as argument
        cmd.extend(["-date", row['date']])
        cmd.extend(["-site", row['site']])
        cmd.extend(["-crs", HARDCODED_CRS])
        cmd.extend(["-smooth", "low"]) # smoothing level

        if row.get('multispec'):
            cmd.extend(["-multispec", row['multispec']])
        if row.get('rgb'):
            cmd.extend(["-rgb", row['rgb']])
        if row.get('sunsens', '').lower() == 'True':
            cmd.append("-sunsens")
        

        if TEST_FLAG_ENABLED:
            cmd.append("-test")

        command_str = " ".join(cmd)
        logging.info(f"Starting command: {command_str}")

        output_paths = {}

        try:
            # Use subprocess.Popen to run the target script and connect its stdout/stderr to ours
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True)
            return_code = process.wait() # Wait for the process to finish

            if return_code != 0: # Check return code ourselves since we are not using check=True anymore
                raise subprocess.CalledProcessError(return_code, cmd)

            # --- Output is already printed directly to the terminal, no need to print again ---
            # --- No need to process stdout for output paths here either, if your target script
            # --- still needs to return output paths, it should still do so in stdout, and
            # --- we would need to capture *and* display it, which complicates things a bit.
            # --- For now, assuming direct terminal output is the priority.

            output_paths = {} # You might still need to extract paths, so keep this part for now,
                             # assuming your target script *also* still prints structured output lines
            result_obj = subprocess.run(cmd, capture_output=True, text=True, check=False) # Re-run to capture output silently
            result = result_obj # rename for consistency

            for line in result.stdout.splitlines(): # Process output from *captured* output
                if line.startswith('OUTPUT_ORTHO_RGB:'):
                    output_paths['ortho_rgb'] = line.split(':', 1)[1].strip()
                elif line.startswith('OUTPUT_ORTHO_MS:'):
                    output_paths['ortho_ms'] = line.split(':', 1)[1].strip()
                elif line.startswith('OUTPUT_REPORT_RGB:'):
                    output_paths['report_rgb'] = line.split(':', 1)[1].strip()
                elif line.startswith('OUTPUT_REPORT_MS:'):
                    output_paths['report_ms'] = line.split(':', 1)[1].strip()


            update_csv_row(csv_file_path, project_path, output_paths, 'success', initial_fieldnames)
            logging.info(f"Project processed successfully: {project_path}")

        except subprocess.CalledProcessError as e:
            logging.error(f"Error processing project {project_path}: {e}")
            # --- Error output is already printed directly to the terminal, no need to print stderr again here ---
            update_csv_row(csv_file_path, project_path, {}, 'error_subprocess', initial_fieldnames)
            
print("Script execution completed.")