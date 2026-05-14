"""
test_htrans_datum_chain.py
Tests two height pipelines against Swisstopo ground truth.

CURRENT (wrong):  h = API_LN02 + htrans_delta   <- uses LN02 as htrans input
CORRECT:          h = h_ETRS89 + htrans_delta    <- uses ETRS89 ellipsoidal as input
GROUND TRUTH:     Swisstopo lv95tolhn95 API

Positions are sourced from:
  1. MRK file  – if it contains non-zero coordinates
  2. DJI XMP   – drone-dji:GpsLatitude/GpsLongitude/AbsoluteAltitude from P1 JPG
                  (same fallback logic as upd_micasense_pos_filename.py)
"""
import sys, re, glob, requests, rasterio, pyproj, logging, math, os
logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Sites to test — add/remove entries freely
# ---------------------------------------------------------------------------
TEST_SITES = [
    {
        "label": "AAAAA_test (Ticino — border, outside htrans)",
        "mrk":   r"M:\working_package_2\2024_dronecampaign\01_data\P1\AAAAA_test\20260506",
        "is_dir": True,   # pass to find_mrk(); set False to use mrk as a direct path
    },
    {
        "label": "lwf_lens (central Switzerland — inside htrans)",
        "mrk":   r"M:\working_package_2\2024_dronecampaign\01_data\P1\lwf_lens\20250818\DJI_202508181531_002_LWFLens20250410p1mica60m\DJI_202508181531_002_LWFLens20250410p1mica60m_Timestamp.MRK",
        "is_dir": False,
    },
]

HTRANS_PATH     = r"M:\working_package_2\2024_dronecampaign\02_processing\geoid\Swisstopo\ETRS.tif"
HTRANS_FALLBACK = r"M:\working_package_2\2024_dronecampaign\02_processing\geoid\ExtendedGeoid.tif"
API_WGS84_LV95  = "https://geodesy.geo.admin.ch/reframe/wgs84tolv95"
API_LV95_LHN95  = "https://geodesy.geo.admin.ch/reframe/lv95tolhn95"
N_SAMPLES = 5

def find_mrk(root):
    if os.path.isfile(root):
        return root
    m = glob.glob(root + "/**/*.MRK", recursive=True)
    if not m: sys.exit(f"No MRK under {root}")
    return m[0]

def _parse_dji_xmp(raw_bytes):
    xmp_start = raw_bytes.find(b"<?xpacket")
    xmp_end   = raw_bytes.find(b"<?xpacket end")
    if xmp_start == -1 or xmp_end == -1:
        return {}
    xmp = raw_bytes[xmp_start:xmp_end + 50].decode("utf-8", errors="replace")
    fields = {}
    for key in ("GpsLatitude", "GpsLongitude", "AbsoluteAltitude", "RtkFlag", "UTCAtExposure"):
        m = re.search(r'drone-dji:' + key + r'="([^"]+)"', xmp)
        fields[key] = m.group(1) if m else None
    return fields

def read_samples_from_mrk(path, n):
    """Read up to n (lat, lon, ellh) from MRK. Returns [] if all-zero."""
    out = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) < 9: continue
            try:
                lat  = float(p[6].split(",")[0])
                lon  = float(p[7].split(",")[0])
                ellh = float(p[8].split(",")[0])
            except (ValueError, IndexError): continue
            if lat == 0.0 and lon == 0.0 and ellh == 0.0:
                continue  # skip zero-fix lines
            out.append((lat, lon, ellh))
            if len(out) >= n: break
    return out

def read_samples_from_xmp(folder, n):
    """Read up to n (lat, lon, ellh) from DJI XMP in P1 JPGs. Raises if XMP absent."""
    jpg_files = sorted({
        f for pattern in (folder + "/*.JPG", folder + "/*.jpg")
        for f in glob.glob(pattern)
    })
    if not jpg_files:
        sys.exit(f"No JPG files found in {folder}")
    out = []
    for jpg in jpg_files:
        with open(jpg, "rb") as f:
            raw = f.read()
        xmp = _parse_dji_xmp(raw)
        lat_s = xmp.get("GpsLatitude")
        lon_s = xmp.get("GpsLongitude")
        alt_s = xmp.get("AbsoluteAltitude")
        if not (lat_s and lon_s and alt_s):
            sys.exit(f"No XMP position in {jpg} — cannot continue.")
        rtk = xmp.get("RtkFlag", "?")
        if rtk != "50":
            print(f"  [WARN] RtkFlag={rtk} (not RTK fixed) in {jpg.split('/')[-1].split(chr(92))[-1]}")
        out.append((float(lat_s), float(lon_s), float(alt_s)))
        if len(out) >= n: break
    return out

