"""
tests/test_setup_paths.py
=========================
Setup path validation test for drone_metashape.

Checks that the expected directory structure and key files exist after the
repository has been cloned / restructured.  No Metashape installation or
real drone data is required — this test is purely structural.

Run with:
    python tests/test_setup_paths.py
or via pytest:
    pytest tests/test_setup_paths.py -v
"""

import sys
import unittest
from pathlib import Path

# Repo root is two levels up from this file (tests/ → repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _check(paths: list[str]) -> tuple[list[str], list[str]]:
    """Return (found, missing) lists for the given relative paths."""
    found, missing = [], []
    for rel in paths:
        p = REPO_ROOT / rel
        if p.exists():
            found.append(rel)
        else:
            missing.append(rel)
    return found, missing


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestRootFiles(unittest.TestCase):
    """Root-level files that must exist."""

    def test_readme(self):
        self.assertTrue((REPO_ROOT / "README.md").exists(), "README.md missing")

    def test_requirements(self):
        self.assertTrue((REPO_ROOT / "requirements.txt").exists(), "requirements.txt missing")

    def test_setup_py(self):
        self.assertTrue((REPO_ROOT / "setup.py").exists(), "setup.py missing")

    def test_gitignore(self):
        self.assertTrue((REPO_ROOT / ".gitignore").exists(), ".gitignore missing")


class TestSrcCore(unittest.TestCase):
    """src/core/ must contain all main processing scripts."""

    EXPECTED = [
        "src/core/__init__.py",
        "src/core/batch_processor.py",
        "src/core/UpscaleRunScript.py",
        "src/core/metashape_proc_upscale_main.py",
        "src/core/metashape_proc.py",
        "src/core/upd_micasense_pos_filename.py",
        "src/core/TransformHeight.py",
    ]

    def test_files_present(self):
        _, missing = _check(self.EXPECTED)
        self.assertEqual(missing, [], f"Missing files in src/core: {missing}")


class TestSrcProjectManagement(unittest.TestCase):
    """src/project_management/ must contain project-creation scripts."""

    EXPECTED = [
        "src/project_management/__init__.py",
        "src/project_management/CreateProjectsUpscale.py",
        "src/project_management/CreateMultispectralProjects.py",
        "src/project_management/UpscaleProjectCreation2025.py",
        "src/project_management/UpscaleProjectCreation_ExtraMode.py",
        "src/project_management/initiate_project.py",
        "src/project_management/validate_projects.py",
        "src/project_management/OpenProjectsfromCSV.py",
    ]

    def test_files_present(self):
        _, missing = _check(self.EXPECTED)
        self.assertEqual(missing, [], f"Missing files in src/project_management: {missing}")


class TestSrcUtilities(unittest.TestCase):
    """src/utilities/ must contain helper / position-update scripts."""

    EXPECTED = [
        "src/utilities/__init__.py",
        "src/utilities/InterpolateCameraPositions.py",
        "src/utilities/upd_micasense_pos.py",
        "src/utilities/upd_micasense_pos_from_chunk.py",
        "src/utilities/ret_micasense_pos_exiftool.py",
        "src/utilities/LocatePanels.py",
        "src/utilities/UpscaleMultispecProcessing.py",
    ]

    def test_files_present(self):
        _, missing = _check(self.EXPECTED)
        self.assertEqual(missing, [], f"Missing files in src/utilities: {missing}")


class TestSrcMicasense(unittest.TestCase):
    """src/micasense/ must contain the MicaSense library."""

    EXPECTED = [
        "src/micasense/__init__.py",
        "src/micasense/capture.py",
        "src/micasense/image.py",
        "src/micasense/imageset.py",
        "src/micasense/imageutils.py",
        "src/micasense/metadata.py",
        "src/micasense/panel.py",
        "src/micasense/dls.py",
        "src/micasense/utils.py",
    ]

    def test_files_present(self):
        _, missing = _check(self.EXPECTED)
        self.assertEqual(missing, [], f"Missing files in src/micasense: {missing}")


