import csv
import math
import os
import argparse
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from upd_micasense_pos_filename import ret_micasense_pos
from upd_micasense_pos_from_chunk import run_interpolation_from_chunk


def find_master_band_images(root: Path, suffix: str = "_6.tif") -> list[str]:
    suffix_lower = suffix.lower()
    results: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(suffix_lower):
                results.append(str(Path(dirpath) / name))
    # deterministic ordering
    results.sort(key=lambda p: p.lower())
    return results


def read_positions_csv(path: Path) -> dict[str, tuple[float, float, float]]:
    # file format: Label, Easting, Northing, Ellip Height
    out: dict[str, tuple[float, float, float]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("Label") or "").strip()
            if not label:
                continue
            try:
                e = float(row[" Easting"].strip()) if " Easting" in row else float(row["Easting"].strip())
                n = float(row[" Northing"].strip()) if " Northing" in row else float(row["Northing"].strip())
                h_key = " Ellip Height" if " Ellip Height" in row else "Ellip Height"
                h = float(row[h_key].strip())
            except Exception:
                # tolerate malformed rows
                continue
            out[label] = (e, n, h)
    return out


def basename_key(path_str: str) -> str:
    # Labels are typically absolute image paths
    return Path(path_str).name.lower()


def compare(old_csv: Path, new_csv: Path) -> None:
    old = read_positions_csv(old_csv)
    new = read_positions_csv(new_csv)

    # Match by basename first (more robust if drive letters/paths differ)
    old_by_base: dict[str, tuple[str, tuple[float, float, float]]] = {}
    for k, v in old.items():
        old_by_base[basename_key(k)] = (k, v)

    matched = 0
    missing_in_new = 0
    diffs = []  # (de, dn, dh, dist2d, base, old_label, new_label)

    for new_label, new_pos in new.items():
        base = basename_key(new_label)
        if base not in old_by_base:
            missing_in_new += 1
            continue
        old_label, old_pos = old_by_base[base]
        de = new_pos[0] - old_pos[0]
        dn = new_pos[1] - old_pos[1]
        dh = new_pos[2] - old_pos[2]
        dist2d = math.hypot(de, dn)
        diffs.append((de, dn, dh, dist2d, base, old_label, new_label))
        matched += 1

    # Summary stats
    def pct(vals, p):
        if not vals:
            return float("nan")
        vals_sorted = sorted(vals)
        idx = int(round((p / 100.0) * (len(vals_sorted) - 1)))
        return vals_sorted[max(0, min(idx, len(vals_sorted) - 1))]

    dist2d_vals = [d[3] for d in diffs]
    abs_dh_vals = [abs(d[2]) for d in diffs]

    print("=== Interpolation comparison ===")
    print(f"Old CSV: {old_csv}")
    print(f"New CSV: {new_csv}")
    print(f"Old rows: {len(old)}")
    print(f"New rows: {len(new)}")
    print(f"Matched by basename: {matched}")
    print(f"New labels missing in old: {missing_in_new}")

    if diffs:
        print("2D delta (m) stats:")
        print(f"  median: {pct(dist2d_vals, 50):.3f}")
        print(f"  p90:    {pct(dist2d_vals, 90):.3f}")
        print(f"  p99:    {pct(dist2d_vals, 99):.3f}")
        print(f"  max:    {max(dist2d_vals):.3f}")

        print("|Δh| (m) stats:")
        print(f"  median: {pct(abs_dh_vals, 50):.3f}")
        print(f"  p90:    {pct(abs_dh_vals, 90):.3f}")
        print(f"  p99:    {pct(abs_dh_vals, 99):.3f}")
        print(f"  max:    {max(abs_dh_vals):.3f}")

        # Show top 15 largest horizontal changes
        diffs.sort(key=lambda t: t[3], reverse=True)
        print("\nTop 15 largest 2D deltas (m):")
        for de, dn, dh, dist2d, base, old_label, new_label in diffs[:15]:
            print(f"  {dist2d:8.3f} m  (ΔE={de:+.3f}, ΔN={dn:+.3f}, Δh={dh:+.3f})  {base}")

        # Count how many changes are essentially identical vs changed
        unchanged = sum(1 for d in dist2d_vals if d < 0.01)  # < 1 cm
        changed_10cm = sum(1 for d in dist2d_vals if d >= 0.10)
        changed_1m = sum(1 for d in dist2d_vals if d >= 1.0)
        print("\nChange counts:")
        print(f"  < 1 cm: {unchanged}")
        print(f"  >= 10 cm: {changed_10cm}")
        print(f"  >= 1 m: {changed_1m}")


def _find_campaign_root(path: Path) -> Optional[Path]:
    # Locate the folder named "2024_dronecampaign" (convention in this repo)
    parts = [p.lower() for p in path.parts]
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "2024_dronecampaign":
            return Path(*path.parts[: i + 1])
    return None


