"""Read and write audio metadata across supported formats."""

import os


def update_audio_metadata(file_path, metadata):
    """
    Updates all available metadata in the audio file.

    Args:
        file_path (str): Path to the audio file
        metadata (dict): Metadata to update

    Returns:
        tuple: (success: bool, error: str) or bool for backward compatibility
    """
    try:
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == ".mp3":
            # For MP3 files use ID3
            try:
                from mutagen.id3 import ID3
                from mutagen.id3._frames import (
                    TIT2,
                    TPE1,
                    TALB,
                    TDRC,
                    TCON,
                    TRCK,
                    TPOS,
                    TPE2,
                    TCOM,
                )
            except ImportError:
                return False, "mutagen.id3 not available"

            try:
                tags = ID3(file_path)
            except Exception:
                tags = ID3()

            changed = False

            def update_tag(frame_id, frame_cls, value):
                nonlocal changed
                # Force update to ensure correct encoding (UTF-16 for Windows compatibility)
                tags[frame_id] = frame_cls(encoding=1, text=str(value))
                changed = True

            # Update basic metadata
            if "title" in metadata:
                update_tag("TIT2", TIT2, metadata["title"])
            if "artist" in metadata:
                update_tag("TPE1", TPE1, metadata["artist"])
            if "album" in metadata:
                update_tag("TALB", TALB, metadata["album"])
            if "date" in metadata:
                update_tag("TDRC", TDRC, metadata["date"])
            if "genre" in metadata:
                update_tag("TCON", TCON, metadata["genre"])
            if "tracknumber" in metadata:
                track_value = metadata["tracknumber"]
                if "totaltracks" in metadata:
                    track_value = f"{track_value}/{metadata['totaltracks']}"
                update_tag("TRCK", TRCK, track_value)
            if "discnumber" in metadata:
                disc_value = metadata["discnumber"]
                if "totaldiscs" in metadata:
                    disc_value = f"{disc_value}/{metadata['totaldiscs']}"
                update_tag("TPOS", TPOS, disc_value)
            if "albumartist" in metadata:
                update_tag("TPE2", TPE2, metadata["albumartist"])
            if "composer" in metadata:
                update_tag("TCOM", TCOM, metadata["composer"])

            if changed:
                tags.save(file_path, v2_version=3)

            # If there is a cover URL, download and embed
            if "cover_url" in metadata:
                # Import album art manager
                from musren.core.artwork import AlbumArtManager

                art_manager = AlbumArtManager()

                image_data = art_manager.fetch_cover_image(metadata["cover_url"])
                if image_data:
                    art_manager.embed_album_art(file_path, image_data)

            return True, ""

        elif file_ext in [".flac", ".ogg"]:
            # For FLAC and OGG files
            try:
                from mutagen import File  # type: ignore[attr-defined]
            except ImportError:
                return False, "Mutagen not installed"

            audio = File(file_path)
            if audio is None:
                return False, "Could not open audio file"
            changed = False

            # Field mapping
            field_mapping = {
                "title": "title",
                "artist": "artist",
                "album": "album",
                "date": "date",
                "genre": "genre",
                "tracknumber": "tracknumber",
                "discnumber": "discnumber",
                "albumartist": "albumartist",
                "totaltracks": "totaltracks",
                "totaldiscs": "totaldiscs",
                "composer": "composer",
            }

            # Update metadata
            for meta_key, file_key in field_mapping.items():
                if meta_key in metadata:
                    new_val = str(metadata[meta_key])
                    current_val = audio.get(file_key, [""])[0]
                    if current_val != new_val:
                        audio[file_key] = new_val
                        changed = True

            if changed:
                audio.save()

            # If there is a cover URL, download and embed (only for FLAC)
            if "cover_url" in metadata and file_ext == ".flac":
                # Import album art manager
                from musren.core.artwork import AlbumArtManager

                art_manager = AlbumArtManager()

                image_data = art_manager.fetch_cover_image(metadata["cover_url"])
                if image_data:
                    art_manager.embed_album_art(file_path, image_data)

            return True, ""

        elif file_ext == ".m4a":
            # For M4A/AAC files
            try:
                from mutagen.mp4 import MP4
            except ImportError:
                return False, "Mutagen not installed"

            audio = MP4(file_path)

            # Field mapping for M4A
            field_mapping = {
                "title": "\xa9nam",
                "artist": "\xa9ART",
                "album": "\xa9alb",
                "date": "\xa9day",
                "genre": "\xa9gen",
                "albumartist": "aART",
                "composer": "\xa9wrt",
            }

            changed = False

            # Update metadata
            for meta_key, file_key in field_mapping.items():
                if meta_key in metadata:
                    audio[file_key] = [metadata[meta_key]]
                    changed = True

            # Handle track/disc number for M4A
            if "tracknumber" in metadata:
                try:
                    trkn = int(metadata["tracknumber"])
                    total = int(metadata.get("totaltracks", 0))
                    audio["trkn"] = [(trkn, total)]
                    changed = True
                except ValueError:
                    pass

            if "discnumber" in metadata:
                try:
                    disk = int(metadata["discnumber"])
                    total = int(metadata.get("totaldiscs", 0))
                    audio["disk"] = [(disk, total)]
                    changed = True
                except ValueError:
                    pass

            if changed:
                audio.save()

            # If there is a cover URL, download and embed
            if "cover_url" in metadata:
                # Import album art manager
                from musren.core.artwork import AlbumArtManager

                art_manager = AlbumArtManager()

                image_data = art_manager.fetch_cover_image(metadata["cover_url"])
                if image_data:
                    art_manager.embed_album_art(file_path, image_data)

            return True

        else:
            # For other formats, use generic handling
            try:
                from mutagen._file import File
            except ImportError:
                return False

            audio = File(file_path)
            if audio:
                for key, value in metadata.items():
                    if key in [
                        "status",
                        "score",
                        "cover_url",
                        "tags",
                        "genres",
                        "artists",
                        "acoustid",
                    ]:
                        continue  # Skip metadata that is not for the file
                    if isinstance(value, list):
                        value = value[0] if value else ""
                    audio[key] = value
                audio.save()
                return True

            return False

    except Exception:
        return False
