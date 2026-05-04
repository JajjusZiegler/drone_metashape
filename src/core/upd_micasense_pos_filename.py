# -*- coding: utf-8 -*-
"""
Created August 2021

@authors: Poornima Sivanandam and Darren Turner

Script by Darren Turner (lever_arm_m300.py) updated to interpolate micasense camera positions using P1 MRK.

This module is imported in other py scripts that process p1+micasense imagery.

- EXIF Image Date/Time and SubSecTime of MicaSense master band images used to identify the two closest P1 images (before
  and after Micasense image).
- P1 positions converted to target projected coordinate reference system for interpolation based on timestamp and distance 
- MicaSense position interpolated using the timestamps and positions of the two closest P1 images
- If Micasense image was captured before P1 triggered, original X, Y and Altitude of 0 written to output CSV to delete
  these images later (outisde this script).
- Updated camera coordinates written in csv in the format (and with the header):
    label, Easting, Northing, Ellipsoidal height

"""

import os
import glob
import numpy as np
import exifread
import datetime
import requests
from pyproj.transformer import TransformerGroup
from datetime import datetime, timedelta
import logging


###############################################################################
# Variable declarations, constants
###############################################################################
global mrk_file_count, P1_first_timestamp, P1_last_timestamp, P1_events, P1_pos, P1_pos_mrk

P1_shift_vec = np.array([0.0, 0.0, 0.0])
P1_events = []
P1_pos_mrk = []
P1_pos = []
P1_first_timestamp = {}
P1_last_timestamp = {}

LEAPSECS = 37
GPSUTC_deltat = 0
MICA_deltat = -18
EPSG_4326 = 4326


# API endpoint for the Swisstopo transformation.
# wgs84tolv95 returns CH1903+/LV95 horizontal coordinates (EPSG:2056) + LN02 altitude,
# which is the correct modern Swiss datum.  The old wgs84tolv03 (LV03/CH1903) endpoint
# introduces a ~1–3 m horizontal offset and should not be used for EPSG:2056 targets.
API_URL = "https://geodesy.geo.admin.ch/reframe/wgs84tolv95"

###############################################################################
# Functions
###############################################################################
# added twp new functions, that use swisstopo api to get CH1903+ coordinates for P1 positions


