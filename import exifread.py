import exifread
import datetime
import glob
import os
import fnmatch

def extract_timestamp(image_path):
    """
    Extract the timestamp from an image's EXIF data.
    
    Parameters:
    image_path (str): Path to the image file.
    
    Returns:
    datetime: The extracted timestamp.
    """
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f)
        if not tags:
            raise ValueError(f"No EXIF data found in {image_path}")
        
        image_time = str(tags.get('EXIF DateTimeOriginal'))
        image_subsec_time = str(tags.get('EXIF SubSecTime'))
        
        subsec = int(image_subsec_time)
        negative = 1.0
        if subsec < 0:
            negative = -1.0
            subsec *= -1.0
        subsec = float('0.{}'.format(int(subsec)))
        subsec *= negative
        millisec = subsec * 1e3
        
        utc_time = datetime.datetime.strptime(image_time, "%Y:%m:%d %H:%M:%S")
        temp_timestamp = utc_time + datetime.timedelta(milliseconds=millisec)
        
        return temp_timestamp

def find_images(folder, pattern):
    """
    Find images in a folder matching the given pattern.
    
    Parameters:
    folder (str): Path to the folder.
    pattern (str): Pattern to match the images.
    
    Returns:
    list: List of matching image paths.
    """
    matches = []
    for root, dirnames, filenames in os.walk(folder):
        for filename in fnmatch.filter(filenames, pattern):
            matches.append(os.path.join(root, filename))
    return matches

def calculate_average_time_difference(folder1, suffix1, folder2, suffix2, subset_size=10):
    """
    Calculate the average time difference between images from two folders.
    
    Parameters:
    folder1 (str): Path to the first folder.
    suffix1 (str): Suffix for images in the first folder.
    folder2 (str): Path to the second folder.
    suffix2 (str): Suffix for images in the second folder.
    subset_size (int): Number of images to consider for the subset.
    
    Returns:
    float: The average time difference in seconds.
    """
    pattern1 = f"*{suffix1}[0-9][0-9][0-9][0-9].jpeg"
    pattern2 =