import numpy as np
import Metashape
import upd_micasense_pos_copy as upd_micasense_pos
import os
import glob
import numpy as np
import exifread
import datetime
from pyproj.transformer import TransformerGroup
from upd_micasense_pos_copy import find_nearest
from upd_micasense_pos_copy import _convert_to_degress


P1_shift_vec = np.array([0.0, 0.0, 0.0])
P1_events = []
P1_pos_mrk = []
P1_pos = []
P1_first_timestamp = {}
P1_last_timestamp = {}

LEAPSECS = 37
GPSUTC_deltat = 0
MICA_deltat = 0
EPSG_4326 = 4326



P1_shift_vec = np.array([0.0, 0.0, 0.0])
img_suffix_master = "_2"
MRK_PATH = r"M:\\working_package_2\\2024_dronecampaign\\01_data\\dronetest\\P1Data\\DJI_202408080937_002_p1micasense60mtest"
MICASENSE_PATH = r"M:\\working_package_2\\2024_dronecampaign\\01_data\\dronetest\\MicasenseData\\fullset"
MICASENSE_CAM_CSV = "interpolated_micasense_pos.csv"

def ret_micasense_pos(mrk_folder, micasense_folder, image_suffix, epsg_crs, out_file, P1_shift_vec):
    """
    Parameters
    ----------
    mrk_folder : string
        Path to P1 MRK files
    micasense_folder : string
        Path to MicaSense images 
    image_suffix : integer
        File suffix for MicaSense master band images
    epsg_crs : 
        EPSG code for projected coordinate system - used to interpoalte MicaSense position based on nearest timestamps
    out_file : string
        Path and name of output CSV file with udpated Easting/Norhting/Altitude for all MicaSense images
    P1_shift_vec : vector
        Vector to be used to blockshift P1 positions. 

    Returns
    -------
    None. out_file written with updated positions.

    """
    print("Loading micasense images")
    
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
    os.chdir(micasense_folder)
    filelist = glob.glob("**/IMG*_" + str(image_suffix)+".tif", recursive=True)
    
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
        
        utc_time = datetime.datetime.strptime(mica_time, "%Y:%m:%d %H:%M:%S")
        temp_timestamp = utc_time + datetime.timedelta(milliseconds = millisec)
               
        mica_timestamp = temp_timestamp - datetime.timedelta(seconds = MICA_deltat)
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
    mrk_file_count = 0
    mrk_file_list = []
    for filename in glob.iglob(mrk_folder + '/' + '**/*.MRK', recursive=True):
        mrk_file_list.append(filename)
        mrk_file_count = mrk_file_count + 1
    
    loop_count = 1
    for mrk_file in mrk_file_list:
        # Get first and last P1 timestamp. Update global vars with timestamp and position of all P1 images.
        get_P1_position(mrk_file, loop_count)
        loop_count = loop_count + 1
    
    # Debug print to check the contents of P1_pos_mrk
    print("P1_pos_mrk:", P1_pos_mrk)
    
    # Shift Lat/Lon/Ellip height in P1_pos_mrk
    # If blockshift was not enabled, P1_shift_vec will be 0,0,0 
    P1_pos_arr = np.array(P1_pos_mrk)
    
    # Check if P1_pos_arr is empty
    if P1_pos_arr.size == 0:
        print("Error: P1_pos_mrk is empty. Ensure that MRK files are correctly processed.")
        return
    
    P1_pos_shifted = P1_pos_arr + P1_shift_vec         
    
    # Convert to target projected CRS prior to interpolating position
    E, N = transformer.transform(P1_pos_shifted[:,0], P1_pos_shifted[:,1])
    P1_pos = np.dstack((E, N, P1_pos_shifted[:,2]))[0]    
        
    # Create output MicaSense position csv 
    out_frame = open(out_file, 'w')
    # write header row
    rec = ("Label, Easting, Northing, Ellip Height\n")
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
    
        time_delta=0
        if (time2-time1) != 0:
            time_delta = (camera_time_sec - time1)/(time2 - time1)
      
        upd_micasense_pos = [0.0,0.0,0.0]
        upd_micasense_pos[0] = upd_pos1[0] + time_delta * (upd_pos2[0] - upd_pos1[0])
        upd_micasense_pos[1] = upd_pos1[1] + time_delta * (upd_pos2[1] - upd_pos1[1])
        upd_micasense_pos[2] = upd_pos1[2] + time_delta * (upd_pos2[2] - upd_pos1[2])
    
        path_image_name = filelist[count]
        image_name = path_image_name.split("\\")[-1]
        
        pos_index = mica_events.index(m_cam_time)
        
        # For images captured within P1 times, write updated Easting, Northing, Ellipsoidal height to CSV
        if(upd_micasense_pos[2]!=0):
            rec = ("%s, %10.4f, %10.4f, %10.4f\n" % \
                    (image_name, upd_micasense_pos[0], upd_micasense_pos[1], upd_micasense_pos[2]))
        else:
            # For MicaSense images captured outisde P1 times, just save original Easting, Northing. BUT set ellipsoidal height to 0 
            # to filter and delete these cameras
            rec = ("%s, %10.4f, %10.4f, %10.4f\n" % \
                    (image_name, mica_pos[pos_index][0], mica_pos[pos_index][1], upd_micasense_pos[2]))
            
        out_frame.write(rec) 
        
        # Print the closest two P1 camera timestamps for the first 20 MicaSense cameras
        if count < 20:
            print(f"MicaSense Image: {image_name}")
            print(f"Closest P1 Timestamp 1: {datetime.datetime.fromtimestamp(time1)}")
            print(f"Closest P1 Timestamp 2: {datetime.datetime.fromtimestamp(time2)}")
            print()
        
        count = count + 1
        
    # Close the CSV file
    out_frame.close()

