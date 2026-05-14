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
    label, Easting, Northing, LHN95 orthometric height

"""

import os
import glob
import re
import numpy as np
import exifread
import datetime
import requests
import rasterio
import pyproj
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
# wgs84tolv95 returns CH1903+/LV95 horizontal coordinates (EPSG:2056) + LN02 orthometric altitude
# (~3–10 cm vertical accuracy via HTRANS).
# The wgs84tolv95lhn95 variant (LHN95/CHGeo2004 heights) does not exist on this server.
# The old wgs84tolv03 (LV03/CH1903) endpoint introduces a ~1–3 m horizontal offset and must not be used.
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


_HTRANS_NODATA_SENTINEL = 99.9  # Value stored in htrans grids for cells outside coverage


def _sample_htrans_grid(path, lon, lat):
    """
    Sample a geoid GeoTIFF at (lon, lat) in WGS84 using bilinear interpolation.

    Returns the geoid undulation N, or None if the point is outside coverage
    (nodata sentinel ≈ 99.9) or if sampling raises an exception.

    Bilinear interpolation is used so that results match swisstopo Reframe
    to ~7 mm; nearest-neighbour produces errors up to ~260 mm.

    Some GeoTIFFs (e.g. older chgeo2004_ETRS89_LHN95.tif) carry an incorrect
    CRS tag (EPSG:2056 / LV95) while pixel coordinates are in geographic degrees.
    We detect this by checking whether the raster bounds fall in the ±180/±90
    range and bypass reprojection in that case.
    """
    try:
        with rasterio.open(path) as ds:
            bounds = ds.bounds
            extent_is_geographic = (
                -180 <= bounds.left  <= 180 and
                -180 <= bounds.right <= 180 and
                -90  <= bounds.bottom <= 90 and
                -90  <= bounds.top    <= 90
            )
            if extent_is_geographic:
                sample_x, sample_y = lon, lat
            else:
                grid_crs = ds.crs
                wgs84 = pyproj.CRS("EPSG:4326")
                if grid_crs and not grid_crs.equals(wgs84):
                    tfm = pyproj.Transformer.from_crs(wgs84, grid_crs, always_xy=True)
                    sample_x, sample_y = tfm.transform(lon, lat)
                else:
                    sample_x, sample_y = lon, lat

            tf = ds.transform
            col_f = (sample_x - tf.c) / tf.a
            row_f = (sample_y - tf.f) / tf.e  # tf.e is negative
            c0, r0 = int(col_f), int(row_f)

            # Quick bounds check before reading
            if c0 < 0 or r0 < 0 or c0 >= ds.width - 1 or r0 >= ds.height - 1:
                return None

            data = ds.read(1, window=rasterio.windows.Window(c0, r0, 2, 2))
            v00, v01, v10, v11 = data[0, 0], data[0, 1], data[1, 0], data[1, 1]
            if any(abs(v - _HTRANS_NODATA_SENTINEL) < 0.05 for v in (v00, v01, v10, v11)):
                return None  # any neighbour is nodata → on coverage boundary

            dc, dr = col_f - c0, row_f - r0
            delta = (v00 * (1 - dc) * (1 - dr) + v01 * dc * (1 - dr) +
                     v10 * (1 - dc) * dr        + v11 * dc * dr)
            return delta
    except Exception as e:
        logging.warning(f"_sample_htrans_grid failed for '{path}' at lon={lon}, lat={lat}: {e}")
    return None


def apply_htrans_correction(lon, lat, etrs89_height, htrans_path, fallback_path=None):
    """
    Convert an ETRS89 ellipsoidal height to an orthometric height using a geoid grid.

    Both the primary and fallback grids store the geoid undulation N (positive):
        N = h_ETRS89 - H_orthometric
    So for both:  H_orthometric = h_ETRS89 - N

    Primary grid (ETRS.tif from swisstopo CHGeo2004, geographic extent):
        N ≈ 47-52 m for Switzerland.  H_LHN95 = h_ETRS89 - N
        Bilinear interpolation matches swisstopo Reframe to ~7 mm.

    Fallback grid (ExtendedGeoid.tif, WGS84->EGM2008, EPSG:3855):
        N ≈ 47-52 m.  H_EGM2008 = h_ETRS89 - N
        EGM2008 is a global approximation; may differ from LHN95 by up to a few dm.

    If neither grid covers the point, etrs89_height is returned unchanged with a warning.

    Parameters
    ----------
    lon : float
        Longitude in WGS84 (EPSG:4326).
    lat : float
        Latitude in WGS84 (EPSG:4326).
    etrs89_height : float
        ETRS89 ellipsoidal height from MRK or DJI XMP (AbsoluteAltitude, metres).
    htrans_path : str
        Path to the primary CHGeo2004 GeoTIFF (stores undulation N = h_ETRS89 - H_LHN95).
    fallback_path : str or None
        Path to a fallback geoid GeoTIFF (EGM2008; stores undulation N = h_WGS84 - H_EGM2008).

    Returns
    -------
    float
        Orthometric height (LHN95 from primary, EGM2008 from fallback),
        or etrs89_height unchanged if all grids miss.
    """
    N = _sample_htrans_grid(htrans_path, lon, lat)
    if N is not None:
        return etrs89_height - N  # H_LHN95 = h_ETRS89 - N

    if fallback_path:
        logging.info(
            f"[HTRANS] Primary grid has no coverage at lon={lon:.6f}, lat={lat:.6f}. "
            f"Trying EGM2008 fallback: {fallback_path}"
        )
        N = _sample_htrans_grid(fallback_path, lon, lat)
        if N is not None:
            return etrs89_height - N  # H_EGM2008 = h_ETRS89 - N
        logging.warning(
            f"[HTRANS] Fallback grid also has no coverage at lon={lon:.6f}, lat={lat:.6f}. "
            f"Returning ETRS89 ellipsoidal height unchanged."
        )
    else:
        logging.warning(
            f"[HTRANS] Primary grid has no coverage at lon={lon:.6f}, lat={lat:.6f} "
            f"and no fallback was provided. Returning ETRS89 ellipsoidal height unchanged."
        )
    return etrs89_height


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
    Parse MRK file. Does NOT commit to global state.

    Returns
    -------
    (valid: bool, entries: list, mrk_lines: list)
        valid   - True if MRK contains non-zero GPS positions.
        entries - list of (camera_timestamp, lat, lon, ellh) for every line.
        mrk_lines - raw lines, needed by _commit_mrk_entries for first/last timestamp.
    """
    print("Get P1 position")

    with open(MRK_file, 'r') as mrk_in:
        mrks = mrk_in.readlines()

    entries = []
    for mrk in mrks:
        m = mrk.split()
        if len(m) < 9:
            continue
        secs = float(m[1])
        week = int(m[2].strip("[").strip("]"))
        epoch_secs = secs + (week * 7 * 24 * 60 * 60)
        camera_timestamp = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs) - timedelta(seconds=GPSUTC_deltat)
        lat  = float(m[6].split(",")[0])
        lon  = float(m[7].split(",")[0])
        ellh = float(m[8].split(",")[0])
        entries.append((camera_timestamp, lat, lon, ellh))

    if not entries:
        logging.warning(f"[MRK_FAULTY] '{MRK_file}' is empty or unparseable.")
        return False, [], mrks

    all_zero = all(lat == 0.0 and lon == 0.0 and ellh == 0.0
                   for _, lat, lon, ellh in entries)
    if all_zero:
        logging.warning(f"[MRK_FAULTY] '{MRK_file}' has all-zero coordinates (no GPS fix).")
        print(f"[MRK_FAULTY] All MRK coordinates are zero in '{MRK_file}'.")
        return False, [], mrks

    return True, entries, mrks


