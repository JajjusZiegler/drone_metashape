import os

# Import the function from your script (assuming it is saved as 'micasense_processing.py')
from upd_micasense_pos_filename import ret_micasense_pos

# User input for paths
mrk_folder = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\P1Data\DJI_202408080937_002_p1micasense60mtest"
micasense_folder = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\MicasenseData\fullset"
# Ensure paths exist
if not os.path.exists(mrk_folder):
    print(f"Error: The MRK folder '{mrk_folder}' does not exist.")
    exit(1)

if not os.path.exists(micasense_folder):
    print(f"Error: The MicaSense folder '{micasense_folder}' does not exist.")
    exit(1)

# Test parameters
image_suffix = 6  # Assuming master band suffix is '1' (adjust if needed)
epsg_crs = 2056  # Example EPSG code for Australia (adjust based on location)
output_csv = "output_micasense_pos.csv"
P1_shift_vec = [0, 0, 0]  # No shift applied

# Run the function
print("Processing data...")
ret_micasense_pos(mrk_folder, micasense_folder, image_suffix, epsg_crs, output_csv, P1_shift_vec)

print(f"Processing complete! Check the output CSV: {output_csv}")
