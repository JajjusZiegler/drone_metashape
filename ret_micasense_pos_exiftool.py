"""
MicaSense position interpolation that falls back to exiftool when MRK RTK quality is bad.

Logic:
- Read MRK files under the RGB folder. If every MRK row has quality flag 50 or "50,Q",
  use MRK times/positions as usual.
- Otherwise, read the RGB images with exiftool to obtain UTC time (XMP:UTCAtExposure or
  EXIF:DateTimeOriginal + SubSec) and GPS lat/lon/alt, then convert to CH1903+ using the
  same transform_coordinates helper. These times/positions are used for interpolation.

Interpolation: linear between the two nearest P1 shots (by time) for each MicaSense image.

Usage example:
  python ret_micasense_pos_exiftool.py \
    --mrk-folder "M:/.../P1/..." \
    --rgb-folder "M:/.../P1/..." \
    --micasense-folder "M:/.../Micasense/..." \
    --image-suffix 6 \
    --epsg 2056 \
    --out-file output.csv

Note: Requires exiftool installed (use --exiftool to point to the executable) and exifread.
"""

import argparse
import glob
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import exifread
import numpy as np
from exiftool import ExifToolHelper
from pyproj.transformer import TransformerGroup

# Reuse constants/logic from the original script
GPSUTC_deltat = 0
MICA_deltat = -18
EPSG_4326 = 4326