def _commit_mrk_entries(entries, mrk_lines, file_count):
    """Commit parsed MRK entries to the global P1 state variables."""
    global P1_first_timestamp, P1_last_timestamp, P1_events, P1_pos_mrk
    P1_first_timestamp[file_count] = get_P1_timestamp(mrk_lines[0])
    P1_last_timestamp[file_count]  = get_P1_timestamp(mrk_lines[-1])
    for ts, lat, lon, ellh in entries:
        P1_events.append(ts)
        P1_pos_mrk.append([lat, lon, ellh])


def _haversine_m(lat1, lon1, lat2, lon2):
    """Return distance in metres between two WGS84 lat/lon points."""
    from math import radians, cos, sin, asin, sqrt
    R = 6_371_000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _spot_check_mrk_vs_exif(entries, p1_image_folder, sample_step=10, threshold_m=0.5):
    """
    Cross-validate a sample of MRK positions against DJI XMP positions in the
    corresponding P1 JPG images.  Images and MRK lines are matched by sort order
    (both are in chronological/sequence order).

    Parameters
    ----------
    entries : list of (timestamp, lat, lon, ellh)
        Parsed MRK entries (from get_P1_position).
    p1_image_folder : str
        Folder containing the P1 JPG images.
    sample_step : int
        Check every Nth image (default 10).  Reduces I/O on network drives.
    threshold_m : float
        Maximum acceptable horizontal distance between MRK and EXIF position.

    Returns
    -------
    True  – positions agree within threshold (use MRK).
    False – mismatch found (fall back to EXIF).
    """
    import time
    jpg_files = sorted(set(
        glob.glob(os.path.join(p1_image_folder, "*.JPG")) +
        glob.glob(os.path.join(p1_image_folder, "*.jpg"))
    ))
    if not jpg_files:
        logging.warning("[MRK_CHECK] No JPG files found for cross-validation. Trusting MRK.")
        return True

    n_imgs   = len(jpg_files)
    n_mrk    = len(entries)
    if n_imgs != n_mrk:
        logging.warning(
            "[MRK_CHECK] Image count (%d) != MRK entry count (%d). "
            "Cross-validation may be unreliable.", n_imgs, n_mrk
        )

    indices = list(range(0, min(n_imgs, n_mrk), sample_step))
    print(f"[MRK_CHECK] Cross-validating {len(indices)} sample positions "
          f"(every {sample_step}th of {min(n_imgs, n_mrk)}) against XMP...")

    t0 = time.time()
    checked = 0
    mismatches = []

    for i in indices:
        jpg = jpg_files[i]
        _, mrk_lat, mrk_lon, _ = entries[i]
        try:
            with open(jpg, 'rb') as f:
                raw = f.read()
            xmp = _parse_dji_xmp(raw)
            lat_str = xmp.get("GpsLatitude")
            lon_str = xmp.get("GpsLongitude")
            if not lat_str or not lon_str:
                logging.warning(f"[MRK_CHECK] No XMP position in '{jpg}', skipping.")
                continue
            dist = _haversine_m(mrk_lat, mrk_lon, float(lat_str), float(lon_str))
            checked += 1
            if dist > threshold_m:
                mismatches.append((i, dist, jpg))
                logging.warning(
                    "[MRK_CHECK] Image #%d: MRK vs EXIF = %.1f m > threshold %.1f m  (%s)",
                    i, dist, threshold_m, os.path.basename(jpg)
                )
        except Exception as e:
            logging.warning(f"[MRK_CHECK] Failed to read '{jpg}': {e}")

    elapsed = time.time() - t0
    per_img = elapsed / max(checked, 1)
    print(
        f"[MRK_CHECK] Checked {checked} images in {elapsed:.1f}s "
        f"({per_img:.3f}s/image, sample_step={sample_step})."
    )

    if mismatches:
        print(
            f"[MRK_CHECK] MISMATCH: {len(mismatches)}/{checked} sampled images exceed "
            f"{threshold_m:.0f} m threshold. Falling back to EXIF positions."
        )
        return False

    print(f"[MRK_CHECK] OK: all {checked} sampled positions agree within {threshold_m:.0f} m. Using MRK.")
    return True


