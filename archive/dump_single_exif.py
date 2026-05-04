"""
Dump all metadata tags available via exifread for a single image.

Usage:
  python dump_single_exif.py --image "M:\working_package_2\2024_dronecampaign\01_data\P1\marteloskop\20251002\DJI_202510021240_003_marteloskopp1mica60m\DJI_20251002124500_0013.JPG"
"""

import argparse
from pathlib import Path

import exifread


def main():
    ap = argparse.ArgumentParser(description="Dump all EXIF/XMP tags for one image")
    ap.add_argument("--image", required=True, type=Path, help="Path to the image file")
    args = ap.parse_args()

    if not args.image.exists():
        raise FileNotFoundError(f"Image not found: {args.image}")

    with args.image.open("rb") as f:
        tags = exifread.process_file(f, details=True)

    print(f"Tags found: {len(tags)}\n")
    for key in sorted(tags.keys()):
        print(f"{key}: {tags[key]}")


if __name__ == "__main__":
    main()