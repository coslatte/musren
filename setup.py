from setuptools import setup, find_packages
import os

from constants.info import (
    PARSER_DESCRIPTION,
    MUSIC_RENAMER_NAME,
    MUSIC_RENAMER_VERSION,
    MUSIC_RENAMER_DESCRIPTION,
    MUSIC_RENAMER_AUTHOR,
    MUSIC_RENAMER_AUTHOR_EMAIL,
    MUSIC_RENAMER_MAINTAINER,
    MUSIC_RENAMER_MAINTAINER_EMAIL,
    MUSIC_RENAMER_URL,
    MUSIC_RENAMER_KEYWORDS,
    MUSIC_RENAMER_LICENSE,
)

with open("CLI.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name=MUSIC_RENAMER_NAME,
    version=MUSIC_RENAMER_VERSION,
    description=MUSIC_RENAMER_DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=MUSIC_RENAMER_AUTHOR,
    author_email=MUSIC_RENAMER_AUTHOR_EMAIL,
    maintainer=MUSIC_RENAMER_MAINTAINER,
    maintainer_email=MUSIC_RENAMER_MAINTAINER_EMAIL,
    url=MUSIC_RENAMER_URL,
    keywords=MUSIC_RENAMER_KEYWORDS,
    packages=find_packages(where=["."]),
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
        "lyrics": ["syncedlyrics>=0.9"],
        "musicbrainz": ["musicbrainzngs>=0.6"],
    },
    entry_points={
        "console_scripts": [
            "musren=app:main",
            "music-renamer=app:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Music",
    ],
    python_requires=">=3.8",
    zip_safe=False,
)