def _parse_dji_xmp(raw_bytes):
    """
    Extract DJI XMP fields from raw image bytes.
    Returns a dict with keys: UTCAtExposure, GpsLatitude, GpsLongitude,
    AbsoluteAltitude, RtkFlag (all as strings, or None if not found).
    """
    xmp_start = raw_bytes.find(b"<?xpacket")
    xmp_end   = raw_bytes.find(b"<?xpacket end")
    if xmp_start == -1 or xmp_end == -1:
        return {}
    xmp = raw_bytes[xmp_start:xmp_end + 50].decode("utf-8", errors="replace")
    fields = {}
    for key in ("UTCAtExposure", "GpsLatitude", "GpsLongitude", "AbsoluteAltitude", "RtkFlag"):
        m = re.search(r'drone-dji:' + key + r'="([^"]+)"', xmp)
        fields[key] = m.group(1) if m else None
    return fields


def get_P1_position_from_exif(p1_image_folder, file_count, sample_step=1):
    """
    Fallback: populate P1_events and P1_pos_mrk from DJI XMP metadata embedded in
    P1 JPG images, when the MRK file is faulty or its positions mismatch EXIF.

    Timestamp : drone-dji:UTCAtExposure — GPS-clock UTC, microsecond precision.
                Raises if this field is absent (no DateTimeOriginal fallback).
    Position  : drone-dji:GpsLatitude/GpsLongitude/AbsoluteAltitude (WGS84 ellipsoidal).
                Raises if absent.

    Timing is printed so the caller can decide whether to increase sample_step.

    Parameters
    ----------
    p1_image_folder : str
    file_count : int
    sample_step : int
        Load every Nth image (default 1 = all).  Increase to 10 or 20 on slow
        network drives.  Note: sparse sampling reduces interpolation accuracy.
    """
    import time
    global P1_first_timestamp, P1_last_timestamp
    global P1_pos_mrk, P1_events

    jpg_files = sorted(set(
        glob.glob(os.path.join(p1_image_folder, "*.JPG")) +
        glob.glob(os.path.join(p1_image_folder, "*.jpg"))
    ))
    if not jpg_files:
        raise FileNotFoundError(
            f"[MRK_FALLBACK] No JPG files found in '{p1_image_folder}'."
        )

    sampled = jpg_files[::sample_step]
    if sample_step > 1:
        print(f"[MRK_FALLBACK] Sampling every {sample_step}th image: "
              f"{len(sampled)} of {len(jpg_files)} images.")
        logging.warning(
            "[MRK_FALLBACK] sample_step=%d: loading %d/%d P1 images. "
            "Sparse sampling reduces MicaSense interpolation accuracy.",
            sample_step, len(sampled), len(jpg_files)
        )

    timestamps_added = []
    non_rtk_count = 0
    t0 = time.time()

    for idx, jpg_path in enumerate(sampled):
        try:
            with open(jpg_path, 'rb') as f:
                raw = f.read()
            xmp = _parse_dji_xmp(raw)

            # ---- Timestamp (required: GPS-clock UTC, microsecond precision) ----
            utc_str = xmp.get("UTCAtExposure")
            if not utc_str:
                raise ValueError(
                    f"drone-dji:UTCAtExposure missing in XMP of '{jpg_path}'. "
                    "Cannot use this image for interpolation."
                )
            camera_timestamp = datetime.fromisoformat(utc_str)

            # ---- Position (required) ----
            lat_str = xmp.get("GpsLatitude")
            lon_str = xmp.get("GpsLongitude")
            alt_str = xmp.get("AbsoluteAltitude")
            if not (lat_str and lon_str and alt_str):
                raise ValueError(
                    f"drone-dji:GpsLatitude/GpsLongitude/AbsoluteAltitude missing in '{jpg_path}'."
                )
            lat  = float(lat_str)
            lon  = float(lon_str)
            ellh = float(alt_str)

            # ---- RTK flag ----
            if xmp.get("RtkFlag") != "50":
                non_rtk_count += 1

            P1_events.append(camera_timestamp)
            P1_pos_mrk.append([lat, lon, ellh])
            timestamps_added.append(camera_timestamp)

        except Exception as e:
            logging.warning(f"[MRK_FALLBACK] Skipping '{jpg_path}': {e}")

    elapsed = time.time() - t0
    n = len(sampled)
    print(
        f"[MRK_FALLBACK] Read {len(timestamps_added)}/{n} images in "
        f"{elapsed:.1f}s ({elapsed/max(n,1):.3f}s/image)."
    )
    if n > 0 and elapsed / n > 0.5:
        print(
            f"[MRK_FALLBACK] Slow I/O detected ({elapsed/n:.2f}s/image). "
            "Consider passing sample_step=10 or sample_step=20 to reduce load time."
        )

    if not timestamps_added:
        raise RuntimeError(
            f"[MRK_FALLBACK] No valid XMP positions found in '{p1_image_folder}'. "
            "Both MRK and EXIF XMP are unusable — cannot continue."
        )

    if non_rtk_count > 0:
        logging.warning(
            "[MRK_FALLBACK] %d/%d P1 images have RtkFlag != 50 (standard GNSS, ~1-5 m accuracy).",
            non_rtk_count, len(timestamps_added)
        )
        print(
            f"[MRK_FALLBACK] WARNING: {non_rtk_count}/{len(timestamps_added)} images "
            "have no RTK fix (RtkFlag != 50). Position accuracy ~1-5 m (standard GNSS)."
        )

    timestamps_added.sort()
    P1_first_timestamp[file_count] = timestamps_added[0].timestamp()
    P1_last_timestamp[file_count]  = timestamps_added[-1].timestamp()
    print(
        f"[MRK_FALLBACK] Loaded {len(timestamps_added)} P1 positions from XMP "
        f"(drone-dji:UTCAtExposure, microsecond GPS UTC)."
    )
    return True


