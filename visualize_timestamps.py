import os
import glob
import argparse
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple, Sequence
from statistics import median

from exiftool import ExifToolHelper

# Constants from upd_micasense_pos_filename.py
GPSUTC_deltat = 0
MICA_deltat = -18


def _resolve_exiftool(exe_override: Optional[str]) -> Optional[str]:
    """Return an exiftool path (override > known paths > PATH)."""
    if exe_override:
        return exe_override
    candidates = [
        r"C:\\Program Files\\exiftool-13.03_64\\exiftool.exe",
        r"C:\\Program Files\\exiftool-13.01_64\\exiftool.exe",
        r"C:\\Program Files\\exiftool\\exiftool.exe",
        r"C:\\Program Files (x86)\\exiftool\\exiftool.exe",
    ]
    for cand in candidates:
        if Path(cand).exists():
            return cand
    return None

def get_P1_timestamp(p1_mrk_line):
    """Return timestamp from line p1_mrk_line in MRK"""
    mrk_line = p1_mrk_line.split()   
    secs = float(mrk_line[1])
    week = int(mrk_line[2].strip("[").strip("]"))
    epoch_secs = secs + (week*7*24*60*60)
    temp_timestamp = datetime(1980, 1, 6) + timedelta(seconds=epoch_secs)
    p1_camera_timestamp = temp_timestamp - timedelta(seconds=GPSUTC_deltat) 
    return p1_camera_timestamp

def read_mrk_files(mrk_folder):
    """Read all MRK files; keep both line-order timestamps and sorted timestamps."""
    discovered_mrks = sorted(glob.iglob(str(mrk_folder) + '/' + '**/*.MRK', recursive=True))
    if not discovered_mrks:
        print(f"No .MRK files found in {mrk_folder}")
        return []

    mrk_data = []  # List of dicts: {'file', 'timestamps', 'timestamps_raw', 'qualities_raw', 'start', 'end}

    for mrk_path in discovered_mrks:
        with open(mrk_path, 'r') as f:
            lines = f.readlines()

        if not lines:
            continue

        timestamps_raw = []
        qualities_raw = []
        for line in lines:
            try:
                ts = get_P1_timestamp(line)
                parts = line.split()
                q = parts[9] if len(parts) > 9 else ""
                timestamps_raw.append(ts)
                qualities_raw.append(q)
            except Exception:
                pass

        if timestamps_raw:
            timestamps_sorted = sorted(timestamps_raw)
            mrk_data.append({
                'file': os.path.basename(mrk_path),
                'timestamps': timestamps_sorted,
                'timestamps_raw': timestamps_raw,
                'qualities_raw': qualities_raw,
                'start': timestamps_sorted[0],
                'end': timestamps_sorted[-1]
            })

    # Sort MRKs by start time for plotting/coverage
    mrk_data.sort(key=lambda x: x['start'])
    return mrk_data

def _parse_micasense_ts(tags: dict) -> Optional[datetime]:
    """Extract a naive UTC datetime from exiftool tags."""
    # Prefer fully combined timestamp if available
    ts_candidates = [
        tags.get("Composite:SubSecDateTimeOriginal"),
        tags.get("EXIF:SubSecDateTimeOriginal"),
        tags.get("EXIF:DateTimeOriginal"),
        tags.get("XMP:UTCAtExposure"),
    ]

    for raw in ts_candidates:
        if not raw:
            continue
        ts_str = str(raw).strip()
        ts_norm = ts_str.replace("Z", "+0000").replace("+00:00", "+0000").replace("-00:00", "-0000")
        fmt_candidates = [
            "%Y:%m:%d %H:%M:%S.%f%z",
            "%Y:%m:%d %H:%M:%S%z",
            "%Y:%m:%d %H:%M:%S.%f",
            "%Y:%m:%d %H:%M:%S",
        ]
        for fmt in fmt_candidates:
            try:
                dt_val = datetime.strptime(ts_norm, fmt)
                if dt_val.tzinfo:
                    dt_val = dt_val.astimezone(timezone.utc).replace(tzinfo=None)
                return dt_val
            except ValueError:
                continue
    return None


