
import os
import json
import time
import sqlite3
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
DB_PATH = os.environ.get("DB_PATH", "/data/games.sqlite3")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
OPENAI_API = "https://api.openai.com/v1/responses"

QUESTIONS = [
    ("players_type", "Кто играет?", ["👧 Только дети", "👨‍👩‍👧 Дети + взрослые", "👩 Только взрослые"]),
    ("ages", "Возраст участников?", ["2–3", "4–5", "6–7", "8–10", "11–13", "14+"]),
    ("count", "Сколько участников?", ["2", "3", "4", "5+"]),
    ("game_type", "Какой формат?", ["🎯 Квест", "🎲 Настольная игра", "🎭 Ролевая игра", "✨ Смешанный"]),
    ("theme", "Какая тема?", ["🧙 Фэнтези", "🏰 Средневековье", "🏴‍☠️ Пираты", "🔎 Детектив",
                              "🚀 Космос", "🦖 Динозавры", "🪄 Магия", "🏙 Современность",
                              "🎃 Хэллоуин", "🎄 Новый год", "🎲 Случайная"]),
    ("duration", "Сколько времени?", ["15–20 минут", "30 минут", "45 минут", "60 минут", "90–120 минут"]),
    ("place", "Где играем?", ["🏠 Квартира", "🏡 Дом", "🌿 Дача", "📍 Другое"]),
]

MENU = ["🎲 Создать игру", "✨ Удиви меня", "📚 Мои игры"]

def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, state TEXT, data TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS games(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, title TEXT, content TEXT, created_at TEXT
    )""")
    con.commit()
    return con

def tg(method, payload=None):
    data = urllib.parse.urlencode(payload or {}).encode()
    req = urllib.request.Request(f"{TG_API}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.loads(r.read().decode())

def send(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = json.dumps({
            "keyboard": [[{"text": x} for x in row] for row in keyboard],
            "resize_keyboard": True
        }, ensure_ascii=False)
    else:
        payload["reply_markup"] = json.dumps({"remove_keyboard": True})
    return tg("sendMessage", payload)

def split_text(text, limit=3900):
    return [text[i:i+limit] for i in range(0, len(text), limit)] or [""]

def save_user(user_id, state, data):
    con = db()
    con.execute("INSERT INTO users(user_id,state,data) VALUES(?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state,data=excluded.data",
                (user_id, state, json.dumps(data, ensure_ascii=False)))
    con.commit()
    con.close()

def load_user(user_id):
    con = db()
    row = con.execute("SELECT state,data FROM users WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    if not row:
        return None, {}
    return row[0], json.loads(row[1] or "{}")

def clear_user(user_id):
    save_user(user_id, "", {})

def save_game(user_id, title, content):
    con = db()
    con.execute("INSERT INTO games(user_id,title,content,created_at) VALUES(?,?,?,?)",
                (user_id, title, content, datetime.now().isoformat(timespec="seconds")))
    con.commit()
    con.close()

def my_games(user_id):
    con = db()
    rows = con.execute("SELECT id,title,content FROM games WHERE user_id=? "
                       "ORDER BY id DESC LIMIT 10", (user_id,)).fetchall()
    con.close()
    return rows

def openai_generate(prompt):
    body = json.dumps({
        "model": OPENAI_MODEL,
        "input": prompt,
        "max_output_tokens": 1800
    }).encode()
    req = urllib.request.Request(
        OPENAI_API,
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode())

    if data.get("output_text"):
        return data["output_text"].strip()

    parts = []
    for item in data.get("output", []):
        for c in item.get("content", []):
            if isinstance(c, dict) and c.get("text"):
                parts.append(c["text"])
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("OpenAI не вернул текст.")
    return text

def make_prompt(d):
    return f"""
Ты создаёшь домашнюю игру «Домашнее приключение» для семьи.
Параметры:
- участники: {d.get("players_type")}
- возраст: {d.get("ages")}
- количество: {d.get("count")}
- формат: {d.get("game_type")}
- тема: {d.get("theme")}
- длительность: {d.get("duration")}
- место: {d.get("place")}

Используй обычные безопасные предметы дома как реквизит: подушка, плед, шапка,
бумага, коробка, игрушки, ложка и т.п. Не требуй покупок.

ВАЖНО ПО БЕЗОПАСНОСТИ:
не используй огонь, горячие предметы, плиту, розетки, лекарства, бытовую химию,
острые/стеклянные/тяжёлые предметы, высоту, подоконники и опасные активные действия.
Для детей 2–5 лет задания должны быть короткими и простыми, без сложных загадок;
предусмотри помощь взрослого.

