"""
Compare metadata parsed by exiftool (via pyexiftool) vs exifread for a single image.

Usage:
  python ExiftoolTester.py --image "M:\working_package_2\2024_dronecampaign\01_data\P1\marteloskop\20251002\DJI_202510021240_003_marteloskopp1mica60m\DJI_20251002124500_0013.JPG"

Notes:
- Requires pyexiftool (already installed per pip command) and exifread.
- exiftool executable is assumed on PATH; override with --exiftool if needed.
"""

import argparse
import json
import os
from pathlib import Path

import exifread
import exiftool


def _resolve_exiftool(exe_override: str | None) -> str | None:
	"""Return a path to exiftool if found; None lets pyexiftool use its default lookup."""
	if exe_override:
		return exe_override

	# Common install locations on Windows
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


def dump_exiftool(image_path: Path, exe_override: str | None = None) -> dict:
	exe = _resolve_exiftool(exe_override)
	kwargs = {"executable": exe} if exe else {}
	try:
		# ExifToolHelper is the modern helper that has get_metadata
		from exiftool import ExifToolHelper

		with ExifToolHelper(**kwargs) as et:
			data_list = et.get_metadata(str(image_path))
		if not data_list:
			return {}
		if isinstance(data_list, list):
			return data_list[0] if data_list else {}
		return data_list or {}
	except FileNotFoundError as e:
		raise FileNotFoundError(
			"exiftool not found. Pass --exiftool PATH or install/add to PATH. "
			"Checked candidates: " + "; ".join([
				exe_override or "(none provided)",
				r"C:\\Program Files\\exiftool-13.03_64\\exiftool.exe",
				r"C:\\Program Files\\exiftool-13.01_64\\exiftool.exe",
				r"C:\\Program Files\\exiftool\\exiftool.exe",
				r"C:\\Program Files (x86)\\exiftool\\exiftool.exe",
			])
		) from e


def dump_exifread(image_path: Path) -> dict:
	with image_path.open("rb") as f:
		tags = exifread.process_file(f, details=True)
	# Convert values to strings for easy printing/comparison
	return {k: str(v) for k, v in tags.items()}


def print_summary(title: str, data: dict, limit: int = 25):
	print(f"\n=== {title} (count={len(data)}) ===")
	shown = 0
	for k in sorted(data.keys()):
		if shown >= limit:
			remaining = len(data) - limit
			if remaining > 0:
				print(f"... ({remaining} more)")
			break
		print(f"{k}: {data[k]}")
		shown += 1


def main():
	ap = argparse.ArgumentParser(description="Compare exiftool vs exifread metadata for one image")
	ap.add_argument("--image", required=True, type=Path, help="Path to image")
	ap.add_argument("--exiftool", type=str, help="Path to exiftool executable (optional)")
	ap.add_argument("--full", action="store_true", help="Print all tags (otherwise show first 25 from each)")
	args = ap.parse_args()

	img = args.image
	if not img.exists():
		raise FileNotFoundError(f"Image not found: {img}")

	exiftool_data = dump_exiftool(img, args.exiftool)
	exifread_data = dump_exifread(img)

	limit = 10**9 if args.full else 25
	print_summary("exiftool tags", exiftool_data, limit=limit)
	print_summary("exifread tags", exifread_data, limit=limit)

	# Show a few key time-related fields if present
	keys_of_interest = [
		"EXIF:DateTimeOriginal",
		"EXIF:SubSecTimeOriginal",
		"EXIF:SubSecTimeDigitized",
		"EXIF:SubSecTime",
		"EXIF:CreateDate",
		"EXIF:ModifyDate",
		"XMP:DateCreated",
		"Composite:SubSecDateTimeOriginal",
		"Composite:SubSecCreateDate",
		"Composite:SubSecModifyDate",
		"MakerNotes:CameraSerialNumber",
		"MakerNotes:FirmwareVersion",
		"File:FileModifyDate",
		"File:FileAccessDate",
		"File:FileInodeChangeDate",
		"EXIF:GPSTimeStamp",
		"EXIF:GPSDateStamp",
		"MakerNotes:AbsoluteAltitude",
		"MakerNotes:RelativeAltitude",
		"MakerNotes:FlightYawDegree",
		"MakerNotes:FlightPitchDegree",
		"MakerNotes:FlightRollDegree",
	]

	print("\n=== Key fields (exiftool) ===")
	for k in keys_of_interest:
		if k in exiftool_data:
			print(f"{k}: {exiftool_data[k]}")

	print("\n=== Key fields (exifread) ===")
	for k in keys_of_interest:
		# exifread keys use section names like "EXIF DateTimeOriginal" without colon
		alt_key = k.replace(":", " ") if ":" in k else k
		if alt_key in exifread_data:
			print(f"{alt_key}: {exifread_data[alt_key]}")


if __name__ == "__main__":
	main()


