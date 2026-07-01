import logging

import anthropic

import config

log = logging.getLogger(__name__)

_PROMPTS = {
    "cases": """Отполировать этот текст кейса как пост для Telegram канала.
Требования:
- 2-5 абзацев
- Без # в начале текста
- Без эмодзи и символов
- Без хэштегов
- Сохранить факты и цифры из оригинала
- Первая строка - краткий заголовок жирным шрифтом
- Последний абзац - краткий вывод

Кейс:
Title: {title}
Text: {content}""",
    "default": """Переписать эту новость на русском языке как пост для Telegram канала.
Требования:
- 2-5 абзацев
- Без # в начале текста
- Без эмодзи и символов
- Без хэштегов
- Добавить детали и факты из оригинальной новости
- Первая строка - краткий заголовок жирным шрифтом
- Последний абзац - краткое резюме новости

Новость:
Title: {title}
Description: {description}
Content: {content}""",
}


def rewrite(item):
    """Переписывает/адаптирует материал под Telegram через Claude."""
    try:
        template = _PROMPTS.get(item.source_type, _PROMPTS["default"])
        prompt = template.format(
            title=item.title,
            description=item.description,
            content=item.content,
        )

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        log.error(f"Claude error: {e}")
        return None
