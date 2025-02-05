import os
from upd_micasense_pos_original import ret_micasense_pos

def main():
    # Define sample inputs
    mrk_folder = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\P1Data\DJI_202408080937_002_p1micasense60mtest"
    micasense_folder = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\MicasenseData\fullset"
    image_suffix = 5
    epsg_crs = 4326
    out_file = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\outputMicapos\output.csv"
    P1_shift_vec = [0.0, 0.0, 0.0]

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    # Call the function
    ret_micasense_pos(mrk_folder, micasense_folder, image_suffix, epsg_crs, out_file, P1_shift_vec)

    # Print a message indicating the function has completed
    print("ret_micasense_pos function has completed. Check the output file for results.")

if __name__ == "__main__":
    main()