class TestDocs(unittest.TestCase):
    """docs/ must contain documentation files."""

    EXPECTED = [
        "docs/USAGE_GUIDE.md",
        "docs/METASHAPE_INSTALLATION.md",
        "docs/metashape_python_api_2_1_0.pdf",
        "docs/EXTRA_MODE_README.md",
        "docs/QUICK_REFERENCE_EXTRA_MODE.md",
        "docs/ROBUST_PROJECT_TOOLS_README.md",
        "docs/UPSCALE_PROJECT_CREATION_EXTRAMODE_README.md",
    ]

    def test_files_present(self):
        _, missing = _check(self.EXPECTED)
        self.assertEqual(missing, [], f"Missing files in docs/: {missing}")


class TestScripts(unittest.TestCase):
    """scripts/ must contain setup and testing helpers."""

    EXPECTED = [
        "scripts/README.md",
        "scripts/setup/setup_environment.py",
        "scripts/setup/setup_conda_env.bat",
        "scripts/setup/setup_conda_env.ps1",
        "scripts/setup/install_metashape.bat",
        "scripts/setup/activate_environment.ps1",
        "scripts/testing/test_metashape_installation.py",
        "scripts/testing/quick_metashape_check.py",
        "scripts/testing/metashape_proc_widget_testing.py",
        "scripts/testing/run_tests_with_metashape.bat",
        "scripts/testing/final_test.bat",
        "scripts/testing/confirm_success.bat",
    ]

    def test_files_present(self):
        _, missing = _check(self.EXPECTED)
        self.assertEqual(missing, [], f"Missing files in scripts/: {missing}")


class TestExamples(unittest.TestCase):
    """examples/ must contain example scripts."""

    EXPECTED = [
        "examples/metashape_blockshift.py",
        "examples/metashape_proc_p1.py",
    ]

    def test_files_present(self):
        _, missing = _check(self.EXPECTED)
        self.assertEqual(missing, [], f"Missing files in examples/: {missing}")


class TestSysPathFixes(unittest.TestCase):
    """Verify that sys.path inserts are present in scripts that need them."""

    def _file_contains(self, rel_path: str, text: str) -> bool:
        p = REPO_ROOT / rel_path
        return p.exists() and text in p.read_text(encoding="utf-8", errors="ignore")

    def test_metashape_proc_upscale_main_has_path_insert(self):
        self.assertTrue(
            self._file_contains(
                "src/core/metashape_proc_upscale_main.py",
                "sys.path.insert(0, str(Path(__file__).parent))",
            ),
            "metashape_proc_upscale_main.py is missing sys.path.insert for sibling imports",
        )

    def test_interpolate_cameras_has_path_insert(self):
        self.assertTrue(
            self._file_contains(
                "src/utilities/InterpolateCameraPositions.py",
                "sys.path.insert",
            ),
            "InterpolateCameraPositions.py is missing sys.path.insert for src/core",
        )

    def test_batch_processor_uses_relative_target_path(self):
        self.assertTrue(
            self._file_contains(
                "src/core/batch_processor.py",
                "Path(__file__).parent",
            ),
            "batch_processor.py TARGET_SCRIPT_PATH should use Path(__file__).parent, not a hardcoded absolute path",
        )

    def test_upscale_run_script_uses_relative_target_path(self):
        self.assertTrue(
            self._file_contains(
                "src/core/UpscaleRunScript.py",
                "Path(__file__).parent",
            ),
            "UpscaleRunScript.py target_script_path should use Path(__file__).parent",
        )


# ---------------------------------------------------------------------------
# Main: run all tests and print a human-readable summary
# ---------------------------------------------------------------------------

def main():
    print("drone_metashape — Setup Path Validation")
    print("=" * 50)
    print(f"Repository root: {REPO_ROOT}\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestRootFiles,
        TestSrcCore,
        TestSrcProjectManagement,
        TestSrcUtilities,
        TestSrcMicasense,
        TestDocs,
        TestScripts,
        TestExamples,
        TestSysPathFixes,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 50)
    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed

    print(f"Tests run  : {total}")
    print(f"Passed     : {passed}")
    print(f"Failed     : {failed}")

    if failed == 0:
        print("\n✅ All path checks passed — repository structure is correct!")
        return 0
    else:
        print("\n❌ Some path checks failed — review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
