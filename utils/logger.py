import logging


def get_logger(name: str) -> logging.Logger:
    """
    Создает и настраивает логгер с указанным именем.
    
    Args:
        name: Имя логгера (обычно __name__ модуля)
        
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    
    # Если у логгера уже есть обработчики, не добавляем новые
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    
    logger.addHandler(stream_handler)
    
    return logger


# Основной логгер для обратной совместимости
logger = get_logger(__name__)
