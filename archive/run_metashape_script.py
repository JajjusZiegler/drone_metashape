import csv
import subprocess
import sys

# Path to the CSV file containing the arguments
csv_file_path = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\logbook_test_RGBandMulti_dataproject_created.csv"

# Path to the target Python script you want to call
target_script_path = r"C:\Users\admin\Documents\Python Scripts\drone_metashape\metashape_proc_Upscale_copy.py"

# Open the CSV and read rows
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    
    for row in csv_reader:
        cmd = [sys.executable, target_script_path]

        # Append required arguments
        if row['proj_path']:
            cmd.extend(["-proj_path", row['project_path']])
        if row['date']:
            cmd.extend(["-date", row['date']])
        if row['site']:
            cmd.extend(["-site", row['site']])
        if row['crs']:
            cmd.extend(["-crs", "2056"])
        
        # Append optional arguments
        if row['multispec']:
            cmd.extend(["-multispec", row['multispec']])
        if row['rgb']:
            cmd.extend(["-rgb", row['rgb']])
        if row['sunsens'] and row['sunsens'].lower() == 'true':
            cmd.append("-sunsens")

        # Check if all required arguments are present
        required_args = ['proj_path', 'date', 'site', 'crs']
        missing_args = [arg for arg in required_args if not row[arg]]
        if missing_args:
            print(f"Skipping row due to missing required arguments: {', '.join(missing_args)}")
            continue

        # Print the command for debugging purposes
        print("Running command:", " ".join(cmd))

        print("Running command:", " ".join(cmd))
        
        # Run the target script with the arguments
        subprocess.run(cmd, check=True)