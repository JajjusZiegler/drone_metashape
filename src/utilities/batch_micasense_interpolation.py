"""
Batch MicaSense interpolation runner.

Reads a project-list CSV (same format used by UpscaleProjectCreation), deduplicates
rows by (rgb, multispec) pair, checks folder existence, then runs the full
interpolation pipeline for every valid entry.

Usage
-----
    python batch_micasense_interpolation.py <project_list.csv> \
        [--out-dir  C:/Temp/interp_results]                    \
        [--htrans   <ETRS.tif>]                                \
        [--htrans-fallback <ExtendedGeoid.tif>]                \
        [--master-suffix _6.tif]

Output layout
-------------
    <out-dir>/
        <date>_<site>/
            interpolated_micasense_pos.csv
            run_micasense_interpolation.log
        batch_summary.csv
"""

import argparse
import csv
import glob
import logging
import os
import sys
from pathlib import Path

import numpy as np

# ── Make src/core importable ────────────────────────────────────────────────
_script_dir = Path(__file__).resolve().parent
_core_dir   = _script_dir.parent / "core"
if str(_core_dir) not in sys.path:
    sys.path.insert(0, str(_core_dir))

from upd_micasense_pos_filename import ret_micasense_pos  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_master_band_files(folder: str, suffix: str) -> list:
    pattern = os.path.join(folder, "**", f"*{suffix}")
    return sorted(glob.glob(pattern, recursive=True))


