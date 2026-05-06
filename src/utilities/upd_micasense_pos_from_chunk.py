# -*- coding: utf-8 -*-
"""
New interpolation method using aligned RGB chunk camera positions instead of MRK files.
"""

import Metashape
import numpy as np
import exifread
import datetime
import glob
import os
import math
from datetime import datetime, timedelta

# Constants (matching original script)
MICA_deltat = -18  # GPS to UTC offset if needed, or sensor specific offset? 
# In original script: MICA_deltat = -18. 
# It seems this is actually LEAP seconds related (GPS linear time vs UTC). 
# But let's stick to the user's existing constants if possible or derive from context.
# Original script uses:
LEAPSECS = 37
GPSUTC_deltat = 0
MICA_deltat = -18 

# We will need to check how timestamps are handled. 
# If we get timestamps from Metashape cameras, they might be in a specific format.

def get_micasense_images(micasense_folder, image_suffix):
    """
    Get list of MicaSense images and their timestamps/paths.
    """
    print(f"Searching for *{image_suffix}.tif in {micasense_folder}")
    if not os.path.exists(micasense_folder):
         print(f"Folder not found: {micasense_folder}")
         return []
         
    # Recursive search
    files = list(glob.iglob(os.path.join(micasense_folder, "**", f"*{image_suffix}.tif"), recursive=True))
    
    micasense_data = []
    
    for file_path in files:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            
            if not tags:
                continue
                
            # Extract timestamp
            dt_str = str(tags.get('EXIF DateTimeOriginal')) 
            subsec_str = str(tags.get('EXIF SubSecTime'))
            
            try:
                dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                
                # Handle subsecond
                subsec = float(subsec_str)
                # Handle negative/positive logic from original script
                if subsec < 0:
                    subsec_val = -1.0 * float(f"0.{int(abs(subsec))}")
                else:
                    subsec_val = float(f"0.{int(subsec)}")
                
                full_dt = dt + timedelta(seconds=subsec_val)
                # Apply MICA_deltat from original script logic
                # mica_timestamp = temp_timestamp - timedelta(seconds=MICA_deltat)
                # The original script does: mica_timestamp = temp_timestamp - timedelta(seconds=MICA_deltat)
                # This suggests MICA_deltat is subtracting (-18), effectively adding 18 seconds? 
                # Or extracting 18 seconds. 
                # GPS time is ahead of UTC by ~18 seconds.
                # If EXIF is UTC, and we want GPS time? Or vice versa.
                # Let's trust the constant from the original file (-18).
                
                final_dt = full_dt - timedelta(seconds=-18) 
                
                micasense_data.append({
                    'path': file_path,
                    'timestamp': final_dt.timestamp(),
                    'datetime': final_dt,
                    'filename': os.path.basename(file_path)
                })
                
            except Exception as e:
                print(f"Error reading timestamp for {file_path}: {e}")
                
    # Sort by timestamp
    micasense_data.sort(key=lambda x: x['timestamp'])
    return micasense_data

