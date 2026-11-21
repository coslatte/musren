"""Write synchronized lyrics into supported audio files."""


def embed_lyrics(file_path: str, lyrics_content: str) -> bool:
    """Replace embedded lyrics and report whether the file was saved."""
    try:
        if file_path.lower().endswith(".mp3"):
            from mutagen.id3 import ID3, USLT

            try:
                tags = ID3(file_path)
            except Exception:
                tags = ID3()
            tags.delall("USLT")
            tags["USLT::'eng'"] = USLT(
                encoding=1, lang="eng", desc="Lyrics", text=lyrics_content
            )
            tags.save(file_path)
            return True

        from mutagen import File

        audio = File(file_path)
        if audio is None:
            return False
        if "lyrics" in audio:
            del audio["lyrics"]
        audio["lyrics"] = lyrics_content
        audio.save()
        return True
    except (ImportError, OSError, ValueError, TypeError, KeyError):
        return False