def _find_p1_ref_csv(project_path: str):
    """Look for p1_pos_CH1903.csv in the standard references location."""
    if not project_path:
        return None
    ref = Path(project_path).parent / "references" / "p1_pos_CH1903.csv"
    return str(ref) if ref.exists() else None


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-run MicaSense interpolation over a project-list CSV."
    )
    parser.add_argument("csv", help="Path to the project-list CSV.")
    parser.add_argument("--out-dir", default=r"C:\Temp\micasense_interp_results",
                        help="Root output directory (default: C:\\Temp\\micasense_interp_results).")
    parser.add_argument("--htrans",
                        help="Primary Swisstopo CHGeo2004 htrans GeoTIFF (ETRS.tif).")
    parser.add_argument("--htrans-fallback",
                        help="Fallback geoid GeoTIFF (ExtendedGeoid.tif).")
    parser.add_argument("--master-suffix", default="_6.tif",
                        help="Master-band TIF suffix (default: _6.tif).")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        sys.exit(f"ERROR: CSV not found: {csv_path}")

    root_out = Path(args.out_dir)
    root_out.mkdir(parents=True, exist_ok=True)

    # ── Logging (batch-level) ────────────────────────────────────────────────
    batch_log = root_out / "batch_run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(batch_log),
        ],
    )
    logging.info("=== batch_micasense_interpolation.py ===")
    logging.info("Project list : %s", csv_path)
    logging.info("Output root  : %s", root_out)
    logging.info("htrans       : %s", args.htrans or "(none)")
    logging.info("htrans-fallback: %s", args.htrans_fallback or "(none)")

    # ── Read and deduplicate CSV rows ────────────────────────────────────────
    with open(csv_path, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    seen = set()
    unique_rows = []
    for row in rows:
        key = (row.get('rgb', '').strip(), row.get('multispec', '').strip())
        if key not in seen and key[0] and key[1]:
            seen.add(key)
            unique_rows.append(row)

    logging.info("Total rows: %d  |  Unique (rgb, multispec) pairs: %d",
                 len(rows), len(unique_rows))
    print(f"\nTotal rows in CSV       : {len(rows)}")
    print(f"Unique project entries  : {len(unique_rows)}\n")

    # ── Per-project summary tracking ─────────────────────────────────────────
    summary_rows = []  # list of dicts for batch_summary.csv

    for i, row in enumerate(unique_rows, start=1):
        date      = row.get('date', '').strip()
        site      = row.get('site', '').strip()
        p1_folder = row.get('rgb', '').strip()
        ms_folder = row.get('multispec', '').strip()
        proj_path = row.get('project_path', '').strip()

        label = f"{date}_{site}"
        sep   = "─" * 60
        print(f"\n{sep}")
        print(f"[{i}/{len(unique_rows)}]  {label}")
        print(sep)

        status = "ok"
        out_csv = ""

        # ── Validate folders ─────────────────────────────────────────────────
        if not Path(p1_folder).is_dir():
            msg = f"P1 folder not found: {p1_folder}"
            logging.warning("[SKIP] %s  —  %s", label, msg)
            print(f"  SKIP: {msg}")
            status = f"skip: P1 folder missing"
            summary_rows.append({"label": label, "status": status,
                                  "p1": p1_folder, "micasense": ms_folder,
                                  "out_csv": ""})
            continue

        if not Path(ms_folder).is_dir():
            msg = f"MicaSense folder not found: {ms_folder}"
            logging.warning("[SKIP] %s  —  %s", label, msg)
            print(f"  SKIP: {msg}")
            status = "skip: MicaSense folder missing"
            summary_rows.append({"label": label, "status": status,
                                  "p1": p1_folder, "micasense": ms_folder,
                                  "out_csv": ""})
            continue

        # ── Master-band files ────────────────────────────────────────────────
        master_paths = _find_master_band_files(ms_folder, args.master_suffix)
        if not master_paths:
            msg = f"No *{args.master_suffix} files in {ms_folder}"
            logging.warning("[SKIP] %s  —  %s", label, msg)
            print(f"  SKIP: {msg}")
            status = f"skip: no master-band files"
            summary_rows.append({"label": label, "status": status,
                                  "p1": p1_folder, "micasense": ms_folder,
                                  "out_csv": ""})
            continue
        print(f"  Master-band images: {len(master_paths)}")

        # ── p1_ref_csv (optional) ────────────────────────────────────────────
        p1_ref_csv = _find_p1_ref_csv(proj_path)
        if p1_ref_csv:
            print(f"  p1_ref_csv found  : {p1_ref_csv}")
            logging.info("[%s] p1_ref_csv: %s", label, p1_ref_csv)
        else:
            print(f"  p1_ref_csv        : (none — will use Swisstopo API)")
            logging.info("[%s] No p1_ref_csv; Swisstopo API will be used.", label)

        # ── Per-project output directory ─────────────────────────────────────
        proj_out = root_out / label
        proj_out.mkdir(parents=True, exist_ok=True)
        out_csv = str(proj_out / "interpolated_micasense_pos.csv")

        # Redirect logging to a per-project file as well
        proj_log_handler = logging.FileHandler(proj_out / "run_micasense_interpolation.log")
        proj_log_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(proj_log_handler)

        # ── Run interpolation ─────────────────────────────────────────────────
        try:
            ret_micasense_pos(
                absolute_micasense_file_list=master_paths,
                mrk_folder=p1_folder,
                micasense_folder=ms_folder,
                image_suffix=args.master_suffix.lstrip("_").replace(".tif", ""),
                epsg_crs="2056",
                out_file=out_csv,
                P1_shift_vec=np.array([0.0, 0.0, 0.0]),
                htrans_path=args.htrans or None,
                htrans_fallback=args.htrans_fallback or None,
                p1_ref_csv=p1_ref_csv,
            )
            print(f"  Output: {out_csv}")
            logging.info("[%s] Done. Output: %s", label, out_csv)
        except Exception as exc:
            status = f"error: {exc}"
            logging.error("[%s] FAILED: %s", label, exc, exc_info=True)
            print(f"  ERROR: {exc}")

        finally:
            logging.getLogger().removeHandler(proj_log_handler)
            proj_log_handler.close()

        summary_rows.append({"label": label, "status": status,
                              "p1": p1_folder, "micasense": ms_folder,
                              "out_csv": out_csv})

    # ── Write batch summary CSV ───────────────────────────────────────────────
    summary_csv = root_out / "batch_summary.csv"
    with open(summary_csv, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=["label", "status", "p1", "micasense", "out_csv"])
        writer.writeheader()
        writer.writerows(summary_rows)

    # ── Print final summary ───────────────────────────────────────────────────
    ok     = sum(1 for r in summary_rows if r["status"] == "ok")
    errors = sum(1 for r in summary_rows if r["status"].startswith("error"))
    skips  = sum(1 for r in summary_rows if r["status"].startswith("skip"))

    print(f"\n{'═'*60}")
    print(f"BATCH COMPLETE")
    print(f"  Processed OK : {ok}")
    print(f"  Errors       : {errors}")
    print(f"  Skipped      : {skips}")
    print(f"  Summary CSV  : {summary_csv}")
    print(f"  Batch log    : {batch_log}")
    print(f"{'═'*60}\n")
    logging.info("Batch done. ok=%d  errors=%d  skipped=%d", ok, errors, skips)


if __name__ == "__main__":
    main()
