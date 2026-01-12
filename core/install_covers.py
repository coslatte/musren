#!/usr/bin/env python
"""
Script to add album covers to existing music files.
Uses the encapsulated music_renamer library classes.
"""

import os
import concurrent.futures
from core.artwork import AlbumArtManager
from utils.tools import get_audio_files


def process_file(file_path, art_manager):
    """Processes an individual file by adding album cover."""
    try:
        # Get current metadata
        try:
            from mutagen import File  # type: ignore[attr-defined]
        except ImportError:
            return {
                "status": False,
                "error": "The mutagen library is not installed.",
            }

        audio = File(file_path, easy=True)
        if not audio:
            return {"status": False, "error": "Could not read metadata"}

        artist = (
            audio.get("artist", ["Unknown Artist"])[0]
            if "artist" in audio
            else "Unknown Artist"
        )
        album = (
            audio.get("album", ["Unknown Album"])[0]
            if "album" in audio
            else "Unknown Album"
        )

        # Check if the file already has cover
        has_cover = False
        if file_path.lower().endswith(".mp3"):
            from mutagen.id3 import ID3

            try:
                tags = ID3(file_path)
                has_cover = any(frame.startswith("APIC") for frame in tags.keys())
            except Exception:
                has_cover = False
        elif file_path.lower().endswith(".flac"):
            from mutagen.flac import FLAC

            try:
                audio = FLAC(file_path)
                has_cover = len(audio.pictures) > 0
            except Exception:
                has_cover = False
        elif file_path.lower().endswith(".m4a"):
            from mutagen.mp4 import MP4

            try:
                audio = MP4(file_path)
                has_cover = "covr" in audio
            except Exception:
                has_cover = False

        # If it already has cover, inform and skip
        if has_cover:
            return {
                "status": True,
                "message": "File already has cover",
                "skipped": True,
            }

        # Search for cover
        cover_url = art_manager.fetch_album_cover(artist, album)

        if not cover_url:
            return {"status": False, "error": "No cover found"}

        # Download and embed cover
        image_data = art_manager.fetch_cover_image(cover_url)
        if not image_data:
            return {"status": False, "error": "Could not download cover"}

        if art_manager.embed_album_art(file_path, image_data):
            return {"status": True, "message": "Cover embedded successfully"}
        else:
            return {"status": False, "error": "Error embedding cover"}

    except Exception as e:
        return {"status": False, "error": str(e)}


def run(directory: str, max_workers: int = 4, progress_callback=None) -> dict:
    """Runs the cover installation process without using argparse.

    Designed to be called from other parts of the code (e.g., Typer CLI)
    without argument conflicts.
    """
    directory = os.path.abspath(directory)

    # Get audio files
    files = get_audio_files(directory)
    if not files:
        return {"success": 0, "skipped": 0, "failed": 0, "total": 0}

    # Create cover manager
    art_manager = AlbumArtManager()

    # Process files in parallel
    results = {"success": 0, "skipped": 0, "failed": 0, "total": len(files)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(process_file, file, art_manager): file for file in files
        }

        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                if result["status"]:
                    if result.get("skipped"):
                        results["skipped"] += 1
                    else:
                        results["success"] += 1
                else:
                    results["failed"] += 1

                if progress_callback:
                    progress_callback(file, result)

            except Exception as e:
                results["failed"] += 1
                if progress_callback:
                    progress_callback(file, {"status": False, "error": str(e)})

    return results