Ответ дай готовым сценарием, который можно сразу провести:
1. Название
2. Легенда и цель
3. Подготовка реквизита
4. Правила
5. Пошаговый сценарий с заданиями
6. Финал/награда
7. Советы ведущему

Пиши конкретно, весело и без лишней теории.
""".strip()

def start_create(chat_id, user_id):
    key, q, options = QUESTIONS[0]
    save_user(user_id, f"q:{key}", {})
    send(chat_id, q, [options[:2], options[2:]])

def surprise(chat_id, user_id):
    d = {
        "players_type": "Дети + взрослые",
        "ages": "4–5",
        "count": "3",
        "game_type": "Смешанный",
        "theme": "Случайная",
        "duration": "30 минут",
        "place": "Квартира",
    }
    send(chat_id, "✨ Придумываю неожиданное домашнее приключение…")
    try:
        text = openai_generate(make_prompt(d))
        save_game(user_id, "Удивительное домашнее приключение", text)
        for part in split_text(text):
            send(chat_id, part)
        send(chat_id, "Готово! Игра сохранена в «📚 Мои игры».", [MENU])
    except Exception as e:
        send(chat_id, f"Не удалось создать игру. Попробуй ещё раз.\n\nТехническая причина: {e}", [MENU])

def handle_text(chat_id, user_id, text):
    state, data = load_user(user_id)

    if text == "/start":
        clear_user(user_id)
        send(chat_id, "🏠 Добро пожаловать в «Домашнее приключение»!\n\nЯ помогу придумать игру или квест из обычных вещей дома.", [MENU])
        return

    if text == "🎲 Создать игру":
        start_create(chat_id, user_id)
        return

    if text == "✨ Удиви меня":
        surprise(chat_id, user_id)
        return

    if text == "📚 Мои игры":
        rows = my_games(user_id)
        if not rows:
            send(chat_id, "Пока сохранённых игр нет.", [MENU])
        else:
            buttons = [[f"#{r[0]} {r[1][:30]}"] for r in rows]
            buttons.append(["⬅️ В меню"])
            save_user(user_id, "games", {str(r[0]): r[2] for r in rows})
            send(chat_id, "📚 Твои последние игры:", buttons)
        return

    if text == "⬅️ В меню":
        clear_user(user_id)
        send(chat_id, "Главное меню:", [MENU])
        return

    if state == "games":
        for gid, content in data.items():
            if text.startswith(f"#{gid} "):
                for part in split_text(content):
                    send(chat_id, part)
                send(chat_id, "Готово. Что дальше?", [MENU])
                return

    if state.startswith("q:"):
        key = state[2:]
        idx = next((i for i, (k, _, _) in enumerate(QUESTIONS) if k == key), None)
        if idx is None:
            start_create(chat_id, user_id)
            return

        data[key] = text
        next_idx = idx + 1
        if next_idx < len(QUESTIONS):
            nk, question, options = QUESTIONS[next_idx]
            save_user(user_id, f"q:{nk}", data)
            rows = [options[i:i+2] for i in range(0, len(options), 2)]
            send(chat_id, question, rows)
        else:
            clear_user(user_id)
            send(chat_id, "⏳ Отлично! Создаю игру…")
            try:
                game = openai_generate(make_prompt(data))
                title = "Домашнее приключение"
                first = game.splitlines()
                for line in first[:5]:
                    if "Название" in line:
                        title = line.replace("#", "").replace("Название", "").replace(":", "").strip() or title
                        break
                save_game(user_id, title[:100], game)
                for part in split_text(game):
                    send(chat_id, part)
                send(chat_id, "🎉 Игра готова и сохранена!", [MENU])
            except Exception as e:
                send(chat_id, f"Не удалось создать игру.\n\nТехническая причина: {e}", [MENU])
        return

    send(chat_id, "Выбери действие:", [MENU])

def main():
    db()
    offset = 0
    print("Home Adventure bot started", flush=True)

    while True:
        try:
            result = tg("getUpdates", {
                "timeout": 50,
                "offset": offset,
                "allowed_updates": json.dumps(["message"])
            })
            for upd in result.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg or not msg.get("text"):
                    continue
                chat_id = msg["chat"]["id"]
                user_id = msg["from"]["id"]
                handle_text(chat_id, user_id, msg["text"].strip())
        except Exception as e:
            print(f"Loop error: {e}", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    main()
