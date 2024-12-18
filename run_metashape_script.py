import csv
import subprocess
import sys

# Path to the CSV file containing the arguments
csv_file_path = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\processing_test\arguments_log.csv"

# Path to the target Python script you want to call
target_script_path = r"C:\Users\admin\Documents\Python Scripts\drone_metashape\metashape_proc_Upscale.py"


# Open the CSV and read rows
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    
    for row in csv_reader:
        # Build the arguments for the target script
        # This depends on what your script expects. For example:
        # If the target script expects arguments like:
        #   -proj_path <path>
        #   -date <date>
        #   -site <site>
        #   -crs <crs>
        #   -multispec <path>
        #   -rgb <path>
        #   -smooth <value>
        #   -drtk <value>
        #   -sunsens <value>
        #   -test (flag)
        #   -multionly (flag)
        # You can add them as needed.

        cmd = [sys.executable, target_script_path
                 # For instance, if your script uses -csv for proj_path (adjust as needed)    
              ]

        # Now append additional arguments that your target script expects:
        # For each column in the CSV that your script uses as an argument, append them:
        
        # Example: If your script is expecting a '-date' argument:
        print(row)   
        cmd.extend(["-date", row['date']])
        cmd.extend(["-site", row['site']])
        cmd.extend(["-crs", row['crs']])
        cmd.extend(["-multispec", row['multispec']])
        cmd.extend(["-rgb", row['rgb']])
        cmd.extend(["-smooth", row['smooth']])
        
        # If 'drtk' is optional, only add if not None
        if row['drtk'] and row['drtk'].lower() != "none":
            cmd.extend(["-drtk", row['drtk']])

        # If 'sunsens' is True/False, maybe your script expects a flag:
        if row['sunsens'].lower() == "true":
            cmd.append("-sunsens")

        # If your script expects a '-test' flag when True:
        if row['test'].lower() == "true":
            cmd.append("-test")

        # If your script expects a '-multionly' flag when True:
        if row['multionly'].lower() == "true":
            cmd.append("-multionly")

        # Print the command for debugging purposes
        print("Running command:", " ".join(cmd))
        
        # Run the target script with the arguments
        subprocess.run(cmd, check=True)