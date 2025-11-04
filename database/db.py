"""
Модуль для работы с базой данных SQLite.
Создает и управляет подключением к БД, инициализирует таблицы.
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)

DB_PATH = os.getenv("DB_PATH", "lyrics_bot.db")


class Database:
    """Класс для работы с SQLite базой данных."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        
    def connect(self) -> sqlite3.Connection:
        """Создает подключение к базе данных."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row  # Для доступа к полям по имени
            logger.info(f"Подключение к БД установлено: {self.db_path}")
        return self._conn
    
    def close(self):
        """Закрывает подключение к базе данных."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Подключение к БД закрыто")
    
    def init_db(self):
        """Инициализирует базу данных, создает таблицы если их нет."""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_requests INTEGER DEFAULT 0
            )
        """)
        
        # Таблица истории запросов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                artist TEXT NOT NULL,
                song_name TEXT NOT NULL,
                query_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Индекс для быстрого поиска по пользователю
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_history_user_id 
            ON query_history(user_id)
        """)
        
        # Индекс для быстрого поиска по дате
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_history_date 
            ON query_history(query_date DESC)
        """)
        
        # Таблица кэша песен
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS song_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist TEXT NOT NULL,
                song_name TEXT NOT NULL,
                lyrics TEXT NOT NULL,
                analysis_summary TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 1,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(artist, song_name)
            )
        """)
        
        # Индекс для быстрого поиска по исполнителю и названию песни
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_song_cache_artist_song 
            ON song_cache(artist, song_name)
        """)
        
        # Индекс для поиска популярных песен
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_song_cache_access_count 
            ON song_cache(access_count DESC)
        """)
        
        conn.commit()
        logger.info("База данных инициализирована")
    
    def execute(self, query: str, params: tuple = ()):
        """Выполняет SQL запрос."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor
    
    def fetchone(self, query: str, params: tuple = ()):
        """Выполняет SELECT запрос и возвращает одну строку."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    
    def fetchall(self, query: str, params: tuple = ()):
        """Выполняет SELECT запрос и возвращает все строки."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


# Глобальный экземпляр базы данных
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """Возвращает глобальный экземпляр базы данных."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.init_db()
    return _db_instance


def init_database():
    """Инициализирует базу данных при запуске приложения."""
    db = get_db()
    logger.info("База данных готова к работе")
    return db