def get_p1_data_from_chunk(chunk):
    """
    Extract timestamps and aligned positions from RGB chunk cameras.
    Returns sorted lists of timestamps and positions.
    """
    p1_data = []
    
    if not chunk:
        print("RGB Chunk is None")
        return None, None

    print(f"Processing chunk: {chunk.label}, Cameras: {len(chunk.cameras)}")
    
    for camera in chunk.cameras:
        if not camera.transform:
            continue # Skip unaligned cameras
            
        # Get position in chunk coordinate system (usually local or georeferenced)
        # We need the Estimated position (from reference) or the Aligned position (from transform)?
        # User said: "use the aligned camera positions of the rgb chunk"
        # If the chunk is georeferenced, chunk.crs is present.
        
        if not chunk.crs:
            print("Chunk has no CRS. Cannot rely on alignment for georeferencing.")
            return None, None
            
        # Transform camera center to geocentric/projected coordinates
        # camera.center is in internal chunk coordinates
        center_internal = camera.center
        if center_internal is None:
            continue

        # Convert to geographic/projected (CRS of the chunk)
        center_geo = chunk.crs.project(chunk.transform.matrix.mulp(center_internal))
        
        # We also need the timestamp. 
        # Metashape usually stores captured time in camera.photo.meta['Exif/DateTimeOriginal']
        # But sometimes it might be simpler to read from disk if needed, 
        # but accessing meta property is faster if available.
        try:
            # Try to get timestamp from meta
            date_str = camera.photo.meta["Exif/DateTimeOriginal"]
            # Format usually: 2024:08:08 09:37:05
            # Subseconds might be in "Exif/SubSecTime"
            subsec_str = "0"
            if "Exif/SubSecTime" in camera.photo.meta:
                 subsec_str = camera.photo.meta["Exif/SubSecTime"]

            try:
                subsec = float(f"0.{int(subsec_str)}")
            except:
                subsec = 0.0

            dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            
            # P1 (DJI) timestamps in EXIF are usually UTC.
            # We need to ensure we align with how we treated MicaSense.
            # In original script:
            # P1 timestamp logic: parsed MRK, GPS time.
            # MRK is GPS time?
            # User's logic: "Quality marker in the MRK... if it is 50 the RTK tag is good".
            # The user wants to replace MRK with Aligned Position.
            # Aligned positions corresponds to the image. 
            # We assume image timestamp is consistent with the position.
            
            full_dt = dt + timedelta(seconds=subsec)
            
            # DJI P1 images usually store UTC in Exif.
            # Original script MRK parsing: 
            # epoch_secs = secs + (week*7*24*60*60) -> GPS Time
            # p1_camera_timestamp = temp_timestamp - timedelta(seconds=GPSUTC_deltat) -> UTC (if GPSUTC_deltat=0)
            # original script has GPSUTC_deltat = 0.
            
            p1_data.append({
                'timestamp': full_dt.timestamp(),
                'pos': [center_geo.x, center_geo.y, center_geo.z], # Easting, Northing, Altitude
                'label': camera.label
            })
            
        except Exception as e:
            # print(f"Could not parse time for {camera.label}: {e}")
            pass
            
    # Sort by timestamp
    p1_data.sort(key=lambda x: x['timestamp'])
    
    timestamps = np.array([x['timestamp'] for x in p1_data])
    positions = np.array([x['pos'] for x in p1_data])
    
    return timestamps, positions

# Constants
GPSUTC_deltat = 0     # From original script
LEAPSECS = 37         # From original script
MICA_deltat = -18     # From original script

def get_timestamp_from_mrk_line(mrk_line):
    """
    Parse timestamp from a single MRK line.
    Reuses logic from visualize_timestamps.py / original script.
    """
    parts = mrk_line.split()
    if len(parts) < 3:
        return None
        
    secs = float(parts[1])
    week = int(parts[2].strip("[]"))
    
    # GPS Time to UTC logic from original script
    epoch_secs = secs + (week * 7 * 24 * 60 * 60)
    temp_timestamp = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
    p1_timestamp = temp_timestamp - timedelta(seconds=GPSUTC_deltat)
    
    return p1_timestamp.timestamp()

