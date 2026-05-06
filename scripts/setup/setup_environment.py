#!/usr/bin/env python3
"""
Setup script for drone_metashape toolkit.

Checks system compatibility and guides through the installation process.
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible with Metashape."""
    version = sys.version_info
    print(f"Current Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major != 3:
        print("❌ Error: Python 3 is required")
        return False

    if version.minor < 8:
        print("❌ Error: Python 3.8 or newer is required")
        return False

    if version.minor > 11:
        print("❌ Error: Python 3.12+ is not supported by Metashape 2.1.4")
        print("   Please use Python 3.11 or earlier")
        print("\n💡 Suggestion: Create a conda environment with Python 3.11:")
        print("   conda create -n upscale-drone python=3.11")
        print("   conda activate upscale-drone")
        return False

    print("✅ Python version is compatible")
    return True


def install_dependencies():
    """Install required Python packages."""
    print("\nInstalling dependencies...")
    repo_root = Path(__file__).parent.parent.parent
    req_path = repo_root / "requirements.txt"

    if not req_path.exists():
        print(f"❌ requirements.txt not found at {req_path}")
        return False

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_path)],
            check=True,
        )
        print("✅ Dependencies installed")

        # Install Metashape wheel if present
        wheel_path = repo_root / "wheels" / "Metashape-2.1.4-cp37.cp38.cp39.cp310.cp311-none-win_amd64.whl"
        if wheel_path.exists():
            subprocess.run(
                [sys.executable, "-m", "pip", "install", str(wheel_path)],
                check=True,
            )
            print("✅ Metashape Python API installed from wheel")
        else:
            print("⚠️  Metashape wheel not found — install manually:")
            print("   pip install <path-to-Metashape-wheel.whl>")

        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Installation failed: {e}")
        return False


def test_installation():
    """Test the installation."""
    print("\nTesting installation...")
    try:
        import Metashape  # noqa: F401
        import importlib
        version = importlib.import_module("Metashape").app.version
        print(f"✅ Metashape {version} imported successfully")
        return True
    except ImportError:
        print("⚠️  Metashape not importable — this is expected without a license.")
        print("   Run scripts\\testing\\test_metashape_installation.py for details.")
        return False


def main():
    """Run the setup process."""
    print("=== drone_metashape Setup ===\n")

    if not check_python_version():
        print("\n🛑 Setup cannot continue due to Python version incompatibility.")
        return 1

    if not install_dependencies():
        print("\n🛑 Setup failed during dependency installation.")
        return 1

    test_installation()

    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Ensure you have a valid Metashape Pro license")
    print("2. Run: python scripts\\testing\\test_metashape_installation.py")
    print("3. Follow the usage guide in docs\\USAGE_GUIDE.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
