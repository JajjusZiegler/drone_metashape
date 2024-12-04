
import argparse
import os
from upd_micasense_pos_custom import ret_micasense_pos

def main():
    parser = argparse.ArgumentParser(description="Debug script for ret_micasense_pos function")
    parser.add_argument('-mrk', help='Path to P1 MRK files', required=True)
    parser.add_argument('-micasense', help='Path to MicaSense images', required=True)
    parser.add_argument('-suffix', help='File suffix for MicaSense master band images', required=True)
    parser.add_argument('-epsg', help='EPSG code for projected coordinate system', required=True)
    parser.add_argument('-output', help='Path and name of output CSV file', required=True)
    parser.add_argument('-shift', help='Vector to blockshift P1 positions (comma-separated)', default="0.0,0.0,0.0")
    
    args = parser.parse_args()
    
    P1_shift_vec = [float(x) for x in args.shift.split(',')]
    
    if not os.path.isdir(args.mrk):
        raise FileNotFoundError(f"The directory {args.mrk} does not exist.")
    
    if not os.path.isdir(args.micasense):
        raise FileNotFoundError(f"The directory {args.micasense} does not exist.")
    
    ret_micasense_pos(args.mrk, args.micasense, args.suffix, args.epsg, args.output, P1_shift_vec)
    print(f"Output written to {args.output}")

if __name__ == "__main__":
    main()