def read_samples(mrk_path, n):
    """Try MRK first; fall back to XMP if MRK is all-zero."""
    samples = read_samples_from_mrk(mrk_path, n)
    if samples:
        print(f"Source: MRK file  ({len(samples)} positions)")
        return samples, "MRK"
    print("[MRK_FAULTY] MRK has all-zero coordinates. Falling back to P1 XMP (EXIF).")
    folder = mrk_path.rsplit("\\", 1)[0]
    samples = read_samples_from_xmp(folder, n)
    print(f"Source: P1 XMP/EXIF  ({len(samples)} positions)")
    return samples, "XMP"

def wgs84_to_lv95(lon, lat, alt):
    r = requests.get(API_WGS84_LV95, params={"northing":lat,"easting":lon,"altitude":alt,"format":"json"}, timeout=10)
    r.raise_for_status(); d = r.json()
    return float(d["easting"]), float(d["northing"]), float(d["altitude"])

def lv95_to_lhn95(E, N, ln02):
    r = requests.get(API_LV95_LHN95, params={"easting":E,"northing":N,"altitude":ln02,"format":"json"}, timeout=10)
    r.raise_for_status()
    return float(r.json()["altitude"])

HTRANS_NODATA = 99.9  # Sentinel value used by CHGeo2004 for out-of-coverage areas

def grid_delta(lon, lat, htrans_path=None, fallback_path=None):
    """
    Sample an htrans grid at (lon, lat).  Returns (delta, source) where source is
    'primary', 'fallback', or None (out-of-coverage everywhere).

    fallback_path must be passed explicitly — there is NO automatic fallback to
    the HTRANS_FALLBACK global so that the datum-chain test can check the primary
    grid in isolation.
    """
    path = htrans_path or HTRANS_PATH
    def _sample(tif_path):
        with rasterio.open(tif_path) as ds:
            bounds = ds.bounds
            extent_is_geographic = (
                -180 <= bounds.left  <= 180 and
                -180 <= bounds.right <= 180 and
                -90  <= bounds.bottom <= 90 and
                -90  <= bounds.top    <= 90
            )
            if extent_is_geographic:
                x, y = lon, lat
            else:
                grid_crs = pyproj.CRS(ds.crs.to_epsg()) if ds.crs.to_epsg() else pyproj.CRS(ds.crs.to_wkt())
                wgs84 = pyproj.CRS("EPSG:4326")
                if not grid_crs.equals(wgs84):
                    tr = pyproj.Transformer.from_crs(wgs84, grid_crs, always_xy=True)
                    x, y = tr.transform(lon, lat)
                else:
                    x, y = lon, lat
            for v in ds.sample([(x, y)]):
                d = float(v[0])
                if abs(d - HTRANS_NODATA) < 0.05:
                    return None
                return d
        return None

    d = _sample(path)
    if d is not None:
        return d, "primary"
    if fallback_path:
        try:
            d = _sample(fallback_path)
            if d is not None:
                return d, "fallback"
        except Exception as e:
            print(f"  [WARN] Fallback grid error: {e}")
    return None, None