def generate_p1_interp_reference(mrk_file, p1_ref_csv, p1_image_folder, out_dir, flight_idx):
    """
    Build a per-segment interpolation reference CSV by pairing GPS timestamps
    from P1 JPG XMP (drone-dji:UTCAtExposure) with already-transformed
    LV95/LHN95 positions from p1_pos_CH1903.csv.

    The MRK file is passed only for logging purposes — its content is never
    read (it is faulty or failed spot-check).

    Parameters
    ----------
    mrk_file : str
        Path to the (faulty) MRK file — used for log messages only.
    p1_ref_csv : str
        Path to p1_pos_CH1903.csv (Label, E, N, h; '#'-prefixed header lines).
    p1_image_folder : str
        Folder containing P1 JPG images for this flight segment.
    out_dir : str
        Directory where the reference CSV will be written.
    flight_idx : int
        Flight segment index (1-based).  Output file is named
        ``p1_interp_reference_{flight_idx}.csv``.

    Returns
    -------
    str
        Absolute path to the written reference CSV.
    """
    import time as _time

    out_path = os.path.join(out_dir, f"p1_interp_reference_{flight_idx}.csv")

    # ── 1. Load LV95/LHN95 positions from reference CSV ──────────────────────
    csv_by_label = {}
    with open(p1_ref_csv, 'r') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 4:
                continue
            try:
                E = float(parts[1])
                N = float(parts[2])
                h = float(parts[3])
            except ValueError:
                continue  # skip header row ("Label,X/Easting,...")
            csv_by_label[os.path.basename(parts[0])] = (E, N, h)

    if not csv_by_label:
        raise RuntimeError(
            f"[INTERP_REF] No valid positions in '{p1_ref_csv}'. "
            "Ensure proc_rgb has run and exported p1_pos_CH1903.csv."
        )

    # ── 2. Find JPGs and read XMP timestamps ─────────────────────────────────
    jpg_files = sorted(set(
        glob.glob(os.path.join(p1_image_folder, "*.JPG")) +
        glob.glob(os.path.join(p1_image_folder, "*.jpg"))
    ))
    if not jpg_files:
        raise FileNotFoundError(
            f"[INTERP_REF] No JPG files found in '{p1_image_folder}'."
        )

    t0 = _time.time()
    rows = []      # list of (datetime, E, N, h)
    unmatched = 0

    for jpg_path in jpg_files:
        label = os.path.basename(jpg_path)
        if label not in csv_by_label:
            logging.warning("[INTERP_REF] No CSV entry for '%s', skipping.", label)
            unmatched += 1
            continue
        try:
            with open(jpg_path, 'rb') as f:
                raw = f.read()
            xmp = _parse_dji_xmp(raw)
            utc_str = xmp.get("UTCAtExposure")
            if not utc_str:
                raise ValueError(f"drone-dji:UTCAtExposure missing in '{jpg_path}'")
            ts = datetime.fromisoformat(utc_str)
        except Exception as exc:
            logging.warning("[INTERP_REF] Skipping '%s': %s", jpg_path, exc)
            unmatched += 1
            continue

        E, N, h = csv_by_label[label]
        rows.append((ts, E, N, h))

    elapsed = _time.time() - t0

    if not rows:
        raise RuntimeError(
            f"[INTERP_REF] No matched P1 positions in '{p1_image_folder}'. "
            "Check that p1_pos_CH1903.csv was produced from the same image set."
        )

    total = len(rows) + unmatched
    if unmatched / max(total, 1) > 0.05:
        logging.warning(
            "[INTERP_REF] %d/%d images unmatched (>5%%). MRK: '%s'.",
            unmatched, total, mrk_file
        )

    rows.sort(key=lambda r: r[0])

    # ── 3. Write reference CSV ─────────────────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as fh:
        fh.write("# P1 interpolation reference (XMP timestamps + LV95/LHN95 positions)\n")
        fh.write("# Generated from: {} | {}\n".format(
            os.path.basename(mrk_file), os.path.basename(p1_ref_csv)))
        fh.write("timestamp_utc,easting,northing,height_lhn95\n")
        for ts, E, N, h in rows:
            fh.write(f"{ts.isoformat()},{E:.6f},{N:.6f},{h:.6f}\n")

    print(
        f"[INTERP_REF] Wrote {len(rows)} positions to "
        f"'{os.path.basename(out_path)}' ({elapsed:.1f}s, {unmatched} skipped)."
    )
    logging.info(
        "[INTERP_REF] Segment %d: %d positions written to '%s' (%d skipped).",
        flight_idx, len(rows), out_path, unmatched
    )
    return out_path


