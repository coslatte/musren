import asyncio
from typing import Dict, Any

try:
    from shazamio import Shazam

    _shazam_available = True
except ImportError:
    Shazam = None
    _shazam_available = False


class ShazamProcessor:
    def __init__(self):
        if not _shazam_available or Shazam is None:
            raise ImportError(
                "La librería 'shazamio' no está instalada. Instálala con: pip install shazamio"
            )

    async def _recognize_async(self, file_path: str) -> Dict[str, Any]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if Shazam is None:
                    return {"error": "Shazam not available"}
                shazam = Shazam()
                timeout = 20.0 + (attempt * 10.0)
                out = await asyncio.wait_for(
                    shazam.recognize(file_path), timeout=timeout
                )
                return out
            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    return {"error": "timeout"}
                await asyncio.sleep(1 * (attempt + 1))
            except Exception as e:
                if "429" in str(e):
                    await asyncio.sleep(5)
                else:
                    return {}
        return {}

    def recognize(self, file_path: str) -> Dict[str, Any]:
        """
        Reconoce una canción usando Shazam.
        Retorna un diccionario compatible con el formato de MusRen.
        """
        try:
            result = asyncio.run(self._recognize_async(file_path))
        except Exception as e:
            return {"status": False, "message": f"Error ejecutando Shazam: {str(e)}"}

        if not result or "track" not in result:
            return {"status": False, "message": "No se encontró coincidencia en Shazam"}

        track = result["track"]

        title = track.get("title", "Título Desconocido")
        artist = track.get("subtitle", "Artista Desconocido")

        metadata = {
            "status": True,
            "score": 100,
            "service": "Shazam",
            "title": title,
            "artist": artist,
            "artists": [artist],
            "album": "Álbum Desconocido",
            "albumartist": artist,
            "cover_url": track.get("images", {}).get("coverarthq", ""),
            "shazam_id": track.get("key"),
            "genres": [],
        }

        if "genres" in track:
            metadata["genres"] = [track["genres"]["primary"]]

        if "sections" in track:
            for section in track["sections"]:
                if section.get("type") == "SONG":
                    for meta in section.get("metadata", []):
                        key = meta.get("title")
                        value = meta.get("text")

                        if key == "Album":
                            metadata["album"] = value
                        elif key == "Label":
                            metadata["label"] = value
                        elif key == "Released":
                            metadata["date"] = value

        return metadata


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Uso: python shazam_processor.py <archivo_audio>")
        sys.exit(1)

    file_path = sys.argv[1]
    processor = ShazamProcessor()
    result = processor.recognize(file_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
