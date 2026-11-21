import os
import platform
import concurrent.futures
from typing import Any, Callable, Optional

from musren.utils.audio_files import get_audio_files
from musren.core.jobs import EnrichmentRequest, process_enrichment_file
from musren.core.lyrics_tags import embed_lyrics
from musren.core.audio_metadata import update_audio_metadata
from musren.core.renaming import (
    safe_rename,
    build_target_name as make_rename_target,
    preview_rename,
)


class AudioProcessor:
    """
    Main class for processing audio files: recognition, metadata, synchronized lyrics and album covers.
    """

    def __init__(
        self,
        directory=".",
        acoustid_api_key=None,
        max_workers=4,
        recursive=False,
        use_shazam=False,
    ):
        """
        Initializes the audio processor.

        Args:
            directory (str): Directorio donde se encuentran los archivos de audio
            acoustid_api_key (str): Clave API para AcoustID
            max_workers (int): Número máximo de trabajadores para procesamiento concurrente
        """

        self.directory = os.path.abspath(directory)
        # Si se pasa None, usar la clave por defecto
        self.acoustid_api_key = acoustid_api_key or os.environ.get("ACOUSTID_API_KEY")
        self.max_workers = max_workers
        self.recursive = recursive
        self.os_type = platform.system()
        self.use_shazam = use_shazam
        self.shazam_processor = None

        if self.use_shazam:
            # Reducir concurrencia para Shazam para evitar saturación y timeouts
            # ShazamIO es pesado y sensible a múltiples peticiones simultáneas
            self.max_workers = min(max_workers, 2)

            try:
                from musren.core.shazam_processor import ShazamProcessor

                self.shazam_processor = ShazamProcessor()
            except Exception as error:
                print(f"Unable to initialize Shazam: {error}")
                self.use_shazam = False

    def process_files(
        self,
        use_recognition=False,
        process_lyrics=False,
        fetch_covers=False,
        progress_callback=None,
    ):
        """
        Processes all audio files in the directory.

        Args:
            use_recognition (bool): Si debe usar reconocimiento de audio
            process_lyrics (bool): Si debe procesar letras sincronizadas

        Returns:
            dict: Processing results
        """

        files = get_audio_files(self.directory, recursive=self.recursive)
        results = {}

        if not files:
            return results

        if process_lyrics or use_recognition or fetch_covers:
            results = self._process_files_batch(
                files, use_recognition, process_lyrics, fetch_covers, progress_callback
            )

        return results

    def _process_files_batch(
        self,
        files,
        use_recognition,
        process_lyrics,
        fetch_covers,
        progress_callback=None,
    ):
        """
        Procesa múltiples archivos para añadir letras sincronizadas.

        Args:
            files (list): Lista de archivos a procesar
            use_recognition (bool): Si debe usar reconocimiento de audio

        Returns:
            dict: Processing results
        """

        results = {}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            future_to_file = {
                executor.submit(
                    process_enrichment_file,
                    self,
                    # file is already absolute path from get_audio_files
                    file,
                    EnrichmentRequest(use_recognition, process_lyrics, fetch_covers),
                ): file
                for file in files
            }

            for future in concurrent.futures.as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    result = future.result()
                    results[file] = result
                    if progress_callback:
                        progress_callback(file, result)

                except Exception as e:
                    error_result = {"error": str(e)}
                    results[file] = error_result
                    if progress_callback:
                        progress_callback(file, error_result)

        return results

    def process_file(
        self, file_path, use_recognition, process_lyrics, fetch_covers=False
    ):
        """
        Processes an individual file: recognizes the song and embeds synchronized lyrics.

        Args:
            file_path (str): Path to the audio file
            use_recognition (bool): Whether to use audio recognition
            process_lyrics (bool): Whether to process synchronized lyrics
            fetch_covers (bool): Whether to fetch and download covers

        Returns:
            dict: Processing result
        """

        result = {}

        # Get current metadata
        try:
            from mutagen import File  # type: ignore[attr-defined]
        except ImportError:
            return {
                "status": False,
                "message": "The mutagen library is not installed. Install it with 'pip install mutagen'.",
            }

        audio = File(file_path, easy=True)
        current_artist = (
            audio.get("artist", ["Unknown Artist"])[0] if audio else "Unknown Artist"
        )
        current_title = (
            audio.get("title", ["Unknown Title"])[0] if audio else "Unknown Title"
        )
        current_album = (
            audio.get("album", ["Unknown Album"])[0] if audio else "Unknown Album"
        )

        # Length decides whether a lyrics hit is this recording or a live take.
        try:
            duration = float(audio.info.length) if audio else 0.0
        except (AttributeError, TypeError, ValueError):
            duration = 0.0

        # Initialize variables for metadata tracking
        final_artist = current_artist
        final_title = current_title
        final_album = current_album
        metadata_to_update = {}
        should_update_metadata = False
        artist_for_lyrics = current_artist
        title_for_lyrics = current_title

        # If recognition is requested
        if use_recognition:
            # Use Shazam if configured and available
            if self.use_shazam and self.shazam_processor:
                recognition = self.shazam_processor.recognize(file_path)
            else:
                from musren.core.acoustid import recognize_song

                recognition = recognize_song(
                    file_path, self.acoustid_api_key, self.os_type
                )

            if recognition["status"]:
                result["recognition"] = True
                result["artist"] = recognition.get("artist", "")
                result["title"] = recognition.get("title", "")
                result["album"] = recognition.get("album", "")
                result["score"] = recognition.get("score", 0)

                final_artist = result["artist"]
                final_title = result["title"]
                final_album = result["album"]
                artist_for_lyrics = final_artist
                title_for_lyrics = final_title

                metadata_to_update.update(recognition)
                should_update_metadata = True
            else:
                result["recognition"] = False
                result["recognition_error"] = recognition.get(
                    "message", "Unknown error"
                )
                # If recognition fails, don't update metadata (not even covers)
                should_update_metadata = False

        # If covers were requested, search and add to metadata
        # Only if recognition was NOT requested (use current tags)
        # Or if it was requested AND succeeded (use recognized tags)
        if fetch_covers:
            # Check if artist is "Unknown" in various languages/formats
            unknown_variants = ["unknown artist", "artista desconocido", "unknown"]
            is_unknown = any(v in str(final_artist).lower() for v in unknown_variants)

            if (not use_recognition) or (
                use_recognition and result.get("recognition", False)
            ):
                if final_artist and final_album and not is_unknown:
                    try:
                        from musren.core.artwork import AlbumArtManager

                        art_manager = AlbumArtManager()
                        cover_url = art_manager.fetch_album_cover(
                            final_artist, final_album
                        )
                        if cover_url:
                            metadata_to_update["cover_url"] = cover_url
                            should_update_metadata = True
                    except Exception as e:
                        result["cover_error"] = str(e)

        # Update complete file metadata if needed
        if should_update_metadata:
            update_result = update_audio_metadata(file_path, metadata_to_update)
            # Handle both tuple and bool return types
            if isinstance(update_result, tuple):
                update_success, update_error = update_result
            else:
                update_success = update_result
                update_error = ""
            result["metadata_updated"] = update_success
            if not update_success and update_error:
                result["metadata_error"] = update_error

        # Search for synchronized lyrics only if requested
        if process_lyrics:
            lyrics_result = self._fetch_synced_lyrics(
                artist_for_lyrics, title_for_lyrics, final_album, duration
            )

            if lyrics_result["status"]:
                result["lyrics_found"] = True
                # Embed lyrics in the file
                if embed_lyrics(file_path, lyrics_result["lyrics"]):
                    result["lyrics_embedded"] = True
                else:
                    result["lyrics_embedded"] = False
                    result["embed_error"] = "Error embedding lyrics"
            else:
                result["lyrics_found"] = False
                result["lyrics_error"] = lyrics_result.get("message", "Unknown error")

        return result

    def _fetch_synced_lyrics(self, artist, title, album="", duration=0.0):
        """
        Searches for synchronized lyrics through the provider chain.

        Args:
            artist (str): Artist name
            title (str): Song title
            album (str): Album name, narrows the LRCLib lookup
            duration (float): Track length in seconds, rejects another recording

        Returns:
            dict: Synchronized lyrics or error message
        """
        from musren.core.lyrics import fetch_lyrics

        lrc_content, provider = fetch_lyrics(artist, title, album, duration)

        if lrc_content:
            return {"status": True, "lyrics": lrc_content, "provider": provider}

        return {"status": False, "message": "No synchronized lyrics found"}

    def _read_rename_metadata(
        self,
        files: list[str],
        scan_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[Optional[dict[str, Optional[dict[str, Any]]]], dict[str, int]]:
        try:
            from mutagen import File
        except ImportError:
            return None, {}

        album_counts: dict[str, int] = {}
        file_metadata: dict[str, Optional[dict[str, Any]]] = {}
        for file_path in files:
            if scan_callback:
                scan_callback(file_path)
            try:
                audio = File(file_path, easy=True)
                if not audio or not audio.tags:
                    file_metadata[file_path] = None
                    continue

                artist = audio.get("artist", [""])[0]
                title = audio.get("title", [""])[0]
                album = audio.get("album", [""])[0]
                tracknumber = audio.get("tracknumber", [""])[0]
                if (
                    not artist
                    or not title
                    or artist == "Unknown Artist"
                    or title == "Unknown Title"
                ):
                    file_metadata[file_path] = None
                    continue

                album_label = (
                    album.strip() if album and album.strip() else "__no_album__"
                )
                album_counts[album_label] = album_counts.get(album_label, 0) + 1
                file_metadata[file_path] = {
                    "artist": artist,
                    "title": title,
                    "album": album_label,
                    "tracknumber": tracknumber,
                }
            except Exception:
                file_metadata[file_path] = None
        return file_metadata, album_counts

    def preview_rename_files(
        self,
        rename_format: str = "1",
        scan_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> list[dict[str, Any]]:
        """Return rename changes without modifying files."""
        files = get_audio_files(directory=self.directory, recursive=self.recursive)
        scanned = 0

        def report_scan(path: str) -> None:
            nonlocal scanned
            scanned += 1
            if scan_callback:
                scan_callback(path, scanned, len(files))

        file_metadata, album_counts = self._read_rename_metadata(files, report_scan)
        if file_metadata is None:
            raise RuntimeError("The mutagen library is not installed.")

        reserved_paths: set[str] = set()
        preview: list[dict[str, Any]] = []
        for file_path in files:
            metadata = file_metadata.get(file_path)
            if metadata is None:
                preview.append(
                    {
                        "path": file_path,
                        "current_name": os.path.basename(file_path),
                        "target_path": None,
                        "build_target_name": None,
                        "action": "skipped",
                        "reason": "Missing or unreadable metadata.",
                    }
                )
                continue

            build_target_name = make_rename_target(
                file_path, metadata, album_counts, rename_format
            )
            target_path, action, reason = preview_rename(
                self.os_type, file_path, build_target_name, reserved_paths
            )
            if action == "rename":
                reserved_paths.add(os.path.normcase(target_path))
            preview.append(
                {
                    "path": file_path,
                    "current_name": os.path.basename(file_path),
                    "target_path": target_path,
                    "build_target_name": os.path.basename(target_path),
                    "action": action,
                    "reason": reason,
                }
            )
        return preview

    def rename_files(
        self,
        progress_callback: Optional[Callable[[str, dict[str, Any]], None]] = None,
        rename_format: str = "1",
        scan_callback: Optional[Callable[[str], None]] = None,
    ) -> dict[str, str]:
        """Rename audio files from their tags and return reversible changes."""
        files = get_audio_files(directory=self.directory, recursive=self.recursive)
        changes: dict[str, str] = {}
        file_metadata, album_counts = self._read_rename_metadata(files, scan_callback)
        if file_metadata is None:
            for file_path in files:
                if progress_callback:
                    progress_callback(
                        file_path, {"status": False, "error": "Mutagen missing"}
                    )
            return changes

        for file_path in files:
            try:
                metadata = file_metadata.get(file_path)
                if metadata is None:
                    if progress_callback:
                        progress_callback(
                            file_path,
                            {
                                "status": False,
                                "skipped": True,
                                "reason": "Missing metadata",
                            },
                        )
                    continue

                new_name = make_rename_target(
                    file_path, metadata, album_counts, rename_format
                )
                actual_new_path, changed, error = safe_rename(
                    self.directory, self.os_type, file_path, new_name
                )
                if error:
                    if progress_callback:
                        progress_callback(file_path, {"status": False, "error": error})
                elif changed:
                    changes[actual_new_path] = file_path
                    if progress_callback:
                        progress_callback(
                            file_path,
                            {
                                "status": True,
                                "renamed": True,
                                "new_name": os.path.basename(actual_new_path),
                            },
                        )
                elif progress_callback:
                    progress_callback(
                        file_path,
                        {
                            "status": True,
                            "renamed": False,
                            "reason": "No change needed",
                        },
                    )
            except Exception as error:
                if progress_callback:
                    progress_callback(file_path, {"status": False, "error": str(error)})

        return changes

    def undo_rename(self, changes: dict, progress_callback=None):
        """
        Reverts file renames.

        Args:
            changes (dict): {new_absolute_path: old_absolute_path}
            progress_callback (callable): Function to call upon completing each file
        """
        for new_path, old_path in changes.items():
            try:
                if os.path.exists(new_path):
                    if not os.path.exists(old_path):
                        os.rename(new_path, old_path)
                        if progress_callback:
                            progress_callback(
                                new_path, {"status": True, "restored": True}
                            )
                    else:
                        if progress_callback:
                            progress_callback(
                                new_path, {"status": False, "error": "Target exists"}
                            )
                else:
                    if progress_callback:
                        progress_callback(
                            new_path, {"status": False, "error": "Source missing"}
                        )
            except Exception as e:
                if progress_callback:
                    progress_callback(new_path, {"status": False, "error": str(e)})