def load_p1_interp_reference(ref_csv, file_count):
    """
    Load a per-segment interpolation reference CSV into the global P1 state.

    Reads rows written by ``generate_p1_interp_reference`` (or a manually
    prepared file with the same format) and appends timestamps to ``P1_events``
    and LV95/LHN95 positions to ``P1_pos``.  Sets ``P1_first_timestamp`` and
    ``P1_last_timestamp`` for the given flight segment index.

    Parameters
    ----------
    ref_csv : str
        Path to the p1_interp_reference_N.csv file.
    file_count : int
        Flight segment index (1-based) used as key for first/last timestamps.
    """
    global P1_events, P1_pos, P1_first_timestamp, P1_last_timestamp

    loaded = []
    with open(ref_csv, 'r') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 4:
                continue
            try:
                ts = datetime.fromisoformat(parts[0])
                E  = float(parts[1])
                N  = float(parts[2])
                h  = float(parts[3])
            except (ValueError, IndexError):
                continue  # skip header row
            loaded.append((ts, E, N, h))

    if not loaded:
        raise RuntimeError(
            f"[INTERP_REF] No valid rows found in '{ref_csv}'."
        )

    loaded.sort(key=lambda r: r[0])
    for ts, E, N, h in loaded:
        P1_events.append(ts)
        P1_pos.append([E, N, h])

    P1_first_timestamp[file_count] = loaded[0][0].timestamp()
    P1_last_timestamp[file_count]  = loaded[-1][0].timestamp()

    print(
        f"[INTERP_REF] Loaded {len(loaded)} positions from "
        f"'{os.path.basename(ref_csv)}' for flight segment {file_count}."
    )
    logging.info(
        "[INTERP_REF] Segment %d: %d positions loaded from '%s'.",
        file_count, len(loaded), ref_csv
    )


