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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

ARTIST, SONG = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    await update.message.reply_text(
        "Привет! Я бот для анализа текстов песен.\n"
        "Отправь мне команду /analyze, чтобы начать."
    )


async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и запрашивает имя исполнителя."""
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

    try:
        async with AnylyzeService() as service:
            data = await service.analyze(artist, song_name)

        if not data or "summary" not in data:
            await processing_message.edit_text(
                "Не удалось получить данные для этой песни. Проверьте правильность написания."
            )
            return ConversationHandler.END

        response_text = (
            f"<b>Краткий обзор песни «{song_name}» исполнителя {artist}:</b>\n\n"
            f"{data['summary']}"
        )

        await processing_message.edit_text(response_text, parse_mode="MARKDOWN")

    except Exception as e:
        logger.error(
            f"Ошибка при анализе песни {artist} - {song_name}: {e}", exc_info=True
        )
        await processing_message.edit_text(
            "Произошла ошибка во время анализа. Попробуйте еще раз позже."
        )
    finally:
        context.user_data.clear()
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог."""
    await update.message.reply_text("Действие отменено.")
    context.user_data.clear()
    return ConversationHandler.END


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError(
            "Необходимо установить переменную окружения TELEGRAM_BOT_TOKEN"
        )

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_start)],
        states={
            ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, artist_received)],
            SONG: [MessageHandler(filters.TEXT & ~filters.COMMAND, song_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    logger.info("Бот запущен...")

    application.run_polling()


if __name__ == "__main__":
    main()
