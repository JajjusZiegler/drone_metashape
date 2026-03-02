"""
Export EXIF (exiftool) time/GPS tags and MRK time/GPS data for all images in a folder.

Usage example:
  python export_exif_mrk_times.py \
    --folder "M:\\working_package_2\\2024_dronecampaign\\01_data\\P1\\marteloskop\\20251002\\DJI_202510021240_003_marteloskopp1mica60m" \
    --csv-out exif_mrk_times.csv

Outputs CSV columns:
  image_path,exif_utc_at_exposure,exif_datetimeoriginal,exif_gps_lat,exif_gps_lon,exif_gps_alt,
  mrk_time_iso,mrk_time_epoch,mrk_lat,mrk_lon,mrk_alt,mrk_quality,mrk_file,mrk_line

Rows are paired by sorted order (images sorted by name/time, MRK entries sorted by time); if counts differ, the shorter length is used.
"""

import argparse
import re
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime, timedelta

import exifread
from exiftool import ExifToolHelper


GPSUTC_deltat = 0  # MRK GPS->UTC offset


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


def get_mrk_records(folder: Path) -> List[Tuple[float, float, float, float, str, int, str]]:
    """Return MRK list in file/line order: (utc_ts, lat, lon, alt, mrk_file, line_no, quality)."""
    mrk_files = sorted(folder.rglob("*.MRK"))
    records = []
    for m_path in mrk_files:
        with m_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                parts = line.split()
                if len(parts) < 9:
                    continue
                try:
                    secs = float(parts[1])
                    week = int(parts[2].strip("[]"))
                    lat = float(parts[6].split(",")[0])
                    lon = float(parts[7].split(",")[0])
                    alt = float(parts[8].split(",")[0])
                except Exception:
                    continue
                epoch_secs = secs + (week * 7 * 24 * 60 * 60)
                ts = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
                ts -= timedelta(seconds=GPSUTC_deltat)
                quality = parts[9] if len(parts) > 9 else ""
                records.append((ts.timestamp(), lat, lon, alt, str(m_path), line_no, quality))
    # Keep original order (file order + line order) to align with image sequence
    return records


def _seq_from_name(path: Path) -> int:
    m = re.search(r"(\d+)(?=\.[^.]+$)", path.name)
    return int(m.group(1)) if m else 0


def get_images(folder: Path) -> List[Path]:
    patterns = ["**/*.JPG", "**/*.JPEG", "**/*.TIF", "**/*.TIFF", "**/*.DNG"]
    files: List[Path] = []
    for pat in patterns:
        files.extend(folder.glob(pat))
    # Sort by numeric suffix to match MRK line order (001 -> line 1, etc.)
    files.sort(key=_seq_from_name)
    return files


def read_exiftool_batch(images: List[Path], exe_override: Optional[str]) -> List[dict]:
    exe = _resolve_exiftool(exe_override)
    kwargs = {"executable": exe} if exe else {}
    with ExifToolHelper(**kwargs) as et:
        data_list = et.get_metadata([str(p) for p in images])
    return data_list or []


def main():
    ap = argparse.ArgumentParser(description="Export EXIF (exiftool) vs MRK times/GPS to CSV")
    ap.add_argument("--folder", required=True, type=Path, help="Folder containing images and MRK")
    ap.add_argument("--csv-out", required=True, type=Path, help="Output CSV path")
    ap.add_argument("--exiftool", type=str, help="Path to exiftool executable (optional)")
    args = ap.parse_args()

    images = get_images(args.folder)
    if not images:
        raise FileNotFoundError(f"No images found under: {args.folder}")

    mrk_recs = get_mrk_records(args.folder)
    if not mrk_recs:
        raise FileNotFoundError(f"No MRK entries found under: {args.folder}")

    exif_list = read_exiftool_batch(images, args.exiftool)

    n = min(len(images), len(mrk_recs), len(exif_list))
    if n == 0:
        raise RuntimeError("No paired data to export")
    if n < len(images) or n < len(mrk_recs):
        print(f"Warning: truncating to {n} pairs (images={len(images)}, mrk={len(mrk_recs)}, exif={len(exif_list)})")

    with args.csv_out.open("w", encoding="utf-8", newline="") as f:
        f.write(
            "image_path,exif_utc_at_exposure,exif_datetimeoriginal,exif_gps_lat,exif_gps_lon,exif_gps_alt,"
            "mrk_time_iso,mrk_time_epoch,mrk_lat,mrk_lon,mrk_alt,mrk_quality,mrk_file,mrk_line\n"
        )

        for i in range(n):
            img_path = str(images[i])
            exif = exif_list[i] if i < len(exif_list) else {}

            exif_utc = exif.get("XMP:UTCAtExposure") or ""
            exif_dto = exif.get("EXIF:DateTimeOriginal") or ""
            exif_gps_lat = exif.get("EXIF:GPSLatitude") or exif.get("Composite:GPSLatitude") or ""
            exif_gps_lon = exif.get("EXIF:GPSLongitude") or exif.get("Composite:GPSLongitude") or ""
            exif_gps_alt = exif.get("EXIF:GPSAltitude") or ""

            mrk_ts, mrk_lat, mrk_lon, mrk_alt, mrk_file, mrk_line, mrk_q = mrk_recs[i]
            mrk_iso = datetime.fromtimestamp(mrk_ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            f.write(
                ",".join([
                    img_path,
                    str(exif_utc),
                    str(exif_dto),
                    str(exif_gps_lat),
                    str(exif_gps_lon),
                    str(exif_gps_alt),
                    mrk_iso,
                    f"{mrk_ts:.6f}",
                    f"{mrk_lat}",
                    f"{mrk_lon}",
                    f"{mrk_alt}",
                    str(mrk_q),
                    mrk_file,
                    str(mrk_line),
                ]) + "\n"
            )

    print(f"Wrote {n} paired rows to {args.csv_out}")


if __name__ == "__main__":
    main()