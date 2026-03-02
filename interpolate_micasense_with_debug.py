import os
import glob
import logging
import argparse
import requests
import numpy as np
import exifread
import csv
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional, Sequence, Dict
from statistics import median
from pyproj.transformer import TransformerGroup

try:
    import Metashape  # type: ignore
except Exception:  # noqa: BLE001
    Metashape = None

# Constants
GPSUTC_deltat = 0
MICA_deltat = -18
EPSG_4326 = 4326
API_URL = "https://geodesy.geo.admin.ch/reframe/wgs84tolv95"


def transform_coordinates(lon: float, lat: float, alt: float) -> Optional[Tuple[float, float, float]]:
    """Transform coordinates using the Swisstopo API; fallback to EPSG transformer if needed."""
    params = {"northing": lat, "easting": lon, "altitude": alt, "format": "json"}
    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
        result = response.json()
        e = float(result.get("easting", 0.0))
        n = float(result.get("northing", 0.0))
        h = float(result.get("altitude", 0.0))
        return e, n, h
    except Exception as exc:  # noqa: BLE001
        logging.warning("API transform failed, will try proj fallback: %s", exc)
        return None


def _make_transformer(target_epsg: int):
    tg = TransformerGroup(EPSG_4326, target_epsg)
    step_counts = [str(tr).count("step") for tr in tg.transformers]
    min_idx = step_counts.index(min(step_counts))
    return tg.transformers[min_idx]


def get_P1_timestamp(line: str) -> datetime:
    parts = line.split()
    secs = float(parts[1])
    week = int(parts[2].strip("[").strip("]"))
    epoch_secs = secs + (week * 7 * 24 * 60 * 60)
    ts = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
    return ts - timedelta(seconds=GPSUTC_deltat)