def transform_coordinates(lon, lat, alt=None, max_retries=3, delay=0.15):
    """
    Transform coordinates using the Swisstopo API.
    Parameters:
      lon (float): Longitude (or easting) in WGS84.
      lat (float): Latitude (or northing) in WGS84.
      alt (float, optional): Altitude value.
      max_retries (int): Number of retry attempts on failure.
      delay (float): Seconds to wait between API calls to avoid rate limiting.
    Returns:
      dict: A dictionary with keys 'easting', 'northing', and 'altitude' containing transformed values.
            Returns None if the transformation fails.
    """
    import time
    # Build the request parameters.
    params = {"northing": lat, "easting": lon, "altitude": alt, "format": "json"}
    for attempt in range(max_retries):
        try:
            if delay > 0:
                time.sleep(delay)
            response = requests.get(API_URL, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()

            # Ensure we get numeric values from the response
            return {
                "easting": float(result.get("easting", 0.0)),
                "northing": float(result.get("northing", 0.0)),
                "altitude": float(result.get("altitude", 0.0))
            }
        except Exception as e:
            logging.warning(f"API attempt {attempt+1}/{max_retries} failed for lon={lon}, lat={lat}: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(1.0)  # longer back-off before retry
    print(f"Error in transform_coordinates for lon: {lon}, lat: {lat}: all {max_retries} attempts failed")
    return None

def get_transformed_P1_positions(mrk_file):
    """
    Reads an MRK file and transforms each position using the API.
    Assumes that each MRK file line is space‐delimited and that
    latitude is in field 6, longitude in field 7, and ellipsoidal height in field 8.
    (Adjust indexes if your file format differs.)
    
    Parameters:
      mrk_file (str): Path to the MRK file.
      
    Returns:
      list: A list of dictionaries with the transformed positions for each line.
            Each entry is of the form:
              {"timestamp": <timestamp>, "easting": <value>, "northing": <value>, "altitude": <value>}
            or None for lines that could not be transformed.
    """
    transformed_positions = []
    with open(mrk_file, 'r') as f:
        lines = f.readlines()
    
    # Optional: if your file contains a header or metadata, skip those lines here.
    for line in lines:
        # Split the line into components
        fields = line.split()
        if len(fields) < 9:
            print(f"Skipping line due to insufficient fields: {line}")
            continue

        # Extract latitude, longitude, and ellipsoidal height.
        # Adjust the splitting if your file uses a different separator.
        try:
            lat = float(fields[6].split(",")[0])
            lon = float(fields[7].split(",")[0])
            ellh = float(fields[8].split(",")[0])
        except Exception as e:
            print(f"Error parsing line '{line}': {e}")
            transformed_positions.append(None)
            continue

        # # Optionally, if you need the timestamp from the MRK file, you can compute it here.
        # # For example, using fields[1] (seconds) and fields[2] (week), as in your original code:
        # try:
        #     secs = float(fields[1])
        #     week = int(fields[2].strip("[").strip("]"))
        #     epoch_secs = secs + (week * 7 * 24 * 60 * 60)
        #     temp_timestamp = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
        #     # Adjust for GPS to UTC offset if needed:
        #     # p1_timestamp = temp_timestamp - timedelta(seconds=GPSUTC_deltat)
        #     p1_timestamp = temp_timestamp  # Adjust as required
        # except Exception as e:
        #     print(f"Error parsing timestamp from line '{line}': {e}")
        #     p1_timestamp = None

        # Call the API to transform coordinates
        result = transform_coordinates(lon, lat, ellh)
        if result:
            transformed_positions.append({
                #"timestamp": p1_timestamp,
                "easting": result["easting"],
                "northing": result["northing"],
                "altitude": result["altitude"]
            })
        else:
            transformed_positions.append(None)
    return transformed_positions


def find_nearest(array, value):
    """
    Return index of value nearest to "value" in array, that is, nearest P1 timestamp to MicaSense time 'value'
    """
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx   


def get_P1_timestamp(p1_mrk_line):
    """
    Return timestamp from line p1_mrk_line in MRK
    """
    mrk_line = p1_mrk_line.split()   
    secs = float(mrk_line[1])
    week = int(mrk_line[2].strip("[").strip("]"))
    epoch_secs = secs + (week*7*24*60*60)
    temp_timestamp = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
    p1_camera_timestamp = temp_timestamp - timedelta(seconds=GPSUTC_deltat) 
    return(p1_camera_timestamp.timestamp())


def _convert_to_degress(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value:
    :type value: exifread.utils.Ratio
    :rtype: float
    """
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den)
    s = float(value.values[2].num) / float(value.values[2].den)

    return d + (m / 60.0) + (s / 3600.0)


def get_P1_position(MRK_file, file_count):
    """
    Inputs: MRK file name, file count (in case of more than one MRK file for same mission). 
    Returns: None
    - Updates First and Last P1 timestamp for flight
    For all images:
    - Update P1_events with camera timestamp
    - Update P1_pos_mrk with Lat/Lon/Ellipsoidal height from MRK

    """
    global P1_first_timestamp, P1_last_timestamp
    global P1_pos_mrk, P1_events
        
    print("Get P1 position")

    with open(MRK_file, 'r') as mrk_in:
        mrks = mrk_in.readlines()
    
    P1_first_timestamp[file_count] = get_P1_timestamp(mrks[0])
    P1_last_timestamp[file_count] = get_P1_timestamp(mrks[-1])
    
    for mrk in mrks:
        m = mrk.split()
        
        secs = float(m[1])
        week = int(m[2].strip("[").strip("]"))
        epoch_secs = secs + (week*7*24*60*60)
        temp_timestamp = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
        camera_timestamp = temp_timestamp - timedelta(seconds=GPSUTC_deltat)
        
        lat = float(m[6].split(",")[0])
        lon = float(m[7].split(",")[0])
        ellh = float(m[8].split(",")[0])
        
        P1_events.append(camera_timestamp)
        P1_pos_mrk.append([lat, lon, ellh])

    
def ret_micasense_pos(absolute_micasense_file_list,mrk_folder, micasense_folder, image_suffix, epsg_crs, out_file, P1_shift_vec):
    """
    Parameters
    ----------
    mrk_folder : string
        Path to P1 MRK files
    micasense_folder : string
        Path to MicaSense images 
    image_suffix : integer
        File suffix for MicaSense master band images

 ++++++++++++++ CURRENTLY NOT IN USE ++++++++++++++
    epsg_crs : 
        EPSG code for projected coordinate system - used to interpoalte MicaSense position based on nearest timestamps

++++++++++++++ CURRENTLY NOT IN USE ++++++++++++++


    out_file : string
        Path and name of output CSV file with udpated Easting/Norhting/Altitude for all MicaSense images
    P1_shift_vec : vector
        Vector to be used to blockshift P1 positions. 

    Returns
    -------
    None. out_file written with updated positions.

    """
    print("Loading micasense images")

    # Reset global state per call (module is imported and reused across runs)
    global P1_events, P1_pos_mrk, P1_pos, P1_first_timestamp, P1_last_timestamp
    P1_events = []
    P1_pos_mrk = []
    P1_pos = []
    P1_first_timestamp = {}
    P1_last_timestamp = {}
    
    mica_events = []
    mica_pos = []
    mica_count = 0
    
    # Used to convert P1 positions from WGS84 Lat/Lon (EPSG: 4326) to projected coordinate system
    # Assumption that '-crs' input by user (TERN data across Australia only) is GDA2020 projected coordinate system.
    # E.g. EPSG: 7855 for Tasmania

    # Issue in pyproj/proj version available for py3.9/Metashape Pro 2.0.1 where a different transformation (to
    # Metashape/previous Proj version) is chosen.
    # Fix in later PROJ version has been to chose transformation with fewer steps - which in the case of GDA2020
    # projected CS is the one chosen in Metashape as well.
    # see https://github.com/OSGeo/PROJ/pull/3248
    transf_group = TransformerGroup(EPSG_4326, int(epsg_crs))

    # Specify pipeline to avoid issues with different transformers being chosen depending on PROJ version
    # More info:https://github.com/pyproj4/pyproj/issues/989#issuecomment-974149918
    step_count = []
    for tr in transf_group.transformers:
        step_count.append(str(tr).count("step")) # count 'steps' in each pipeline

    # Revisit below fix to use transformer with fewer steps in case of any future updates to Metashape/PyProj/PROJ
    min_step_idx = step_count.index(min(step_count))
    transformer = transf_group.transformers[min_step_idx]

    # List of MicaSense master band images
    if absolute_micasense_file_list:
        filelist = absolute_micasense_file_list
    else:
        os.chdir(micasense_folder)
        filelist = glob.glob("**/IMG*_" + str(image_suffix)+".tif", recursive=True)
    
    if not filelist:
        logging.warning("No matching images found in the specified folder.")
    
    # Get timestamp of MicaSense images using exifread
    for file in filelist:
        f = open(file, 'rb')
        
        # Read Exif tags
        tags = exifread.process_file(f)
        
        # 20/12 adding this check to skip empty image files seen with old RedEdge sensor
        if not tags:
            continue
        
        mica_time = str(tags.get('EXIF DateTimeOriginal'))     
        mica_subsec_time = str(tags.get('EXIF SubSecTime'))
        
        #interpretation of SubSecTime for RedEdge from:
        #https://github.com/micasense/imageprocessing/blob/master/micasense/metadata.py
        # From micasense email: The code corrects negative subsecond time which was a bug years ago in the GPS chip, 
        # but this has now been fixed. If you ever do encounter negative subsecond time, it should 
        # be interpreted literally. You would subtract that from the time instead of adding the positive time.   
        subsec = int(mica_subsec_time)
        negative = 1.0
        if subsec < 0:
            print(subsec)
            negative = -1.0
            subsec *= -1.0
        subsec = float('0.{}'.format(int(subsec)))
        subsec *= negative
        millisec = subsec * 1e3
        
        utc_time = datetime.strptime(mica_time, "%Y:%m:%d %H:%M:%S")
        temp_timestamp = utc_time + timedelta(milliseconds=millisec)
               
        mica_timestamp = temp_timestamp - timedelta(seconds=MICA_deltat)
        mica_events.append(mica_timestamp)
        
        # Get geotagged positions
        latitude = tags.get('GPS GPSLatitude')
        latitude_ref = tags.get('GPS GPSLatitudeRef')
        longitude = tags.get('GPS GPSLongitude')
        longitude_ref = tags.get('GPS GPSLongitudeRef')
        altitude = tags.get('GPS GPSAltitude')
        altitude_ref = tags.get('GPS GPSAltitudeRef')
         
        if latitude:
            lat_value = _convert_to_degress(latitude)
        if latitude_ref.values != 'N':
            lat_value = -lat_value           
        if longitude:
            lon_value = _convert_to_degress(longitude)
        if longitude_ref.values != 'E':
            lon_value = -lon_value
        if altitude:
            alt_value = float(altitude.values[0].num) / float(altitude.values[0].den)
        if altitude_ref == 1:
            print("GPS altitude ref is below sea level")

        E, N = transformer.transform(lat_value, lon_value)
        mica_pos.append([E, N, alt_value])
        
        # Just a print to show progress
        if mica_count % 100 == 0:
            print(mica_count)
        mica_count = mica_count + 1
        f.close()
    
        
    # List of MRK file(s)
    # NOTE: mrk_folder may contain multiple subfolders (e.g., multiple flights / missions).
    # We must NOT mix unrelated MRKs, otherwise the P1 time window and between-flight filtering becomes unreliable.
    discovered_mrks = list(glob.iglob(str(mrk_folder) + '/' + '**/*.MRK', recursive=True))
    if not discovered_mrks:
        raise FileNotFoundError(f"No .MRK files found under: {mrk_folder}")

    # Determine MicaSense capture time range (epoch seconds)
    mica_epoch_secs = [dt.timestamp() for dt in mica_events]
    mica_min = min(mica_epoch_secs) if mica_epoch_secs else None
    mica_max = max(mica_epoch_secs) if mica_epoch_secs else None

    # Select MRK files that overlap the MicaSense time range.
    # This avoids pulling in MRKs from other missions/days if the folder contains multiple exports.
    mrk_windows = []  # (first_ts, last_ts, mrk_path)
    for mrk_path in discovered_mrks:
        try:
            with open(mrk_path, 'r') as f:
                lines = f.readlines()
            if not lines:
                continue
            first_ts = get_P1_timestamp(lines[0])
            last_ts = get_P1_timestamp(lines[-1])
            mrk_windows.append((first_ts, last_ts, mrk_path))
        except Exception as e:
            logging.warning(f"Failed to read MRK file '{mrk_path}': {e}")

    if not mrk_windows:
        raise FileNotFoundError(f"Found MRK paths but could not read any: {mrk_folder}")

    selected = []
    if mica_min is not None and mica_max is not None:
        for first_ts, last_ts, mrk_path in mrk_windows:
            # Overlap check
            if not (last_ts < mica_min or first_ts > mica_max):
                selected.append((first_ts, last_ts, mrk_path))

    if selected:
        # Sort MRKs chronologically by first timestamp (critical for P1_first/last indexing logic)
        selected.sort(key=lambda t: t[0])
        mrk_file_list = [t[2] for t in selected]
        if len(mrk_windows) > len(selected):
            logging.warning(
                "Multiple MRK files found under '%s' (%d). Using %d that overlap MicaSense time range.",
                str(mrk_folder), len(mrk_windows), len(selected)
            )
    else:
        # Fallback: use all MRKs, but in deterministic chronological order
        mrk_windows.sort(key=lambda t: t[0])
        mrk_file_list = [t[2] for t in mrk_windows]
        logging.warning(
            "No MRK files overlapped the MicaSense time range. Falling back to all MRKs under '%s' (%d).",
            str(mrk_folder), len(mrk_windows)
        )

    mrk_file_count = len(mrk_file_list)

    loop_count = 1
    for mrk_file in mrk_file_list:
        # Get first and last P1 timestamp. Update global vars with timestamp and position of all P1 images.
        get_P1_position(mrk_file, loop_count)
        loop_count = loop_count + 1
        
    # Transform all P1 positions from WGS84 (lat/lon) to CH1903+/LV95 using Swisstopo API
    P1_pos_arr = np.array(P1_pos_mrk)
    P1_pos_shifted = P1_pos_arr + P1_shift_vec

    P1_pos = []
    total = len(P1_pos_shifted)
    for i, pos in enumerate(P1_pos_shifted):
        lat = pos[0]
        lon = pos[1]
        alt = pos[2]

        result = transform_coordinates(lon, lat, alt)

        if result:
            P1_pos.append([result["easting"], result["northing"], result["altitude"]])
        else:
            # Fallback to pyproj transformer if API fails
            try:
                E, N = transformer.transform(lat, lon)
                P1_pos.append([E, N, alt])
                logging.warning(f"Used pyproj fallback for position {i}: lat={lat}, lon={lon}")
            except Exception as e:
                logging.error(f"Both API and pyproj failed for position {i}: {e}")
                P1_pos.append([0.0, 0.0, 0.0])

        if (i + 1) % 50 == 0 or (i + 1) == total:
            print(f"Transformed {i+1}/{total} P1 positions")

    P1_pos = np.array(P1_pos)
 
        
    # Create output MicaSense position csv 
    out_frame = open(out_file, 'w', encoding='utf-8')
    # write header row
    rec = ("Label, Easting, Northing, Ellip Height\n")
    print("Writing to file: ", rec)
    out_frame.write(rec) 
    
    count = 0
    
    first_P1_timestamp = P1_first_timestamp[1]
    last_P1_timestamp = P1_last_timestamp[mrk_file_count]

    for m_cam_time in mica_events:
        P1_triggered = True 
        a = find_nearest(P1_events, m_cam_time)
        camera_time_sec = m_cam_time.timestamp()
        P1_pos_time = P1_events[a].timestamp()
        
        # MicaSense images captured before P1 started or after it stopped have time = 0, pos = 0     
        if((camera_time_sec < first_P1_timestamp) or 
           (camera_time_sec > last_P1_timestamp)):
            time1 = 0
            time2 = 0
            upd_pos1 = [0, 0, 0]
            upd_pos2 = [0, 0, 0]
            P1_triggered = False
            
        # When more than one flight for same mission, also ignore MicaSense images that triggered between flights    
        elif(mrk_file_count > 1):
            for mrk_loop in range(1, mrk_file_count):
                if ((camera_time_sec > P1_last_timestamp[mrk_loop] and 
                     camera_time_sec < P1_first_timestamp[mrk_loop+1])):
                    time1 = 0
                    time2 = 0
                    upd_pos1 = [0, 0, 0]
                    upd_pos2 = [0, 0, 0]
                    P1_triggered = False
                    
        # Update MicaSense position for images that triggered within P1 times.           
        if P1_triggered:    
            if P1_pos_time <= camera_time_sec:
                time1 = P1_pos_time
                time2 = P1_events[a+1].timestamp()
                upd_pos1 = P1_pos[a]
                upd_pos2 = P1_pos[a+1]
            elif P1_pos_time > camera_time_sec:
                time1 = P1_events[a-1].timestamp()
                time2 = P1_pos_time
                upd_pos1 = P1_pos[a-1]
                upd_pos2 = P1_pos[a]
    
            # Check if bracketing positions are valid (not None)
            if (upd_pos1[0] is None or upd_pos1[1] is None or upd_pos1[2] is None or
                upd_pos2[0] is None or upd_pos2[1] is None or upd_pos2[2] is None):
                print(f"Warning: Invalid bracketing positions for MicaSense image {count}. Skipping interpolation.")
                logging.warning(f"Invalid bracketing positions for MicaSense image {count}. Camera will use original GPS position.")
                # Use the original MicaSense position from GPS
                pos_index = mica_events.index(m_cam_time)
                path_image_name = os.path.abspath(filelist[count])
                image_name = path_image_name
                rec = ("%s, %10.6f, %10.6f, %10.4f\n" % \
                        (image_name, mica_pos[pos_index][0], mica_pos[pos_index][1], mica_pos[pos_index][2]))
                print("Writing to file (original GPS): ", rec)
                out_frame.write(rec)
                count = count + 1
                continue
    
            # Compute time_delta only if time2 and time1 are different
        time_delta = 0.0

        if (time2 - time1) != 0:
            time_delta = (camera_time_sec - time1) / (time2 - time1)

        # Interpolate Easting (X) and Northing (Y) from P1 positions:
        interp_E = upd_pos1[0] + time_delta * (upd_pos2[0] - upd_pos1[0])
        interp_N = upd_pos1[1] + time_delta * (upd_pos2[1] - upd_pos1[1])

        # Interpolate the altitude (Z) from the P1 data:
        interp_h = upd_pos1[2] + time_delta * (upd_pos2[2] - upd_pos1[2])

            # If needed, you can adjust the altitude to a different vertical datum.
            # For example, if your P1 altitude is ellipsoidal and you need to convert to MSL,
            # you can use a geoid model to get the geoid height at (interp_E, interp_N).
            #
            # Uncomment and modify the next two lines if you have a function to get the geoid offset:
            #
            # geoid_offset = get_geoid_offset(interp_E, interp_N)  # User-defined function: returns the geoid separation at this point.
            # interp_h = interp_h - geoid_offset  # Adjust the ellipsoidal height to mean sea level (or vice versa)

        # Combine into a new interpolated position vector for the MicaSense image:
        upd_micasense_pos = [interp_E, interp_N, interp_h]

        path_image_name = os.path.abspath(filelist[count]) 
        image_name = path_image_name
        
        pos_index = mica_events.index(m_cam_time)

        # For images captured within P1 times, write updated Easting, Northing, Ellipsoidal height to CSV
        if(upd_micasense_pos[2] != 0):
                        rec = ("%s, %10.6f, %10.6f, %10.4f\n" % \
                                (image_name, upd_micasense_pos[0], upd_micasense_pos[1], upd_micasense_pos[2]))
        else:
                        # For MicaSense images captured outisde P1 times, just save original Easting, Northing. BUT set ellipsoidal height to 0 
                        # to filter and delete these cameras
                        rec = ("%s, %10.6f, %10.6f, %10.4f\n" % \
                                (image_name, mica_pos[pos_index][0], mica_pos[pos_index][1], upd_micasense_pos[2]))
                        
        print("Writing to file: ", rec)                
        out_frame.write(rec)
        count = count + 1
        
    # Close the CSV file
    out_frame.close()
    
    # Print summary statistics
    cameras_outside_p1 = len([pos for pos in mica_pos if pos[2] == 0])
    cameras_interpolated = count - cameras_outside_p1
    print(f"\n=== MicaSense Position Interpolation Summary ===")
    print(f"Total MicaSense images processed: {count}")
    print(f"Images interpolated from P1 positions: {cameras_interpolated}")
    print(f"Images outside P1 capture times (will be deleted): {cameras_outside_p1}")
    logging.info(f"MicaSense interpolation complete: {cameras_interpolated} interpolated, {cameras_outside_p1} outside P1 times")
    print(f"Output written to: {out_file}")