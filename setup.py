"""Setup script for drone_metashape package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements (skip comment lines)
requirements = []
requirements_path = this_directory / "requirements.txt"
if requirements_path.exists():
    for line in requirements_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            requirements.append(line)

setup(
    name="drone-metashape",
    version="1.0.0",
    author="Jan Ziegler et al.",
    description="RGB and multispectral drone imagery processing with Agisoft Metashape Pro",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JajjusZiegler/drone_metashape",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: GIS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8,<3.12",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.2.0",
            "pytest-cov>=2.12.0",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt"],
    },
)
