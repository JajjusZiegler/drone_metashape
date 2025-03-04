"""
Script to process drone imagery in Metashape.

Author: Your Name
Date: YYYY-MM-DD

This script reads project parameters from an input CSV file, processes the projects in Metashape,
and writes the results to an output CSV file.

Example usage:
    python metashape_proc_CreateProjects.py "M:/working_package_2/2024_dronecampaign/01_data/dronetest/processing_test/arguments_log_test3.csv"

The output CSV file will be generated automatically with "_processed" appended to the input CSV filename.
"""

import argparse
import csv
import os
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple
import exifread
import Metashape

# ---------- Added from metashape_proc_Upscale ----------
def find_files(folder: Path, extensions: Tuple[str]) -> List[str]:
    """Recursively find files with specified extensions."""
    return [
        str(p) for p in folder.rglob("*")
        if p.suffix.lower() in extensions and p.is_file()
    ]

# Define Metashape project directory
proj_directory = Path(r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects")


# Chunk labels
CHUNK_RGB = "rgb"
CHUNK_MULTISPEC = "multispec"

# Sensor offset configuration (example values - modify according to your setup)
P1_GIMBAL1_OFFSET = (0.087, 0.0, 0.0)

offset_dict = defaultdict(dict)
offset_dict['RedEdge-M']['Red'] = (-0.097, -0.03, -0.06)
offset_dict['RedEdge-M']['Dual'] = (-0.097, 0.02, -0.08)
offset_dict['RedEdge-P']['Red'] = (0,0,0)
offset_dict['RedEdge-P']['Dual'] = (0,0,0)


def process_projects(input_csv, output_csv):
    """
    Processes projects from the input CSV and writes results to the output CSV.
    """
    with open(input_csv, 'r', newline='', encoding='utf-8') as infile, open(output_csv, 'a', newline='', encoding='utf-8') as outfile: # Added encoding='utf-8' for both files        
        reader = csv.DictReader(infile)
        writer = csv.writer(outfile)

        # Write header if output file is empty
        if outfile.tell() == 0:
            writer.writerow(['date', 'site', 'rgb', 'multispec', 'sunsens', 'project_path', 'image_load_status'])

        for row in reader:
            # Extract required columns
            date = row['date']
            site = row['site']
            rgb_path = Path(row['rgb'])
            multispec_path = Path(row['multispec'])
            sunsens = row['sunsens']

            # Define project path
            proj_file = proj_directory / site / date / f"metashape_project_{site}_{date}.psx"

            # Prepare result entry
            result = [
                date, site, str(rgb_path), str(multispec_path), sunsens,
                str(proj_file), 'skipped'  # Default status
            ]

            try:
                # Skip if project already exists
                if proj_file.exists():
                    print(f"Skipping existing project: {proj_file}")
                    result[6] = 'skipped (exists)'
                    writer.writerow(result)
                    continue

                # Create new Metashape document
                doc = Metashape.Document()
                proj_file.parent.mkdir(parents=True, exist_ok=True)

                # Add images to project
                add_images_to_project(doc, rgb_path, multispec_path, proj_file)

                # Save project
                doc.save(path=str(proj_file))
                print(f"Created project: {proj_file}")
                result[6] = 'success'

            except Exception as e:
                print(f"Error processing {site}/{date}: {str(e)}")
                result[6] = f'error: {str(e)}'

            finally:
                # Write result to CSV
                writer.writerow(result)


def add_images_to_project(doc, rgb_path, multispec_path, proj_file):
    """
    Adds images to the Metashape project with validation.
    """
    # Validate input paths
    if not rgb_path.exists():
        raise ValueError(f"RGB path not found: {rgb_path}")
    if not multispec_path.exists():
        raise ValueError(f"Multispec path not found: {multispec_path}")

    # Add RGB images
    p1_images = find_files(rgb_path, (".jpg", ".jpeg", ".tif", ".tiff"))
    if not p1_images:
        raise ValueError("No RGB images found")

    rgb_chunk = doc.addChunk()
    rgb_chunk.label = CHUNK_RGB
    rgb_chunk.addPhotos(p1_images)
    rgb_chunk.loadReferenceExif(load_rotation=True, load_accuracy=True)

    # Validate RGB chunk
    if len(rgb_chunk.cameras) == 0:
        raise ValueError("RGB chunk is empty")
    if "EPSG::4326" not in str(rgb_chunk.crs):
        raise ValueError("RGB chunk has invalid CRS")

    # Add multispec images
    micasense_images = find_files(multispec_path, (".jpg", ".jpeg", ".tif", ".tiff"))
    if not micasense_images:
        raise ValueError("No multispec images found")

    multispec_chunk = doc.addChunk()
    multispec_chunk.label = CHUNK_MULTISPEC
    multispec_chunk.addPhotos(micasense_images)

    # Validate multispec chunk
    if len(multispec_chunk.cameras) == 0:
        raise ValueError("Multispec chunk is empty")
    if "EPSG::4326" not in str(multispec_chunk.crs):
        raise ValueError("Multispec chunk has invalid CRS")

    # Validate sensor offsets
    if P1_GIMBAL1_OFFSET == 0:
        raise ValueError("Invalid P1 gimbal offset")

    # Check MicaSense configuration
    with open(micasense_images[0], 'rb') as f:
        exif_tags = exifread.process_file(f)
        cam_model = str(exif_tags.get('Image Model', 'UNKNOWN'))

    sensor_config = 'Dual' if len(multispec_chunk.sensors) >= 10 else 'Red'
    if offset_dict.get(cam_model, {}).get(sensor_config) == (0, 0, 0):
        raise ValueError(f"Invalid offsets for {cam_model} ({sensor_config})")

    # Clean up default chunk
    for chunk in doc.chunks:
        if chunk.label == "Chunk 1":
            doc.remove(chunk)
            break

if __name__ == "__main__":
    # Check Metashape license first
    try:
        if not Metashape.app.activated:
            raise RuntimeError("Metashape license not activated")
    except AttributeError:
        raise RuntimeError("Metashape module not properly installed")

    parser = argparse.ArgumentParser(description='Process drone imagery in Metashape')
    parser.add_argument('input_csv', help='Input CSV file with project parameters')
    args = parser.parse_args()

    # Generate output path automatically
    input_path = Path(args.input_csv)
    output_csv = proj_directory.with_name(input_path.stem + "project_created.csv")
    
    process_projects(args.input_csv, str(output_csv))