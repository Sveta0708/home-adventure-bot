# Home Adventure Bot — Light

Минимальная версия для запуска на тарифе с ограниченной RAM.
Не использует aiogram, openai SDK или python-dotenv — только стандартную библиотеку Python.

Переменные окружения:
- BOT_TOKEN
- OPENAI_API_KEY
- OPENAI_MODEL (по умолчанию gpt-5.6-luna)
- DB_PATH (по умолчанию /data/games.sqlite3)

Для Amvera достаточно Dockerfile и этих переменных.