def _infer_inputs_from_project(project_psx: Path) -> Tuple[Path, Path, Path, Path, Path]:
    # Expected project path shape:
    # ...\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\<site>\<date>\<project>.psx
    project_dir = project_psx.parent
    date = project_dir.name
    site = project_dir.parent.name

    campaign_root = _find_campaign_root(project_psx)
    if campaign_root is None:
        raise ValueError(
            f"Could not infer campaign root (2024_dronecampaign) from: {project_psx}"
        )

    rgb_root = campaign_root / "01_data" / "P1" / site / date
    mica_root = campaign_root / "01_data" / "Micasense" / site / date
    project_ref_dir = project_dir / "references"

    old_csv = project_ref_dir / "interpolated_micasense_pos_updated.csv"
    new_csv = project_ref_dir / "interpolated_micasense_pos_updated_FIXED.csv"
    return rgb_root, mica_root, project_ref_dir, old_csv, new_csv


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run fixed MicaSense interpolation and compare against an existing CSV. "
            "If --project-psx is provided, inputs are inferred from the folder structure."
        )
    )
    p.add_argument(
        "--project-psx",
        type=Path,
        help=(
            "Path to the Metashape .psx project. Used to infer site/date and default roots."
        ),
    )
    p.add_argument("--rgb-root", type=Path, help="Override RGB/P1 root folder")
    p.add_argument("--mica-root", type=Path, help="Override MicaSense root folder")
    p.add_argument(
        "--references-dir",
        type=Path,
        help="Override references output folder (default: <project_dir>/references)",
    )
    p.add_argument(
        "--old-csv",
        type=Path,
        help="Override old/reference CSV to compare against",
    )
    p.add_argument(
        "--new-csv",
        type=Path,
        help="Override output CSV path for the fixed interpolation",
    )
    return p.parse_args()


def main():
    args = _parse_args()

    if args.project_psx:
        project_psx = args.project_psx
        if not project_psx.exists():
            raise FileNotFoundError(f"Project .psx not found: {project_psx}")

        rgb_root, mica_root, project_ref_dir, old_csv, new_csv = _infer_inputs_from_project(project_psx)

        if args.rgb_root:
            rgb_root = args.rgb_root
        if args.mica_root:
            mica_root = args.mica_root
        if args.references_dir:
            project_ref_dir = args.references_dir
            old_csv = project_ref_dir / "interpolated_micasense_pos_updated.csv"
            new_csv = project_ref_dir / "interpolated_micasense_pos_updated_FIXED.csv"
        if args.old_csv:
            old_csv = args.old_csv
        if args.new_csv:
            new_csv = args.new_csv
    else:
        # Backward-compatible default (previous hard-coded run)
        rgb_root = Path(r"M:\working_package_2\2024_dronecampaign\01_data\P1\Pfynwald\20251104")
        mica_root = Path(r"M:\working_package_2\2024_dronecampaign\01_data\Micasense\Pfynwald\20251104")
        project_ref_dir = Path(
            r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\Pfynwald\20251104\references"
        )
        old_csv = project_ref_dir / "interpolated_micasense_pos_updated.csv"
        new_csv = project_ref_dir / "interpolated_micasense_pos_updated_FIXED.csv"

    compare_enabled = True
    if not old_csv.exists():
        compare_enabled = False
        print(f"Baseline CSV not found; will skip comparison: {old_csv}")

    if not rgb_root.exists():
        raise FileNotFoundError(f"RGB/P1 root not found: {rgb_root}")
    if not mica_root.exists():
        raise FileNotFoundError(f"MicaSense root not found: {mica_root}")

    project_ref_dir.mkdir(parents=True, exist_ok=True)

    master_band_images = find_master_band_images(mica_root, suffix="_6.tif")
    if not master_band_images:
        raise FileNotFoundError(f"No master band images (*_6.tif) found under: {mica_root}")

    print(f"Found {len(master_band_images)} MicaSense master band images")
    print("Running fixed interpolation (using aligned RGB chunk)...")

    # Use the new chunk-based interpolation
    # We need the project path. In the args.project_psx case, we have it.
    # In the fallback case, we need to construct it or fail if not present.
    
    project_path_for_interp = None
    if args.project_psx:
        project_path_for_interp = args.project_psx
    else:
        # Construct from hardcoded default if possible, or raise error. 
        # The hardcoded default was: ...\Upscale_Metashapeprojects\Pfynwald\20251104\metashape_project_pfynwald_20251104.psx (guessing name)
        # Let's try to find it in the folder if not provided
        # Or simpler: require --project-psx for the new method since it relies on the doc.
        
        # Try to find psx in the parent of project_ref_dir
        candidate_psx = list(project_ref_dir.parent.glob("*.psx"))
        if candidate_psx:
            project_path_for_interp = candidate_psx[0]
        else:
             print("Error: No .psx project found for chunk-based interpolation. Please provide --project-psx.")
             return

    run_interpolation_from_chunk(
        project_path_for_interp,
        mica_root,
        new_csv,
        rgb_folder=rgb_root
    )

    print("Fixed interpolation written:", new_csv)
    if compare_enabled:
        compare(old_csv, new_csv)


if __name__ == "__main__":
    main()