def get_mrk_timestamps(rgb_folder):
    """
    Read all MRK files in the folder and return a flat list of timestamps.
    Assumes MRK files are named/sorted such that they match image order.
    """
    print(f"Reading MRK files from: {rgb_folder}")
    mrk_files = sorted(glob.glob(os.path.join(rgb_folder, "**", "*.MRK"), recursive=True))
    
    if not mrk_files:
        print("No MRK files found.")
        return []
        
    timestamps = []
    for m_file in mrk_files:
        with open(m_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                ts = get_timestamp_from_mrk_line(line)
                if ts is not None:
                    timestamps.append(ts)
                    
    print(f"Loaded {len(timestamps)} timestamps from MRK files.")
    return timestamps

def get_p1_data_hybrid(chunk, rgb_folder):
    """
    Combine Metashape Estimated Reference positions with MRK timestamps.
    Matches are made by sorting cameras by filename and matching with MRK line order.
    Position Source: Metashape exportReference (Estimated - nuvw)
    Timestamp Source: MRK Files
    """
    if not chunk:
        print("RGB Chunk is None")
        return None, None

    # 1. Get MRK Timestamps (Precise)
    mrk_timestamps = get_mrk_timestamps(rgb_folder)
    if not mrk_timestamps:
        return None, None

    # 2. Export Estimated Reference (n=label, u=est_x, v=est_y, w=est_z)
    print(f"Exporting estimated reference for chunk: {chunk.label}")
    temp_csv = "temp_metashape_reference_export.csv"
    if os.path.exists(temp_csv):
        try:
            os.remove(temp_csv)
        except:
            pass
            
    try:
        # Export Label and Estimated Coordinates
        chunk.exportReference(path=temp_csv, format=Metashape.ReferenceFormatCSV, items=Metashape.ReferenceItemsCameras, columns="nuvw", delimiter=",")
    except Exception as e:
        print(f"Error exporting reference: {e}")
        return None, None

    # 3. Read Estimated Positions
    est_pos_map = {} # Label -> [x, y, z]
    try:
        with open(temp_csv, "r", encoding="utf-8") as f:
            # Skip header if present (metashape usually doesn't add header with custom columns unless specified differently, but let's check content)
            # Actually exportReference usually creates a header-less CSV or straightforward one.
            # We iterate and parse.
            import csv
            reader = csv.reader(f, delimiter=',')
            for row in reader:
                if len(row) < 4:
                    continue
                # map: label -> x,y,z
                label = row[0]
                try:
                    x = float(row[1])
                    y = float(row[2])
                    z = float(row[3])
                    
                    # Store both raw label and label without extension for robust matching
                    est_pos_map[label] = [x, y, z]
                    base_label = os.path.splitext(label)[0]
                    if base_label != label:
                        est_pos_map[base_label] = [x, y, z]
                        
                except ValueError:
                    continue # header or invalid
            print(f"DEBUG: Loaded {len(est_pos_map)} estimated positions from reference export.")
    except Exception as e:
         print(f"Error reading exported reference: {e}")
         return None, None
    finally:
        if os.path.exists(temp_csv):
            try:
                os.remove(temp_csv)
            except:
                pass


    # 4. Match with MRK Timestamps
    print(f"Processing chunk: {chunk.label}, Cameras: {len(chunk.cameras)}")
    
    valid_cameras = []
    for camera in chunk.cameras:
        valid_cameras.append(camera)

    # Sort cameras by label (filename) to match MRK order
    valid_cameras.sort(key=lambda c: c.label)
    
    if len(valid_cameras) != len(mrk_timestamps):
        print(f"WARNING: Count mismatch! MRK lines: {len(mrk_timestamps)}, Metashape Cameras: {len(valid_cameras)}")
        print("Attempting to proceed, using minimum common length.")
    
    p1_data = []
    limit = min(len(valid_cameras), len(mrk_timestamps))
    
    match_count = 0
    aligned_count = 0
    
    for i in range(limit):
        cam = valid_cameras[i]
        ts = mrk_timestamps[i]
        
        if cam.label not in est_pos_map:
            # This happens if camera is not aligned (so no estimated position exported)
            continue
            
        aligned_count += 1
        pos = est_pos_map[cam.label]
        
        p1_data.append({
            'timestamp': ts,
            'pos': pos,
            'label': cam.label
        })
        match_count += 1

    print(f"Matched {match_count} aligned cameras with timestamps/exported positions.")
    
    # Sort just in case
    p1_data.sort(key=lambda x: x['timestamp'])
    
    timestamps = np.array([x['timestamp'] for x in p1_data])
    positions = np.array([x['pos'] for x in p1_data])
    
    return timestamps, positions

def interpolate_positions(mica_data, p1_timestamps, p1_positions):
    """
    Interpolate MicaSense positions based on P1 data.
    """
    interpolated_positions = []
    
    for mica in mica_data:
        ts = mica['timestamp']
        
        # Check bounds
        if ts < p1_timestamps[0] or ts > p1_timestamps[-1]:
            # Out of range
            interpolated_positions.append({
                'label': mica['path'], 
                'easting': 0, 'northing': 0, 'height': 0,
                'timestamp_str': mica['datetime'].strftime("%Y-%m-%d %H:%M:%S.%f"),
                'valid': False
            })
            continue
            
        # Find neighbours
        idx = np.searchsorted(p1_timestamps, ts)
        
        # idx is where ts should be inserted.
        # So p1_timestamps[idx-1] <= ts <= p1_timestamps[idx]
        if idx == 0:
            # Should have been caught by bounds check, but just in case
            idx = 1
            
        t0 = p1_timestamps[idx-1]
        t1 = p1_timestamps[idx]
        
        p0 = p1_positions[idx-1]
        p1 = p1_positions[idx]
        
        # Linear interpolation factor
        if t1 == t0:
            alpha = 0
        else:
            alpha = (ts - t0) / (t1 - t0)
            
        # Interpolate
        pos_interp = p0 + alpha * (p1 - p0)
        
        interpolated_positions.append({
            'label': mica['path'], # Use full path as label to match original output format
            'easting': pos_interp[0],
            'northing': pos_interp[1],
            'height': pos_interp[2],
            'timestamp_str': mica['datetime'].strftime("%Y-%m-%d %H:%M:%S.%f"),
            'valid': True
        })
        
    return interpolated_positions

def run_interpolation_from_chunk(project_path, micasense_folder, output_csv, rgb_folder=None):
    """
    Main function to run the process.
    rgb_folder: Optional, path to folder with MRK files. If provided, uses hybrid method (Metashape Position + MRK Timestamp).
    """
    print(f"Opening project: {project_path}")
    doc = Metashape.Document()
    doc.open(str(project_path), read_only=True)
    
    # 1. Find RGB chunk
    # We look for a chunk that is likely the RGB one. 
    # Usually named "Chunk 1" or similar, or we can check if it has P1 (DJI) images.
    rgb_chunk = None
    for chunk in doc.chunks:
        # Check cameras
        if chunk.cameras and len(chunk.cameras) > 0:
            cam = chunk.cameras[0]
            if cam.photo and cam.photo.meta:
                try:
                    model = cam.photo.meta["Exif/Model"]
                except KeyError:
                    model = ""
                
                if "P1" in model or "M300" in model or "Zenmuse" in model:
                    rgb_chunk = chunk
                    print(f"Found RGB Chunk: {chunk.label}")
                    break
    
    if not rgb_chunk:
        # Fallback: try finding first chunk that is NOT multispectral (if labeled)
        for chunk in doc.chunks:
            if "multispec" not in chunk.label.lower():
                rgb_chunk = chunk
                print(f"Assuming RGB Chunk (fallback): {chunk.label}")
                break
                
    if not rgb_chunk:
        print("Could not identify RGB chunk.")
        return

    # 2. Get P1 Data
    if rgb_folder:
        print("Using Hybrid Method: Position from Metashape + Timestamp from MRK")
        p1_ts, p1_pos = get_p1_data_hybrid(rgb_chunk, rgb_folder)
    else:
        print("Using Standard Method: Position and Timestamp from Metashape/EXIF")
        p1_ts, p1_pos = get_p1_data_from_chunk(rgb_chunk)
    
    if p1_ts is None or len(p1_ts) == 0:
        print("No aligned P1 cameras found in chunk.")
        return

    # 3. Get MicaSense Data
    # suffix 6 is generic master, usually red edge or similar in 6-band? 
    # Original script uses suffix depending on input. We'll default to 6 or user provided.
    mica_data = get_micasense_images(micasense_folder, image_suffix="6")
    
    if not mica_data:
        print("No MicaSense images found.")
        return
        
    # 4. Interpolate
    results = interpolate_positions(mica_data, p1_ts, p1_pos)
    
    # 5. Write CSV
    print(f"Writing results to {output_csv}")
    with open(output_csv, "w", encoding="utf-8") as f:
        # Header matching original format
        f.write("Label, Easting, Northing, Ellip Height, Timestamp\n")
        
        for res in results:
            ts_str = res.get('timestamp_str', '')
            f.write(f"{res['label']}, {res['easting']:.4f}, {res['northing']:.4f}, {res['height']:.4f}, {ts_str}\n")
            
    print("Done.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="Path to Metashape project (.psx)")
    parser.add_argument("--micasense", required=True, help="Path to MicaSense images folder")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--rgb", help="Path to RGB folder containing MRK files (optional)")
    args = parser.parse_args()
    
    run_interpolation_from_chunk(args.project, args.micasense, args.output, args.rgb)
