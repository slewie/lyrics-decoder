import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from frontend.service.analyze_service import AnylyzeService
from database.db import init_database
from database.operations import (
    create_or_update_user,
    add_query_to_history,
    get_user_history,
    get_user_stats,
    get_popular_songs,
    get_global_stats
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

ARTIST, SONG = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    
    # Создаем или обновляем пользователя в БД
    create_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    await update.message.reply_text(
        "👋 Привет! Я бот для анализа текстов песен.\n\n"
        "Доступные команды:\n"
        "/analyze - начать анализ песни\n"
        "/history - показать историю запросов\n"
        "/stats - показать вашу статистику\n"
        "/popular - показать популярные песни\n"
        "/help - помощь"
    )


async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и запрашивает имя исполнителя."""
    user = update.effective_user
    
    # Создаем или обновляем пользователя в БД
    create_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    await update.message.reply_text("Отлично! Введите имя исполнителя:")
    # Переходим в состояние ARTIST, ожидая имя исполнителя
    return ARTIST


async def artist_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет имя исполнителя и запрашивает название песни."""
    context.user_data["artist"] = update.message.text
    logger.info(f"Исполнитель: {context.user_data['artist']}")

    await update.message.reply_text("Теперь введите название песни:")
    # Переходим в состояние SONG, ожидая название песни
    return SONG


async def song_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает название песни, запускает анализ и отправляет результат."""
    user = update.effective_user
    artist = context.user_data.get("artist")
    song_name = update.message.text
    logger.info(f"Песня: {song_name}")

    if not artist:
        await update.message.reply_text(
            "Что-то пошло не так. Пожалуйста, начните заново с /analyze"
        )
        return ConversationHandler.END

    processing_message = await update.message.reply_text(
        "⏳ Получаем текст и генерируем трактовки..."
    )

    success = False
    error_message = None

    try:
        async with AnylyzeService() as service:
            data = await service.analyze(artist, song_name)

        if not data or "summary" not in data:
            error_message = "Не удалось получить данные"
            await processing_message.edit_text(
                "Не удалось получить данные для этой песни. Проверьте правильность написания."
            )
            return ConversationHandler.END

        success = True
        
        # Формируем ответ с пометкой о кэше
        cache_status = "📦 Из кэша" if data.get('from_cache') else "🆕 Новый анализ"
        
        response_text = (
            f"<b>Краткий обзор песни «{song_name}» исполнителя {artist}:</b>\n"
            f"<i>{cache_status}</i>\n\n"
            f"{data['summary']}"
        )

        await processing_message.edit_text(response_text, parse_mode="HTML")

    except Exception as e:
        error_message = str(e)
        logger.error(
            f"Ошибка при анализе песни {artist} - {song_name}: {e}", exc_info=True
        )
        await processing_message.edit_text(
            "Произошла ошибка во время анализа. Попробуйте еще раз позже."
        )
    finally:
        # Добавляем запрос в историю
        try:
            add_query_to_history(user.id, artist, song_name, success, error_message)
        except Exception as e:
            logger.error(f"Ошибка при сохранении в историю: {e}")
        
        context.user_data.clear()
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог."""
    await update.message.reply_text("Действие отменено.")
    context.user_data.clear()
    return ConversationHandler.END


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает историю запросов пользователя."""
    user = update.effective_user
    
    try:
        history = get_user_history(user.id, limit=10)
        
        if not history:
            await update.message.reply_text(
                "📜 Ваша история запросов пуста.\n"
                "Используйте /analyze для анализа песни."
            )
            return
        
        response = "📜 <b>Ваша история запросов:</b>\n\n"
        
        for i, query in enumerate(history, 1):
            status = "✅" if query['success'] else "❌"
            date = query['query_date'].split('.')[0] if '.' in query['query_date'] else query['query_date']
            response += (
                f"{i}. {status} <b>{query['artist']}</b> - {query['song_name']}\n"
                f"   <i>{date}</i>\n\n"
            )
        
        await update.message.reply_text(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при получении истории: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при получении истории.")


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статистику пользователя."""
    user = update.effective_user
    
    try:
        stats = get_user_stats(user.id)
        
        if not stats:
            await update.message.reply_text(
                "📊 Статистика пока недоступна.\n"
                "Используйте /analyze для анализа песни."
            )
            return
        
        created_date = stats['created_at'].split()[0] if stats.get('created_at') else 'Неизвестно'
        last_activity = stats['last_activity'].split()[0] if stats.get('last_activity') else 'Неизвестно'
        
        response = (
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"👤 Имя: {stats.get('first_name', 'Неизвестно')}\n"
            f"📅 С нами с: {created_date}\n"
            f"🕒 Последняя активность: {last_activity}\n"
            f"🔢 Всего запросов: {stats.get('total_requests', 0)}\n"
        )
        
        await update.message.reply_text(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при получении статистики.")


async def show_popular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список популярных песен."""
    try:
        popular = get_popular_songs(limit=10)
        
        if not popular:
            await update.message.reply_text(
                "🔥 Популярные песни пока не найдены.\n"
                "Будьте первым, кто воспользуется ботом!"
            )
            return
        
        response = "🔥 <b>Топ популярных песен:</b>\n\n"
        
        for i, song in enumerate(popular, 1):
            response += (
                f"{i}. <b>{song['artist']}</b> - {song['song_name']}\n"
                f"   📊 Запросов: {song['access_count']}\n\n"
            )
        
        await update.message.reply_text(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при получении популярных песен: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при получении популярных песен.")


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает справку по командам."""
    help_text = (
        "📖 <b>Справка по командам:</b>\n\n"
        "/start - запустить бота и показать меню\n"
        "/analyze - начать анализ песни\n"
        "/history - показать вашу историю запросов (последние 10)\n"
        "/stats - показать вашу статистику\n"
        "/popular - показать топ популярных песен\n"
        "/help - показать эту справку\n"
        "/cancel - отменить текущее действие\n\n"
        "<b>Как это работает:</b>\n"
        "1. Используйте команду /analyze\n"
        "2. Введите имя исполнителя\n"
        "3. Введите название песни\n"
        "4. Получите анализ текста песни от AI\n\n"
        "💡 <i>Результаты кэшируются для быстрого доступа!</i>"
    )
    
    await update.message.reply_text(help_text, parse_mode="HTML")


async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает глобальную статистику (только для админа)."""
    # Можно добавить проверку на админа
    # admin_ids = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
    # if update.effective_user.id not in admin_ids:
    #     await update.message.reply_text("У вас нет доступа к этой команде.")
    #     return
    
    try:
        stats = get_global_stats()
        
        response = (
            f"📈 <b>Глобальная статистика бота:</b>\n\n"
            f"👥 Всего пользователей: {stats['total_users']}\n"
            f"📊 Всего запросов: {stats['total_queries']}\n"
            f"💾 Песен в кэше: {stats['cached_songs']}\n"
            f"🕐 Запросов за 24ч: {stats['recent_queries_24h']}\n"
            f"✨ Активных за 7д: {stats['active_users_7d']}\n"
        )
        
        await update.message.reply_text(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при получении глобальной статистики: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при получении статистики.")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError(
            "Необходимо установить переменную окружения TELEGRAM_BOT_TOKEN"
        )

    # Инициализируем базу данных при запуске
    init_database()
    logger.info("База данных инициализирована")

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_start)],
        states={
            ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, artist_received)],
            SONG: [MessageHandler(filters.TEXT & ~filters.COMMAND, song_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", show_help))
    application.add_handler(CommandHandler("history", show_history))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("popular", show_popular))
    application.add_handler(CommandHandler("adminstats", show_admin_stats))
    application.add_handler(conv_handler)

    logger.info("Бот запущен...")

    application.run_polling()


if __name__ == "__main__":
    main()
