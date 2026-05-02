from setuptools import setup, find_packages
from setuptools.command import egg_info

with open("CLI.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="musren",
    version="1.1.0",
    description="Music file renamer with metadata, lyrics, covers and recognition",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="cosLatte",
    author_email="gabrielpazruiz02@gmail.com",
    url="https://github.com/coslatte/MusRen",
    packages=[
        "constants",
        "core", 
        "core.cli",
        "core.cli.commands", 
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
        "lyrics": ["syncedlyrics>=0.9"],
    },
    entry_points={
        "console_scripts": [
            "musren=app:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)