def read_micasense_timestamps(micasense_folder, suffix="_6.tif", exiftool_override: Optional[str] = None):
    """Read EXIF timestamps from MicaSense images using exiftool."""
    print(f"Scanning MicaSense images in {micasense_folder}...")
    filelist = sorted(glob.iglob(str(micasense_folder) + "/**/IMG*" + str(suffix), recursive=True))

    if not filelist:
        print("No matching images found.")
        return []

    exe = _resolve_exiftool(exiftool_override)
    if exiftool_override and not exe:
        print(f"Warning: exiftool override not found: {exiftool_override}")
    kwargs = {"executable": exe} if exe else {}

    mica_data = []  # List of (filename, timestamp)
    with ExifToolHelper(**kwargs) as et:
        meta_list = et.get_metadata(filelist)

    for idx, (path, tags) in enumerate(zip(filelist, meta_list)):
        if idx % 200 == 0:
            print(f"Processed {idx}/{len(filelist)} images...")
        ts_val = _parse_micasense_ts(tags)
        if not ts_val:
            print(f"No timestamp for {path}")
            continue
        mica_timestamp = ts_val - timedelta(seconds=MICA_deltat)
        mica_data.append((os.path.basename(path), mica_timestamp))

    mica_data.sort(key=lambda x: x[1])
    print(f"Collected timestamps from {len(mica_data)}/{len(filelist)} images")
    return mica_data


def _detect_time_jump(sequence: List[Tuple[str, datetime]], jump_threshold_seconds=2.0):
    """Return info about the first negative time jump exceeding threshold in a timestamp sequence."""
    if len(sequence) < 2:
        return None

    deltas = []
    for i in range(1, len(sequence)):
        d = (sequence[i][1] - sequence[i-1][1]).total_seconds()
        deltas.append(d)

    min_delta = min(deltas)
    if min_delta >= -jump_threshold_seconds:
        return None

    jump_idx = deltas.index(min_delta) + 1  # index in sequence where jump occurs
    return {
        "index": jump_idx,
        "filename": sequence[jump_idx][0],
        "delta_seconds": min_delta,
        "prev_ts": sequence[jump_idx - 1][1],
        "curr_ts": sequence[jump_idx][1],
    }


def _apply_jump_fix(sequence: List[Tuple[str, datetime]], jump_info, qualities: Optional[Sequence[str]] = None, window=10):
    """Shift all timestamps from jump onward so the jump frame is aligned to expected cadence.

    Cadence is estimated from the median delta of the preceding window, optionally restricted to
    pairs where both qualities are "50" (assumed good RTK)."""
    if not jump_info:
        return sequence, None

    idx = jump_info["index"]
    if idx <= 0 or idx >= len(sequence):
        return sequence, None

    deltas = []
    start = max(1, idx - window)
    for i in range(start, idx):
        if qualities:
            if qualities[i] != "50" or qualities[i-1] != "50":
                continue
        deltas.append((sequence[i][1] - sequence[i-1][1]).total_seconds())

    if not deltas:
        # fallback to all deltas in window
        for i in range(start, idx):
            deltas.append((sequence[i][1] - sequence[i-1][1]).total_seconds())

    nominal = median(deltas) if deltas else 0.0

    prev_ts = sequence[idx - 1][1]
    desired_ts = prev_ts + timedelta(seconds=nominal)
    offset = desired_ts - sequence[idx][1]

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

