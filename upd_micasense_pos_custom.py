# -*- coding: utf-8 -*-
"""
Created August 2021

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
from datetime import datetime, timedelta
from pyproj.transformer import TransformerGroup
import micasense.metadata_custom 
import pytz

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

LEAPSECS = float(37)
GPSUTC_deltat = float(0)
MICA_deltat = float(0)
EPSG_4326 = 4326
EPSG_CH1903 = 2056


###############################################################################
# Functions
###############################################################################

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
        temp_timestamp =  datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
        p1_camera_timestamp = temp_timestamp - timedelta(seconds=GPSUTC_deltat)
        return p1_camera_timestamp


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
                m=mrk.split()
                
                #photo_num = int(m[0])
                secs = float(m[1])
                week = int(m[2].strip("[").strip("]"))
                epoch_secs = secs + (week*7*24*60*60)
                temp_timestamp = datetime(1980, 1, 6) + timedelta(seconds = epoch_secs)
                camera_timestamp = temp_timestamp - timedelta(seconds = GPSUTC_deltat)
                
                lat = float(m[6].split(",")[0])
                lon = float(m[7].split(",")[0])
                ellh = float(m[8].split(",")[0])
                
                P1_events.append(camera_timestamp)
                P1_pos_mrk.append([lat, lon, ellh])

        
def ret_micasense_pos(mrk_folder, micasense_folder, image_suffix, epsg_crs, out_file, P1_shift_vec, mica_events_epoch, mica_pos, filelist):
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

    # List of MRK file(s)
    mrk_file_count = 0
    mrk_file_list = []
    for filename in glob.iglob(mrk_folder + '/' + '**/*.MRK', recursive=True):
            mrk_file_list.append(filename)
            mrk_file_count = mrk_file_count + 1
    
    loop_count = 1
    print("Initializing P1_events")
    global P1_events
    P1_events = []
    utc = pytz.UTC  # Define utc here
    for mrk_file in mrk_file_list:
            # Get first and last P1 timestamp. Update global vars with timestamp and position of all P1 images.
            get_P1_position(mrk_file, loop_count)
            loop_count = loop_count + 1
            # print(f"P1_events after processing {mrk_file}: {P1_events}")  # Comment out this line
    
    # Ensure P1_events are offset-aware
    P1_events = [utc.localize(event) if event.tzinfo is None else event for event in P1_events]
    # print(f"P1_events after localization: {P1_events}")  # Comment out this line

    # Convert P1_events to Unix epoch format with milliseconds
    P1_events_epoch = [event.timestamp() for event in P1_events]

    # Print P1 first and last timestamps
    first_P1_timestamp = P1_first_timestamp[1]
    last_P1_timestamp = P1_last_timestamp[mrk_file_count]
    print(f"First P1 timestamp: {first_P1_timestamp.isoformat()}")
    print(f"Last P1 timestamp: {last_P1_timestamp.isoformat()}")
            
    # Shift Lat/Lon/Ellip height in P1_pos_mrk
    # If blockshift was not enabled, P1_shift_vec will be 0,0,0 
    P1_pos_arr = np.array(P1_pos_mrk)
    P1_pos_shifted = P1_pos_arr + P1_shift_vec         

    # Convert to target projected CRS prior to interpolating position
    # E, N = transformer.transform(P1_pos_shifted[:,0], P1_pos_shifted[:,1])
    E, N = P1_pos_shifted[:,0], P1_pos_shifted[:,1]  # Placeholder transformation
    P1_pos = np.dstack((E, N, P1_pos_shifted[:,2]))[0]    
    
    # Create output MicaSense position csv 
    out_frame = open(out_file, 'w')
    # write header row
    rec = ("Label, Easting, Northing, Ellip Height\n")
    out_frame.write(rec) 
    
    count = 0
    non_matching_images = []

    for m_cam_time in mica_events_epoch:
        P1_triggered = True 
        a = find_nearest(P1_events_epoch, m_cam_time)
        camera_time_sec = m_cam_time
        P1_pos_time = P1_events_epoch[a]
        
        # MicaSense images captured before P1 started or after it stopped have time = 0, pos = 0     
        if((camera_time_sec < first_P1_timestamp.timestamp()) or 
             (camera_time_sec > last_P1_timestamp.timestamp())):
                time1 = 0
                time2 = 0
                upd_pos1 = [0, 0, 0]
                upd_pos2 = [0, 0, 0]
                P1_triggered = False
                non_matching_images.append((filelist[count], m_cam_time))
                
        # When more than one flight for same mission, also ignore MicaSense images that triggered between flights    
        elif(mrk_file_count > 1):
                for mrk_loop in range(1, mrk_file_count):
                        if ((camera_time_sec > P1_last_timestamp[mrk_loop].timestamp() and 
                                 camera_time_sec < P1_first_timestamp[mrk_loop+1].timestamp())):
                                time1 = 0
                                time2 = 0
                                upd_pos1 = [0, 0, 0]
                                upd_pos2 = [0, 0, 0]
                                P1_triggered = False
                                non_matching_images.append((filelist[count], m_cam_time))
                                
        # Update MicaSense position for images that triggered within P1 times.           
        if P1_triggered:    
                if P1_pos_time <= camera_time_sec:
                        time1 = P1_pos_time
                        time2 = P1_events_epoch[a+1]
                        upd_pos1 = P1_pos[a]
                        upd_pos2 = P1_pos[a+1]
                elif P1_pos_time > camera_time_sec:
                        time1 = P1_events_epoch[a-1]
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
        
        pos_index = mica_events_epoch.index(m_cam_time)
        
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
        count = count + 1
                
    # Close the CSV file
    out_frame.close()

    # Raise message for non-matching images at the end
    if non_matching_images:
        print("The following MicaSense images do not match the timeframe of P1 images:")
        for img, img_time in non_matching_images:
            img_name = img.split("\\")[-1]
            img_time_formatted = datetime.fromtimestamp(img_time).strftime('%Y-%m-%d %H:%M:%S.%f%z')
            print(f"{img_name} at {img_time_formatted}")