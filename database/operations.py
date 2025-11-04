"""
Модуль с операциями для работы с базой данных.
Содержит функции для работы с пользователями, историей запросов и кэшем песен.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from database.db import get_db
from utils.logger import get_logger

logger = get_logger(__name__)


# ============ Операции с пользователями ============

def create_or_update_user(user_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None) -> None:
    """
    Создает нового пользователя или обновляет информацию существующего.
    
    Args:
        user_id: ID пользователя Telegram
        username: Username пользователя
        first_name: Имя пользователя
        last_name: Фамилия пользователя
    """
    db = get_db()
    
    # Проверяем, существует ли пользователь
    user = db.fetchone("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    
    if user:
        # Обновляем информацию и время последней активности
        db.execute("""
            UPDATE users 
            SET username = ?, first_name = ?, last_name = ?, last_activity = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (username, first_name, last_name, user_id))
        logger.info(f"Обновлен пользователь: {user_id}")
    else:
        # Создаем нового пользователя
        db.execute("""
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, last_name))
        logger.info(f"Создан новый пользователь: {user_id}")


def increment_user_requests(user_id: int) -> None:
    """
    Увеличивает счетчик запросов пользователя.
    
    Args:
        user_id: ID пользователя Telegram
    """
    db = get_db()
    db.execute("""
        UPDATE users 
        SET total_requests = total_requests + 1, last_activity = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (user_id,))


def get_user_stats(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает статистику пользователя.
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        Словарь со статистикой или None
    """
    db = get_db()
    user = db.fetchone("""
        SELECT user_id, username, first_name, last_name, 
               created_at, last_activity, total_requests
        FROM users WHERE user_id = ?
    """, (user_id,))
    
    if user:
        return dict(user)
    return None


# ============ Операции с историей запросов ============

def add_query_to_history(user_id: int, artist: str, song_name: str, 
                        success: bool = True, error_message: str = None) -> int:
    """
    Добавляет запрос в историю.
    
    Args:
        user_id: ID пользователя
        artist: Имя исполнителя
        song_name: Название песни
        success: Успешность запроса
        error_message: Сообщение об ошибке (если есть)
        
    Returns:
        ID созданной записи
    """
    db = get_db()
    cursor = db.execute("""
        INSERT INTO query_history (user_id, artist, song_name, success, error_message)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, artist, song_name, success, error_message))
    
    # Увеличиваем счетчик запросов пользователя
    increment_user_requests(user_id)
    
    logger.info(f"Добавлен запрос в историю: {artist} - {song_name} для пользователя {user_id}")
    return cursor.lastrowid


def get_user_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Получает историю запросов пользователя.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество записей
        
    Returns:
        Список запросов
    """
    db = get_db()
    rows = db.fetchall("""
        SELECT id, artist, song_name, query_date, success, error_message
        FROM query_history
        WHERE user_id = ?
        ORDER BY query_date DESC
        LIMIT ?
    """, (user_id, limit))
    
    return [dict(row) for row in rows]


def get_recent_queries(days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Получает недавние запросы за указанный период.
    
    Args:
        days: Количество дней для поиска
        limit: Максимальное количество записей
        
    Returns:
        Список запросов
    """
    db = get_db()
    date_threshold = (datetime.now() - timedelta(days=days)).isoformat()
    
    rows = db.fetchall("""
        SELECT id, user_id, artist, song_name, query_date, success
        FROM query_history
        WHERE query_date >= ?
        ORDER BY query_date DESC
        LIMIT ?
    """, (date_threshold, limit))
    
    return [dict(row) for row in rows]


# ============ Операции с кэшем песен ============

