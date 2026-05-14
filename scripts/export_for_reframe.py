"""
export_for_reframe.py
---------------------
Reads camera positions from a P1 MRK file (or falls back to DJI XMP in JPGs)
and writes two CSV files for upload to Swisstopo Reframe
(https://www.swisstopo.admin.ch/en/transformation-calculation-reframe):

  <output_stem>_input_wgs84.csv     — WGS84 lon/lat + ETRS89 ellipsoidal height
                                       (upload with source CRS = WGS84 / ETRS89)
  <output_stem>_htrans_lhn95.csv    — WGS84 lon/lat + htrans-corrected height
                                       (for side-by-side comparison after Reframe runs)

Both files use the 4-value CSV format accepted by Reframe:
    ID, Longitude, Latitude, Height
No header line — Reframe does not allow title lines.

Usage
-----
    python export_for_reframe.py <mrk_or_folder> [options]

    <mrk_or_folder>   Path to a .MRK file  OR  a folder that contains one.

Options
-------
    --htrans PATH           Path to Swisstopo/ETRS.tif  (optional)
    --htrans-fallback PATH  Path to ExtendedGeoid.tif            (optional)
    --output PATH           Output file stem (default: reframe_export)
    --max-points N          Maximum number of points to export   (default: all)

If --htrans is not supplied the htrans column in the output will be the raw
ETRS89 ellipsoidal height (with a note in the filename).

Example
-------
    python export_for_reframe.py "M:/data/P1/lwf_lens/20250818" \
        --htrans "M:/geoid/Swisstopo/ETRS.tif" \
        --htrans-fallback "M:/geoid/ExtendedGeoid.tif" \
        --output lwf_lens_reframe
"""

import argparse
import csv
import glob
import os
import re
import sys
import logging

logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Optional rasterio / pyproj for htrans correction
# ---------------------------------------------------------------------------
try:
    import rasterio
    import pyproj
    _RASTERIO_OK = True
except ImportError:
    _RASTERIO_OK = False

_HTRANS_NODATA = 99.9


# ---------------------------------------------------------------------------
# MRK / XMP readers  (mirrors test_htrans_datum_chain.py logic)
# ---------------------------------------------------------------------------

def _parse_dji_xmp(raw_bytes):
    xmp_start = raw_bytes.find(b"<?xpacket")
    xmp_end   = raw_bytes.find(b"<?xpacket end")
    if xmp_start == -1 or xmp_end == -1:
        return {}
    xmp = raw_bytes[xmp_start:xmp_end + 50].decode("utf-8", errors="replace")
    fields = {}
    for key in ("GpsLatitude", "GpsLongitude", "AbsoluteAltitude", "RtkFlag"):
        m = re.search(r'drone-dji:' + key + r'="([^"]+)"', xmp)
        fields[key] = m.group(1) if m else None
    return fields


def _read_from_mrk(path, max_points):
    """Parse a .MRK file. Returns list of (id, lat, lon, ellh) or [] if all-zero."""
    out = []
    with open(path) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 9:
                continue
            try:
                pt_id = parts[0]
                lat   = float(parts[6].split(",")[0])
                lon   = float(parts[7].split(",")[0])
                ellh  = float(parts[8].split(",")[0])
            except (ValueError, IndexError):
                continue
            if lat == 0.0 and lon == 0.0 and ellh == 0.0:
                continue
            out.append((pt_id, lat, lon, ellh))
            if max_points and len(out) >= max_points:
                break
    return out


def _read_from_xmp(folder, max_points):
    """Read DJI XMP from P1 JPGs in *folder*. Returns list of (id, lat, lon, ellh)."""
    # Dedup case-insensitive on Windows
    jpg_files = sorted(set(
        glob.glob(folder + "/*.JPG") + glob.glob(folder + "/*.jpg")
    ))
    if not jpg_files:
        sys.exit(f"[ERROR] No JPG files found in {folder}")

    out = []
    non_fixed = 0
    for jpg in jpg_files:
        # DJI always writes XMP in the first APP1 segment — read only the first
        # 64 KB instead of the full ~45 MB file (critical for network drives).
        with open(jpg, "rb") as fh:
            raw = fh.read(65536)
        xmp = _parse_dji_xmp(raw)
        lat_s = xmp.get("GpsLatitude")
        lon_s = xmp.get("GpsLongitude")
        alt_s = xmp.get("AbsoluteAltitude")
        if not (lat_s and lon_s and alt_s):
            continue
        rtk = xmp.get("RtkFlag", "?")
        if rtk != "50":
            non_fixed += 1
        pt_id = os.path.splitext(os.path.basename(jpg))[0]
        out.append((pt_id, float(lat_s), float(lon_s), float(alt_s)))
        if max_points and len(out) >= max_points:
            break

    if non_fixed:
        print(f"  [WARN] {non_fixed}/{len(out)} images do NOT have RtkFlag=50 (RTK fixed)."
              " Heights may be less accurate.")
    return out


