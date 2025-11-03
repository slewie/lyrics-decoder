import os
from dotenv import load_dotenv

from services.genius_client import GeniusClient
from llm_services.analysis import interpret_lyrics

load_dotenv()


class AnylyzeService:
    def __init__(self):
        genius_token = os.getenv("GENIUS_API_TOKEN")
        if not genius_token:
            raise ValueError("GENIUS_API_TOKEN не найден в переменных окружения")
        self.genius = GeniusClient(genius_token)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def analyze(self, genius_artist_name: str, genius_song_name: str) -> dict:
        try:
            lyrics = await self.genius.fetch_lyrics(
                genius_artist_name, genius_song_name
            )
        except Exception as e:
            raise Exception(f"Ошибка Genius API: {e}")

        result = await interpret_lyrics(genius_song_name, genius_artist_name, lyrics)
        return result
