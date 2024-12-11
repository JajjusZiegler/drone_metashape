import csv
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description='Run metashape_proc_Upscale.py with arguments from a CSV file')
    parser.add_argument('-csv', help='Path to the CSV file containing the arguments', required=True)
    args = parser.parse_args()

    # Loop through all lines in the CSV file and run the script with the arguments
    with open(args.csv, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            print("Running metashape_proc_Upscale.py with the following arguments:")
            command = ['metashape', '-r', 'metashape_proc_Upscale.py']
            for key, value in row.items():
                command.append(f'-{key}')
                command.append(value)
                print(f"{key}: {value}")
            # Run the command
            subprocess.run(command)

if __name__ == "__main__":
    main()