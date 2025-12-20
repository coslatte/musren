import os
import re
import platform
import concurrent.futures
import subprocess

from utils.tools import get_audio_files

try:
    from core.shazam_processor import ShazamProcessor
except ImportError:
    ShazamProcessor = None


class AudioProcessor:
    """
    Clase principal para procesar archivos de audio: reconocimiento,
    metadatos, letras sincronizadas y portadas de álbum.
    """

    def __init__(
        self,
        directory=".",
        acoustid_api_key="8XaBELgH",
        max_workers=4,
        recursive=False,
        use_shazam=False,
    ):
        """
        Inicializa el procesador de audio.

        Args:
            directory (str): Directorio donde se encuentran los archivos de audio
            acoustid_api_key (str): Clave API para AcoustID
            max_workers (int): Número máximo de trabajadores para procesamiento concurrente
            recursive (bool): Si buscar en subdirectorios
            use_shazam (bool): Si usar Shazam en lugar de AcoustID
        """

        self.directory = os.path.abspath(directory)
        # Si se pasa None, usar la clave por defecto
        self.acoustid_api_key = acoustid_api_key if acoustid_api_key else "8XaBELgH"
        self.max_workers = max_workers
        self.recursive = recursive
        self.os_type = platform.system()
        self.use_shazam = use_shazam
        self.shazam_processor = None

        if self.use_shazam:
            # Reducir concurrencia para Shazam para evitar saturación y timeouts
            # ShazamIO es pesado y sensible a múltiples peticiones simultáneas
            self.max_workers = min(max_workers, 2)

            if ShazamProcessor:
                try:
                    self.shazam_processor = ShazamProcessor()
                except Exception as e:
                    print(f"Error inicializando Shazam: {e}")
                    self.use_shazam = False
            else:
                print("Advertencia: ShazamProcessor no disponible (instala shazamio).")
                self.use_shazam = False

    def process_files(
        self,
        use_recognition=False,
        process_lyrics=False,
        fetch_covers=False,
        progress_callback=None,
    ):
        """
        Procesa todos los archivos de audio en el directorio.

        Args:
            use_recognition (bool): Si debe usar reconocimiento de audio
            process_lyrics (bool): Si debe procesar letras sincronizadas
            fetch_covers (bool): Si debe buscar y descargar portadas
            progress_callback (callable): Función a llamar al completar cada archivo (recibe el archivo y el resultado)

        Returns:
            dict: Resultados del procesamiento
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
        Procesa múltiples archivos para reconocimiento y/o letras.

        Args:
            files (list): Lista de archivos a procesar
            use_recognition (bool): Si debe usar reconocimiento de audio
            process_lyrics (bool): Si debe procesar letras sincronizadas
            fetch_covers (bool): Si debe buscar y descargar portadas
            progress_callback (callable): Callback de progreso

        Returns:
            dict: Resultados del procesamiento
        """

        results = {}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            future_to_file = {
                executor.submit(
                    self._process_file,
                    # file is already absolute path from get_audio_files
                    file,
                    use_recognition,
                    process_lyrics,
                    fetch_covers,
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

    def _process_file(
        self, file_path, use_recognition, process_lyrics, fetch_covers=False
    ):
        """
        Procesa un archivo individual: reconoce la canción y/o le incrusta letras sincronizadas.

        Args:
            file_path (str): Ruta al archivo de audio
            use_recognition (bool): Si debe usar reconocimiento de audio
            process_lyrics (bool): Si debe procesar letras sincronizadas
            fetch_covers (bool): Si debe buscar y descargar portadas

        Returns:
            dict: Resultado del procesamiento
        """

        result = {}

        # Obtener metadatos actuales
        try:
            from mutagen import File  # type: ignore[attr-defined]
        except ImportError:
            return {
                "status": False,
                "message": "La biblioteca mutagen no está instalada. Instálela con 'pip install mutagen'.",
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

        final_artist = current_artist
        final_title = current_title
        final_album = current_album

        metadata_to_update = {}
        should_update_metadata = False

        if use_recognition:
            # Implementar la lógica de reconocimiento aquí
            if self.use_shazam and self.shazam_processor:
                recognition = self.shazam_processor.recognize(file_path)
            else:
                recognition = self._recognize_song(file_path)

            if recognition["status"]:
                result["recognition"] = True
                result["artist"] = recognition.get("artist", "")
                result["title"] = recognition.get("title", "")
                result["album"] = recognition.get("album", "")
                result["score"] = recognition.get("score", 0)

                final_artist = result["artist"]
                final_title = result["title"]
                final_album = result["album"]

                metadata_to_update.update(recognition)
                should_update_metadata = True
            else:
                result["recognition"] = False
                result["recognition_error"] = recognition.get(
                    "message", "Error desconocido"
                )
                # Si falla el reconocimiento, NO actualizamos metadatos (ni siquiera portadas)
                # a menos que no se haya pedido reconocimiento.
                should_update_metadata = False

        # Si se solicitó portada, buscarla y añadirla a los metadatos
        # Solo si NO se pidió reconocimiento (usamos tags actuales)
        # O si se pidió Y tuvo éxito (usamos tags reconocidos)
        if fetch_covers:
            # Verificar si el artista es "Desconocido" en varios idiomas/formatos
            unknown_variants = ["unknown artist", "artista desconocido", "unknown"]
            is_unknown = any(v in str(final_artist).lower() for v in unknown_variants)

            if (not use_recognition) or (
                use_recognition and result.get("recognition", False)
            ):
                if final_artist and final_album and not is_unknown:
                    try:
                        from core.artwork import AlbumArtManager

                        art_manager = AlbumArtManager()
                        cover_url = art_manager.fetch_album_cover(
                            final_artist, final_album
                        )
                        if cover_url:
                            metadata_to_update["cover_url"] = cover_url
                            should_update_metadata = True
                    except Exception:
                        pass

        # Actualizar metadatos completos del archivo si es necesario
        if should_update_metadata:
            update_success, update_error = self._update_audio_metadata(
                file_path, metadata_to_update
            )
            result["metadata_updated"] = update_success
            if not update_success:
                result["metadata_error"] = update_error

        # Buscar letras sincronizadas solo si se solicita
        # Usamos los mejores metadatos disponibles (reconocidos o actuales)
        if process_lyrics:
            lyrics_result = self._fetch_synced_lyrics(final_artist, final_title)

            if lyrics_result["status"]:
                result["lyrics_found"] = True
                # Incrustar letras en el archivo
                if self._embed_lyrics(file_path, lyrics_result["lyrics"]):
                    result["lyrics_embedded"] = True
                else:
                    result["lyrics_embedded"] = False
                    result["embed_error"] = "Error al incrustar letras"
            else:
                result["lyrics_found"] = False
                result["lyrics_error"] = lyrics_result.get(
                    "message", "Error desconocido"
                )

        return result

    def _recognize_song(self, file_path):
        """
        Reconoce una canción utilizando Chromaprint/AcoustID.

        Args:
            file_path (str): Ruta al archivo de audio

        Returns:
            dict: Información de la canción reconocida
        """

        try:
            # Reconocimiento de canción (mensajes de estado en CLI)

            # Importar acoustid
            try:
                import acoustid
            except ImportError:
                return {
                    "status": False,
                    "message": "La biblioteca pyacoustid no está instalada. Instálela con 'pip install pyacoustid'",
                }

            # Verificar si fpcalc (Chromaprint) está disponible
            # Primero intentamos usar el fpcalc del directorio actual
            # __file__ = core/audio_processor.py
            # dirname = core
            # dirname = MusRen (root)
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            os_type = self.os_type

            # Determinar el nombre del ejecutable según el sistema operativo
            fpcalc_name = "fpcalc.exe" if os_type == "Windows" else "fpcalc"

            # Buscar fpcalc en el directorio del proyecto o en el directorio actual de trabajo
            local_fpcalc = os.path.join(script_dir, fpcalc_name)
            if not os.path.exists(local_fpcalc):
                local_fpcalc = os.path.join(os.getcwd(), fpcalc_name)

            try:
                # Intentar generar la huella acústica usando el fpcalc local o del sistema
                if os.path.exists(local_fpcalc):
                    # Configurar la variable de entorno para que acoustid lo encuentre si usamos la librería
                    os.environ["FPCALC"] = local_fpcalc

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
                            "message": f"Error al ejecutar fpcalc: {stderr.decode('utf-8', errors='ignore')}",
                        }

                    # Parsear la salida JSON
                    import json

                    result = json.loads(stdout.decode("utf-8", errors="ignore"))
                    duration = result.get("duration", 0)
                    fingerprint = result.get("fingerprint", "")

                    if not fingerprint:
                        return {
                            "status": False,
                            "message": "No se pudo obtener la huella acústica del archivo.",
                        }
                else:
                    # Usar la función estándar de la biblioteca
                    duration, fingerprint = acoustid.fingerprint_file(file_path)
            except Exception as e:
                return {
                    "status": False,
                    "message": f"No se pudo generar la huella acústica: {str(e)}. Asegúrese de que Chromaprint (fpcalc) esté instalado.",
                }

            # Buscar coincidencias en la base de datos de AcoustID con metadatos extendidos
            try:
                # api_key gratuita para uso general, pero se recomienda que los usuarios obtengan su propia clave
                # Solicitamos más metadatos incluyendo tags, genres, y releases para obtener información completa

                results = acoustid.lookup(
                    self.acoustid_api_key,
                    fingerprint,
                    duration,
                    meta="recordings releasegroups releases tracks artists tags genres",
                )

                # Procesar los resultados
                if results and "results" in results and results["results"]:
                    selected_result = None
                    selected_recording = None

                    # Estrategia unificada: Buscar el mejor candidato basado en puntuación y calidad de metadatos
                    best_score = -float("inf")

                    for result in results["results"]:
                        acoustid_score = result.get("score", 0)
                        # Restaurar umbral estricto de confianza (80%)
                        if acoustid_score < 0.8:
                            continue

                        if "recordings" in result:
                            for rec in result["recordings"]:
                                # Calcular puntuación base (0-100)
                                candidate_score = acoustid_score * 100

                                # Validación de duración (Penalización fuerte si difiere)
                                if "duration" in rec:
                                    diff = abs(duration - rec["duration"])
                                    if diff > 15:
                                        # Diferencia muy grande: penalización severa
                                        candidate_score -= 50
                                    elif diff > 5:
                                        # Diferencia notable: penalización moderada
                                        candidate_score -= 10
                                else:
                                    # Sin duración: penalización leve
                                    candidate_score -= 5

                                # Verificar metadatos (Deep Search)
                                has_artist = "artists" in rec and rec["artists"]

                                # Búsqueda profunda de título si no está en la grabación
                                rec_title = rec.get("title")
                                if not rec_title and "releases" in rec:
                                    for rel in rec["releases"]:
                                        if "mediums" in rel:
                                            for med in rel["mediums"]:
                                                if "tracks" in med:
                                                    for trk in med["tracks"]:
                                                        if "title" in trk:
                                                            rec_title = trk["title"]
                                                            break
                                                if rec_title:
                                                    break
                                        if rec_title:
                                            break

                                has_title = bool(rec_title)

                                has_album = (
                                    "releasegroups" in rec and rec["releasegroups"]
                                )

                                # Bonificaciones pequeñas para desempatar (nunca superar una diferencia de score real)
                                if has_artist:
                                    candidate_score += 5
                                if has_title:
                                    candidate_score += 5
                                if has_album:
                                    candidate_score += 2

                                # Preferir resultados con fecha
                                if "releases" in rec and rec["releases"]:
                                    if any("date" in r for r in rec["releases"]):
                                        candidate_score += 1

                                # Penalizar "Various Artists" para preferir álbumes de artista
                                if has_artist:
                                    for artist in rec["artists"]:
                                        if artist["name"] == "Various Artists":
                                            candidate_score -= 20
                                            break

                                # Penalizar Compilaciones si hay alternativas
                                if has_album:
                                    for rg in rec["releasegroups"]:
                                        if "type" in rg and rg["type"] == "Compilation":
                                            candidate_score -= 10
                                            break

                                if candidate_score > best_score:
                                    best_score = candidate_score
                                    selected_result = result
                                    selected_recording = rec
                                    # Guardar el título encontrado profundamente para usarlo después
                                    selected_recording["_found_title"] = rec_title

                    # Si el mejor score es muy bajo, descartar
                    if best_score < 50:
                        selected_result = None
                        selected_recording = None

                    if not selected_result or not selected_recording:
                        return {
                            "status": False,
                            "message": "Coincidencias descartadas por baja confianza o falta de metadatos",
                        }

                    # Asignar variables para el resto del código
                    best_result = selected_result
                    recording = selected_recording

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
                        # Si no hay artista, intentar buscar en otras grabaciones del mismo resultado
                        found_artist = False
                        for rec in best_result["recordings"]:
                            if "artists" in rec and rec["artists"]:
                                for artist in rec["artists"]:
                                    artists.append(artist["name"])
                                metadata["artist"] = artists[0]
                                metadata["artists"] = artists
                                found_artist = True
                                break

                        if not found_artist:
                            metadata["artist"] = "Artista Desconocido"
                            metadata["artists"] = ["Artista Desconocido"]

                    # Extraer título
                    # Usar el título encontrado durante la búsqueda profunda si existe
                    metadata["title"] = recording.get("_found_title") or recording.get(
                        "title"
                    )

                    if not metadata["title"]:
                        # Fallback: Buscar título en otras grabaciones del mismo resultado
                        # Esto es útil si la grabación seleccionada (por score) no tiene título pero sus hermanas sí
                        for rec in best_result["recordings"]:
                            # Intento 1: Título directo
                            if rec.get("title"):
                                metadata["title"] = rec["title"]
                                break

                            # Intento 2: Búsqueda profunda en releases
                            if "releases" in rec:
                                deep_title = None
                                for rel in rec["releases"]:
                                    if "mediums" in rel:
                                        for med in rel["mediums"]:
                                            if "tracks" in med:
                                                for trk in med["tracks"]:
                                                    if "title" in trk:
                                                        deep_title = trk["title"]
                                                        break
                                            if deep_title:
                                                break
                                    if deep_title:
                                        break
                                if deep_title:
                                    metadata["title"] = deep_title
                                    break

                    if not metadata["title"]:
                        metadata["title"] = "Título Desconocido"

                    # Extraer álbum
                    # Buscar el mejor grupo de lanzamiento
                    releasegroup = None
                    if "releasegroups" in recording and recording["releasegroups"]:
                        # Preferir álbumes oficiales
                        for rg in recording["releasegroups"]:
                            if rg.get("type") == "Album":
                                releasegroup = rg
                                break
                        # Si no hay álbum oficial, usar el primero
                        if not releasegroup:
                            releasegroup = recording["releasegroups"][0]

                    if releasegroup:
                        metadata["album"] = releasegroup.get(
                            "title", "Álbum Desconocido"
                        )

                        # Artista del álbum
                        if "artists" in releasegroup and releasegroup["artists"]:
                            metadata["albumartist"] = releasegroup["artists"][0]["name"]

                        # Tipo de álbum
                        if "type" in releasegroup:
                            metadata["albumtype"] = releasegroup.get("type")

                        # Fecha de lanzamiento
                        if "releases" in recording and recording["releases"]:
                            # Buscar todas las releases de este releasegroup
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
                                    # Usar la fecha más antigua como fecha del álbum
                                    metadata["date"] = min(release_dates)
                    else:
                        metadata["album"] = "Álbum Desconocido"

                    # Extraer número de pista y disco
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

                    # Extraer género
                    genres = []
                    if "genres" in recording:
                        for genre in recording["genres"]:
                            name = genre["name"]
                            if name.lower() != "other":
                                genres.append(name)
                        if genres:
                            metadata["genre"] = genres[0]
                            metadata["genres"] = genres

                    # Extraer etiquetas adicionales
                    tags = []
                    if "tags" in recording:
                        for tag in recording["tags"]:
                            tags.append(tag["name"])
                        if tags:
                            metadata["tags"] = tags

                    return metadata

                # Si no se encontraron coincidencias
                return {
                    "status": False,
                    "message": f"No se encontraron coincidencias en AcoustID. (Duración: {duration}s, Fingerprint len: {len(fingerprint) if fingerprint else 0}, Response: {results})",
                }

            except acoustid.WebServiceError as e:
                try:
                    key = self.acoustid_api_key or ""
                except Exception:
                    key = ""
                if key:
                    if len(key) > 8:
                        masked_key = f"{key[:4]}...{key[-4:]}"
                    else:
                        masked_key = f"{key[:2]}...{key[-2:]}"
                else:
                    masked_key = "(none)"
                message = f"Error del servicio web AcoustID: {str(e)} (Key usada: {masked_key})"
                if "invalid API key" in str(e):
                    message += ". Por favor obtén una API Key válida en https://acoustid.org/login y úsala con la opción -k"
                return {
                    "status": False,
                    "message": message,
                }

        except Exception as e:
            return {
                "status": False,
                "message": f"Error al reconocer la canción: {str(e)}",
            }

    def _fetch_synced_lyrics(self, artist, title):
        """
        Busca letras sincronizadas usando la biblioteca syncedlyrics.

        Args:
            artist (str): Nombre del artista
            title (str): Título de la canción

        Returns:
            dict: Letras sincronizadas o mensaje de error
        """
        try:
            # Búsqueda de letras (mensajes de estado en CLI)
            import syncedlyrics

            search_term = f"{artist} {title}"
            lrc_content = syncedlyrics.search(search_term)

            if lrc_content and len(lrc_content) > 0:
                return {"status": True, "lyrics": lrc_content}
            else:
                return {
                    "status": False,
                    "message": "No se encontraron letras sincronizadas",
                }

        except ImportError:
            return {
                "status": False,
                "message": "La biblioteca syncedlyrics no está instalada. Instálela con 'pip install syncedlyrics'",
            }
        except Exception as e:
            return {
                "status": False,
                "message": f"Error al buscar letras sincronizadas: {str(e)}",
            }

    def _embed_lyrics(self, file_path, lyrics_content, is_synced=True):
        """
        Incrusta letras en el archivo de audio.

        Args:
            file_path (str): Ruta al archivo de audio
            lyrics_content (str): Contenido de las letras
            is_synced (bool): Si las letras están sincronizadas

        Returns:
            bool: True si se incrustaron correctamente
        """
        try:
            # Incrustando letras (mensajes de estado en CLI)

            if file_path.lower().endswith(".mp3"):
                # Para archivos MP3 usar ID3
                try:
                    from mutagen.id3 import ID3, USLT  # type: ignore[attr-defined]
                except ImportError:
                    return False

                try:
                    tags = ID3(file_path)
                except Exception:
                    tags = ID3()

                # Eliminar letras existentes
                if len(tags.getall("USLT")) > 0:
                    tags.delall("USLT")

                # Agregar nuevas letras
                # Usar encoding=1 (UTF-16) para compatibilidad con ID3v2.3 y Windows
                tags["USLT::'eng'"] = USLT(
                    encoding=1, lang="eng", desc="Lyrics", text=lyrics_content
                )

                tags.save(file_path)
                return True

            else:
                # Para otros formatos usar mutagen genérico
                try:
                    from mutagen import File  # type: ignore[attr-defined]
                except ImportError:
                    return False

                audio = File(file_path)
                if audio is not None:
                    if "lyrics" in audio:
                        del audio["lyrics"]

                    audio["lyrics"] = lyrics_content
                    audio.save()
                    return True
                else:
                    return False

        except Exception:
            return False

    def _update_audio_metadata(self, file_path, metadata):
        """
        Actualiza todos los metadatos disponibles en el archivo de audio.

        Args:
            file_path (str): Ruta al archivo de audio
            metadata (dict): Metadatos a actualizar

        Returns:
            tuple: (bool, str) - (Éxito, Mensaje de error)
        """
        try:
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == ".mp3":
                # Para archivos MP3 usar ID3
                from mutagen.id3 import (  # type: ignore[attr-defined]
                    ID3,
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

                try:
                    tags = ID3(file_path)
                except Exception:
                    tags = ID3()

                changed = False

                def update_tag(frame_id, frame_cls, value):
                    nonlocal changed
                    # Forzar actualización siempre para asegurar encoding correcto (UTF-16)
                    # y corregir posibles problemas de compatibilidad
                    tags[frame_id] = frame_cls(encoding=1, text=str(value))
                    changed = True

                # Actualizar metadatos básicos
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
                    # Usar v2_version=3 para mayor compatibilidad con Windows
                    tags.save(file_path, v2_version=3)

                # Si hay URL de portada, descargar e incrustar
                if "cover_url" in metadata:
                    # Importar el gestor de portadas
                    from core.artwork import AlbumArtManager

                    art_manager = AlbumArtManager()

                    image_data = art_manager.fetch_cover_image(metadata["cover_url"])
                    if image_data:
                        art_manager.embed_album_art(file_path, image_data)

                return True, ""

            elif file_ext in [".flac", ".ogg"]:
                # Para archivos FLAC y OGG
                try:
                    from mutagen import File  # type: ignore[attr-defined]
                except ImportError:
                    return False, "Mutagen no instalado"

                audio = File(file_path)
                if audio is None:
                    return False, "No se pudo abrir el archivo de audio"
                changed = False

                # Mapeo de campos
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

                # Actualizar metadatos
                for meta_key, file_key in field_mapping.items():
                    if meta_key in metadata:
                        new_val = str(metadata[meta_key])
                        current_val = audio.get(file_key, [""])[0]
                        if current_val != new_val:
                            audio[file_key] = new_val
                            changed = True

                if changed:
                    audio.save()

                # Si hay URL de portada, descargar e incrustar (solo para FLAC)
                if "cover_url" in metadata and file_ext == ".flac":
                    # Importar el gestor de portadas
                    from core.artwork import AlbumArtManager

                    art_manager = AlbumArtManager()

                    image_data = art_manager.fetch_cover_image(metadata["cover_url"])
                    if image_data:
                        art_manager.embed_album_art(file_path, image_data)

                return True, ""

            elif file_ext == ".m4a":
                # Para archivos M4A/AAC
                try:
                    from mutagen.mp4 import MP4
                except ImportError:
                    return False, "Mutagen no instalado"

                audio = MP4(file_path)

                # Mapeo de campos para M4A
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
                for meta_key, file_key in field_mapping.items():
                    if meta_key in metadata:
                        new_val = str(metadata[meta_key])
                        current_val_list = audio.get(file_key, [""])
                        current_val = current_val_list[0] if current_val_list else ""
                        if current_val != new_val:
                            audio[file_key] = [new_val]
                            changed = True

                # Manejo especial para tracknumber y discnumber en M4A
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

                # Si hay URL de portada, descargar e incrustar
                if "cover_url" in metadata:
                    # Importar el gestor de portadas
                    from core.artwork import AlbumArtManager

                    art_manager = AlbumArtManager()

                    image_data = art_manager.fetch_cover_image(metadata["cover_url"])
                    if image_data:
                        art_manager.embed_album_art(file_path, image_data)

                return True, ""

            return False, f"Formato no soportado: {file_ext}"

        except Exception as e:
            return False, str(e)

    def rename_files(self, progress_callback=None):
        """
        Renombra los archivos de audio basándose en sus metadatos.
        Si el archivo no tiene los metadatos necesarios (artista o título),
        no se renombra y se muestra un mensaje.

        Args:
            progress_callback (callable): Función a llamar al completar cada archivo

        Returns:
            dict: Cambios realizados (nuevo_nombre: nombre_original)
        """

        files = get_audio_files(directory=self.directory, recursive=self.recursive)
        changes = {}

        for file in files:
            try:
                # file is already an absolute path because get_audio_files returns absolute paths
                file_path = file
                try:
                    from mutagen import File  # type: ignore[attr-defined]
                except ImportError:
                    if progress_callback:
                        progress_callback(
                            file, {"status": False, "error": "Mutagen missing"}
                        )
                    continue

                audio = File(file_path, easy=True)

                # Verificar si existen los metadatos necesarios
                if not audio or not audio.tags:
                    if progress_callback:
                        progress_callback(
                            file,
                            {"status": False, "skipped": True, "reason": "No tags"},
                        )
                    continue

                artist = audio.get("artist", [""])[0]
                title = audio.get("title", [""])[0]

                # Verificar si los metadatos están vacíos o son los valores por defecto
                if (
                    not artist
                    or not title
                    or artist == "Unknown Artist"
                    or title == "Unknown Title"
                ):
                    if progress_callback:
                        progress_callback(
                            file,
                            {
                                "status": False,
                                "skipped": True,
                                "reason": "Missing metadata",
                            },
                        )
                    continue

                # Artista - Título.formato (.mp3, .flac, etc..)
                new_name = f"{artist} - {title}{os.path.splitext(file)[1]}"

                actual_new_path, changed = self._safe_rename(file, new_name)
                if changed:
                    changes[actual_new_path] = file
                    if progress_callback:
                        progress_callback(
                            file,
                            {
                                "status": True,
                                "renamed": True,
                                "new_name": os.path.basename(actual_new_path),
                            },
                        )
                else:
                    if progress_callback:
                        progress_callback(
                            file,
                            {
                                "status": True,
                                "renamed": False,
                                "reason": "No change needed",
                            },
                        )

            except Exception as e:
                if progress_callback:
                    progress_callback(file, {"status": False, "error": str(e)})
                pass

        # La CLI mostrará el resumen de renombrados

        return changes

    def undo_rename(self, changes: dict, progress_callback=None):
        # changes: {new_absolute_path: old_absolute_path}
        for new_path, old_path in changes.items():
            try:
                if os.path.exists(new_path):
                    # Intentar renombrar de vuelta
                    # Usamos os.rename directamente para restaurar el estado exacto
                    # Pero verificamos si el destino (old_path) existe para evitar sobrescritura accidental
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
                pass

    def _safe_rename(self, old_name, new_name):
        """
        Renombra un archivo de forma segura, evitando conflictos de nombres.

        Args:
            old_name (str): Nombre original del archivo (puede ser ruta absoluta)
            new_name (str): Nuevo nombre para el archivo (solo nombre)

        Returns:
            tuple: (nombre_final, cambio_realizado)
        """

        if os.path.isabs(old_name):
            old_path = old_name
            directory = os.path.dirname(old_name)
        else:
            old_path = os.path.join(self.directory, old_name)
            directory = self.directory

        new_name = self._sanitize_filename(new_name)
        new_path = os.path.join(directory, new_name)

        # Verificar si el nombre ya es el correcto (ignorando mayúsculas/minúsculas en Windows)
        if os.path.normcase(old_path) == os.path.normcase(new_path):
            return new_path, False

        # Verificar si el archivo destino ya existe y es idéntico (duplicado)
        if os.path.exists(new_path) and os.path.normcase(new_path) != os.path.normcase(
            old_path
        ):
            if self._are_files_identical(old_path, new_path):
                try:
                    # Eliminar el archivo destino (que es idéntico) y renombrar el actual
                    os.remove(new_path)
                    os.rename(old_path, new_path)
                    return new_path, True
                except OSError:
                    pass

        base, extension = os.path.splitext(new_name)
        counter = 1

        while os.path.exists(new_path):
            # Si el archivo que existe es el mismo que estamos renombrando (caso raro de case-sensitivity)
            if os.path.normcase(new_path) == os.path.normcase(old_path):
                break

            new_name = f"{base} ({counter}){extension}"
            new_path = os.path.join(directory, new_name)
            counter += 1

        # Verificar si después de resolver conflictos terminamos con el mismo archivo
        if os.path.normcase(new_path) == os.path.normcase(old_path):
            return new_path, False

        try:
            os.rename(old_path, new_path)
            return new_path, True
        except OSError:
            return old_path, False

    def _are_files_identical(self, path1, path2):
        """
        Compara dos archivos para ver si son idénticos (tamaño y contenido).
        """
        try:
            if os.path.getsize(path1) != os.path.getsize(path2):
                return False

            # Comparar contenido en bloques
            with open(path1, "rb") as f1, open(path2, "rb") as f2:
                while True:
                    b1 = f1.read(8192)
                    b2 = f2.read(8192)
                    if b1 != b2:
                        return False
                    if not b1:
                        return True
        except OSError:
            return False

    def _sanitize_filename(self, filename):
        """
        Sanitiza el nombre del archivo según el sistema operativo.

        Args:
            filename (str): Nombre del archivo a sanitizar

        Returns:
            str: Nombre sanitizado
        """
        if self.os_type == "Windows":
            invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
            sanitized = re.sub(invalid_chars, "", filename)
            forbidden_names = {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                "COM1",
                "COM2",
                "COM3",
                "COM4",
                "COM5",
                "COM6",
                "COM7",
                "COM8",
                "COM9",
                "LPT1",
                "LPT2",
                "LPT3",
                "LPT4",
                "LPT5",
                "LPT6",
                "LPT7",
                "LPT8",
                "LPT9",
            }
            if sanitized.upper() in forbidden_names:
                sanitized = "_" + sanitized
        else:
            sanitized = re.sub(r"/", "-", filename)
            sanitized = sanitized.strip(".")

        sanitized = sanitized.strip()
        max_length = 255
        base, ext = os.path.splitext(sanitized)

        if len(sanitized) > max_length:
            base = base[: max_length - len(ext) - 1]
            sanitized = base + ext

        if not base:
            sanitized = f"audio_file{ext}"

        return sanitized
