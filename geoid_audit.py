# -*- coding: utf-8 -*-
"""
Swiss Geoid Height Audit Script
================================
Checks what height information is actually present in:
  1. The RTK EXIF data of a P1 image (WGS84 ellipsoidal)
  2. The DJI MRK file (WGS84 ellipsoidal, for comparison)
  3. The Swisstopo API response used by the pipeline (wgs84tolv03 → LN02)
  4. Manual CHGeo2004 geoid correction (LN02 and optionally LHN95)
  5. The exported DSM GeoTIFF pixel value at the same location

Usage
-----
  python geoid_audit.py ^
      --image  "path/to/P1_image.JPG"          ^
      --mrk    "path/to/flight.MRK"             ^
      --dsm    "path/to/dsm.tif"                ^
      --geoid_ln02  "path/to/chgeo2004_ETRS89_LN02.tif"  ^
      --geoid_lhn95 "path/to/chgeo2004_ETRS89_LHN95.tif"

Required
--------
  --image      : Any RTK-tagged JPG from the DJI Zenmuse P1 for the flight
  --geoid_ln02 : CHGeo2004 LN02 GeoTIFF (default path pre-filled below)

Optional but strongly recommended
-----------------------------------
  --mrk        : Corresponding DJI .MRK file (confirms EXIF altitude)
  --dsm        : Exported DSM GeoTIFF to check its height datum
  --geoid_lhn95: CHGeo2004 LHN95 GeoTIFF (needed to compare LN02 vs LHN95)

Dependencies (install via pip into Metashape's Python or a standalone env):
  pip install exifread rasterio pyproj requests
"""

import argparse
import sys
import time
from pathlib import Path

import requests
import exifread
import rasterio
import numpy as np
from pyproj import Transformer

# ---------------------------------------------------------------------------
# Swisstopo reframe API endpoints
# ---------------------------------------------------------------------------
API_LV03 = "https://geodesy.geo.admin.ch/reframe/wgs84tolv03"   # → CH1903/LV03 + LN02  (what DEMtests.py currently uses)
API_LV95 = "https://geodesy.geo.admin.ch/reframe/wgs84tolv95"   # → CH1903+/LV95 + LN02 (what should be used for EPSG:2056)

# Default geoid path (matches the hardcoded path in DEMtests.py)
DEFAULT_GEOID_LN02 = (
    r"M:\working_package_2\2024_dronecampaign\02_processing"
    r"\geoid\ch_swisstopo_chgeo2004_ETRS89_LN02.tif"
)


# ===========================================================================
# EXIF helpers
# ===========================================================================

def _dms_to_decimal(dms_values, ref: str) -> float:
    d = float(dms_values[0].num) / float(dms_values[0].den)
    m = float(dms_values[1].num) / float(dms_values[1].den)
    s = float(dms_values[2].num) / float(dms_values[2].den)
    value = d + m / 60.0 + s / 3600.0
    if ref.strip().upper() in ("S", "W"):
        value = -value
    return value


def read_exif_position(image_path: str):
    """
    Return (lat_deg, lon_deg, alt_m, alt_description) from GPS EXIF tags.
    For DJI RTK images the altitude tag stores WGS84 ellipsoidal height.
    GPSAltitudeRef == 0 means 'above reference' (ellipsoid for RTK images).
    """
    with open(image_path, "rb") as fh:
        tags = exifread.process_file(fh, details=False)

    lat = _dms_to_decimal(
        tags["GPS GPSLatitude"].values,
        str(tags.get("GPS GPSLatitudeRef", "N"))
    )
    lon = _dms_to_decimal(
        tags["GPS GPSLongitude"].values,
        str(tags.get("GPS GPSLongitudeRef", "E"))
    )
    alt_raw = tags["GPS GPSAltitude"].values[0]
    alt = float(alt_raw.num) / float(alt_raw.den)

    alt_ref = str(tags.get("GPS GPSAltitudeRef", "0"))
    if alt_ref == "0":
        desc = "above reference datum (ellipsoidal for RTK)"
    else:
        desc = f"GPSAltitudeRef={alt_ref}"

    return lat, lon, alt, desc