def read_positions(mrk_or_folder, max_points):
    """
    Returns (list_of_(id,lat,lon,ellh), source_label).
    Tries MRK first; falls back to XMP if MRK yields all-zero rows.
    """
    path = mrk_or_folder

    # If a directory, find the first MRK inside it
    if os.path.isdir(path):
        mrk_files = glob.glob(path + "/**/*.MRK", recursive=True)
        if not mrk_files:
            # No MRK at all — go straight to XMP
            print(f"[INFO] No MRK found under {path}. Reading XMP from JPGs.")
            return _read_from_xmp(path, max_points), "XMP"
        path = mrk_files[0]
        print(f"[INFO] Using MRK: {path}")

    if not os.path.isfile(path):
        sys.exit(f"[ERROR] Not a file or directory: {mrk_or_folder}")

    if path.upper().endswith(".MRK"):
        rows = _read_from_mrk(path, max_points)
        if rows:
            return rows, f"MRK ({os.path.basename(path)})"
        print("[WARN] MRK has all-zero coordinates. Falling back to XMP in same folder.")
        folder = os.path.dirname(path)
        return _read_from_xmp(folder, max_points), "XMP"

    sys.exit(f"[ERROR] Expected a .MRK file or a directory; got: {path}")


# ---------------------------------------------------------------------------
# Geoid grid sampling
# ---------------------------------------------------------------------------

def _sample_grid(tif_path, lon, lat):
    """
    Sample a GeoTIFF at (lon, lat) using bilinear interpolation.

    Bilinear interpolation is used so that results match swisstopo Reframe
    to ~7 mm; nearest-neighbour produces errors up to ~260 mm.

    Handles the CHGeo2004 quirk where the file is tagged as LV95 but stored
    in geographic degrees.
    Returns float or None (nodata / out of coverage).
    """
    if not _RASTERIO_OK:
        return None
    try:
        with rasterio.open(tif_path) as ds:
            bounds = ds.bounds
            geographic = (
                -180 <= bounds.left  <= 180 and
                -180 <= bounds.right <= 180 and
                -90  <= bounds.bottom <= 90 and
                -90  <= bounds.top    <= 90
            )
            if geographic:
                x, y = lon, lat
            else:
                epsg = ds.crs.to_epsg() if ds.crs else None
                grid_crs = pyproj.CRS(epsg) if epsg else pyproj.CRS(ds.crs.to_wkt())
                wgs84    = pyproj.CRS("EPSG:4326")
                if not grid_crs.equals(wgs84):
                    tr = pyproj.Transformer.from_crs(wgs84, grid_crs, always_xy=True)
                    x, y = tr.transform(lon, lat)
                else:
                    x, y = lon, lat

            tf = ds.transform
            col_f = (x - tf.c) / tf.a
            row_f = (y - tf.f) / tf.e  # tf.e is negative
            c0, r0 = int(col_f), int(row_f)

            if c0 < 0 or r0 < 0 or c0 >= ds.width - 1 or r0 >= ds.height - 1:
                return None

            data = ds.read(1, window=rasterio.windows.Window(c0, r0, 2, 2))
            v00, v01, v10, v11 = data[0, 0], data[0, 1], data[1, 0], data[1, 1]
            if any(abs(v - _HTRANS_NODATA) < 0.05 for v in (v00, v01, v10, v11)):
                return None   # nodata sentinel on any corner

            dc, dr = col_f - c0, row_f - r0
            val = (v00 * (1 - dc) * (1 - dr) + v01 * dc * (1 - dr) +
                   v10 * (1 - dc) * dr        + v11 * dc * dr)
            return val
    except Exception as exc:
        logging.debug("Grid sampling failed for %s: %s", tif_path, exc)
    return None