def load_mrk_records(mrk_folder: Path) -> List[Tuple[datetime, float, float, float, str, str]]:
    """Return MRK records as (ts, lat, lon, ellh, quality, file)."""
    records: List[Tuple[datetime, float, float, float, str, str]] = []
    mrk_paths = sorted(glob.iglob(str(mrk_folder) + "/**/*.MRK", recursive=True))
    if not mrk_paths:
        raise FileNotFoundError(f"No .MRK files found under: {mrk_folder}")

    for mp in mrk_paths:
        with open(mp, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                parts = line.split()
                if len(parts) < 9:
                    continue
                try:
                    ts = get_P1_timestamp(line)
                    lat = float(parts[6].split(",")[0])
                    lon = float(parts[7].split(",")[0])
                    ellh = float(parts[8].split(",")[0])
                    qual = parts[9] if len(parts) > 9 else ""
                except Exception:
                    continue
                records.append((ts, lat, lon, ellh, qual, os.path.basename(mp)))
    if not records:
        raise RuntimeError(f"MRK files found but no valid entries parsed under: {mrk_folder}")
    return records


def _detect_time_jump(sequence: List[Tuple[str, datetime]], jump_threshold_seconds: float) -> Optional[dict]:
    if len(sequence) < 2:
        return None
    deltas = []
    for i in range(1, len(sequence)):
        deltas.append((sequence[i][1] - sequence[i - 1][1]).total_seconds())
    min_delta = min(deltas)
    if min_delta >= -jump_threshold_seconds:
        return None
    idx = deltas.index(min_delta) + 1
    return {
        "index": idx,
        "filename": sequence[idx][0],
        "delta_seconds": min_delta,
        "prev_ts": sequence[idx - 1][1],
        "curr_ts": sequence[idx][1],
    }


def _apply_jump_fix(sequence: List[Tuple[str, datetime]], jump_info: dict, qualities: Optional[Sequence[str]], window: int = 10):
    """Shift timestamps from jump onward using cadence estimated from preceding good (quality 50) pairs."""
    if not jump_info:
        return sequence, None
    idx = jump_info["index"]
    if idx <= 0 or idx >= len(sequence):
        return sequence, None

    deltas = []
    start = max(1, idx - window)
    for i in range(start, idx):
        if qualities and (qualities[i] != "50" or qualities[i - 1] != "50"):
            continue
        deltas.append((sequence[i][1] - sequence[i - 1][1]).total_seconds())
    if not deltas:
        for i in range(start, idx):
            deltas.append((sequence[i][1] - sequence[i - 1][1]).total_seconds())

    nominal = median(deltas) if deltas else 0.0
    desired = sequence[idx - 1][1] + timedelta(seconds=nominal)
    offset = desired - sequence[idx][1]

    corrected = []
    for i, (name, ts) in enumerate(sequence):
        if i < idx:
            corrected.append((name, ts))
        else:
            corrected.append((name, ts + offset))

    return corrected, {
        "offset_seconds": offset.total_seconds(),
        "nominal_delta": nominal,
        "applied_from_index": idx,
    }


def read_micasense_events(micasense_folder: Path, suffix: str) -> List[Tuple[str, datetime]]:
    files = sorted(glob.iglob(str(micasense_folder) + f"/**/IMG*{suffix}", recursive=True))
    events: List[Tuple[str, datetime]] = []
    for i, fp in enumerate(files):
        with open(fp, "rb") as f:
            tags = exifread.process_file(f, details=False)
        if not tags:
            continue
        dt_str = str(tags.get("EXIF DateTimeOriginal"))
        subsec_str = str(tags.get("EXIF SubSecTime"))
        try:
            subsec = int(float(subsec_str))
            neg = -1 if subsec < 0 else 1
            subsec = abs(subsec)
            frac = float(f"0.{int(subsec)}") * neg
            millis = frac * 1e3
            base = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            ts = base + timedelta(milliseconds=millis)
            ts = ts - timedelta(seconds=MICA_deltat)
            events.append((fp, ts))
        except Exception:
            continue
        if i % 200 == 0:
            logging.info("Read %d/%d micasense images", i, len(files))
    return events


def _num_key(path_str: str) -> int:
    """Sort key extracting digits from filename stem, fallback to 0 when none."""
    stem = Path(path_str).stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return int(digits) if digits else 0


def load_p1_positions_csv(csv_path: Path) -> Dict[str, Tuple[float, float, float]]:
    """Load P1 positions from Metashape exportReference CSV (nxyz columns)."""
    pos: Dict[str, Tuple[float, float, float]] = {}
    with csv_path.open("r", encoding="utf-8", errors="ignore") as f:  # type: ignore
        for line in f:
            row = line.strip().split(",")
            if len(row) < 4:
                continue
            label = row[0].strip()
            try:
                x = float(row[1]); y = float(row[2]); z = float(row[3])
            except Exception:
                continue
            pos[label] = (x, y, z)
    if not pos:
        raise RuntimeError(f"No positions parsed from {csv_path}")
    return pos


def interpolate_positions(p1_times: List[float], p1_positions: np.ndarray, mica_events: List[Tuple[str, float]]):
    outputs = []
    for path, t in mica_events:
        if t < p1_times[0] or t > p1_times[-1]:
            outputs.append((path, 0.0, 0.0, 0.0, False))
            continue
        idx = np.searchsorted(p1_times, t)
        idx = min(max(idx, 1), len(p1_times) - 1)
        t1 = p1_times[idx - 1]
        t2 = p1_times[idx]
        p1a = p1_positions[idx - 1]
        p1b = p1_positions[idx]
        ratio = 0.0 if t2 == t1 else (t - t1) / (t2 - t1)
        interp = p1a + ratio * (p1b - p1a)
        outputs.append((path, float(interp[0]), float(interp[1]), float(interp[2]), True))
    return outputs


def main():
    parser = argparse.ArgumentParser(description="Interpolate MicaSense positions with MRK jump debug and Metashape camera positions")
    parser.add_argument("--mrk-folder", required=True, type=Path)
    parser.add_argument("--micasense-folder", required=True, type=Path)
    parser.add_argument("--image-suffix", default="_6.tif")
    parser.add_argument("--epsg", default=2056, type=int, help="Used only if Metashape positions are not provided")
    parser.add_argument("--out-csv", required=True, type=Path)
    parser.add_argument("--jump-threshold", type=float, default=2.0)
    parser.add_argument("--no-fix", action="store_true", help="Report jump but do not apply fix")
    parser.add_argument("--psx", type=Path, help="Metashape project to pull estimated RGB camera positions")
    parser.add_argument("--chunk-name", type=str, default="rgb", help="Chunk name for RGB cameras")
    parser.add_argument("--p1-csv", type=Path, help="CSV of P1 camera positions (exportReference nxyz)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    mrk_records = load_mrk_records(args.mrk_folder)
    flat_seq = [(rec[5], rec[0]) for rec in mrk_records]
    qualities = [rec[4] for rec in mrk_records]

    jump_info = _detect_time_jump(flat_seq, args.jump_threshold)
    if jump_info:
        logging.info("Detected MRK negative time jump: idx=%s file=%s delta=%.3fs prev=%s curr=%s", jump_info['index'], jump_info['filename'], jump_info['delta_seconds'], jump_info['prev_ts'], jump_info['curr_ts'])
        if not args.no_fix:
            fixed_seq, fix_info = _apply_jump_fix(flat_seq, jump_info, qualities=qualities)
            if fix_info:
                logging.info("Applied jump fix: offset=%.3fs nominal=%.3fs from_idx=%d", fix_info['offset_seconds'], fix_info['nominal_delta'], fix_info['applied_from_index'])
                # propagate corrected times back into records
                fixed_times = [ts for _, ts in fixed_seq]
                mrk_records = [(fixed_times[i], r[1], r[2], r[3], r[4], r[5]) for i, r in enumerate(mrk_records)]
    else:
        logging.info("No MRK negative time jump detected")

    # Prepare P1 arrays sorted by corrected time
    mrk_records.sort(key=lambda r: r[0])
    p1_times = [dt.timestamp() for dt in [r[0] for r in mrk_records]]

    # Load RGB camera positions: priority p1-csv > psx > MRK geotags
    p1_positions_proj = None

    if args.p1_csv:
        csv_pos = load_p1_positions_csv(args.p1_csv)
        rgb_files = sorted(glob.iglob(str(args.mrk_folder) + "/**/*.JPG", recursive=True))
        rgb_files += sorted(glob.iglob(str(args.mrk_folder) + "/**/*.JPEG", recursive=True))
        rgb_files += sorted(glob.iglob(str(args.mrk_folder) + "/**/*.TIF", recursive=True))
        rgb_files += sorted(glob.iglob(str(args.mrk_folder) + "/**/*.TIFF", recursive=True))
        rgb_files = sorted(set(rgb_files), key=_num_key)

        take = min(len(rgb_files), len(p1_times))
        rgb_files = rgb_files[:take]
        p1_times = p1_times[:take]
        if len(mrk_records) > take:
            mrk_records = mrk_records[:take]

        coords = []
        missing = 0
        for fp in rgb_files:
            lbl_full = Path(fp).name
            lbl_stem = Path(fp).stem
            pos = csv_pos.get(lbl_full) or csv_pos.get(lbl_stem)
            if pos is None:
                missing += 1
                coords.append((np.nan, np.nan, np.nan))
            else:
                coords.append(pos)
        if missing:
            logging.warning("%d RGB labels missing in P1 CSV; filled with NaN", missing)
        p1_positions_proj = np.array(coords, dtype=float)

    elif args.psx:
        if Metashape is None:
            raise RuntimeError("Metashape module not available; install/enable Metashape Python to use --psx")

        doc = Metashape.Document()
        doc.open(str(args.psx))
        chunk = next((c for c in doc.chunks if c.label == args.chunk_name), None)
        if chunk is None:
            raise RuntimeError(f"Chunk '{args.chunk_name}' not found in {args.psx}")

        cam_positions: Dict[str, Tuple[float, float, float]] = {}
        for cam in chunk.cameras:
            if not cam.transform:
                continue
            if not cam.center:
                continue
            center = cam.center  # 3-vector in chunk internal coordinates
            if chunk.transform and chunk.crs:
                pt = chunk.crs.project(chunk.transform.matrix.mulp(center))
                cam_positions[cam.label] = (pt.x, pt.y, pt.z)
            else:
                cam_positions[cam.label] = (center.x, center.y, center.z)

        rgb_files = sorted(glob.iglob(str(args.mrk_folder) + "/**/*.JPG", recursive=True))
        rgb_files += sorted(glob.iglob(str(args.mrk_folder) + "/**/*.JPEG", recursive=True))
        rgb_files += sorted(glob.iglob(str(args.mrk_folder) + "/**/*.TIF", recursive=True))
        rgb_files += sorted(glob.iglob(str(args.mrk_folder) + "/**/*.TIFF", recursive=True))
        rgb_files = sorted(set(rgb_files), key=_num_key)

        take = min(len(rgb_files), len(p1_times))
        if take == 0:
            raise RuntimeError("No RGB files found to align with MRK records")
        rgb_files = rgb_files[:take]
        p1_times = p1_times[:take]
        if len(mrk_records) > take:
            mrk_records = mrk_records[:take]

        coords = []
        missing_labels = 0
        for fp in rgb_files:
            lbl = Path(fp).name
            pos = cam_positions.get(lbl)
            if pos is None:
                missing_labels += 1
                coords.append((np.nan, np.nan, np.nan))
            else:
                coords.append(pos)
        if missing_labels:
            logging.warning("%d RGB labels not found in Metashape chunk; filled with NaN", missing_labels)
        p1_positions_proj = np.array(coords, dtype=float)

    else:
        latlonalt = np.array([[r[1], r[2], r[3]] for r in mrk_records], dtype=float)
        transformer = _make_transformer(args.epsg)
        p1_positions_proj = []
        for lat, lon, ellh in latlonalt:
            api_res = transform_coordinates(lon, lat, ellh)
            if api_res:
                p1_positions_proj.append(api_res)
            else:
                e, n = transformer.transform(lat, lon)
                p1_positions_proj.append((e, n, ellh))
        p1_positions_proj = np.array(p1_positions_proj, dtype=float)

    mica_events = read_micasense_events(args.micasense_folder, args.image_suffix)
    mica_events_sorted = sorted([(p, ts.timestamp()) for p, ts in mica_events], key=lambda x: x[1])

    outputs = interpolate_positions(p1_times, p1_positions_proj, mica_events_sorted)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8", newline="") as f:
        f.write("label,easting,northing,ellip_height,inside_p1\n")
        for path, e, n, h, inside in outputs:
            f.write(f"{path},{e:.6f},{n:.6f},{h:.4f},{int(inside)}\n")

    logging.info("Wrote %d interpolated records to %s", len(outputs), args.out_csv)


if __name__ == "__main__":
    main()
