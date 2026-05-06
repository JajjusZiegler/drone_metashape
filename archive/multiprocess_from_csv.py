import csv
import argparse
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description='Run metashape_proc_Upscale.py with arguments from a CSV file')
    parser.add_argument('-csv', help='Path to the CSV file containing the arguments', required=True)
    args = parser.parse_args()

    # Function to filter out empty keys from the CSV row
    def filter_empty_keys(row):
        return {k: v for k, v in row.items() if k and v}

    # Loop through all lines in the CSV file and run the script with the arguments
    with open(args.csv, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            try:
                filtered_row = filter_empty_keys(row)
                print("Running metashape_proc_Upscale.py with the following arguments:")
                command = [sys.executable, r'C:\Users\admin\Documents\Python Scripts\drone_metashape\metashape_proc_Upscale.py']
                for key, value in filtered_row.items():
                    command.append(f'-{key}')
                    command.append(value)
                    print(f"{key}: {value}")
                # Print the full command to be run
                print(f"Full command: {' '.join(command)}")
                # Run the command
                result = subprocess.run(command, capture_output=True, text=True)
                # Print the result of the subprocess
                print(f"Subprocess returned with code {result.returncode}")
                if result.stdout:
                    print(f"Subprocess output: {result.stdout}")
                if result.stderr:
                    print(f"Subprocess errors: {result.stderr}")
            except Exception as e:
                print(f"An error occurred: {e}")
            
            # Prompt the user to check the results before proceeding
            try:
                input("Press Enter to proceed to the next iteration...")
            except KeyboardInterrupt:
                print("Process interrupted by user.")
                sys.exit(0)

if __name__ == "__main__":
    main()