"""This script is used to interpolate the camera positions of the MicaSense RedEdge camera in Metashape. 
The script reads the camera positions from the MicaSense RedEdge camera images and interpolates the positions 
for the missing images. The script uses the `ret_micasense_pos` function from the `upd_micasense_pos_filename.py` 
script to interpolate the camera positions. The script reads the project file path, RGB image path, multispectral 
image path, date, and site information from a CSV file. The script processes the Metashape project file, 
retrieves the MicaSense RedEdge camera positions, and interpolates the positions for the missing images. 
The script saves the interpolated camera positions to a CSV file in the references folder of the project directory.

The script should be used, if the original script fails. 

```python"""

import Metashape
import csv
import os
import time
from pathlib import Path
from upd_micasense_pos_filename import ret_micasense_pos

def get_master_band_paths_by_suffix(chunk, suffix="_6.tif"):
    if not chunk:
        print("Error: Input chunk is None.")
        return []
    master_band_paths = [camera.photo.path for camera in chunk.cameras if camera.photo and camera.photo.path.endswith(suffix)]
    return master_band_paths

def safe_get_position(upd_pos, retries=3, delay=1):
    for _ in range(retries):
        if upd_pos is not None:
            return upd_pos
        time.sleep(delay)
    raise ValueError("Failed to retrieve valid position data after retries.")

def process_metashape(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            project_path = Path(row['project_path'])
            rgb_path = row['rgb']
            multispec_path = row['multispec']
            date = row['date']
            site = row['site']

            project_dir = project_path.parent
            file_prefix = f"{date}_{site}"
            export_dir = project_dir / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            reference_dir = project_dir / "references"
            reference_dir.mkdir(parents=True, exist_ok=True)
            MICASENSE_CAM_CSV = reference_dir / "interpolated_micasense_pos.csv"   

            if not project_path.exists():
                print(f"Skipping: Project file not found - {project_path}")
                continue

            if MICASENSE_CAM_CSV.exists():
                print(f"Skipping: Interpolated MicaSense positions already exist - {MICASENSE_CAM_CSV}")
                continue


            
            print(f"Processing project: {project_path}")
            doc = Metashape.Document()
            doc.open(str(project_path), read_only=False)
            doc.read_only = False
            
            if not doc.chunks:
                print(f"Skipping: No chunks found in {project_path}")
                continue
            
           
            CHUNK_MULTISPEC = "multispec"
            dict_chunks = {get_chunk.label: get_chunk.key for get_chunk in doc.chunks}
            chunk = doc.findChunk(dict_chunks.get(CHUNK_MULTISPEC))
            
            if not chunk:
                print(f"Skipping: Multispectral chunk not found in {project_path}")
                continue
            
            master_band_paths = get_master_band_paths_by_suffix(chunk)
            if not master_band_paths:
                print(f"Skipping: No master band images found in {project_path}")
                continue
            

            

            P1_shift_vec = [0, 0, 0]
            
            print(f"Running ret_micasense_pos for {project_path}...")
            ret_micasense_pos(master_band_paths, rgb_path, multispec_path, "6", "2056", str(MICASENSE_CAM_CSV), P1_shift_vec)
            print(f"Processing complete for {project_path}. Output: {MICASENSE_CAM_CSV}")
            doc.save() # Save the Metashape document after processing each project
            del doc# Close the Metashape document after processing each project

if __name__ == "__main__":
    csv_file_path = input("Enter the path to your CSV file: ").strip()
    process_metashape(csv_file_path)
