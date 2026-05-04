import argparse
import csv
import os
from pathlib import Path
from typing import List, Tuple
import exifread
import Metashape

# Define Metashape project directory
proj_directory = Path(r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Multispec_Metashapeprojects")

# Chunk label for multispectral images
CHUNK_MULTISPEC = "multispec"


def find_files(folder: Path, extensions: Tuple[str]) -> List[str]:
    """Recursively find files with specified extensions."""
    return [
        str(p) for p in folder.rglob("*")
        if p.suffix.lower() in extensions and p.is_file()
    ]


def process_projects(input_csv, output_csv):
    """
    Processes projects from the input CSV and writes results to the output CSV.
    """
    with open(input_csv, 'r', newline='', encoding='utf-8') as infile, open(output_csv, 'a', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile)
        writer = csv.writer(outfile)

        # Write header if output file is empty
        if outfile.tell() == 0:
            writer.writerow(['date', 'site', 'multispec', 'sunsens', 'project_path', 'image_load_status'])

        for row in reader:
            # Extract required columns
            date = row['date']
            site = row['site']
            multispec_path = Path(row['multispec'])
            sunsens = row['sunsens']

            # Define project path
            proj_file = proj_directory / site / date / f"metashape_project_{site}_{date}.psx"

            # Prepare result entry
            result = [date, site, str(multispec_path), sunsens, str(proj_file), 'skipped']

            try:
                # Skip if project already exists
                if proj_file.exists():
                    print(f"Skipping existing project: {proj_file}")
                    result[5] = 'skipped (exists)'
                    writer.writerow(result)
                    continue

                # Create new Metashape document
                doc = Metashape.Document()
                proj_file.parent.mkdir(parents=True, exist_ok=True)

                # Add multispectral images to project
                add_images_to_project(doc, multispec_path, proj_file)

                # Save project
                doc.save(path=str(proj_file))
                print(f"Created project: {proj_file}")
                result[5] = 'success'

            except Exception as e:
                print(f"Error processing {site}/{date}: {str(e)}")
                result[5] = f'error: {str(e)}'

            finally:
                writer.writerow(result)


def add_images_to_project(doc, multispec_path, proj_file):
    """
    Adds multispectral images to the Metashape project with validation.
    """
    if not multispec_path.exists():
        raise ValueError(f"Multispec path not found: {multispec_path}")

    # Add multispec images
    micasense_images = find_files(multispec_path, (".jpg", ".jpeg", ".tif", ".tiff"))
    if not micasense_images:
        raise ValueError("No multispec images found")

    multispec_chunk = doc.addChunk()
    multispec_chunk.label = CHUNK_MULTISPEC
    multispec_chunk.addPhotos(micasense_images)
    # Locate reflectance panels
    multispec_chunk.locateReflectancePanels()

    # Validate multispec chunk
    if len(multispec_chunk.cameras) == 0:
        raise ValueError("Multispec chunk is empty")
    if "EPSG::4326" not in str(multispec_chunk.crs):
        raise ValueError("Multispec chunk has invalid CRS")

    # Clean up default chunk
    for chunk in doc.chunks:
        if chunk.label == "Chunk 1":
            doc.remove(chunk)
            break


if __name__ == "__main__":
    try:
        if not Metashape.app.activated:
            raise RuntimeError("Metashape license not activated")
    except AttributeError:
        raise RuntimeError("Metashape module not properly installed")

    parser = argparse.ArgumentParser(description='Process multispectral drone imagery in Metashape')
    parser.add_argument('input_csv', help='Input CSV file with project parameters')
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_csv = proj_directory.with_name(input_path.stem + "_project_created.csv")
    
    process_projects(args.input_csv, str(output_csv))
