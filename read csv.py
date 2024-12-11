import csv
import argparse
import subprocess

def read_args_from_csv(csv_file):
    args_dict = {}
    with open(csv_file, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            for key, value in row.items():
                args_dict[key] = value
    return args_dict

def main():
    parser = argparse.ArgumentParser(description='Run metashape_proc_Upscale.py with arguments from a CSV file')
    parser.add_argument('-csv', help='Path to the CSV file containing the arguments', required=True)
    args = parser.parse_args()

    # Read arguments from CSV file
    csv_args = read_args_from_csv(args.csv)

    for key, value in csv_args.items():
        print(f"{key}: {value}")
    

if __name__ == "__main__":
    main()