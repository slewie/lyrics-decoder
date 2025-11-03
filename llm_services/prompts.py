from textwrap import dedent
from langchain.prompts import ChatPromptTemplate


# TODO: make prompts for different languages
summarize_template = ChatPromptTemplate.from_template(
    dedent(
        """
        Ты — музыкальный аналитик.
        Дай краткий обзор основных тем и мотивов в этом тексте песни, объясни суть песни, различные отсылки.
        Используй цитаты в формате markdown, чтобы пояснить смысл строк.
        В качестве дополнительного источника используй данные об исполнителе:
        {artist_info}

        Текст песни:
        {lyrics}
        """
    )
)

explain_template = ChatPromptTemplate.from_template(
    dedent(
        """Ты — музыкальный аналитик. Объясни смысл следующей строки из песни {song_name}, исполнителя {artist_name}, дай возможные трактовки, будь лаконичен и краток(не больше пары предложений).
        "{line}"
        """
    )
)


collect_artist_info_template = ChatPromptTemplate.from_template(
    dedent(
        """
        Ты - музыкальный аналитик. Найди главные тематики у исполнителя {artist_name}. 
        Проведи очень глубокий анализ его творчества и выведи только основные темы и мотивы, которые он использует в своих песнях.
        Вывод оформи в виде bullet list, старайся оформить каждый пункт в виде keywords
        """
    )
)
