# 🏠 Домашнее приключение — Telegram Bot v2

Обновлённый MVP семейного Telegram-бота.

## Что улучшено
- SQLite-история созданных игр;
- раздел «📚 Мои игры»;
- открытие сохранённых сценариев;
- автоматическое разделение длинных сообщений Telegram;
- загрузка `.env` через python-dotenv;
- модель OpenAI настраивается через `OPENAI_MODEL`;
- безопасный промпт и возрастная адаптация;
- режим «🎲 Удиви меня»;
- `.gitignore`, чтобы `.env` и база не попадали в Git;
- Dockerfile для будущего размещения.

## Локальный запуск
```bash
python -m pip install -r requirements.txt
python bot.py
```
Создай `.env` рядом с `bot.py` и укажи `BOT_TOKEN`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `DB_PATH`.

**Важно:** `.env` не загружать в GitHub.

## Команда запуска на сервере
`python bot.py`

Бот использует Telegram long polling; для одного токена должен работать только один polling-процесс.