def visualize(mrk_data, mica_data, jump_info_mica=None, jump_info_mrk=None):
    """Plot the timeline"""
    if not mrk_data or not mica_data:
        print("Insufficient data to plot.")
        return

    fig, ax = plt.subplots(figsize=(15, 8))
    
    # Plot P1 Ranges (Flight lines)
    roi_y_min = 0.8
    roi_y_max = 1.2
    
    colors = ['blue', 'green', 'purple', 'cyan', 'orange']
    
    print("\n=== P1 Flight Segments ===")
    total_mrk_triggers = 0
    for i, flight in enumerate(mrk_data):
        start = flight['start']
        end = flight['end']
        count = len(flight['timestamps'])
        total_mrk_triggers += count
        label = f"P1 Flight {i+1}: {flight['file']}"
        color = colors[i % len(colors)]
        
        # Plot a bar/line for the duration
        ax.hlines(y=1, xmin=start, xmax=end, linewidth=10, color=color, alpha=0.5, label=label)
        
        # Plot individual triggers
        ax.plot(flight['timestamps'], [1] * len(flight['timestamps']), '|', color=color, markersize=10)
        
        print(f"Flight {i+1}: {start} -> {end} ({count} triggers)")
    
    print(f"Total P1 triggers from MRK files: {total_mrk_triggers}")

    print("\n=== MicaSense Images ===")
    # Check coverage
    mica_times = [m[1] for m in mica_data]
    mica_y = [1.02] * len(mica_times) # Slightly offset
    
    # Classify MicaSense images
    inside_any = []
    outside = []
    
    # "Between flights" logic check
    # Original script sets to 0 if:
    # 1. Before FIRST timestamp of Flight 1
    # 2. After LAST timestamp of Flight N
    # 3. In the GAP between Flights (if multiple flights)
    
    overall_start = mrk_data[0]['start']
    overall_end = mrk_data[-1]['end']
    
    for fname, ts in mica_data:
        status = "OUTSIDE"
        ts_val = ts.timestamp()
        
        # Check if strictly within OVERALL range
        if overall_start.timestamp() <= ts_val <= overall_end.timestamp():
            # Check gaps if multiple flights
            in_gap = False
            if len(mrk_data) > 1:
                # Check if it falls BETWEEN flights (e.g. after flight 1 end, before flight 2 start)
                for i in range(len(mrk_data) - 1):
                    flight_end = mrk_data[i]['end'].timestamp()
                    next_flight_start = mrk_data[i+1]['start'].timestamp()
                    
                    if flight_end < ts_val < next_flight_start:
                        in_gap = True
                        break
            
            if not in_gap:
                status = "INSIDE"
        
        if status == "INSIDE":
            inside_any.append(ts)
        else:
            outside.append(ts)

    print(f"Total MicaSense: {len(mica_data)}")
    if mica_data:
         print(f"MicaSense Range: {mica_data[0][1]} -> {mica_data[-1][1]}")
         
         # User debug request: check specific indices
         # Note: User mentioned 64-471 (1-based likely). So index 63 and 470.
         if len(mica_data) > 471:
             idx_start = 63
             idx_end = 470
             ts_start = mica_data[idx_start][1]
             ts_end = mica_data[idx_end][1]
                 
             print(f"\n--- User Interest Area (Img 64-471) ---")
             print(f"P1 Start: {overall_start}")
             print(f"P1 End:   {overall_end}")
             
             print(f"Img 64 ({mica_data[idx_start][0]}): {ts_start}")
             print(f"  -> Currently {abs((ts_start - overall_start).total_seconds()):.2f}s AFTER P1 start")
             
             print(f"Img 471 ({mica_data[idx_end][0]}): {ts_end}")
             print(f"  -> Currently {abs((ts_end - overall_end).total_seconds()):.2f}s AFTER P1 end")
             
             # To check if offset is the problem, let's look at the density
             # If user says Img 64 should be start, let's see what index IS the start currently
             current_start_idx = next((i for i, x in enumerate(mica_data) if x[1] >= overall_start), None)
             current_end_idx = next((i for i, x in enumerate(mica_data) if x[1] > overall_end), None)
             
             if current_start_idx is not None:
                 print(f"Current Start Image: Index {current_start_idx+1} ({mica_data[current_start_idx][0]}) at {mica_data[current_start_idx][1]}")
             else:
                 print("Current Start Image: None (all before start)")
                     
             if current_end_idx is not None:
                 print(f"Current End Image: Index {current_end_idx} ({mica_data[current_end_idx-1][0]}) at {mica_data[current_end_idx-1][1]}")
             else:
                 print("Current End Image: None (all within range)")
                     
             print(f"Current Count Inside: {len(inside_any)}")
             print(f"Expected Count (user): {471-64+1}")

             # Suggest offset
             suggested_offset_start = (ts_start - overall_start).total_seconds()
             print(f"Current MICA_deltat (applied): {MICA_deltat}")
             # print(f"Suggested added adjustment: {-suggested_offset_start:.2f}s")

    if outside:
        outs = sorted(outside)
        print(f"Outside Range: {outs[0]} -> {outs[-1]}")
        # Check if they are before or after
        before = [t for t in outs if t < overall_start]
        after = [t for t in outs if t > overall_end]
        print(f"  - Before P1 start: {len(before)}")
        print(f"  - After P1 end: {len(after)}")
        if len(mrk_data) > 1:
             # loose check for gaps
             print(f"  - (Approx in gaps/other): {len(outs) - len(before) - len(after)}")

    # Plot MicaSense
    ax.scatter(inside_any, [0.98]*len(inside_any), color='green', s=10, label='MicaSense (Valid)', alpha=0.6)
    ax.scatter(outside, [0.98]*len(outside), color='red', s=30, marker='x', label='MicaSense (Outside/Zero)', alpha=1.0)

    if jump_info_mica:
        ax.axvline(jump_info_mica['curr_ts'], color='red', linestyle='--', alpha=0.6, label='Mica jump')
    if jump_info_mrk:
        ax.axvline(jump_info_mrk['curr_ts'], color='magenta', linestyle='--', alpha=0.6, label='MRK jump')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.title('Timestamp Alignment: P1 (Lines) vs MicaSense (Dots)')
    plt.xlabel('Time (UTC)')
    plt.yticks([])
    plt.legend()
    plt.grid(True, axis='x', linestyle='--', alpha=0.7)
    
    output_path = "timestamp_visualisation.png"
    plt.savefig(output_path)
    print(f"\nPlot saved to: {output_path}")
    # plt.show() # Cannot show in this env

