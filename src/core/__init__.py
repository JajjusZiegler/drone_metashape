"""
Core processing module.

Contains the main processing scripts:
- batch_processor:               Batch orchestrator (reads CSV, launches metashape_proc_upscale_main.py)
- UpscaleRunScript:              Simpler single-run launcher
- metashape_proc_upscale_main:   Full Metashape processing pipeline (UPSCALE campaigns)
- metashape_proc:                Generic Metashape processing pipeline (TERN/other)
- upd_micasense_pos_filename:    MicaSense position interpolation from filenames
- TransformHeight:               Height/geoid transformation utilities
"""