def apply_htrans(lon, lat, etrs89_h, htrans_path, fallback_path):
    """
    Returns (corrected_height, source_label).
    source_label: 'LHN95', 'EGM2008', or 'ETRS89_ellipsoidal' (no grid).
    """
    if htrans_path and _RASTERIO_OK:
        N = _sample_grid(htrans_path, lon, lat)
        if N is not None:
            return etrs89_h - N, "LHN95"

    if fallback_path and _RASTERIO_OK:
        N = _sample_grid(fallback_path, lon, lat)
        if N is not None:
            return etrs89_h - N, "EGM2008"

    return etrs89_h, "ETRS89_ellipsoidal"


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def write_reframe_csv(path, rows):
    """
    Write a Reframe-compatible 4-value CSV (no header):
        ID, Longitude, Latitude, Height
    """
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        for row in rows:
            writer.writerow(row)
    print(f"  Written: {path}  ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export P1 camera positions for Swisstopo Reframe verification."
    )
    parser.add_argument("source",
        help="Path to a .MRK file or a folder containing one.")
    parser.add_argument("--htrans",
        default=None,
        help="Path to Swisstopo/ETRS.tif (swisstopo CHGeo2004, ETRS89 input)")
    parser.add_argument("--htrans-fallback",
        dest="htrans_fallback",
        default=None,
        help="Path to ExtendedGeoid.tif (EGM2008 fallback)")
    parser.add_argument("--output",
        default="reframe_export",
        help="Output file stem (default: reframe_export)")
    parser.add_argument("--max-points",
        dest="max_points",
        type=int,
        default=0,
        help="Limit number of exported points (default: all)")
    args = parser.parse_args()

    # Validate optional grid files
    if args.htrans and not os.path.isfile(args.htrans):
        sys.exit(f"[ERROR] htrans file not found: {args.htrans}")
    if args.htrans_fallback and not os.path.isfile(args.htrans_fallback):
        sys.exit(f"[ERROR] htrans fallback not found: {args.htrans_fallback}")
    if (args.htrans or args.htrans_fallback) and not _RASTERIO_OK:
        sys.exit("[ERROR] rasterio / pyproj not installed — cannot apply htrans.")

    # Read positions
    positions, source_label = read_positions(args.source, args.max_points)
    if not positions:
        sys.exit("[ERROR] No valid positions found.")
    print(f"[INFO] Read {len(positions)} positions from {source_label}")

    # Build output rows
    input_rows   = []   # WGS84 lon/lat + ETRS89 ellipsoidal → upload to Reframe
    htrans_rows  = []   # WGS84 lon/lat + htrans-corrected height → for comparison

    height_sources = set()
    for (pt_id, lat, lon, ellh) in positions:
        input_rows.append([pt_id, f"{lon:.9f}", f"{lat:.9f}", f"{ellh:.4f}"])

        h_corr, h_src = apply_htrans(lon, lat, ellh, args.htrans, args.htrans_fallback)
        height_sources.add(h_src)
        htrans_rows.append([pt_id, f"{lon:.9f}", f"{lat:.9f}", f"{h_corr:.4f}"])

    # Determine file name suffix for the htrans file
    if "LHN95" in height_sources:
        h_label = "lhn95"
    elif "EGM2008" in height_sources:
        h_label = "egm2008"
    else:
        h_label = "etrs89_ellipsoidal"

    # Write files
    out_input  = f"{args.output}_input_wgs84.csv"
    out_htrans = f"{args.output}_htrans_{h_label}.csv"

    print("\n--- Writing Reframe input files ---")
    write_reframe_csv(out_input,  input_rows)
    write_reframe_csv(out_htrans, htrans_rows)

    print("\n--- How to verify ---")
    print(f"1. Go to https://www.swisstopo.admin.ch/en/transformation-calculation-reframe")
    print(f"2. Upload:  {os.path.abspath(out_input)}")
    print(f"   Source CRS:  WGS84 geographic (EPSG:4326) + ellipsoidal height")
    print(f"   Target CRS:  LV95 / LHN95  (or LV03 / LN02 for comparison)")
    print(f"3. Reframe returns LHN95 heights.  Compare with:  {os.path.abspath(out_htrans)}")
    print(f"   Height source used for that file: {', '.join(sorted(height_sources))}")
    print(f"\n   Expected agreement: < 5 cm for Swiss sites; up to ~30 cm for EGM2008 vs LHN95.")


if __name__ == "__main__":
    main()