def transform_coordinates(lon, lat, alt=None, max_retries=3, delay=0.15):
    import time
    import requests

    API_URL = "https://geodesy.geo.admin.ch/reframe/wgs84tolv95"
    params = {"northing": lat, "easting": lon, "altitude": alt, "format": "json"}
    for attempt in range(max_retries):
        try:
            if delay > 0:
                time.sleep(delay)
            response = requests.get(API_URL, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()
            return {
                "easting": float(result.get("easting", 0.0)),
                "northing": float(result.get("northing", 0.0)),
                "altitude": float(result.get("altitude", 0.0)),
            }
        except Exception:
            if attempt == max_retries - 1:
                return None
            time.sleep(1.0)
    return None


def _resolve_exiftool(exe_override: Optional[str]) -> Optional[str]:
    if exe_override:
        return exe_override
    candidates = [
        r"C:\\Program Files\\exiftool-13.03_64\\exiftool.exe",
        r"C:\\Program Files\\exiftool-13.01_64\\exiftool.exe",
        r"C:\\Program Files\\exiftool\\exiftool.exe",
        r"C:\\Program Files (x86)\\exiftool\\exiftool.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def _seq_from_name(path: Path) -> int:
    m = re.search(r"(\d+)(?=\.[^.]+$)", path.name)
    return int(m.group(1)) if m else 0


def parse_mrk(folder: Path) -> Tuple[List[float], List[List[float]], bool, List[str]]:
    mrk_files = sorted(folder.rglob("*.MRK"))
    ts_list: List[float] = []
    pos_list: List[List[float]] = []
    all_good = True
    labels: List[str] = []

    for m_path in mrk_files:
        with m_path.open("r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f):
                parts = line.split()
                if len(parts) < 9:
                    continue
                try:
                    secs = float(parts[1])
                    week = int(parts[2].strip("[]"))
                    lat = float(parts[6].split(",")[0])
                    lon = float(parts[7].split(",")[0])
                    alt = float(parts[8].split(",")[0])
                    quality = parts[9] if len(parts) > 9 else ""
                except Exception:
                    continue

                if not (str(quality).startswith("50") or str(quality).startswith("50,Q")):
                    all_good = False

                epoch_secs = secs + (week * 7 * 24 * 60 * 60)
                ts = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
                ts -= timedelta(seconds=GPSUTC_deltat)
                ts_list.append(ts.timestamp())
                pos_list.append([lat, lon, alt])
                labels.append(f"MRK:{m_path.name}#{idx:05d}")

    return ts_list, pos_list, all_good, labels


def convert_wgs84_to_lv95(lat_lon_alt: List[List[float]], transformer) -> np.ndarray:
    out = []
    for lat, lon, alt in lat_lon_alt:
        result = transform_coordinates(lon, lat, alt)
        if result:
            out.append([result["easting"], result["northing"], result["altitude"]])
        else:
            E, N = transformer.transform(lat, lon)
            out.append([E, N, alt])
    return np.array(out)


def load_p1_from_exif(rgb_folder: Path, transformer, exe_override: Optional[str]) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    images = []
    for pat in ["**/*.JPG", "**/*.JPEG", "**/*.TIF", "**/*.TIFF", "**/*.DNG"]:
        images.extend(rgb_folder.glob(pat))
    images.sort(key=_seq_from_name)
    if not images:
        raise FileNotFoundError(f"No RGB images found under: {rgb_folder}")

    exe = _resolve_exiftool(exe_override)
    kwargs = {"executable": exe} if exe else {}
    with ExifToolHelper(**kwargs) as et:
        meta = et.get_metadata([str(p) for p in images])

    ts_list = []
    pos_list = []
    labels: List[str] = []
    for m in meta:
        utc = m.get("XMP:UTCAtExposure") 
        if not utc:
            continue
        # Parse times like "2025:10:02 10:45:19.801464"
        try:
            dt = datetime.strptime(str(utc), "%Y:%m:%d %H:%M:%S.%f")
        except ValueError:
            dt = datetime.strptime(str(utc), "%Y:%m:%d %H:%M:%S")
        ts_list.append(dt.timestamp())

        lat = m.get("EXIF:GPSLatitude")
        lon = m.get("EXIF:GPSLongitude") 
        alt = m.get("EXIF:GPSAltitude") or 0.0
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            alt_f = float(alt)
        except Exception:
            lat_f, lon_f, alt_f = 0.0, 0.0, 0.0
        pos_list.append([lat_f, lon_f, alt_f])
        labels.append(str(m.get("SourceFile", "")))

    if not ts_list:
        raise RuntimeError("No timestamps extracted from RGB images via exiftool")

    positions_lv95 = convert_wgs84_to_lv95(pos_list, transformer)
    return np.array(ts_list), positions_lv95, labels


def load_micasense_events(micasense_folder: Path, image_suffix: int) -> Tuple[List[datetime], List[List[float]], List[Path]]:
    filelist = list(Path(micasense_folder).glob(f"**/IMG*_{image_suffix}.tif"))
    # Stable sort: group by parent folder (capture set), then by numeric suffix within that folder
    filelist.sort(key=lambda p: (str(p.parent), _seq_from_name(p)))
    events = []
    gps_pos = []
    files_used = []
    for file in filelist:
        with file.open("rb") as f:
            tags = exifread.process_file(f)
        if not tags:
            continue
        mica_time = str(tags.get("EXIF DateTimeOriginal"))
        sub = str(tags.get("EXIF SubSecTime"))
        subsec = float(f"0.{int(float(sub))}") if sub not in (None, "None") else 0.0
        dt = datetime.strptime(mica_time, "%Y:%m:%d %H:%M:%S") + timedelta(seconds=subsec)
        dt -= timedelta(seconds=MICA_deltat)
        events.append(dt)
        files_used.append(file)

        lat = tags.get("GPS GPSLatitude")
        lon = tags.get("GPS GPSLongitude")
        alt = tags.get("GPS GPSAltitude")
        if lat and lon and alt:
            try:
                # exifread Ratio lists
                def to_deg(ratio):
                    return float(ratio.values[0].num) / float(ratio.values[0].den) + \
                           float(ratio.values[1].num) / float(ratio.values[1].den) / 60 + \
                           float(ratio.values[2].num) / float(ratio.values[2].den) / 3600

                lat_v = to_deg(lat)
                lon_v = to_deg(lon)
                alt_v = float(alt.values[0].num) / float(alt.values[0].den)
            except Exception:
                lat_v, lon_v, alt_v = 0.0, 0.0, 0.0
        else:
            lat_v, lon_v, alt_v = 0.0, 0.0, 0.0
        gps_pos.append([lat_v, lon_v, alt_v])
    return events, gps_pos, files_used


def _fmt_ts(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def interpolate(
    mica_events: List[datetime],
    p1_ts: np.ndarray,
    p1_pos: np.ndarray,
    debug: bool = False,
    p1_labels: Optional[List[str]] = None,
    mica_labels: Optional[List[str]] = None,
) -> Tuple[List[List[float]], List[dict]]:
    out = []
    dbg_rows: List[dict] = []
    for idx_mica, dt in enumerate(mica_events):
        ts = dt.timestamp()
        mica_label = mica_labels[idx_mica] if mica_labels and idx_mica < len(mica_labels) else f"Mica_{idx_mica+1:05d}"
        status = "ok"
        if ts < p1_ts[0] or ts > p1_ts[-1]:
            out.append([0.0, 0.0, 0.0])
            status = "out_of_range"
            if debug:
                dbg_rows.append(
                    {
                        "mica": mica_label,
                        "mica_ts": _fmt_ts(ts),
                        "lower": None,
                        "upper": None,
                        "alpha": None,
                        "status": status,
                    }
                )
            continue
        idx = np.searchsorted(p1_ts, ts)
        if idx == 0:
            idx = 1
        lower_idx = idx - 1
        upper_idx = idx
        t0, t1 = p1_ts[lower_idx], p1_ts[upper_idx]
        p0, p1 = p1_pos[lower_idx], p1_pos[upper_idx]
        alpha = 0 if t1 == t0 else (ts - t0) / (t1 - t0)
        out.append(list(p0 + alpha * (p1 - p0)))
        if debug:
            lower_label = p1_labels[lower_idx] if p1_labels and lower_idx < len(p1_labels) else f"P1_{lower_idx:05d}"
            upper_label = p1_labels[upper_idx] if p1_labels and upper_idx < len(p1_labels) else f"P1_{upper_idx:05d}"
            dbg_rows.append(
                {
                    "mica": mica_label,
                    "mica_ts": _fmt_ts(ts),
                    "lower": f"{lower_label} @ {_fmt_ts(t0)}",
                    "upper": f"{upper_label} @ {_fmt_ts(t1)}",
                    "alpha": alpha,
                    "status": status,
                }
            )
    return out, dbg_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mrk-folder", required=True, type=Path)
    ap.add_argument("--rgb-folder", required=True, type=Path)
    ap.add_argument("--micasense-folder", required=True, type=Path)
    ap.add_argument("--image-suffix", type=int, default=6)
    ap.add_argument("--epsg", type=int, required=True)
    ap.add_argument("--out-file", required=True, type=Path)
    ap.add_argument("--exiftool", type=str, help="Path to exiftool executable")
    ap.add_argument("--debug", action="store_true", help="Print ordered P1 times and interpolation pairs")
    args = ap.parse_args()

    # Early path validation for clearer errors
    for label, p in [
        ("mrk-folder", args.mrk_folder),
        ("rgb-folder", args.rgb_folder),
        ("micasense-folder", args.micasense_folder),
    ]:
        if not p.exists():
            raise FileNotFoundError(f"Path not found for {label}: {p}")

    # Transformer selection to match original behavior
    transf_group = TransformerGroup(EPSG_4326, int(args.epsg))
    step_count = [str(tr).count("step") for tr in transf_group.transformers]
    transformer = transf_group.transformers[step_count.index(min(step_count))]

    mrk_ts, mrk_pos_geo, mrk_ok, mrk_labels = parse_mrk(args.mrk_folder)
    if mrk_ok and mrk_ts:
        print("MRK quality OK (all 50/Q). Using MRK for timestamps/positions.")
        p1_ts = np.array(mrk_ts)
        p1_pos = convert_wgs84_to_lv95(mrk_pos_geo, transformer)
        p1_labels = mrk_labels
    else:
        print("MRK quality missing/low. Falling back to exiftool for P1 times/positions.")
        p1_ts, p1_pos, p1_labels = load_p1_from_exif(args.rgb_folder, transformer, args.exiftool)

    if args.debug:
        print("\nP1 timeline (ordered):")
        for i, ts in enumerate(p1_ts):
            label = p1_labels[i] if i < len(p1_labels) else f"P1_{i:05d}"
            print(f"{i:05d} | {label} | {_fmt_ts(ts)}")

    # MicaSense
    mica_events, _, mica_files = load_micasense_events(args.micasense_folder, args.image_suffix)
    if not mica_events:
        raise FileNotFoundError("No MicaSense images found or no timestamps parsed")

    mica_labels = [str(p.resolve()) for p in mica_files]
    interp_pos, dbg_rows = interpolate(
        mica_events,
        p1_ts,
        p1_pos,
        debug=args.debug,
        p1_labels=p1_labels,
        mica_labels=mica_labels,
    )

    with args.out_file.open("w", encoding="utf-8", newline="") as f:
        f.write("Label, Easting, Northing, Ellip Height\n")
        for i, pos in enumerate(interp_pos):
            label = mica_labels[i] if i < len(mica_labels) else f"Mica_{i+1:05d}"
            f.write(f"{label}, {pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}\n")

    if args.debug:
        print("\nInterpolation pairs (Mica -> P1 bracketing):")
        for row in dbg_rows:
            if row["status"] == "out_of_range":
                print(f"{row['mica']} @ {row['mica_ts']} -> out of P1 range")
            else:
                alpha_txt = f"alpha={row['alpha']:.3f}" if row.get("alpha") is not None else "alpha=?"
                print(f"{row['mica']} @ {row['mica_ts']} -> [{row['lower']} | {row['upper']}] {alpha_txt}")

    print(f"Wrote interpolated positions to {args.out_file}")


if __name__ == "__main__":
    main()