def run_site(site_label, mrk_path, n):
    """
    Run the full datum-chain test for one site.
    Returns the sample list so the fallback comparison can reuse it.
    """
    print("\n" + "#"*80)
    print(f"  SITE: {site_label}")
    print(f"  MRK : {mrk_path}")
    print("#"*80)

    samples, source = read_samples(mrk_path, n)
    if not samples:
        print("  [SKIP] No valid positions found.")
        return []

    print(f"\n{'#':<3} {'lat':>12} {'lon':>12} {'h_ETRS89':>10} {'LN02':>9} {'sep_m':>8} {'delta':>8} {'WRONG':>9} {'CORRECT':>9} {'TRUTH':>9} {'err_wrong':>10} {'err_corr':>9}")
    print("-"*118)
    all_pass = True
    in_coverage = 0
    separations = []
    for i, (lat, lon, h_etrs89) in enumerate(samples):
        E, N, ln02 = wgs84_to_lv95(lon, lat, h_etrs89)
        sep = h_etrs89 - ln02
        separations.append(sep)
        d, _src = grid_delta(lon, lat)
        if d is None:
            print(f"{i+1:<3} {lat:>12.6f} {lon:>12.6f} {h_etrs89:>10.3f} {ln02:>9.3f} {sep:>+8.3f}   [OUT OF HTRANS COVERAGE]")
            continue
        in_coverage += 1
        h_wrong   = ln02     + d    # wrong: LN02 + N (nonsensical)
        h_correct = h_etrs89 - d    # correct: h_ETRS89 - N (both grids store undulation N)
        try:    truth = lv95_to_lhn95(E, N, ln02)
        except Exception as ex: truth = float("nan"); print(f"  [WARN lv95tolhn95] {ex}")
        ew = h_wrong - truth; ec = h_correct - truth
        ok_str = "N/A" if math.isnan(ec) else ("OK" if abs(ec) < 0.05 else "FAIL")
        if not math.isnan(ec) and abs(ec) >= 0.05:
            all_pass = False
        print(f"{i+1:<3} {lat:>12.6f} {lon:>12.6f} {h_etrs89:>10.3f} {ln02:>9.3f} {sep:>+8.3f} {d:>8.4f} {h_wrong:>9.3f} {h_correct:>9.3f} {truth:>9.3f} {ew:>+10.4f} {ec:>+9.4f}  {ok_str}")

    print("\n" + "="*60)
    avg_sep = sum(separations) / len(separations) if separations else 0
    print(f"Ellipsoidal (ETRS89) - Orthometric (LN02) separation: avg = {avg_sep:+.3f} m")
    if in_coverage == 0:
        print(f"[NOTE] All {len(samples)} positions outside htrans coverage (border/south).")
        print("       Use lwf_lens or other central-CH site for ground-truth validation.")
    else:
        verdict = "PASS" if all_pass else "FAIL"
        print(f"\n{verdict} — correct pipeline vs Swisstopo lv95tolhn95 (5 cm tolerance)")

    return samples


def run_grid_comparison(site_label, samples):
    """
    For each sample position print primary (LHN95) vs fallback (EGM2008) heights
    side-by-side so the difference between the two geoids is visible.
    """
    import os as _os
    print("\n" + "="*72)
    print(f"  GRID COMPARISON — {site_label}")
    print(f"  Primary  (LHN95)  : {HTRANS_PATH}")
    fb_exists = _os.path.isfile(HTRANS_FALLBACK)
    print(f"  Fallback (EGM2008): {HTRANS_FALLBACK}  {'[FOUND]' if fb_exists else '[NOT FOUND]'}")
    print("="*72)
    if not fb_exists:
        print("  Fallback file not available. Skipping comparison.")
        return

    print(f"  {'#':<3} {'lat':>12} {'lon':>12} {'h_ETRS89':>10} {'h_LHN95':>9} {'h_EGM2008':>10} {'diff_mm':>9}  source")
    print("  " + "-"*80)
    for i, (lat, lon, h_etrs89) in enumerate(samples):
        # Sample each grid independently so we can always compare them
        N_primary,  _ = grid_delta(lon, lat)                              # primary only
        N_fallback, _ = grid_delta(lon, lat, htrans_path=HTRANS_FALLBACK) # fallback only (no chain)

        h_lhn95   = (h_etrs89 - N_primary)  if N_primary  is not None else float("nan")
        h_egm2008 = (h_etrs89 - N_fallback) if N_fallback is not None else float("nan")

        if math.isnan(h_lhn95) and math.isnan(h_egm2008):
            print(f"  {i+1:<3} {lat:>12.6f} {lon:>12.6f} {h_etrs89:>10.3f}   [both grids: no coverage]")
            continue

        diff_mm = (h_lhn95 - h_egm2008) * 1000 if not (math.isnan(h_lhn95) or math.isnan(h_egm2008)) else float("nan")
        lhn95_str = f"{h_lhn95:>9.3f}"    if not math.isnan(h_lhn95)   else "      N/A"
        egm_str   = f"{h_egm2008:>10.3f}" if not math.isnan(h_egm2008) else "       N/A"
        diff_str  = f"{diff_mm:>+9.1f}"   if not math.isnan(diff_mm)   else "      N/A"
        src = ("both" if N_primary is not None and N_fallback is not None
               else ("primary only" if N_primary is not None else "fallback only"))
        print(f"  {i+1:<3} {lat:>12.6f} {lon:>12.6f} {h_etrs89:>10.3f} {lhn95_str} {egm_str} {diff_str}  {src}")

    print("  (diff_mm = h_LHN95 - h_EGM2008; positive = LHN95 is higher)")


def main():
    for site in TEST_SITES:
        mrk_path = site["mrk"]
        if site.get("is_dir", False):
            mrk_path = find_mrk(mrk_path)
        samples = run_site(site["label"], mrk_path, N_SAMPLES)
        if samples:
            run_grid_comparison(site["label"], samples)

if __name__ == "__main__":
    main()
