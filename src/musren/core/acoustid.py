"""AcoustID fingerprint recognition."""

import os
import subprocess

from musren.core.network import check_internet_connection


def recognize_song(file_path: str, acoustid_api_key: str | None, os_type: str):
    """
    Recognizes a song using Chromaprint/AcoustID.

    Args:
        file_path (str): Path to the audio file

    Returns:
        dict: Recognized song information
    """

    if not check_internet_connection():
        return {
            "status": False,
            "message": "No internet connection. Skipping recognition.",
        }

    try:
        # Song recognition (status messages in CLI)

        # Import acoustid
        try:
            import acoustid
        except ImportError:
            return {
                "status": False,
                "message": "The pyacoustid library is not installed. Install it with 'pip install pyacoustid'",
            }

        # Verificar si fpcalc (Chromaprint) está disponible
        # Primero intentamos usar el fpcalc del directorio del proyecto
        # __file__ = core/audio_processor.py
        # dirname(__file__) = core/
        # dirname(dirname(__file__)) = MusRen (project root)
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os_type = os_type

        # Determine executable name based on operating system
        fpcalc_name = "fpcalc.exe" if os_type == "Windows" else "fpcalc"

        # Buscar fpcalc en el directorio actual
        local_fpcalc = os.path.join(script_dir, fpcalc_name)
        if not os.path.exists(local_fpcalc):
            local_fpcalc = os.path.join(os.getcwd(), fpcalc_name)

        try:
            # Try to generate acoustic fingerprint using local or system fpcalc
            if os.path.exists(local_fpcalc):
                # Usar directamente el binario local
                command = [local_fpcalc, "-json", file_path]
                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                try:
                    stdout, stderr = process.communicate(timeout=60)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return {
                        "status": False,
                        "message": "Tiempo de espera agotado al ejecutar fpcalc.",
                    }

                if process.returncode != 0:
                    return {
                        "status": False,
                        "message": f"Error executing fpcalc: {stderr.decode('utf-8', errors='ignore')}",
                    }

                # Parse JSON output
                import json

                result = json.loads(stdout.decode("utf-8", errors="ignore"))
                duration = result.get("duration", 0)
                fingerprint = result.get("fingerprint", "")

                if not fingerprint:
                    return {
                        "status": False,
                        "message": "Could not obtain the acoustic fingerprint of the file.",
                    }
            else:
                # Use standard library function
                duration, fingerprint = acoustid.fingerprint_file(file_path)
        except Exception as e:
            return {
                "status": False,
                "message": f"Could not generate acoustic fingerprint: {str(e)}. Make sure Chromaprint (fpcalc) is installed.",
            }

        # Search for matches in AcoustID database with extended metadata
        try:
            # api_key gratuita para uso general, pero se recomienda que los usuarios obtengan su propia clave
            # Solicitamos más metadatos incluyendo tags, genres, y releases para obtener información completa
            results = acoustid.lookup(
                acoustid_api_key,
                fingerprint,
                duration,
                meta="recordings releasegroups releases tracks artists tags genres",
            )

            # Check for API errors in the response
            if results and results.get("status") == "error":
                error_info = results.get("error", {})
                error_message = error_info.get("message", "Unknown API error")
                error_code = error_info.get("code", "")
                if error_code == 4 or "invalid" in error_message.lower():
                    return {
                        "status": False,
                        "message": "Invalid AcoustID API key. Please get a valid API key at https://acoustid.org/login and use it with the -k option.",
                    }
                return {
                    "status": False,
                    "message": f"AcoustID API error: {error_message}",
                }

            # Process the results
            if results and "results" in results and results["results"]:
                # Obtener el primer resultado con la mayor puntuación
                best_result = results["results"][0]

                # Extraer información del resultado
                if "recordings" in best_result and best_result["recordings"]:
                    recording = best_result["recordings"][0]

                    # Información básica
                    metadata = {
                        "status": True,
                        "score": best_result.get("score", 0),
                        "acoustid": best_result.get("id", ""),
                    }

                    # Extraer artista
                    artists = []
                    if "artists" in recording and recording["artists"]:
                        for artist in recording["artists"]:
                            artists.append(artist["name"])
                        metadata["artist"] = artists[0]
                        metadata["artists"] = artists
                    else:
                        metadata["artist"] = "Artista Desconocido"
                        metadata["artists"] = ["Artista Desconocido"]

                    # Extract title
                    metadata["title"] = recording.get("title", "Unknown Title")

                    # Extract album
                    if "releasegroups" in recording and recording["releasegroups"]:
                        releasegroup = recording["releasegroups"][0]
                        metadata["album"] = releasegroup.get("title", "Unknown Album")

                        # Album artist
                        if "artists" in releasegroup and releasegroup["artists"]:
                            metadata["albumartist"] = releasegroup["artists"][0]["name"]

                        # Album type
                        if "type" in releasegroup:
                            metadata["albumtype"] = releasegroup.get("type")

                        # Release date
                        if "releases" in recording and recording["releases"]:
                            # Search for all releases of this releasegroup
                            matching_releases = [
                                r
                                for r in recording["releases"]
                                if r.get("releasegroup-id") == releasegroup.get("id")
                            ]

                            if matching_releases:
                                release_dates = [
                                    r.get("date")
                                    for r in matching_releases
                                    if r.get("date")
                                ]
                                if release_dates:
                                    # Use the earliest date as album date
                                    metadata["date"] = min(release_dates)
                    else:
                        metadata["album"] = "Unknown Album"

                    # Extract track and disc number
                    if "releases" in recording and recording["releases"]:
                        for release in recording["releases"]:
                            if "mediums" in release:
                                for medium in release["mediums"]:
                                    if "tracks" in medium:
                                        for track in medium["tracks"]:
                                            if track.get("id") == recording.get("id"):
                                                metadata["tracknumber"] = track.get(
                                                    "position", ""
                                                )
                                                metadata["discnumber"] = medium.get(
                                                    "position", ""
                                                )
                                                metadata["totaltracks"] = medium.get(
                                                    "track-count", ""
                                                )
                                                metadata["totaldiscs"] = release.get(
                                                    "medium-count", ""
                                                )

                    # Extract genre
                    genres = []
                    if "genres" in recording:
                        for genre in recording["genres"]:
                            genres.append(genre["name"])
                        if genres:
                            metadata["genre"] = genres[0]
                            metadata["genres"] = genres

                    # Extract additional tags
                    tags = []
                    if "tags" in recording:
                        for tag in recording["tags"]:
                            tags.append(tag["name"])
                        if tags:
                            metadata["tags"] = tags

                    # After extracting metadata, search for album cover using an alternative service
                    if "artist" in metadata and "album" in metadata:
                        try:
                            # Import album art manager
                            from musren.core.artwork import AlbumArtManager

                            art_manager = AlbumArtManager()

                            cover_url = art_manager.fetch_album_cover(
                                metadata["artist"], metadata["album"]
                            )
                            if cover_url:
                                metadata["cover_url"] = cover_url
                        except Exception:
                            # If cover fetching fails, continue without it
                            pass

                    return metadata

            # If no matches were found
            return {
                "status": False,
                "message": "No matches found in the database",
            }

        except acoustid.WebServiceError as e:
            try:
                key = acoustid_api_key or ""
            except Exception:
                key = ""
            if key:
                if len(key) > 8:
                    masked_key = f"{key[:4]}...{key[-4:]}"
                else:
                    masked_key = f"{key[:2]}...{key[-2:]}"
            else:
                masked_key = "(none)"
            message = f"AcoustID web service error: {str(e)} (Key used: {masked_key})"
            if "invalid API key" in str(e):
                message += ". Please get a valid API Key at https://acoustid.org/login and use it with the -k option"
            return {
                "status": False,
                "message": f"AcoustID web service error: {str(e)}",
            }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error recognizing the song: {str(e)}",
        }
