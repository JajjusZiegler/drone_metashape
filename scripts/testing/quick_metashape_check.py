#!/usr/bin/env python3
"""
Quick Metashape availability check.
"""

import sys


def check_metashape():
    print(f"Python version:    {sys.version}")
    print(f"Python executable: {sys.executable}")

    try:
        import Metashape  # noqa: F401
        print(f"✅ Metashape successfully imported!")
        print(f"   Version: {Metashape.app.version}")
        return True
    except ImportError as e:
        print(f"❌ Metashape import failed: {e}")
        print("\nPossible reasons:")
        print("  1. Metashape wheel not installed")
        print("  2. Wrong Python version (need 3.8-3.11)")
        print("  3. Environment not activated")
        return False


if __name__ == "__main__":
    check_metashape()
