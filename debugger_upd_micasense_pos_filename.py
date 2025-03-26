import os

# Import the function from your script (assuming it is saved as 'upd_micasense_pos_filename.py')
from upd_micasense_pos_filename import ret_micasense_pos

# --- Configuration ---
mrk_folder = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\P1Data\DJI_202408080937_002_p1micasense60mtest"
# micasense_folder is no longer directly used for finding files
micasense_folder = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\MicasenseData\fullset"
master_band_paths_file = r"C:\Users\admin\Desktop\DroneStuff\master_band_paths.txt"  # Path to the text file containing master band paths
image_suffix = 6  # Assuming master band suffix is part of the filename (e.g., IMG_XXXX_6.tif)
epsg_crs = 2056  # Example EPSG code
output_csv = r"C:\Users\admin\Desktop\DroneStuff\output_micasense_pos.csv"
P1_shift_vec = [0, 0, 0]  # No shift applied
# --- End Configuration ---

# Ensure MRK folder exists
if not os.path.exists(mrk_folder):
    print(f"Error: The MRK folder '{mrk_folder}' does not exist.")
    exit(1)

# Read the list of master band paths from the text file
absolute_micasense_file_list = []
try:
    with open(master_band_paths_file, 'r') as f:
        for line in f:
            path = line.strip()
            if os.path.exists(path):
                absolute_micasense_file_list.append(path)
            else:
                print(f"Warning: Path in '{master_band_paths_file}' does not exist: {path}")
except FileNotFoundError:
    print(f"Error: The master band paths file '{master_band_paths_file}' was not found. Please run the script to generate this file first.")
    exit(1)

if not absolute_micasense_file_list:
    print(f"Warning: No valid master band paths found in '{master_band_paths_file}'.")
    exit(1)

# Run the function with the loaded file list
print("Processing data using the loaded list of MicaSense files...")
ret_micasense_pos(absolute_micasense_file_list, mrk_folder,micasense_folder, str(image_suffix), str(epsg_crs), output_csv, P1_shift_vec)

print(f"Processing complete! Check the output CSV: {output_csv}")