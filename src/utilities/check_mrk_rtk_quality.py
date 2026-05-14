"""
check_mrk_rtk_quality.py
────────────────────────────────────────────────────────────────────────────
Cross-check MRK RTK quality against MicaSense interpolation outcomes.

For every project in the batch project-list CSV:
  - Parses every MRK file in the P1 folder:
      * counts total / RTK-50 / non-RTK images per segment
      * detects GPS time resets (backward jump in GPS epoch seconds)
      * flags all-zero / missing / unparseable MRK
  - Reads interpolated_micasense_pos.csv from --out-dir:
      * counts total / interpolated (h != 0) / outside-P1 (h == 0) MicaSense images
  - Writes a summary CSV and prints a console table.

Projects flagged for manual intervention (needs_manual_review = YES):
  1. MRK has any non-RTK-50 entries      (positions unreliable mid-flight)
  2. GPS time reset detected             (timestamps scrambled -> INTERP_REF corrupt)
  3. > --outside-threshold % of MicaSense images outside P1 times

Manual intervention means:
  - Stop automatic processing after P1 alignment step
  - Manually delete P1 images without RTK-50 fix
  - Re-do alignment using general (non-PPK) alignment mode
  - MicaSense interpolation for those flights must be repeated afterwards

Usage
─────
    python check_mrk_rtk_quality.py <project_list.csv> \\
        [--out-dir  C:/Temp/micasense_interp_results]  \\
        [--report   C:/Temp/mrk_rtk_report.csv]        \\
        [--outside-threshold 20]
"""

import argparse
import csv
import glob
import os
import sys
from pathlib import Path


# ── MRK helpers ──────────────────────────────────────────────────────────────

def _parse_mrk_file(mrk_path):
    """
    Parse one MRK file.

    MRK line format (space-separated):
        img_idx  gps_secs  [gps_week]  dN  dE  dV
        lat,Lat  lon,Lon  ellh,Ellh
        std_N std_E std_V  q_flag,Q

    Returns a dict with keys:
        total        int   valid lines parsed
        rtk50        int   lines with Q flag == 50
        non_rtk      int   lines with Q flag != 50
        all_zero     bool  all lat/lon/ellh are 0.0  (no GPS fix)
        time_resets  int   number of backward GPS-epoch jumps detected
        reset_at     list  image indices where each reset was detected
        faulty       bool  file unreadable or entirely unparseable
        note         str   optional error detail
    """
    result = dict(
        total=0, rtk50=0, non_rtk=0, all_zero=False,
        time_resets=0, reset_at=[], faulty=False, note='', mrk_path=str(mrk_path)
    )

    try:
        with open(str(mrk_path), 'r', errors='replace') as fh:
            lines = fh.readlines()
    except OSError as exc:
        result['faulty'] = True
        result['note'] = str(exc)
        return result

    entries = []
    for line in lines:
        m = line.split()
        if len(m) < 9:
            continue
        try:
            img_idx   = int(m[0])
            gps_secs  = float(m[1])
            gps_week  = int(m[2].strip('[').strip(']'))
            lat       = float(m[6].split(',')[0])
            lon       = float(m[7].split(',')[0])
            ellh      = float(m[8].split(',')[0])
            # Q flag is last token, formatted as "50,Q"
            q_flag    = int(m[-1].split(',')[0])
        except (ValueError, IndexError):
            continue

        epoch_secs = gps_secs + gps_week * 7 * 24 * 3600
        entries.append((img_idx, epoch_secs, lat, lon, ellh, q_flag))

    if not entries:
        result['faulty'] = True
        result['note'] = 'no parseable lines'
        return result

    result['all_zero'] = all(
        lat == 0.0 and lon == 0.0 and ellh == 0.0
        for _, _, lat, lon, ellh, _ in entries
    )

    prev_epoch = None
    for img_idx, epoch_secs, _lat, _lon, _ellh, q_flag in entries:
        result['total'] += 1
        if q_flag == 50:
            result['rtk50'] += 1
        else:
            result['non_rtk'] += 1
        if prev_epoch is not None and epoch_secs < prev_epoch:
            result['time_resets'] += 1
            result['reset_at'].append(img_idx)
        prev_epoch = epoch_secs

    return result