def get_cached_song(artist: str, song_name: str) -> Optional[Dict[str, Any]]:
    """
    Получает закэшированную песню.
    
    Args:
        artist: Имя исполнителя
        song_name: Название песни
        
    Returns:
        Словарь с данными песни или None
    """
    db = get_db()
    
    # Нормализуем для поиска (приводим к нижнему регистру)
    artist_lower = artist.lower().strip()
    song_lower = song_name.lower().strip()
    
    row = db.fetchone("""
        SELECT id, artist, song_name, lyrics, analysis_summary, 
               cached_at, access_count, last_accessed
        FROM song_cache
        WHERE LOWER(TRIM(artist)) = ? AND LOWER(TRIM(song_name)) = ?
    """, (artist_lower, song_lower))
    
    if row:
        # Обновляем счетчик обращений и время последнего доступа
        db.execute("""
            UPDATE song_cache 
            SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (row['id'],))
        
        logger.info(f"Найдена кэшированная песня: {artist} - {song_name}")
        return dict(row)
    
    return None


def cache_song(artist: str, song_name: str, lyrics: str, 
               analysis_summary: str = None) -> int:
    """
    Сохраняет песню в кэш.
    
    Args:
        artist: Имя исполнителя
        song_name: Название песни
        lyrics: Текст песни
        analysis_summary: Результат анализа
        
    Returns:
        ID записи в кэше
    """
    db = get_db()
    
    try:
        cursor = db.execute("""
            INSERT INTO song_cache (artist, song_name, lyrics, analysis_summary)
            VALUES (?, ?, ?, ?)
        """, (artist, song_name, lyrics, analysis_summary))
        
        logger.info(f"Песня добавлена в кэш: {artist} - {song_name}")
        return cursor.lastrowid
    except Exception as e:
        # Если песня уже есть в кэше, обновляем её
        logger.warning(f"Песня уже в кэше, обновляем: {artist} - {song_name}")
        db.execute("""
            UPDATE song_cache 
            SET lyrics = ?, analysis_summary = ?, 
                access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
            WHERE LOWER(TRIM(artist)) = LOWER(TRIM(?)) 
              AND LOWER(TRIM(song_name)) = LOWER(TRIM(?))
        """, (lyrics, analysis_summary, artist, song_name))
        
        # Получаем ID обновленной записи
        row = db.fetchone("""
            SELECT id FROM song_cache 
            WHERE LOWER(TRIM(artist)) = LOWER(TRIM(?)) 
              AND LOWER(TRIM(song_name)) = LOWER(TRIM(?))
        """, (artist, song_name))
        
        return row['id'] if row else None


def get_popular_songs(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Получает список самых популярных песен из кэша.
    
    Args:
        limit: Максимальное количество песен
        
    Returns:
        Список популярных песен
    """
    db = get_db()
    rows = db.fetchall("""
        SELECT artist, song_name, access_count, last_accessed
        FROM song_cache
        ORDER BY access_count DESC, last_accessed DESC
        LIMIT ?
    """, (limit,))
    
    return [dict(row) for row in rows]


def clean_old_cache(days: int = 30) -> int:
    """
    Удаляет старые записи из кэша, к которым не обращались указанное время.
    
    Args:
        days: Количество дней неактивности
        
    Returns:
        Количество удаленных записей
    """
    db = get_db()
    date_threshold = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor = db.execute("""
        DELETE FROM song_cache
        WHERE last_accessed < ? AND access_count < 5
    """, (date_threshold,))
    
    deleted_count = cursor.rowcount
    logger.info(f"Удалено {deleted_count} старых записей из кэша")
    return deleted_count


# ============ Статистика ============

def get_global_stats() -> Dict[str, Any]:
    """
    Получает глобальную статистику бота.
    
    Returns:
        Словарь со статистикой
    """
    db = get_db()
    
    total_users = db.fetchone("SELECT COUNT(*) as count FROM users", ())['count']
    total_queries = db.fetchone("SELECT COUNT(*) as count FROM query_history", ())['count']
    cached_songs = db.fetchone("SELECT COUNT(*) as count FROM song_cache", ())['count']
    
    # Запросы за последние 24 часа
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    recent_queries = db.fetchone("""
        SELECT COUNT(*) as count FROM query_history 
        WHERE query_date >= ?
    """, (yesterday,))['count']
    
    # Активные пользователи за последние 7 дней
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    active_users = db.fetchone("""
        SELECT COUNT(*) as count FROM users 
        WHERE last_activity >= ?
    """, (week_ago,))['count']
    
    return {
        'total_users': total_users,
        'total_queries': total_queries,
        'cached_songs': cached_songs,
        'recent_queries_24h': recent_queries,
        'active_users_7d': active_users
    }

