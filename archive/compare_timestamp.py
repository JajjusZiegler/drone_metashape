import exifread

def get_timestamp(image_path):
    with open(image_path, 'rb') as image_file:
        tags = exifread.process_file(image_file)
        timestamp = tags.get('EXIF DateTimeOriginal')
        if timestamp:
            return str(timestamp)
        else:
            return None

def compare_timestamps(rgb_image_path, multispec_image_path):
    rgb_timestamp = get_timestamp(rgb_image_path)
    multispec_timestamp = get_timestamp(multispec_image_path)

    if rgb_timestamp and multispec_timestamp:
        if rgb_timestamp == multispec_timestamp:
            print("The timestamps are identical.")
        else:
            print(f"Timestamps differ:\nRGB: {rgb_timestamp}\nMultispectral: {multispec_timestamp}")
    else:
        print("One or both images do not have a timestamp.")

# Example usage
rgb_image_path = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\P1Data\DJI_202408080937_002_p1micasense60mtest\DJI_20240808094709_0001.JPG"
multispec_image_path = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\MicasenseData\fullset\SYNC0025SET\000\IMG_0008_1.tif"
compare_timestamps(rgb_image_path, multispec_image_path)