import argparse
import os
from upd_micasense_pos import ret_micasense_pos
from tqdm import tqdm
import pytz
import glob
import exifread
import time
import datetime  # Add this import

MICA_deltat = 0  # Time difference between MicaSense and P1 timestamps

def main():
    parser = argparse.ArgumentParser(description="Debug script for ret_micasense_pos function")
    parser.add_argument('-mrk', help='Path to P1 MRK files', required=True)
    parser.add_argument('-micasense', help='Path to MicaSense images', required=True)
    parser.add_argument('-suffix', help='File suffix for MicaSense master band images', required=True)
    parser.add_argument('-epsg', help='EPSG code for projected coordinate system', required=True)
    parser.add_argument('-output', help='Path and name of output CSV file', required=True)
    parser.add_argument('-shift', help='Vector to blockshift P1 positions (comma-separated)', default="0.0,0.0,0.0")
    
    args = parser.parse_args()
    
    global P1_events
    P1_events = []
    
    P1_shift_vec = [float(x) for x in args.shift.split(',')]
    
    if not os.path.isdir(args.mrk):
        raise FileNotFoundError(f"The directory {args.mrk} does not exist.")
    
    if not os.path.isdir(args.micasense):
        raise FileNotFoundError(f"The directory {args.micasense} does not exist.")
    
    mica_events_epoch = []
    mica_pos = []
    filelist = []
    ret_micasense_pos_with_progress(args.mrk, args.micasense, args.suffix, args.epsg, args.output, P1_shift_vec, mica_events_epoch, mica_pos, filelist)
    print(f"Output written to {args.output}")

def _convert_to_degress(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degrees in float format
    :param value:
    :type value: exifread.utils.Ratio
    :rtype: float
    """
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den)
    s = float(value.values[2].num) / float(value.values[2].den)

    return d + (m / 60.0) + (s / 3600.0)

def ret_micasense_pos_with_progress(mrk_folder, micasense_folder, image_suffix, epsg_crs, out_file, P1_shift_vec, mica_events_epoch, mica_pos, filelist):
    print("Loading micasense images")
    mica_events = []
    mica_pos = []
    mica_count = 0
    utc = pytz.UTC

    # Load MicaSense images once
    os.chdir(micasense_folder)
    filelist = glob.glob("**/IMG*_" + str(image_suffix)+".tif", recursive=True)
    
    for file in filelist:
        f = open(file, 'rb')
        tags = exifread.process_file(f)
        if not tags:
            continue
        mica_time = str(tags.get('EXIF DateTimeOriginal'))
        if mica_time:
            utc_time = datetime.datetime.strptime(mica_time, "%Y:%m:%d %H:%M:%S")
            mica_timestamp = utc_time - datetime.timedelta(seconds=MICA_deltat)
            mica_events.append(mica_timestamp)
        else:
            print(f"Skipping file {file} due to missing EXIF DateTimeOriginal tag.")
            continue
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
        E, N = lat_value, lon_value
        mica_pos.append([E, N, alt_value])
        if mica_count % 100 == 0:
            print(mica_count)
        mica_count += 1
        f.close()

    # Convert MicaSense timestamps to Unix epoch format with milliseconds
    mica_events_epoch = [event.timestamp() for event in mica_events]

    # Process the images
    for _ in tqdm(range(100), desc="Processing"):
        ret_micasense_pos(mrk_folder, micasense_folder, image_suffix, epsg_crs, out_file, P1_shift_vec, mica_events_epoch, mica_pos, filelist)

if __name__ == "__main__":
    main()