def _get_or_generate_interp_ref(mrk_file, p1_ref_csv, p1_folder, out_dir, idx):
    """
    Return path to the per-segment interpolation reference CSV, generating it
    from scratch if it does not already exist.

    Parameters
    ----------
    mrk_file : str
        Path to the (faulty) MRK file — passed through to
        ``generate_p1_interp_reference`` for logging only.
    p1_ref_csv : str
        Path to p1_pos_CH1903.csv.
    p1_folder : str
        Folder containing P1 JPG images for this segment.
    out_dir : str
        Directory for the reference CSV (typically the references dir).
    idx : int
        Flight segment index (1-based).

    Returns
    -------
    str
        Absolute path to the reference CSV.
    """
    out_path = os.path.join(out_dir, f"p1_interp_reference_{idx}.csv")
    if os.path.exists(out_path):
        print(f"[INTERP_REF] Reusing existing reference: '{os.path.basename(out_path)}'.")
        logging.info("[INTERP_REF] Segment %d: reusing '%s'.", idx, out_path)
        return out_path
    return generate_p1_interp_reference(mrk_file, p1_ref_csv, p1_folder, out_dir, idx)


def ret_micasense_pos(absolute_micasense_file_list, mrk_folder, micasense_folder, image_suffix, epsg_crs, out_file, P1_shift_vec, htrans_path=None, htrans_fallback=None, p1_ref_csv=None):
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
    htrans_path : str or None
        Optional path to the primary Swisstopo CHGeo2004 htrans GeoTIFF
        (e.g. chgeo2004_htrans_ETRS89.tif).  When provided, heights are
        converted from LN02 (returned by the wgs84tolv95 API) to LHN95 by
        adding the grid delta.  When None, LN02 heights are written as-is.
    htrans_fallback : str or None
        Optional path to a fallback geoid GeoTIFF (e.g. ExtendedGeoid.tif).
        Used when htrans_path has no coverage for a point (nodata sentinel ~99.9).
    p1_ref_csv : str or None
        Optional path to p1_pos_CH1903.csv produced by the proc_rgb step.
        When the MRK file is faulty (or its positions mismatch EXIF), and this
        file exists, P1 positions are loaded directly from it (already in
        LV95/LHN95) paired with GPS timestamps from P1 XMP metadata.
        This bypasses the WGS84→Swisstopo API→htrans transformation chain.
        If not provided or the file does not exist, falls back to reading
        WGS84 positions from P1 XMP and transforming via the API.

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
    _p1_pos_from_csv = False  # True when any segment uses pre-transformed CSV positions
    _ref_out_dir = os.path.dirname(os.path.abspath(out_file))
    for mrk_file in mrk_file_list:
        p1_folder = os.path.dirname(os.path.abspath(mrk_file))
        mrk_valid, entries, mrk_lines = get_P1_position(mrk_file, loop_count)

        if not mrk_valid:
            # MRK has no GPS fix — prefer pre-transformed CSV positions if available
            if p1_ref_csv and os.path.exists(str(p1_ref_csv)):
                logging.info("[MRK] Faulty MRK '%s'. Generating interpolation reference from '%s'.",
                             mrk_file, p1_ref_csv)
                ref_file = _get_or_generate_interp_ref(
                    mrk_file, str(p1_ref_csv), p1_folder, _ref_out_dir, loop_count)
                load_p1_interp_reference(ref_file, loop_count)
                _p1_pos_from_csv = True
            else:
                print(f"[MRK] Faulty MRK — loading positions from P1 XMP/EXIF: {p1_folder}")
                get_P1_position_from_exif(p1_folder, loop_count)
        else:
            # MRK has positions — spot-check a sample against EXIF XMP
            if _spot_check_mrk_vs_exif(entries, p1_folder):
                # Agreement confirmed — commit MRK entries (faster, denser timestamps)
                _commit_mrk_entries(entries, mrk_lines, loop_count)
            else:
                # Positions disagree — prefer CSV if available, else XMP fallback
                if p1_ref_csv and os.path.exists(str(p1_ref_csv)):
                    logging.info("[MRK] Position mismatch for '%s'. Generating interpolation reference.",
                                 mrk_file)
                    ref_file = _get_or_generate_interp_ref(
                        mrk_file, str(p1_ref_csv), p1_folder, _ref_out_dir, loop_count)
                    load_p1_interp_reference(ref_file, loop_count)
                    _p1_pos_from_csv = True
                else:
                    print(f"[MRK] Position mismatch vs EXIF. Loading from P1 XMP/EXIF: {p1_folder}")
                    get_P1_position_from_exif(p1_folder, loop_count)

        loop_count = loop_count + 1

    # ── Transform P1 positions to LV95/LHN95 ─────────────────────────────────
    if _p1_pos_from_csv:
        # Positions already in LV95/LHN95 — no API/htrans step needed.
        # P1_pos was populated by load_p1_interp_reference from per-segment reference CSVs.
        P1_pos = np.array(P1_pos)
        logging.info(
            "[INTERP_REF] Using %d pre-transformed P1 positions (LV95/LHN95). "
            "Skipping Swisstopo API and htrans transformation.",
            len(P1_pos)
        )
        print(f"[INTERP_REF] Using {len(P1_pos)} pre-transformed P1 positions (LV95/LHN95).")
    else:
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
                h = result["altitude"]  # LN02 orthometric (used as fallback if no htrans)
                # Apply ETRS89 -> LHN95 correction using the htrans grid.
                # IMPORTANT: pass alt (ETRS89 ellipsoidal from MRK/XMP), not h (LN02 from API).
                if htrans_path:
                    h = apply_htrans_correction(lon, lat, alt, htrans_path, fallback_path=htrans_fallback)
                P1_pos.append([result["easting"], result["northing"], h])
            else:
                # Fallback to pyproj transformer if API fails
                try:
                    E, N = transformer.transform(lat, lon)
                    h_fallback = apply_htrans_correction(lon, lat, alt, htrans_path, fallback_path=htrans_fallback) if htrans_path else alt
                    P1_pos.append([E, N, h_fallback])
                    logging.warning(f"Used pyproj fallback for position {i}: lat={lat}, lon={lon}")
                except Exception as e:
                    logging.error(f"Both API and pyproj failed for position {i}: {e}")
                    P1_pos.append([0.0, 0.0, 0.0])

            if (i + 1) % 50 == 0 or (i + 1) == total:
                print(f"Transformed {i+1}/{total} P1 positions")

        P1_pos = np.array(P1_pos)
 
        
    # ── Timestamp diagnostic ──────────────────────────────────────────────────
    print("\n=== TIMESTAMP DIAGNOSTIC ===")
    if P1_events:
        p1_sorted = sorted(P1_events)
        p1_ms = [dt.isoformat(timespec='milliseconds') for dt in p1_sorted]
        print(f"P1 window  : {p1_ms[0]}  ->  {p1_ms[-1]}")
        print(f"P1 images  : {len(p1_sorted)}")
        print("P1 timestamps (all):")
        for i, ts in enumerate(p1_ms):
            print(f"  P1[{i+1:02d}] {ts}")
    else:
        print("P1 timestamps: NONE loaded")

    if mica_events:
        mica_sorted = sorted(mica_events)
        mica_ms = [dt.isoformat(timespec='milliseconds') for dt in mica_sorted]
        print(f"\nMicaSense window : {mica_ms[0]}  ->  {mica_ms[-1]}")
        print(f"MicaSense images : {len(mica_sorted)}")
        print(f"(MICA_deltat={MICA_deltat}s applied to raw EXIF — timestamps shifted by {-MICA_deltat:+.0f}s)")
        print("MicaSense timestamps — first 10:")
        for ts in mica_ms[:10]:
            print(f"  MICA {ts}")
        if len(mica_ms) > 20:
            print(f"  ... ({len(mica_ms) - 20} more) ...")
        print("MicaSense timestamps — last 10:")
        for ts in mica_ms[-10:]:
            print(f"  MICA {ts}")

        if P1_events:
            p1_start_epoch = p1_sorted[0].timestamp()
            p1_end_epoch   = p1_sorted[-1].timestamp()
            before_p1 = [dt for dt in mica_sorted if dt.timestamp() < p1_start_epoch]
            within_p1 = [dt for dt in mica_sorted if p1_start_epoch <= dt.timestamp() <= p1_end_epoch]
            after_p1  = [dt for dt in mica_sorted if dt.timestamp() > p1_end_epoch]

            print(f"\nMicaSense vs P1 window ({p1_ms[0]} -> {p1_ms[-1]}):")
            print(f"  Before P1 window : {len(before_p1)} images")
            print(f"  Within P1 window : {len(within_p1)} images")
            print(f"  After P1 window  : {len(after_p1)} images")
            if before_p1:
                gap_before = p1_start_epoch - before_p1[-1].timestamp()
                print(f"  Last MicaSense before P1 start : {before_p1[-1].isoformat(timespec='milliseconds')}"
                      f"  (gap to P1 start: {gap_before:+.3f}s)")
            if after_p1:
                gap_after = after_p1[0].timestamp() - p1_end_epoch
                print(f"  First MicaSense after P1 end   : {after_p1[0].isoformat(timespec='milliseconds')}"
                      f"  (gap from P1 end:  {gap_after:+.3f}s)")
    else:
        print("MicaSense timestamps: NONE loaded")
    print("=== END TIMESTAMP DIAGNOSTIC ===\n")
    # ─────────────────────────────────────────────────────────────────────────

    # Create output MicaSense position csv 
    out_frame = open(out_file, 'w', encoding='utf-8')
    # write header row: heights are LHN95 (primary grid), EGM2008 (fallback), or ETRS89 ellipsoidal (no grid)
    if htrans_path and htrans_fallback:
        height_label = "LHN95/EGM2008 Height"
    elif htrans_path:
        height_label = "LHN95 Height"
    else:
        height_label = "ETRS89 Ellipsoidal Height"
    rec = (f"Label, Easting, Northing, {height_label}\n")
    print("Writing to file: ", rec)
    out_frame.write(rec) 
    
    count = 0
    n_outside = 0  # MicaSense images outside P1 capture times (written with z=0)

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
            # Clamp index so a+1 and a-1 are always valid
            a = max(1, min(a, len(P1_events) - 2))
            P1_pos_time = P1_events[a].timestamp()  # recompute after clamp

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

            # Interpolated height is LHN95 when htrans_path was supplied to ret_micasense_pos,
            # otherwise it is the LN02 orthometric height returned by the wgs84tolv95 API.

        # Combine into a new interpolated position vector for the MicaSense image:
        upd_micasense_pos = [interp_E, interp_N, interp_h]

        path_image_name = os.path.abspath(filelist[count]) 
        image_name = path_image_name
        
        pos_index = mica_events.index(m_cam_time)

        # For images captured within P1 times, write updated Easting, Northing, orthometric height to CSV
        if(upd_micasense_pos[2] != 0):
            rec = ("%s, %10.6f, %10.6f, %10.4f\n" % \
                    (image_name, upd_micasense_pos[0], upd_micasense_pos[1], upd_micasense_pos[2]))
        else:
            # For MicaSense images captured outside P1 times, just save original Easting, Northing. Set height to 0
            # to filter and delete these cameras
            n_outside += 1
            rec = ("%s, %10.6f, %10.6f, %10.4f\n" % \
                    (image_name, mica_pos[pos_index][0], mica_pos[pos_index][1], upd_micasense_pos[2]))
                        
        print("Writing to file: ", rec)                
        out_frame.write(rec)
        count = count + 1
        
    # Close the CSV file
    out_frame.close()
    
    # Print summary statistics
    cameras_interpolated = count - n_outside
    print(f"\n=== MicaSense Position Interpolation Summary ===")
    print(f"Total MicaSense images processed: {count}")
    print(f"Images interpolated from P1 positions: {cameras_interpolated}")
    print(f"Images outside P1 capture times (will be deleted): {n_outside}")
    logging.info(f"MicaSense interpolation complete: {cameras_interpolated} interpolated, {n_outside} outside P1 times")
    print(f"Output written to: {out_file}")