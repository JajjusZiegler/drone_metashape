"""
Script to process drone imagery in Metashape.

Author: Your Name
Date: 2025-05-07

This script reads project parameters from an input CSV file, processes the projects in Metashape,
and writes the results to an output CSV file.

Example usage:
    python metashape_proc_CreateProjects.py "M:/working_package_2/2024_dronecampaign/01_data/dronetest/processing_test/arguments_log_test3.csv"

The output CSV file will be generated automatically with "_project_created" appended to the input CSV filename
in the Upscale_Metashapeprojects directory.
"""

import argparse
import csv
import os
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Optional
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

# Define the root directory containing the site folders
root_site_directory = Path(r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects")

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

# Define the site name mapping dictionary
SITE_MAPPING = {
    "Stillberg": {
        "image_site_name": "stillberg",
        "folder_name": "Stillberg"
    },
    "Pfynwald": {
        "image_site_name": "Pfynwald",
        "folder_name": "Pfynwald"
    },
    "Illgraben": {
        "image_site_name": "Illgraben",
        "folder_name": "Illgraben"
    },
    "lwf_davos": {
        "image_site_name": "lwf_davos",
        "folder_name": "Davos_LWF"
    },
    "lwf_isone": {
        "image_site_name": "lwf_isone",
        "folder_name": "Isone_LWF"
    },
    "lwf_lens": {
        "image_site_name": "lwf_lens",
        "folder_name": "Lens_LWF"
    },
    "lwf_neunkirch": {
        "image_site_name": "lwf_neunkirch",
        "folder_name": "Neunkirch_LWF"
    },
    "lwf_schänis": {
        "image_site_name": "lwf_schänis",
        "folder_name": "Schänis_LWF"
    },
    "lwf_visp": {
        "image_site_name": "lwf_visp",
        "folder_name": "Visp_LWF"
    },
    "marteloskop": {
        "image_site_name": "marteloskop",
        "folder_name": "Marteloskop"
    },
    "sagno": {
        "image_site_name": "sagno",
        "folder_name": "Sagno_treenet"
    },
    "sanasilva_50845": {
        "image_site_name": "sanasilva_50845",
        "folder_name": "Brüttelen_sanasilva50845"
    },
    "sanasilva_50877": {
        "image_site_name": "sanasilva_50877",
        "folder_name": "Schüpfen_sanasilva50877"
    },
    "treenet_salgesch": {
        "image_site_name": "treenet_salgesch",
        "folder_name": "Salgesch_treenet"
    },
    "treenet_sempach": {
        "image_site_name": "treenet_sempach",
        "folder_name": "Sempach_treenet"
    },
    "wangen_zh": {
        "image_site_name": "wangen_zh",
        "folder_name": "WangenBrüttisellen_treenet"
    }
}

def find_site_folder(root_dir: Path, csv_site_name: str) -> Optional[Path]:
    """
    Finds the existing site folder within the root directory using the SITE_MAPPING.
    """
    for mapping in SITE_MAPPING.values():
        if csv_site_name.lower() == mapping["image_site_name"].lower():
            folder_path = root_dir / mapping["folder_name"]
            if folder_path.is_dir():
                return folder_path
            break
    return None

def process_projects(input_csv, output_csv):
    """
    Processes projects from the input CSV and writes results to the output CSV.
    """
    all_results = []  # Store results in a list

    with open(input_csv, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            # Extract required columns
            date_str = row['date']
            site_name_from_csv = row['site']
            rgb_path = Path(row['rgb'])
            multispec_path = Path(row['multispec'])
            sunsens = row['sunsens'].lower() == 'true' # Convert string to boolean

            # Find the correct site folder using the mapping
            site_folder = find_site_folder(root_site_directory, site_name_from_csv)
            
            if not site_folder:
                print(f"Warning: Could not find a matching site folder for '{site_name_from_csv}' based on the mapping. Skipping project creation.")
                result = [
                    date_str, site_name_from_csv, str(rgb_path), str(multispec_path), sunsens,
                    'N/A', 'skipped (site folder not found - mapping)'
                ]
                all_results.append(result)
                continue

            # Define project path within the found site folder
            proj_file = site_folder / date_str / f"metashape_project_{site_folder.name}_{date_str}.psx"

            # Prepare result entry
            result = [
                date_str, site_name_from_csv, str(rgb_path), str(multispec_path), sunsens,
                str(proj_file), 'skipped'  # Default status
            ]

            try:
                # Skip if project already exists
                if proj_file.exists():
                    print(f"Skipping existing project: {proj_file}")
                    result[6] = 'skipped (exists)'
                else:
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
                print(f"Error processing {site_name_from_csv}/{date_str}: {str(e)}")
                result[6] = f'error: {str(e)}'

            finally:
                all_results.append(result)  # Store the result

    # Write all results to the output CSV at the end
    with open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(['date', 'site', 'rgb', 'multispec', 'sunsens', 'project_path', 'image_load_status'])
        writer.writerows(all_results)

def add_images_to_project(doc, rgb_path, multispec_path, proj_file):
    """
    Adds images to the Metashape project with validation.
    """
    print(f"Adding images to project: {proj_file}")
    print(f"RGB path: {rgb_path}")
    print(f"Multispec path: {multispec_path}")

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
    multispec_chunk.locateReflectancePanels()

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
    output_csv = proj_directory / (input_path.stem + "_project_created.csv")

    #process_projects(args.input_csv, str(output_csv))

    # Debugging: Print the input CSV path and output CSV path
    print(f"Input CSV: {args.input_csv}")
    print(f"Output CSV: {output_csv}")

    # Debugging: Check if the mapping works for each site in the input CSV
    with open(args.input_csv, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            site_name_from_csv = row['site']
            site_folder = find_site_folder(root_site_directory, site_name_from_csv)
            if site_folder:
                print(f"Mapping successful for site '{site_name_from_csv}': {site_folder.name}")
            else:
                print(f"Mapping failed for site '{site_name_from_csv}'")

    # Debugging: Print the folder structure for each site and date
    with open(args.input_csv, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            site_name_from_csv = row['site']
            date_str = row['date']
            site_folder = find_site_folder(root_site_directory, site_name_from_csv)
            if site_folder:
                project_folder = site_folder / date_str
                print(f"Site folder: {site_folder}")
                print(f"Date folder: {project_folder}")
                print(f"Project folder: {project_folder / f'metashape_project_{site_folder.name}_{date_str}.psx'}")
            else:
                print(f"Mapping failed for site '{site_name_from_csv}'")


    process_projects(args.input_csv, str(output_csv))