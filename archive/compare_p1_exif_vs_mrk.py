"""
Compare DJI P1 EXIF capture times against MRK-derived times to spot offsets/drift.

Usage (example):
  python compare_p1_exif_vs_mrk.py \
    --rgb-root "M:\working_package_2\2024_dronecampaign\01_data\P1\Marteloskop\20251002\DJI_202510021240_003_marteloskopp1mica60m"

The script walks the RGB root to find:
- MRK files (recursive) for timestamps (GPS time -> UTC using GPSUTC_deltat).
- P1 images (recursive) with extensions .JPG/.JPEG/.DNG/.TIF and reads EXIF DateTimeOriginal/SubSecTime.

It pairs images to MRK lines by sorted order (capture sequence). If counts differ,
it trims to the minimum and reports the mismatch. Summary stats printed and a few
largest differences listed.
"""

import argparse
import glob
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional

import exifread

# Constants consistent with existing scripts
GPSUTC_deltat = 0  # seconds; MRK GPS->UTC offset (set to 0 in repo)


def get_mrk_records(mrk_folder: Path) -> List[Tuple[float, str, int, str]]:
    """Return sorted list of (timestamp, file, line_no, quality)."""
    mrk_files = sorted(mrk_folder.rglob("*.MRK"))
    if not mrk_files:
        raise FileNotFoundError(f"No .MRK files found under: {mrk_folder}")

    records: List[Tuple[float, str, int, str]] = []
    for m_path in mrk_files:
        with m_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                parts = line.split()
                if len(parts) < 3:
                    continue
                try:
                    secs = float(parts[1])
                    week = int(parts[2].strip("[]"))
                except ValueError:
                    continue

                epoch_secs = secs + (week * 7 * 24 * 60 * 60)
                ts = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
                ts -= timedelta(seconds=GPSUTC_deltat)

                quality = parts[9] if len(parts) > 9 else ""
                records.append((ts.timestamp(), str(m_path), line_no, quality))

    if not records:
        raise RuntimeError("MRK files were found but no timestamps could be parsed.")

    records.sort(key=lambda t: t[0])
    return records


def _parse_subsec(raw) -> Tuple[float, str]:
    """Parse EXIF sub-second tag; return (fractional_seconds, raw_str)."""
    if raw is None:
        return 0.0, ""
    try:
        s = str(raw).strip()
        if not s:
            return 0.0, ""
        sign = -1.0 if s.startswith("-") else 1.0
        digits = s.lstrip("+-")
        frac = float(f"0.{digits}")
        return sign * frac, s
    except Exception:
        return 0.0, str(raw)


def _parse_exif_timestamp(tags) -> Tuple[float, str, str]:
    dt_raw = tags.get("EXIF DateTimeOriginal")
    if not dt_raw:
        raise ValueError("Missing EXIF DateTimeOriginal")
    dt = datetime.strptime(str(dt_raw), "%Y:%m:%d %H:%M:%S")

    # Prefer the most specific sub-second tag available
    sub_raw = (
        tags.get("EXIF SubSecTimeOriginal")
        or tags.get("EXIF SubSecTimeDigitized")
        or tags.get("EXIF SubSecTime")
    )
    subsec, subsec_raw = _parse_subsec(sub_raw)

    dt_full = dt + timedelta(seconds=subsec)
    # P1 EXIF is expected to be UTC already
    return dt_full.timestamp(), subsec_raw, str(dt_raw)


def get_image_timestamps(img_root: Path) -> List[Tuple[str, float, str, str]]:
    patterns = ["**/*.JPG", "**/*.JPEG", "**/*.DNG", "**/*.TIF", "**/*.TIFF"]
    files: List[Path] = []
    for pat in patterns:
        files.extend(img_root.glob(pat))

    if not files:
        raise FileNotFoundError(f"No RGB images found under: {img_root}")

    records: List[Tuple[str, float, str, str]] = []
    for p in files:
        try:
            with p.open("rb") as f:
                tags = exifread.process_file(f, details=False)
            ts, sub_raw, dt_raw = _parse_exif_timestamp(tags)
            records.append((str(p), ts, sub_raw, dt_raw))
        except Exception:
            continue

    if not records:
        raise RuntimeError("Images were found but no EXIF timestamps could be parsed.")

    records.sort(key=lambda t: t[1])
    return records


def percentile(vals: List[float], p: float) -> float:
    if not vals:
        return float("nan")
    vals_sorted = sorted(vals)
    idx = int(round((p / 100.0) * (len(vals_sorted) - 1)))
    idx = max(0, min(idx, len(vals_sorted) - 1))
    return vals_sorted[idx]


