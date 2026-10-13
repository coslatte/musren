from setuptools import setup
from pathlib import Path

setup(
    name="musren",
    version="1.3.0",
    description="Music file renamer with metadata, lyrics, covers and recognition",
    long_description=Path(__file__).with_name("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="cosLatte",
    author_email="gabrielpazruiz02@gmail.com",
    url="https://github.com/coslatte/MusRen",
    py_modules=["app"],
    packages=[
        "constants",
        "core",
        "core.cli",
        "core.cli.commands",
        "core.tui",
        "utils",
    ],
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        "mutagen>=1.45",
        "requests>=2.28",
        "typer>=0.9",
        "rich>=13.0",
        "python-dotenv>=0.21",
    ],
    extras_require={
        "recognition": ["pyacoustid>=1.0"],
        "shazam": ["shazamio>=0.6; python_version >= '3.9'"],
        "lyrics": ["syncedlyrics>=0.9"],
        "musicbrainz": ["musicbrainzngs>=0.7.1"],
        "tui": ["textual>=0.85,<1; python_version >= '3.9'"],
    },
    entry_points={
        "console_scripts": [
            "musren=app:main",
            "musren-tui=app:tui",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