def _find_campaign_root(path):
    parts = list(path.parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].lower() == "2024_dronecampaign":
            return Path(*path.parts[: i + 1])
    return None

def main():
    parser = argparse.ArgumentParser(description="Visualize P1 vs MicaSense timestamps")
    parser.add_argument("--project-psx", type=str, required=True)
    parser.add_argument("--exiftool", type=str, help="Path to exiftool executable (optional)")
    parser.add_argument("--image-suffix", type=str, default="_6.tif", help="Suffix to match MicaSense images (default: _6.tif)")
    parser.add_argument("--jump-threshold", type=float, default=2.0, help="Seconds of negative delta to flag a jump (default: 2s)")
    parser.add_argument("--auto-fix-jump", action="store_true", help="If set, shift P1/MRK timestamps after the detected jump to restore cadence")
    args = parser.parse_args()
    
    project_psx = Path(args.project_psx)
    if not project_psx.exists():
        print(f"Project not found: {project_psx}")
        return

    # Infer paths (logic from compare script)
    project_dir = project_psx.parent
    date = project_dir.name
    site = project_dir.parent.name
    campaign_root = _find_campaign_root(project_psx)
    
    if not campaign_root:
        print("Could not find campaign root")
        return

    rgb_root = campaign_root / "01_data" / "P1" / site / date
    mica_root = campaign_root / "01_data" / "Micasense" / site / date
    
    print(f"Processing for {site} - {date}")
    print(f"RGB Root: {rgb_root}")
    print(f"Mica Root: {mica_root}")
    
    mrk_data = read_mrk_files(rgb_root)
    mica_data = read_micasense_timestamps(mica_root, suffix=args.image_suffix, exiftool_override=args.exiftool)

    # Detect jump in MicaSense (report only)
    jump_info_mica = _detect_time_jump(mica_data, jump_threshold_seconds=args.jump_threshold)
    if jump_info_mica:
        print("\nDetected MicaSense negative time jump:")
        print(f"  Index: {jump_info_mica['index']} ({jump_info_mica['filename']})")
        print(f"  Delta: {jump_info_mica['delta_seconds']:.3f}s")
        print(f"  Prev:  {jump_info_mica['prev_ts']}")
        print(f"  Curr:  {jump_info_mica['curr_ts']}")
    else:
        print("No MicaSense negative time jump detected.")

    # Detect jump in MRK triggers (line order)
    flat_mrk = []
    qualities_flat = []
    lengths = []
    for flight in mrk_data:
        raw_list = flight.get('timestamps_raw') or flight['timestamps']
        q_list = flight.get('qualities_raw') or ["" for _ in raw_list]
        lengths.append(len(raw_list))
        for ts in raw_list:
            flat_mrk.append((flight['file'], ts))
        qualities_flat.extend(q_list)

    jump_info_mrk = _detect_time_jump(flat_mrk, jump_threshold_seconds=args.jump_threshold)
    fix_info_mrk = None
    if jump_info_mrk:
        print("\nDetected MRK negative time jump:")
        print(f"  Index: {jump_info_mrk['index']} ({jump_info_mrk['filename']})")
        print(f"  Delta: {jump_info_mrk['delta_seconds']:.3f}s")
        print(f"  Prev:  {jump_info_mrk['prev_ts']}")
        print(f"  Curr:  {jump_info_mrk['curr_ts']}")

        if args.auto_fix_jump:
            corrected_flat, fix_info_mrk = _apply_jump_fix(flat_mrk, jump_info_mrk, qualities=qualities_flat)
            if fix_info_mrk:
                print("Applied MRK jump fix:")
                print(f"  Offset applied (s): {fix_info_mrk['offset_seconds']:.3f}")
                print(f"  Nominal cadence (s): {fix_info_mrk['nominal_delta']:.3f}")
                print(f"  From index: {fix_info_mrk['applied_from_index']}")

                # Rebuild per-flight data from corrected flat list
                idx = 0
                rebuilt = []
                for flight, count in zip(mrk_data, lengths):
                    slice_flat = corrected_flat[idx: idx + count]
                    slice_q = qualities_flat[idx: idx + count]
                    ts_raw = [t for _, t in slice_flat]
                    ts_sorted = sorted(ts_raw)
                    rebuilt.append({
                        'file': flight['file'],
                        'timestamps_raw': ts_raw,
                        'qualities_raw': slice_q,
                        'timestamps': ts_sorted,
                        'start': ts_sorted[0],
                        'end': ts_sorted[-1],
                    })
                    idx += count
                mrk_data = rebuilt
    else:
        print("No MRK negative time jump detected.")

    visualize(mrk_data, mica_data, jump_info_mica=jump_info_mica, jump_info_mrk=jump_info_mrk)

if __name__ == "__main__":
    main()
