import os
from datetime import datetime
from tabulate import tabulate

# Function to scan a directory and collect information about files
def scan_directory(directory):
    data = []  # List to store file information
    for root, _, files in os.walk(directory):  # Walk through the directory
        print(f"Scanning directory: {root}")  # Debugging log to show progress
        for file in files:
            try:
                if not is_relevant_file(file):  # Skip irrelevant files
                    continue
                file_path = os.path.join(root, file)  # Get the full file path
                file_date, site, description = extract_metadata(file_path)  # Extract metadata from the file path
                content_type = categorize_file(description)  # Determine the content type of the file
                data.append([file_date, site, content_type])  # Append file details to the list
            except Exception as e:
                print(f"Error processing file {file_path}: {e}")  # Log errors
    return data

# Function to check if a file is relevant based on its name
def is_relevant_file(filename):
    filename_lower = filename.lower()  # Convert filename to lowercase for case-insensitive comparison
    return any(keyword in filename_lower for keyword in ["ortho", "model", "dem", "report"])  # Check for keywords

# Function to extract metadata (date, site, description) from the file path
def extract_metadata(file_path):
    parts = file_path.split(os.sep)  # Split the file path into parts
    try:
        date = parts[-3]  # Extract the date from the third-to-last folder
        site = parts[-4]  # Extract the site from the fourth-to-last folder
        description = os.path.splitext(parts[-1])[0]  # Extract the file description (without extension)
    except IndexError:
        date, site, description = "Unknown", "Unknown", "Unknown"  # Default values if extraction fails
    return date, site, description

# Function to categorize files based on their descriptions
def categorize_file(description):
    description_lower = description.lower()  # Convert description to lowercase for case-insensitive comparison
    if "multispec_ortho" in description_lower:
        return "Multi Orthoimage"  # File is an orthoimage
    elif "rgb_ortho" in description_lower:
        return "RGB Orthoimage"
    elif "model" in description_lower:
        return "Model"  # File is a model
    elif "dem" in description_lower:
        return "DEM"  # File is a digital elevation model
    elif "report" in description_lower:
        return "Report"  # File is a report
    else:
        return "Other"  # File type is unknown or other

# Function to print the collected data in a tabular format
def save_to_csv(data, output_file="output.csv"):
    import csv  # Import the CSV module
    headers = ["Date", "Site", "Content"]  # Define CSV headers
    try:
        with open(output_file, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)  # Create a CSV writer object
            writer.writerow(headers)  # Write the headers to the CSV file
            writer.writerows(data)  # Write the data rows to the CSV file
        print(f"Data successfully saved to {output_file}")  # Confirm successful save
    except Exception as e:
        print(f"An error occurred while saving to CSV: {e}")  # Handle errors

# Main script execution
if __name__ == "__main__":
    directory_to_check = input("Enter the directory to scan: ").strip('"')  # Strip quotes from input
    directory_to_check = os.path.normpath(directory_to_check)  # Normalize the path
    if os.path.isdir(directory_to_check):  # Check if the input is a valid directory
        try:
            contents = scan_directory(directory_to_check)  # Scan the directory
            print_table(contents)  # Print the results in a table
        except Exception as e:
            print(f"An error occurred: {e}")  # Handle unexpected errors
    else:
        print("Invalid directory. Please try again.")  # Handle invalid directory input
