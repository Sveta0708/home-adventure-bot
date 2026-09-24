# Домашнее приключение — Telegram MVP

## Что умеет
- анкета: участники, возраст, количество, формат, тема, время, место
- список домашних предметов
- генерация готового семейного квеста/ролевой/настольной игры через OpenAI
- режим «Удиви меня»
- базовая SQLite база
- русские кнопки Telegram
- safety-правила в системном промте

## Запуск
1. Создайте бота через @BotFather и получите BOT_TOKEN.
2. Получите OPENAI_API_KEY.
3. Установите Python 3.11+.
4. `pip install -r requirements.txt`
5. Linux/macOS: `export BOT_TOKEN='...' && export OPENAI_API_KEY='...'`
   Windows PowerShell: `$env:BOT_TOKEN='...'; $env:OPENAI_API_KEY='...'`
6. `python bot.py`

Бот работает через long polling, поэтому для MVP не нужен отдельный webhook.
