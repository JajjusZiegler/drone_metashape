import csv
import Metashape
import os

# Path to the CSV file containing the arguments
csv_file_path = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\processing_test\arguments_log_test3.csv"

# Open the CSV and read rows
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    
    for row in csv_reader:
        proj_path = row['proj_path']  # Path to the Metashape project file
        if not os.path.exists(proj_path):
            print(f"Project path does not exist: {proj_path}")
            continue

        try:
            # Open the Metashape project
            print(f"Opening project: {proj_path}")
            doc = Metashape.Document()
            doc.open(proj_path)  # Opens the project

            # Notify user to perform manual operations
            print("Project is open. Perform manual operations in Metashape.")
            input("Press Enter when finished with modifications to continue...")

            # Save the project after manual modifications
            print(f"Saving project: {proj_path}")
            doc.save()

        except Exception as e:
            print(f"An error occurred while processing {proj_path}: {e}")
        
        finally:
            # Clear the project from memory
            print(f"Closing project: {proj_path}")
            doc.clear()

print("All projects processed.")

