import argparse
import csv
import os
from pathlib import Path
import Metashape

def process_projects(input_csv):
    """
    Opens projects from the input CSV, applies locateReflectancePanels, and saves the project.
    """
    with open(input_csv, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)

        for row in reader:
            date = row['date']
            site = row['site']
            proj_path = Path(row['psx_file'])

            try:
                if not proj_path.exists():
                    print(f"Project file not found: {proj_path}")
                    continue

                # Open existing Metashape project
                doc = Metashape.Document()
                doc.open(str(proj_path))
                
                # Locate multispec chunk
                multispec_chunk = None
                for chunk in doc.chunks:
                    if chunk.label == "multispec":
                        multispec_chunk = chunk
                        break

                if multispec_chunk is None:
                    raise ValueError("Multispec chunk not found")
                
                # Apply locateReflectancePanels
                print(f"Applying locateReflectancePanels on: {proj_path}")
                multispec_chunk.locateReflectancePanels()
                
                # Save project
                doc.save()
                print(f"Project saved: {proj_path}")
            
            except Exception as e:
                print(f"Error processing {site}/{date}: {str(e)}")

if __name__ == "__main__":
    # Check Metashape license first
    try:
        if not Metashape.app.activated:
            raise RuntimeError("Metashape license not activated")
    except AttributeError:
        raise RuntimeError("Metashape module not properly installed")

    parser = argparse.ArgumentParser(description='Apply locateReflectancePanels on Metashape projects')
    parser.add_argument('input_csv', help='Input CSV file with project paths')
    args = parser.parse_args()
    
    process_projects(args.input_csv)
