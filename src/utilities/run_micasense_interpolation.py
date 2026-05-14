"""
Standalone MicaSense interpolation runner.

Runs the full pipeline (P1 MRK check → EXIF spot-check → WGS84→LV95/LHN95
transformation → MicaSense position interpolation) from raw image folders,
with NO dependency on Metashape.

Usage
-----
    python run_micasense_interpolation.py \
        --p1        <path/to/P1/images>      \
        --micasense <path/to/MicaSense>      \
        [--crs          2056]                \
        [--master-suffix _6.tif]             \
        [--out-dir      <output/directory>]  \
        [--htrans       <ETRS.tif>]          \
        [--htrans-fallback <ExtendedGeoid.tif>] \
        [--p1-ref-csv   <p1_pos_CH1903.csv>]

The output CSV (``interpolated_micasense_pos.csv``) is written to ``--out-dir``,
which defaults to a ``references/`` sub-folder inside the MicaSense folder.

Examples
--------
    # Minimal – uses Swisstopo API for WGS84 → LV95 transformation:
    python run_micasense_interpolation.py \
        --p1 "M:/data/P1/site/20260506" \
        --micasense "M:/data/MicaSense/site/20260506"

    # With htrans grids and pre-transformed P1 CSV:
    python run_micasense_interpolation.py \
        --p1        "M:/data/P1/site/20260506" \
        --micasense "M:/data/MicaSense/site/20260506" \
        --htrans    "M:/geoid/ETRS.tif" \
        --htrans-fallback "M:/geoid/ExtendedGeoid.tif" \
        --p1-ref-csv "M:/processing/references/p1_pos_CH1903.csv"
"""

import argparse
import glob
import logging
import os
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Make src/core importable when run directly (no install required)
# ---------------------------------------------------------------------------
_script_dir = Path(__file__).resolve().parent
_core_dir   = _script_dir.parent / "core"
if str(_core_dir) not in sys.path:
    sys.path.insert(0, str(_core_dir))

from upd_micasense_pos_filename import ret_micasense_pos  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_master_band_files(micasense_folder: str, suffix: str) -> list[str]:
    """Return sorted list of MicaSense master-band TIF paths."""
    pattern = os.path.join(micasense_folder, "**", f"*{suffix}")
    files = sorted(glob.glob(pattern, recursive=True))
    return files


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run MicaSense position interpolation from raw image folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--p1", required=True,
                   help="Path to P1 image folder (must contain .MRK files and .JPG images).")
    p.add_argument("--micasense", required=True,
                   help="Path to MicaSense image folder.")
    p.add_argument("--crs", default="2056",
                   help="EPSG code of the projected output CRS (default: 2056 = CH1903+/LV95).")
    p.add_argument("--master-suffix", default="_6.tif",
                   help="File suffix that identifies master-band images (default: _6.tif).")
    p.add_argument("--out-dir",
                   help="Directory for the output CSV. "
                        "Defaults to references/ inside the MicaSense folder.")
    p.add_argument("--htrans",
                   help="Path to primary Swisstopo CHGeo2004 htrans GeoTIFF "
                        "(e.g. ETRS.tif). Converts LN02 → LHN95.")
    p.add_argument("--htrans-fallback",
                   help="Path to fallback geoid GeoTIFF (e.g. ExtendedGeoid.tif).")
    p.add_argument("--p1-ref-csv",
                   help="Path to p1_pos_CH1903.csv produced by proc_rgb. "
                        "When provided (and MRK is faulty), positions are loaded "
                        "directly in LV95/LHN95, bypassing the Swisstopo API.")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # --- Validate inputs ---------------------------------------------------
    p1_folder = Path(args.p1).resolve()
    if not p1_folder.is_dir():
        sys.exit(f"ERROR: P1 folder not found: {p1_folder}")

    mica_folder = Path(args.micasense).resolve()
    if not mica_folder.is_dir():
        sys.exit(f"ERROR: MicaSense folder not found: {mica_folder}")

    # --- Output directory --------------------------------------------------
    if args.out_dir:
        out_dir = Path(args.out_dir).resolve()
    else:
        out_dir = mica_folder / "references"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_dir / "interpolated_micasense_pos.csv"

    # --- Logging -----------------------------------------------------------
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(out_dir / "run_micasense_interpolation.log"),
        ],
    )
    logging.info("=== run_micasense_interpolation.py ===")
    logging.info("P1 folder      : %s", p1_folder)
    logging.info("MicaSense folder: %s", mica_folder)
    logging.info("Output CRS     : EPSG:%s", args.crs)
    logging.info("Master suffix  : %s", args.master_suffix)
    logging.info("Output CSV     : %s", out_csv)
    if args.htrans:
        logging.info("htrans         : %s", args.htrans)
    if args.htrans_fallback:
        logging.info("htrans fallback: %s", args.htrans_fallback)
    if args.p1_ref_csv:
        logging.info("p1_ref_csv     : %s", args.p1_ref_csv)

    # --- Collect MicaSense master-band paths -------------------------------
    print(f"\nScanning for master-band files (*{args.master_suffix}) in: {mica_folder}")
    master_paths = _find_master_band_files(str(mica_folder), args.master_suffix)
    if not master_paths:
        sys.exit(
            f"ERROR: No files matching '*{args.master_suffix}' found under {mica_folder}."
        )
    print(f"Found {len(master_paths)} master-band images.")
    logging.info("Master-band images found: %d", len(master_paths))

    # --- Run interpolation -------------------------------------------------
    P1_shift_vec = np.array([0.0, 0.0, 0.0])

    ret_micasense_pos(
        absolute_micasense_file_list=master_paths,
        mrk_folder=str(p1_folder),
        micasense_folder=str(mica_folder),
        image_suffix=args.master_suffix.lstrip("_").replace(".tif", ""),
        epsg_crs=args.crs,
        out_file=str(out_csv),
        P1_shift_vec=P1_shift_vec,
        htrans_path=args.htrans if args.htrans else None,
        htrans_fallback=args.htrans_fallback if args.htrans_fallback else None,
        p1_ref_csv=args.p1_ref_csv if args.p1_ref_csv else None,
    )

    print(f"\nDone. Output written to: {out_csv}")
    logging.info("Finished. Output: %s", out_csv)


if __name__ == "__main__":
    main()
