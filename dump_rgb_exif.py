"""
List available EXIF/XMP tags from RGB images using exifread.

Usage:
  python dump_rgb_exif.py --rgb-root "M:/path/to/P1/folder" --limit 5

Outputs:
- Unique tag names seen across sampled images with how many files contain each.
- Per sampled image: first few tags and their values (trimmed) for quick inspection.
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import exifread


def find_images(root: Path, limit: int) -> List[Path]:
    patterns = ["**/*.JPG", "**/*.JPEG", "**/*.DNG", "**/*.TIF", "**/*.TIFF"]
    files: List[Path] = []
    for pat in patterns:
        files.extend(root.glob(pat))
    files.sort()
    return files[:limit]


def dump_tags(paths: List[Path], per_file_show: int, show_full_first: bool) -> None:
    tag_freq: Counter = Counter()
    per_file_tags: Dict[str, Dict[str, str]] = {}
    full_first: Dict[str, str] = {}

    for idx, p in enumerate(paths):
        with p.open("rb") as f:
            tags = exifread.process_file(f, details=True)
        per_file_tags[str(p)] = {}
        for k, v in tags.items():
            tag_freq[k] += 1
            if show_full_first and idx == 0:
                full_first[k] = str(v)
            # Store small sample values
            if len(per_file_tags[str(p)]) < per_file_show:
                val = str(v)
                if len(val) > 120:
                    val = val[:117] + "..."
                per_file_tags[str(p)][k] = val

    print("\n=== Tag frequency across sampled images ===")
    for tag, count in tag_freq.most_common():
        print(f"{tag}: {count}/{len(paths)}")

    print("\n=== Sample tag values per file ===")
    for p, tags in per_file_tags.items():
        print(f"\n{p}")
        if not tags:
            print("  (no tags found)")
            continue
        for k, v in tags.items():
            print(f"  {k}: {v}")

    if show_full_first and paths:
        first_path = str(paths[0])
        print(f"\n=== Full tag dump for first image ===\n{first_path}")
        for k in sorted(full_first.keys()):
            print(f"  {k}: {full_first[k]}")


def main():
    ap = argparse.ArgumentParser(description="Inspect available EXIF tags via exifread")
    ap.add_argument("--rgb-root", required=True, type=Path, help="Root folder containing RGB images")
    ap.add_argument("--limit", type=int, default=5, help="Max number of images to sample")
    ap.add_argument("--per-file-show", type=int, default=12, help="Number of tags to show per file")
    ap.add_argument("--full-first", action="store_true", help="Print all tags for the first sampled image")
    args = ap.parse_args()

    paths = find_images(args.rgb_root, args.limit)
    if not paths:
        raise FileNotFoundError(f"No RGB images found under: {args.rgb_root}")

    print(f"Sampling {len(paths)} images (limit={args.limit}) from {args.rgb_root}")
    dump_tags(paths, args.per_file_show, args.full_first)


if __name__ == "__main__":
    main()