import os
from dotenv import load_dotenv

from services.genius_client import GeniusClient
from llm_services.analysis import interpret_lyrics
from database.operations import get_cached_song, cache_song
from utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


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
        """
        Анализирует песню с использованием кэша.
        Сначала проверяет кэш, если данных нет - получает с Genius и анализирует через LLM.
        """
        # Проверяем кэш
        cached_data = get_cached_song(genius_artist_name, genius_song_name)
        
        if cached_data and cached_data.get('analysis_summary'):
            logger.info(f"Используем кэшированные данные для {genius_artist_name} - {genius_song_name}")
            return {
                'summary': cached_data['analysis_summary'],
                'lyrics': cached_data['lyrics'],
                'from_cache': True
            }
        
        # Если в кэше нет, получаем с Genius
        try:
            lyrics = await self.genius.fetch_lyrics(
                genius_artist_name, genius_song_name
            )
        except Exception as e:
            raise Exception(f"Ошибка Genius API: {e}")

        # Анализируем текст через LLM
        result = await interpret_lyrics(genius_song_name, genius_artist_name, lyrics)
        
        # Сохраняем в кэш
        try:
            cache_song(
                genius_artist_name, 
                genius_song_name, 
                lyrics, 
                result.get('summary')
            )
            logger.info(f"Результат сохранен в кэш: {genius_artist_name} - {genius_song_name}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кэш: {e}")
        
        result['from_cache'] = False
        return result