def _fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def compare_sequences(
    mrk_recs: List[Tuple[float, str, int, str]],
    img_ts: List[Tuple[str, float, str, str]],
    csv_out: Optional[Path] = None,
    preview_rows: int = 15,
) -> None:
    n = min(len(mrk_recs), len(img_ts))
    if len(mrk_recs) != len(img_ts):
        print(f"Count mismatch: MRK lines={len(mrk_recs)}, images={len(img_ts)}; comparing first {n} pairs")

    deltas = []
    table_rows = []
    for i in range(n):
        img_path, img_time, sub_raw, dt_raw = img_ts[i]
        mrk_time, mrk_file, line_no, quality = mrk_recs[i]
        delta = img_time - mrk_time
        deltas.append(delta)
        table_rows.append(
            (
                img_path,
                _fmt(img_time),
                img_time,
                _fmt(mrk_time),
                mrk_time,
                f"{delta:+.6f}",
                mrk_file,
                line_no,
                quality,
                sub_raw,
                dt_raw,
            )
        )

    abs_d = [abs(x) for x in deltas]

    print("\n=== MRK vs EXIF time deltas (image - mrk) ===")
    print(f"Pairs compared: {n}")
    print(f"Median: {percentile(deltas, 50):+.3f} s")
    print(f"P90:    {percentile(deltas, 90):+.3f} s")
    print(f"Max:    {max(deltas):+.3f} s")
    print(f"Min:    {min(deltas):+.3f} s")
    print(f"|delta| median: {percentile(abs_d, 50):.3f} s")

    print(f"\nSample rows (first {min(preview_rows, n)}):")
    for row in table_rows[:preview_rows]:
        (
            img_path,
            exif_t,
            _exif_epoch,
            mrk_t,
            _mrk_epoch,
            delta_s,
            mrk_file,
            line_no,
            quality,
            sub_raw,
            dt_raw,
        ) = row
        print(
            f"{Path(img_path).name} | exif {exif_t} (sub:{sub_raw}) | mrk {mrk_t} | Δ {delta_s} s | q={quality} | {mrk_file}#{line_no}"
        )

    if csv_out:
        with csv_out.open("w", encoding="utf-8", newline="") as f:
            f.write(
                "image_path,exif_time_iso,exif_time_epoch,mrk_time_iso,mrk_time_epoch,delta_seconds,mrk_file,line,quality,subsec_raw,datetime_original_raw\n"
            )
            for row in table_rows:
                (
                    image_path,
                    exif_iso,
                    exif_epoch,
                    mrk_iso,
                    mrk_epoch,
                    delta_s,
                    mrk_file,
                    line_no,
                    quality,
                    sub_raw,
                    dt_raw,
                ) = row
                f.write(
                    ",".join([
                        image_path,
                        exif_iso,
                        f"{exif_epoch:.6f}",
                        mrk_iso,
                        f"{mrk_epoch:.6f}",
                        delta_s,
                        mrk_file,
                        str(line_no),
                        str(quality),
                        sub_raw,
                        dt_raw,
                    ])
                    + "\n"
                )
        print(f"\nCSV written to: {csv_out}")


def main():
    ap = argparse.ArgumentParser(description="Compare P1 EXIF timestamps to MRK timestamps")
    ap.add_argument("--rgb-root", required=True, type=Path, help="Root folder containing MRK files and RGB images")
    ap.add_argument("--csv-out", type=Path, help="Optional CSV output path for detailed table")
    ap.add_argument("--preview", type=int, default=15, help="Number of sample rows to print")
    ap.add_argument("--dump-mrk", type=Path, help="Optional CSV path to dump MRK UTC timestamps with line numbers and quality")
    args = ap.parse_args()

    mrk_recs = get_mrk_records(args.rgb_root)
    img_ts = get_image_timestamps(args.rgb_root)

    print(f"Loaded {len(mrk_recs)} MRK timestamps")
    print(f"Loaded {len(img_ts)} images with EXIF time")

    if args.dump_mrk:
        with args.dump_mrk.open("w", encoding="utf-8", newline="") as f:
            f.write("mrk_time_iso,mrk_time_epoch,mrk_file,line,quality\n")
            for ts_epoch, mfile, line_no, quality in mrk_recs:
                iso = _fmt(ts_epoch)
                f.write(
                    ",".join([
                        iso,
                        f"{ts_epoch:.6f}",
                        mfile,
                        str(line_no),
                        str(quality),
                    ]) + "\n"
                )
        print(f"MRK dump written to: {args.dump_mrk}")

    compare_sequences(mrk_recs, img_ts, csv_out=args.csv_out, preview_rows=args.preview)


if __name__ == "__main__":
    main()