def get_P1_position(mrk_file, loop_count):
    global P1_pos_mrk, P1_events, P1_first_timestamp, P1_last_timestamp

    print(f"Processing MRK file: {mrk_file}")

    with open(mrk_file, 'r') as f:
        lines = f.readlines()

    for line in lines:
        if line.startswith('%'):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue

        try:
            # Extract the relevant parts of the line
            timestamp = float(parts[0])
            lat = float(parts[7].replace(',', ''))  # Assuming latitude is at index 7
            lon = float(parts[9].replace(',', ''))  # Assuming longitude is at index 9
            alt = float(parts[11].replace(',', ''))  # Assuming altitude is at index 11
        except ValueError as e:
            print(f"Error parsing line: {line}")
            print(e)
            continue

        P1_events.append(datetime.datetime.utcfromtimestamp(timestamp))
        P1_pos_mrk.append([lat, lon, alt])

    if P1_events:
        if loop_count == 1:
            P1_first_timestamp[loop_count] = P1_events[0].timestamp()
        P1_last_timestamp[loop_count] = P1_events[-1].timestamp()

        print(f"First timestamp: {P1_first_timestamp[loop_count]}")
        print(f"Last timestamp: {P1_last_timestamp[loop_count]}")
        print(f"Number of positions: {len(P1_pos_mrk)}")
    else:
        print("No valid P1 events found in the MRK file.")

# Ensure global variables are initialized
P1_pos_mrk = []
P1_events = []
P1_first_timestamp = {}
P1_last_timestamp = {}

# Example usage
MRK_PATH = r"M:\\working_package_2\\2024_dronecampaign\\01_data\\dronetest\\P1Data\\DJI_202408080937_002_p1micasense60mtest"
MICASENSE_PATH = r"M:\\working_package_2\\2024_dronecampaign\\01_data\\dronetest\\MicasenseData\\fullset"
img_suffix_master = "_2"
output_csv_path = "interpolated_micasense_pos.csv"

ret_micasense_pos(MRK_PATH, MICASENSE_PATH, img_suffix_master, 2056, output_csv_path, P1_shift_vec)