def _find_mrk_files(p1_folder):
    """Return all *.MRK files under p1_folder, sorted."""
    pattern = os.path.join(str(p1_folder), '**', '*.MRK')
    return sorted(glob.glob(pattern, recursive=True))


# ── Interpolation result reader ───────────────────────────────────────────────

def _read_interpolation_result(out_csv):
    """
    Read interpolated_micasense_pos.csv.

    Outside-P1 images are written with h = 0.0000 in the last column.
    Returns (total, interpolated, outside) or None if file is missing.
    """
    if not os.path.exists(str(out_csv)):
        return None

    total = 0
    outside = 0

    with open(str(out_csv), 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.lower().startswith('label'):
                continue
            parts = line.split(',')
            if len(parts) < 4:
                continue
            total += 1
            try:
                # Strip stray non-numeric chars (occasional § artifact in older files)
                h_raw = ''.join(c for c in parts[-1] if c in '0123456789.-')
                h = float(h_raw) if h_raw else 0.0
            except ValueError:
                h = 0.0
            if abs(h) < 1e-6:
                outside += 1

    return total, total - outside, outside


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Check MRK RTK quality and correlate with MicaSense interpolation outcomes."
    )
    parser.add_argument('csv', help='Path to the project-list CSV.')
    parser.add_argument(
        '--out-dir', default=r'C:\Temp\micasense_interp_results',
        help='Root interpolation output directory '
             '(default: C:\\Temp\\micasense_interp_results).'
    )
    parser.add_argument(
        '--report', default=None,
        help='Output CSV report path '
             '(default: <out-dir>/mrk_rtk_report.csv).'
    )
    parser.add_argument(
        '--outside-threshold', type=float, default=20.0,
        help='%% outside-P1 MicaSense images that triggers manual-review flag '
             '(default: 20).'
    )
    args = parser.parse_args()

    csv_path    = Path(args.csv)
    out_dir     = Path(args.out_dir)
    report_path = Path(args.report) if args.report else out_dir / 'mrk_rtk_report.csv'
    threshold   = args.outside_threshold

    if not csv_path.exists():
        sys.exit('ERROR: project-list CSV not found: {}'.format(csv_path))

    # ── Read and deduplicate project list ────────────────────────────────────
    with open(str(csv_path), newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    seen = set()
    unique_rows = []
    for row in rows:
        key = (row.get('rgb', '').strip(), row.get('multispec', '').strip())
        if key not in seen and key[0] and key[1]:
            seen.add(key)
            unique_rows.append(row)

    print('')
    print('Project list : {}'.format(csv_path))
    print('Output dir   : {}'.format(out_dir))
    print('Projects     : {}'.format(len(unique_rows)))
    print('Outside thr. : {:.0f}%\n'.format(threshold))

    # ── Console header ───────────────────────────────────────────────────────
    COL_W = 28
    FMT = ('{:<' + str(COL_W) + 's}  '
           '{:>8s}  {:>7s}  {:>8s}  {:>6s}  '
           '{:>7s}  {:>7s}  {:>7s}  {:>6s}  '
           '{}')

    div = u'\u2500' * 140

    def header_line():
        return FMT.format(
            'Project',
            'P1 imgs', 'RTK-50', 'non-RTK', 'Resets',
            'MS imgs', 'MS ok',  'MS out',  '% out',
            'Flags / Notes'
        )

    print(div)
    print(header_line())
    print(div)

    report_rows = []

    for row in unique_rows:
        date      = row.get('date', '').strip()
        site      = row.get('site', '').strip()
        p1_folder = row.get('rgb', '').strip()
        label     = '{}_{}'.format(date, site)

        # ── Parse all MRK files for this project ──────────────────────────────
        mrk_total = mrk_rtk50 = mrk_non_rtk = mrk_resets = 0
        reset_indices = []
        mrk_notes = []

        if not Path(p1_folder).is_dir():
            mrk_notes.append('P1 folder not found')
        else:
            mrk_files = _find_mrk_files(p1_folder)
            if not mrk_files:
                mrk_notes.append('No MRK files found')
            else:
                for mrk_path in mrk_files:
                    r = _parse_mrk_file(mrk_path)
                    seg = os.path.basename(mrk_path)
                    if r['faulty']:
                        mrk_notes.append('Faulty MRK: {}'.format(seg))
                        continue
                    if r['all_zero']:
                        mrk_notes.append('All-zero GPS: {}'.format(seg))
                        continue
                    mrk_total   += r['total']
                    mrk_rtk50   += r['rtk50']
                    mrk_non_rtk += r['non_rtk']
                    mrk_resets  += r['time_resets']
                    reset_indices.extend(r['reset_at'])

                if mrk_total > 0 and mrk_non_rtk > 0:
                    pct = 100.0 * mrk_non_rtk / mrk_total
                    mrk_notes.append(
                        'non-RTK-50: {}/{} ({:.0f}%)'.format(
                            mrk_non_rtk, mrk_total, pct)
                    )
                if mrk_resets > 0:
                    mrk_notes.append(
                        'GPS reset at img {}'.format(reset_indices)
                    )

        # ── Read MicaSense interpolation result ───────────────────────────────
        interp_csv = out_dir / label / 'interpolated_micasense_pos.csv'
        res = _read_interpolation_result(interp_csv)

        if res is None:
            ms_total = ms_ok = ms_out = 0
            ms_notes = ['no interp result']
        else:
            ms_total, ms_ok, ms_out = res
            ms_notes = []
            if ms_total > 0:
                pct_out = 100.0 * ms_out / ms_total
                if pct_out > threshold:
                    ms_notes.append(
                        '{:.0f}% MS outside P1'.format(pct_out)
                    )

        pct_out_str = (
            '{:.1f}%'.format(100.0 * ms_out / ms_total)
            if ms_total > 0 else 'N/A'
        )

        # ── Manual-review decision ────────────────────────────────────────────
        needs_manual = (
            mrk_non_rtk > 0
            or mrk_resets > 0
            or (ms_total > 0 and (100.0 * ms_out / ms_total) > threshold)
        )

        all_notes = mrk_notes + ms_notes
        flags_str = ' | '.join(all_notes) if all_notes else '-'
        if needs_manual:
            flags_str = '*** MANUAL REVIEW *** | ' + flags_str

        # ── Console row ───────────────────────────────────────────────────────
        print(FMT.format(
            label[:COL_W],
            str(mrk_total) if mrk_total else '-',
            str(mrk_rtk50) if mrk_total else '-',
            str(mrk_non_rtk) if mrk_total else '-',
            str(mrk_resets) if mrk_total else '-',
            str(ms_total) if ms_total else '-',
            str(ms_ok) if ms_total else '-',
            str(ms_out) if ms_total else '-',
            pct_out_str,
            flags_str,
        ))

        report_rows.append({
            'label':               label,
            'p1_folder':           p1_folder,
            'mrk_total':           mrk_total,
            'mrk_rtk50':           mrk_rtk50,
            'mrk_non_rtk':         mrk_non_rtk,
            'mrk_resets':          mrk_resets,
            'reset_at_img':        ';'.join(str(x) for x in reset_indices),
            'ms_total':            ms_total,
            'ms_interpolated':     ms_ok,
            'ms_outside':          ms_out,
            'pct_outside':         '{:.1f}'.format(
                100.0 * ms_out / ms_total) if ms_total else '',
            'needs_manual_review': 'YES' if needs_manual else 'no',
            'notes':               ' | '.join(all_notes),
        })

    print(div)
    n_manual = sum(1 for r in report_rows if r['needs_manual_review'] == 'YES')
    print('\n{}/{} projects flagged for manual review.\n'.format(
        n_manual, len(report_rows)))

    # ── Write CSV report ──────────────────────────────────────────────────────
    out_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'label', 'p1_folder',
        'mrk_total', 'mrk_rtk50', 'mrk_non_rtk',
        'mrk_resets', 'reset_at_img',
        'ms_total', 'ms_interpolated', 'ms_outside', 'pct_outside',
        'needs_manual_review', 'notes',
    ]
    with open(str(report_path), 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    print('Report written: {}\n'.format(report_path))


if __name__ == '__main__':
    main()
