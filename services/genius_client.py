import lyricsgenius


class GeniusClient:
    def __init__(self, token: str):
        self.genius = lyricsgenius.Genius(token, verbose=False)

    async def fetch_lyrics(self, genius_artist_name: str, genius_song_name: str) -> str:
        artist = self.genius.search_artist(genius_artist_name, max_songs=3)
        if artist:
            song = artist.song(genius_song_name)
            if song:
                return song.lyrics[1:]
            raise ValueError(f"Нет песни с названием: {genius_song_name}")

        raise ValueError(f"Нет исполнителя {genius_artist_name}")
