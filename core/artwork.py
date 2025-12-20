"""
Módulo para manejar portadas de álbumes: búsqueda, descarga e incrustación.
"""

import logging
import os

from constants.info import MUSIC_RENAMER_VERSION

logger = logging.getLogger(__name__)


class AlbumArtManager:
    """
    Clase para manejar todas las operaciones relacionadas con portadas de álbumes.
    """

    def __init__(self):
        """Inicializa el gestor de portadas de álbumes."""
        pass

    def fetch_album_cover(self, artist, album):
        """
        Intenta obtener la URL de la portada del álbum mediante múltiples servicios.

        El proceso de búsqueda sigue estos pasos:
        1. Primero intenta con MusicBrainz si está disponible
        2. Si no encuentra resultados o MusicBrainz no está disponible, intenta con iTunes
        3. Como último recurso, intenta con Deezer

        Args:
            artist (str): Nombre del artista
            album (str): Nombre del álbum

        Returns:
            str: URL de la portada del álbum o None si no se encuentra
        """
        try:
            # Intentar con MusicBrainz
            try:
                import musicbrainzngs

                # Configurar el agente de usuario para MusicBrainz (requerido)
                musicbrainzngs.set_useragent(
                    "musicRenamer",
                    MUSIC_RENAMER_VERSION,
                    "https://github.com/coslatte/musicRenamer",
                )

                # Buscar el álbum en MusicBrainz
                result = musicbrainzngs.search_releases(
                    release=album, artist=artist, limit=1
                )

                if result and "release-list" in result and result["release-list"]:
                    release = result["release-list"][0]
                    release_id = release["id"]

                    # Obtener la URL de la portada desde Cover Art Archive
                    cover_url = (
                        f"https://coverartarchive.org/release/{release_id}/front"
                    )

                    # Verificar si la portada realmente existe antes de devolverla
                    try:
                        # requests es opcional; importarlo localmente
                        try:
                            import requests
                        except ImportError:
                            raise

                        cover_response = requests.head(cover_url, timeout=5)
                        if cover_response.status_code == 200:
                            return cover_url
                    except Exception:
                        pass

            except ImportError:
                pass
            except Exception:
                pass

            # Método con iTunes
            search_term = f"{artist} {album}".replace(" ", "+")
            url = f"https://itunes.apple.com/search?term={search_term}&entity=album&limit=1"

            try:
                import requests
            except ImportError:
                response = None
            else:
                response = requests.get(url)
            if response and response.status_code == 200:
                data = response.json()
                if data.get("resultCount", 0) > 0:
                    result = data["results"][0]

                    cover_url = result.get("artworkUrl100", "").replace(
                        "100x100", "600x600"
                    )
                    return cover_url

            # Método con Deezer
            search_term = f"{artist} {album}".replace(" ", "+")
            url = f"https://api.deezer.com/search/album?q={search_term}&limit=1"

            try:
                import requests
            except ImportError:
                return None
            response = requests.get(url)
            if response and response.status_code == 200:
                data = response.json()
                if data.get("total", 0) > 0 and data.get("data"):
                    result = data["data"][0]
                    cover_url = (
                        result.get("cover_xl")
                        or result.get("cover_big")
                        or result.get("cover")
                    )
                    return cover_url

            return None

        except Exception:
            return None

    def fetch_cover_image(self, url):
        """
        Descarga una imagen desde una URL y devuelve los datos binarios.

        Args:
            url (str): URL de la imagen a descargar

        Returns:
            bytes: Datos binarios de la imagen o None si falla
        """

        try:
            try:
                import requests
            except ImportError:
                return None
            response = requests.get(url)
            if response.status_code == 200:
                return response.content
            return None
        except Exception:
            return None

    def embed_album_art(self, file_path, image_data):
        """
        Incrusta la portada del álbum en el archivo de audio.

        Esta función detecta automáticamente el formato del archivo de audio (.mp3, .flac, .m4a)
        y el formato de la imagen (JPEG, PNG). Utiliza diferentes métodos para cada formato
        de archivo, preservando los metadatos existentes.

        Args:
            file_path (str): Ruta al archivo de audio
            image_data (bytes): Datos binarios de la imagen

        Returns:
            bool: True si la operación fue exitosa, False en caso contrario
        """

        if not image_data:
            return False

        try:
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == ".mp3":
                return self._embed_mp3_art(file_path, image_data)
            elif file_ext == ".flac":
                return self._embed_flac_art(file_path, image_data)
            elif file_ext == ".m4a":
                return self._embed_m4a_art(file_path, image_data)
            else:
                return False

        except Exception:
            return False

    def _embed_mp3_art(self, file_path, image_data):
        """
        Incrusta portada en archivo MP3 usando ID3.

        Args:
            file_path (str): Ruta al archivo MP3
            image_data (bytes): Datos de la imagen

        Returns:
            bool: True si tuvo éxito
        """
        try:
            # Primera comprobamos las etiquetas existentes para preservarlas
            original_tags = {}
            try:
                from mutagen.id3 import ID3

                existing_tags = ID3(file_path)
                # Guardar todos los frames excepto APIC
                for frame_key in existing_tags.keys():
                    if not frame_key.startswith("APIC"):
                        original_tags[frame_key] = existing_tags[frame_key]
            except Exception:
                pass

            # Crear nuevas etiquetas
            from mutagen.id3 import ID3, APIC  # type: ignore[attr-defined]

            tags = ID3()

            # Restaurar etiquetas originales
            for key, value in original_tags.items():
                tags[key] = value

            # Determinar tipo MIME
            mime_type = "image/jpeg"  # Asumir JPEG por defecto
            if image_data[:8].startswith(b"\x89PNG\r\n\x1a\n"):
                mime_type = "image/png"

            # Agregar nueva portada
            tags["APIC"] = APIC(
                encoding=3,  # UTF-8
                mime=mime_type,
                type=3,  # Portada frontal
                desc="Cover",
                data=image_data,
            )

            # Guardar archivo
            # Usar v2_version=3 para mayor compatibilidad con Windows
            tags.save(file_path, v2_version=3)
            return True

        except Exception:
            return False

    def _embed_flac_art(self, file_path, image_data):
        """
        Incrusta portada en archivo FLAC.

        Args:
            file_path (str): Ruta al archivo FLAC
            image_data (bytes): Datos de la imagen

        Returns:
            bool: True si tuvo éxito
        """
        try:
            from mutagen.flac import FLAC, Picture

            audio = FLAC(file_path)

            # Eliminar imágenes existentes
            audio.clear_pictures()

            # Agregar nueva imagen
            picture = Picture()
            picture.type = 3  # Portada frontal

            # Detectar tipo de imagen
            if image_data[:8].startswith(b"\x89PNG\r\n\x1a\n"):
                picture.mime = "image/png"
            else:
                picture.mime = "image/jpeg"

            picture.desc = "Cover"
            picture.data = image_data

            audio.add_picture(picture)
            audio.save()
            return True
        except Exception:
            return False

    def _embed_m4a_art(self, file_path: str, image_data: bytes) -> bool:
        """
        Incrusta portada en archivo M4A/AAC.

        Args:
            file_path: Ruta al archivo M4A
            image_data: Datos de la imagen

        Returns:
            True si tuvo éxito, False en caso contrario
        """
        try:
            from mutagen.mp4 import MP4, MP4Cover, MP4StreamInfoError
            from mutagen._util import MutagenError  # type: ignore[attr-defined]
        except ImportError as e:
            logger.error("mutagen.mp4 no disponible: %s", e)
            return False

        # Detect image format from magic bytes
        format_type: int = MP4Cover.FORMAT_JPEG
        if image_data[:8].startswith(b"\x89PNG\r\n\x1a\n"):
            format_type = MP4Cover.FORMAT_PNG
            logger.debug("Detected PNG image for %s", file_path)
        else:
            logger.debug("Assuming JPEG image for %s", file_path)

        try:
            audio = MP4(file_path)
        except MP4StreamInfoError as e:
            logger.error("Archivo M4A corrupto o no válido %s: %s", file_path, e)
            return False
        except (OSError, PermissionError) as e:
            logger.error("No se pudo abrir %s: %s", file_path, e)
            raise  # permission/IO issues should propagate
        except MutagenError as e:
            logger.error("Error leyendo M4A %s: %s", file_path, e)
            return False

        # Remove existing covers
        if "covr" in audio:
            del audio["covr"]

        # Try embedding with detected format first
        try:
            cover = MP4Cover(image_data, format_type)
            audio["covr"] = [cover]
            audio.save()
            logger.info(
                "Portada incrustada en %s con formato %s",
                file_path,
                "PNG" if format_type == MP4Cover.FORMAT_PNG else "JPEG",
            )
            return True
        except (OSError, PermissionError) as e:
            # File system / permission errors should not be swallowed
            logger.error(
                "Error de permisos/IO al guardar portada en %s: %s", file_path, e
            )
            raise
        except MutagenError as e:
            logger.debug(
                "Falló incrustar con formato %s en %s: %s. Intentando formato alternativo.",
                "PNG" if format_type == MP4Cover.FORMAT_PNG else "JPEG",
                file_path,
                e,
            )

        # Fallback: try the alternate format
        alt_format = (
            MP4Cover.FORMAT_PNG
            if format_type == MP4Cover.FORMAT_JPEG
            else MP4Cover.FORMAT_JPEG
        )
        try:
            cover = MP4Cover(image_data, alt_format)
            audio["covr"] = [cover]
            audio.save()
            logger.info(
                "Portada incrustada en %s con formato alternativo %s",
                file_path,
                "PNG" if alt_format == MP4Cover.FORMAT_PNG else "JPEG",
            )
            return True
        except (OSError, PermissionError) as e:
            logger.error(
                "Error de permisos/IO al guardar portada alternativa en %s: %s",
                file_path,
                e,
            )
            raise
        except MutagenError as e:
            logger.error(
                "No se pudo incrustar portada en %s tras intentar ambos formatos: %s",
                file_path,
                e,
            )
            return False
