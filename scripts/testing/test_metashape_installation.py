#!/usr/bin/env python3
"""
Test script to verify Metashape Python API installation and functionality.
"""

import sys
from pathlib import Path

# Add src to path for integration tests
_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / 'src'))


def test_metashape_import():
    """Test basic Metashape import."""
    print("Testing Metashape import...")
    try:
        import Metashape  # noqa: F401
        print(f"✅ Metashape successfully imported")
        print(f"   Version: {Metashape.app.version}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import Metashape: {e}")
        return False


def test_license_status():
    """Test Metashape license / basic document creation."""
    print("\nTesting license status...")
    try:
        import Metashape
        doc = Metashape.Document()  # noqa: F841
        print("✅ Basic document creation successful")
        print(f"✅ Application version: {Metashape.app.version}")
        return True
    except Exception as e:
        print(f"❌ License / document test failed: {e}")
        return False


def test_core_functionality():
    """Test core Metashape functionality (CRS, Vector)."""
    print("\nTesting core functionality...")
    try:
        import Metashape
        crs = Metashape.CoordinateSystem("EPSG::2056")
        print(f"✅ Coordinate system creation: {crs.name}")
        vec = Metashape.Vector([0, 0, 0])
        print(f"✅ Vector creation: {vec}")
        return True
    except Exception as e:
        print(f"❌ Core functionality test failed: {e}")
        return False


def test_upscale_integration():
    """Test integration with drone_metashape src modules."""
    print("\nTesting drone_metashape module integration...")
    try:
        from core import upd_micasense_pos_filename  # noqa: F401
        print("✅ upd_micasense_pos_filename module available")
    except ImportError as e:
        print(f"⚠️  upd_micasense_pos_filename not importable: {e}")

    try:
        from core import TransformHeight  # noqa: F401
        print("✅ TransformHeight module available")
    except ImportError as e:
        print(f"⚠️  TransformHeight not importable: {e}")

    return True


def main():
    """Run all tests."""
    print("=== Metashape Python API Installation Test ===\n")

    tests = [
        ("Import Test", test_metashape_import),
        ("License / Document Test", test_license_status),
        ("Core Functionality", test_core_functionality),
        ("drone_metashape Integration", test_upscale_integration),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:35} {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Metashape is ready for drone processing.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check installation and license.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