# ===========================================================================
# MRK file reader
# ===========================================================================

def read_mrk_positions(mrk_path: str, max_lines: int = 3):
    """
    Parse up to max_lines events from a DJI .MRK file.
    DJI MRK format (space-delimited):
      [0] index  [1] GPS_secs  [2] [week]  [3] Lat,±std  [4] Lon,±std  [5] EllH,±std ...
    Returns list of (lat, lon, ellip_h) tuples.
    """
    positions = []
    with open(mrk_path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            try:
                lat   = float(parts[3].split(",")[0])
                lon   = float(parts[4].split(",")[0])
                ell_h = float(parts[5].split(",")[0])
                positions.append((lat, lon, ell_h))
            except (IndexError, ValueError):
                continue
            if len(positions) >= max_lines:
                break
    return positions


# ===========================================================================
# Swisstopo API
# ===========================================================================

def swisstopo_api(lon: float, lat: float, alt: float, url: str, delay: float = 0.3):
    """
    Call the swisstopo reframe API.
    Returns (easting, northing, altitude) or (None, None, None) on failure.
    The 'altitude' in the response is an LN02 orthometric height.
    """
    time.sleep(delay)
    params = {"northing": lat, "easting": lon, "altitude": alt, "format": "json"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return float(data["easting"]), float(data["northing"]), float(data["altitude"])
    except Exception as exc:
        print(f"    [WARN] API call to {url} failed: {exc}")
        return None, None, None


# ===========================================================================
# Geoid sampling
# ===========================================================================

def sample_geoid(geoid_tif: str, lon_wgs84: float, lat_wgs84: float):
    """
    Sample CHGeo2004 geoid undulation N (metres) at (lon, lat) in WGS84.
    The GeoTIFF is georeferenced in ETRS89 geographic coords (≈ WGS84).
    Returns the undulation value, or None if outside bounds / file missing.
    """
    if not Path(geoid_tif).exists():
        return None
    with rasterio.open(geoid_tif) as ds:
        results = list(ds.sample([(lon_wgs84, lat_wgs84)]))
    if results:
        val = float(results[0][0])
        # nodata check
        with rasterio.open(geoid_tif) as ds:
            nd = ds.nodata
        if nd is not None and abs(val - nd) < 1e-3:
            return None
        return val
    return None


# ===========================================================================
# DSM sampling
# ===========================================================================

def sample_dsm(dsm_path: str, easting: float, northing: float):
    """
    Sample the DSM at CH1903+/LV95 (easting, northing).
    Returns (pixel_value_m, crs_wkt_str) or (None, None).
    """
    with rasterio.open(dsm_path) as ds:
        try:
            row, col = ds.index(easting, northing)
            if 0 <= row < ds.height and 0 <= col < ds.width:
                win = rasterio.windows.Window(col, row, 1, 1)
                data = ds.read(1, window=win)
                val = float(data[0, 0])
                nd = ds.nodata
                if nd is not None and abs(val - nd) < 1e-3:
                    return None, str(ds.crs)
                return val, str(ds.crs)
        except Exception as exc:
            print(f"    [WARN] DSM sampling error: {exc}")
    return None, None


# ===========================================================================
# Pretty-print report
# ===========================================================================

def _fmt(value, decimals=4, unit="m"):
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f} {unit}"


def _diff(a, b, label_a="", label_b=""):
    if a is None or b is None:
        return "N/A"
    d = a - b
    sign = "+" if d >= 0 else ""
    note = ""
    if abs(d) > 0.5:
        note = "  ← ⚠  >0.5 m discrepancy!"
    elif abs(d) > 0.1:
        note = "  ← ⚠  >0.1 m discrepancy"
    return f"{sign}{d:.4f} m{note}"


def print_report(r):
    W = 72
    sep = "─" * W

    def section(title):
        print(f"\n  {'─'*3} {title} {'─'*(W-6-len(title))}")

    def row(label, value):
        print(f"    {label:<42} {value}")

    print("\n" + "═" * W)
    print("   SWISS GEOID HEIGHT AUDIT  —  " + time.strftime("%Y-%m-%d %H:%M"))
    print("═" * W)

    # ── 1. EXIF ──────────────────────────────────────────────────────────────
    section("1. Image EXIF  (RTK GPS)")
    row("Latitude  (WGS84°)",       f"{r['lat']:.8f}")
    row("Longitude (WGS84°)",       f"{r['lon']:.8f}")
    row("GPS Altitude  (m)",        f"{r['alt_exif']:.4f} m   ← {r['alt_desc']}")

    # ── 2. MRK ───────────────────────────────────────────────────────────────
    if r.get("mrk_positions"):
        section("2. DJI MRK File  (first 3 events)")
        for i, (la, lo, h) in enumerate(r["mrk_positions"]):
            row(f"  Event {i+1}: lat/lon/ellH",
                f"{la:.6f} / {lo:.6f} / {h:.4f} m")
        if r.get("alt_exif") and r["mrk_positions"]:
            diff_mrk = r["alt_exif"] - r["mrk_positions"][0][2]
            row("EXIF alt − MRK[0] ellH", f"{diff_mrk:+.4f} m  (should be ~0 or offset by lever arm)")

    # ── 3. Swisstopo API ──────────────────────────────────────────────────────
    section("3. Swisstopo reframe API responses")
    row("Input: WGS84 ellipsoidal h",  f"{r['alt_exif']:.4f} m")
    print()

    if r.get("lv03") and r["lv03"][0] is not None:
        e, n, h = r["lv03"]
        row("wgs84tolv03 → E  (LV03/CH1903)",  f"{e:.3f} m")
        row("wgs84tolv03 → N  (LV03/CH1903)",  f"{n:.3f} m")
        row("wgs84tolv03 → alt  (LN02 h)",     f"{h:.4f} m   ← ⚠ LV03 is the OLD system")
    else:
        row("wgs84tolv03", "API call failed")

    print()
    if r.get("lv95") and r["lv95"][0] is not None:
        e95, n95, h95 = r["lv95"]
        row("wgs84tolv95 → E  (LV95/CH1903+)", f"{e95:.3f} m")
        row("wgs84tolv95 → N  (LV95/CH1903+)", f"{n95:.3f} m")
        row("wgs84tolv95 → alt  (LN02 h)",     f"{h95:.4f} m   ← correct horizontal, BUT still LN02")
    else:
        row("wgs84tolv95", "API call failed")

    if r.get("lv03") and r.get("lv95") and r["lv03"][0] and r["lv95"][0]:
        print()
        row("ΔE  (LV95 − LV03)",  f"{r['lv95'][0]-r['lv03'][0]:+.3f} m")
        row("ΔN  (LV95 − LV03)",  f"{r['lv95'][1]-r['lv03'][1]:+.3f} m")
        row("Δalt (both are LN02)", f"{r['lv95'][2]-r['lv03'][2]:+.4f} m")

    # ── 4. CHGeo2004 geoid ────────────────────────────────────────────────────
    section("4. CHGeo2004 geoid correction  (manual)")
    row("h_ellipsoidal input (WGS84)",  f"{r['alt_exif']:.4f} m")
    if r.get("N_ln02") is not None:
        row("Undulation N  (CHGeo2004 LN02)",  f"{r['N_ln02']:.4f} m")
        row("h_LN02  = h_ell − N_LN02",        f"{r['h_ln02']:.4f} m")
    else:
        row("CHGeo2004 LN02 geoid", "file not found or sampling failed")

    if r.get("N_lhn95") is not None:
        row("Undulation N  (CHGeo2004 LHN95)", f"{r['N_lhn95']:.4f} m")
        row("h_LHN95 = h_ell − N_LHN95",       f"{r['h_lhn95']:.4f} m")
        if r.get("h_ln02") is not None:
            d = r["h_ln02"] - r["h_lhn95"]
            row("h_LN02 − h_LHN95",
                f"{d:+.4f} m  ← this is the datum error if using LN02 for LHN95 target")
    else:
        row("CHGeo2004 LHN95 geoid", "not provided  (use --geoid_lhn95 to compare)")

    # ── 5. DSM ────────────────────────────────────────────────────────────────
    if r.get("dsm_val") is not None:
        section("5. DSM pixel at image location")
        e_s = r["lv95"][0] if r.get("lv95") and r["lv95"][0] else r.get("dsm_e")
        n_s = r["lv95"][1] if r.get("lv95") and r["lv95"][1] else r.get("dsm_n")
        row("Sample coordinates (CH1903+/LV95)",
            f"E={e_s:.1f}  N={n_s:.1f}")
        row("DSM CRS (from GeoTIFF metadata)", r.get("dsm_crs", "unknown"))
        row("DSM pixel value (m)",             f"{r['dsm_val']:.4f} m")
        print()
        row("NOTE: DSM is the SURFACE height, not drone height.",
            "Differences below are indicative only.")
        if r.get("h_ln02") is not None:
            row("DSM − h_LN02", _diff(r["dsm_val"], r["h_ln02"]))
        if r.get("h_lhn95") is not None:
            row("DSM − h_LHN95", _diff(r["dsm_val"], r["h_lhn95"]))
        if r.get("lv95") and r["lv95"][2]:
            row("DSM − API_LV95_alt (LN02)", _diff(r["dsm_val"], r["lv95"][2]))
        row("DSM − WGS84 ellipsoidal",
            _diff(r["dsm_val"], r["alt_exif"]) + "  (≈ −AGL flight height − geoid N)")

    # ── Diagnosis ─────────────────────────────────────────────────────────────
    print(f"\n{'═'*W}")
    print("   DIAGNOSIS")
    print(f"{'─'*W}")

    issues = []
    ok     = []

    # Issue 1: LV03 vs LV95
    if r.get("lv03") and r.get("lv95") and r["lv03"][0] and r["lv95"][0]:
        de = abs(r["lv95"][0] - r["lv03"][0])
        dn = abs(r["lv95"][1] - r["lv03"][1])
        if de > 0.5 or dn > 0.5:
            issues.append(
                f"  ⚠  Pipeline uses wgs84tolv03 (LV03/old CH1903) in upd_micasense_pos_filename.py\n"
                f"     but Metashape target CRS is LV95 (EPSG:2056/CH1903+).\n"
                f"     Horizontal offset: ΔE={de:+.3f} m, ΔN={dn:+.3f} m  across your site."
            )
        else:
            ok.append("  ✓  LV03 vs LV95 horizontal offset is negligible at this location.")

    # Issue 2: LN02 vs LHN95
    if r.get("h_ln02") and r.get("h_lhn95"):
        d = r["h_ln02"] - r["h_lhn95"]
        if abs(d) > 0.05:
            issues.append(
                f"  ⚠  Pipeline heights are LN02 but your target vertical datum is LHN95.\n"
                f"     Height difference at this location: {d:+.4f} m\n"
                f"     Fix: use chgeo2004_ETRS89_LHN95.tif (or the REFRAME service)."
            )
        else:
            ok.append(f"  ✓  LN02 vs LHN95 difference is negligible here ({d:+.4f} m).")
    else:
        issues.append(
            "  ⚠  Cannot check LN02 vs LHN95: --geoid_lhn95 file not provided.\n"
            "     Download chgeo2004_ETRS89_LHN95.tif from swisstopo and re-run."
        )

    # Issue 3: TransformHeight commented out
    issues.append(
        "  ⚠  TransformHeight.process_csv() is COMMENTED OUT in DEMtests.py.\n"
        "     MicaSense positions receive no explicit geoid correction in the current pipeline.\n"
        "     Heights come directly from the swisstopo API (LN02 via wgs84tolv03)."
    )

    for msg in issues:
        print(msg)
    for msg in ok:
        print(msg)

    print(f"{'═'*W}\n")


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Audit Swiss geoid height handling in the drone_metashape pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--image",       required=True,
                        help="Path to a sample RTK-tagged JPG from the P1 camera")
    parser.add_argument("--mrk",         required=False,
                        help="Path to the DJI .MRK file for the same flight (optional)")
    parser.add_argument("--dsm",         required=False,
                        help="Path to the exported DSM GeoTIFF (optional)")
    parser.add_argument("--geoid_ln02",  default=DEFAULT_GEOID_LN02,
                        help="Path to CHGeo2004 LN02 GeoTIFF")
    parser.add_argument("--geoid_lhn95", required=False,
                        help="Path to CHGeo2004 LHN95 GeoTIFF (optional, for comparison)")
    args = parser.parse_args()

    results = {}

    # ── Step 1: EXIF ──────────────────────────────────────────────────────────
    print(f"\n[1] Reading EXIF from: {args.image}")
    try:
        lat, lon, alt_exif, alt_desc = read_exif_position(args.image)
        results.update({"lat": lat, "lon": lon, "alt_exif": alt_exif, "alt_desc": alt_desc})
        print(f"    lat={lat:.8f}°, lon={lon:.8f}°, alt={alt_exif:.4f} m  ({alt_desc})")
    except Exception as exc:
        print(f"    ERROR reading EXIF: {exc}")
        sys.exit(1)

    # ── Step 2: MRK ───────────────────────────────────────────────────────────
    if args.mrk:
        print(f"\n[2] Reading MRK file: {args.mrk}")
        positions = read_mrk_positions(args.mrk, max_lines=3)
        if positions:
            results["mrk_positions"] = positions
            print(f"    First event: lat={positions[0][0]:.8f}°, lon={positions[0][1]:.8f}°, ellH={positions[0][2]:.4f} m")
        else:
            print("    Could not parse MRK file (check format).")

    # ── Step 3: Swisstopo API ─────────────────────────────────────────────────
    print(f"\n[3] Querying Swisstopo reframe API (requires internet access) ...")
    print(f"    → wgs84tolv03  (what DEMtests.py currently uses)")
    e03, n03, h03 = swisstopo_api(lon, lat, alt_exif, API_LV03)
    results["lv03"] = (e03, n03, h03)

    print(f"    → wgs84tolv95  (correct for EPSG:2056 target)")
    e95, n95, h95 = swisstopo_api(lon, lat, alt_exif, API_LV95)
    results["lv95"] = (e95, n95, h95)

    # ── Step 4: CHGeo2004 geoid ───────────────────────────────────────────────
    print(f"\n[4] Sampling geoid files ...")

    N_ln02 = sample_geoid(args.geoid_ln02, lon, lat)
    if N_ln02 is not None:
        results["N_ln02"] = N_ln02
        results["h_ln02"] = alt_exif - N_ln02
        print(f"    LN02:  N={N_ln02:.4f} m  →  h_LN02={results['h_ln02']:.4f} m")
    else:
        print(f"    LN02 geoid file not found or sampling failed: {args.geoid_ln02}")

    if args.geoid_lhn95:
        N_lhn95 = sample_geoid(args.geoid_lhn95, lon, lat)
        if N_lhn95 is not None:
            results["N_lhn95"] = N_lhn95
            results["h_lhn95"] = alt_exif - N_lhn95
            print(f"    LHN95: N={N_lhn95:.4f} m  →  h_LHN95={results['h_lhn95']:.4f} m")
        else:
            print(f"    LHN95 geoid file sampling failed: {args.geoid_lhn95}")

    # ── Step 5: DSM ───────────────────────────────────────────────────────────
    if args.dsm:
        print(f"\n[5] Sampling DSM: {args.dsm}")
        # Use LV95 from API if available, else fall back to pyproj
        if e95 is not None:
            sample_e, sample_n = e95, n95
        else:
            print("    (API failed — using pyproj for CRS transform)")
            tr = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)
            sample_e, sample_n = tr.transform(lon, lat)
        results["dsm_e"] = sample_e
        results["dsm_n"] = sample_n
        dsm_val, dsm_crs = sample_dsm(args.dsm, sample_e, sample_n)
        results["dsm_val"] = dsm_val
        results["dsm_crs"] = dsm_crs
        if dsm_val is not None:
            print(f"    DSM value at (E={sample_e:.1f}, N={sample_n:.1f}): {dsm_val:.4f} m")
        else:
            print("    Sampling returned NoData or location is outside DSM extent.")
            print("    TIP: Pass a point that is within the DSM coverage area.")

    # ── Report ────────────────────────────────────────────────────────────────
    print_report(results)


if __name__ == "__main__":
    main()
