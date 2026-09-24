import os, json, asyncio, logging, sqlite3
from typing import Any
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from openai import AsyncOpenAI

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DB_PATH = os.getenv('DB_PATH', 'games.sqlite3')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.6-luna')
if not BOT_TOKEN: raise RuntimeError('BOT_TOKEN is not set')
if not OPENAI_API_KEY: raise RuntimeError('OPENAI_API_KEY is not set')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('home_adventure')
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

QUESTIONS = [
 ('players_type','Кто будет играть?',[('👶 Только дети','kids'),('👨‍👩‍👧 Дети + взрослые','family'),('👩 Только взрослые','adults')]),
 ('ages','Возраст участников?',[('2–3 года','2-3'),('4–5 лет','4-5'),('6–7 лет','6-7'),('8–10 лет','8-10'),('11–13 лет','11-13'),('14+','14+')]),
 ('count','Сколько участников?',[('2','2'),('3','3'),('4','4'),('5+','5+')]),
 ('game_type','Какой формат?',[('🗺 Квест','quest'),('🎲 Настольная игра','board'),('🎭 Ролевая игра','roleplay'),('🎯 Смешанный','mixed')]),
 ('theme','Тематика?',[('🧙 Фэнтези','fantasy'),('🏰 Средневековье','medieval'),('🏴‍☠️ Пираты','pirates'),('🕵️ Детектив','detective'),('🚀 Космос','space'),('🦖 Динозавры','dinosaurs'),('🧚 Волшебный мир','magic'),('🏙 Современность','modern'),('🎃 Хэллоуин','halloween'),('🎄 Новый год','new_year'),('🎲 Случайная','random')]),
 ('duration','Сколько времени?',[('15–20 минут','15-20'),('30 минут','30'),('45 минут','45'),('60 минут','60'),('1,5–2 часа','90-120')]),
 ('place','Где играем?',[('Квартира','apartment'),('Дом','house'),('Дача','dacha'),('Другое','other')]),
]
QMAP={k:(t,o) for k,t,o in QUESTIONS}

def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, state TEXT NOT NULL DEFAULT "idle", data TEXT NOT NULL DEFAULT "{}")')
    c.execute('CREATE TABLE IF NOT EXISTS games (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    c.commit(); c.close()

def set_user(uid,state,data=None):
    c=db(); c.execute('INSERT INTO users(user_id,state,data) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state,data=excluded.data',(uid,state,json.dumps(data or {},ensure_ascii=False))); c.commit(); c.close()

def get_user(uid):
    c=db(); c.execute('INSERT OR IGNORE INTO users(user_id) VALUES (?)',(uid,)); c.commit(); r=c.execute('SELECT state,data FROM users WHERE user_id=?',(uid,)).fetchone(); c.close(); return r['state'],json.loads(r['data'] or '{}')

def save_game(uid,title,content):
    c=db(); cur=c.execute('INSERT INTO games(user_id,title,content) VALUES (?,?,?)',(uid,title[:200],content)); c.commit(); x=cur.lastrowid; c.close(); return int(x)

def get_games(uid):
    c=db(); r=c.execute('SELECT id,title,created_at FROM games WHERE user_id=? ORDER BY id DESC LIMIT 10',(uid,)).fetchall(); c.close(); return r

def get_game(uid,gid):
    c=db(); r=c.execute('SELECT id,title,content FROM games WHERE id=? AND user_id=?',(gid,uid)).fetchone(); c.close(); return r

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✨ Создать игру',callback_data='menu:create')],[InlineKeyboardButton(text='🎲 Удиви меня',callback_data='menu:surprise')],[InlineKeyboardButton(text='📚 Мои игры',callback_data='menu:games')]])

def cancel_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='❌ Отмена',callback_data='menu:cancel')]])

def q_kb(key):
    _,opts=QMAP[key]; rows=[[InlineKeyboardButton(text=l,callback_data=f'q:{key}:{v}')] for l,v in opts]
    rows.append([InlineKeyboardButton(text='❌ Отмена',callback_data='menu:cancel')]); return InlineKeyboardMarkup(inline_keyboard=rows)

def split_message(text,limit=3900):
    if len(text)<=limit: return [text]
    out=[]; cur=''
    for p in text.split('\n\n'):
        p=p.strip()
        if not p: continue
        cand=p if not cur else cur+'\n\n'+p
        if len(cand)<=limit: cur=cand; continue
        if cur: out.append(cur); cur=''
        while len(p)>limit:
            cut=p.rfind('\n',0,limit); cut=cut if cut>limit//2 else p.rfind(' ',0,limit); cut=cut if cut>limit//2 else limit
            out.append(p[:cut].rstrip()); p=p[cut:].lstrip()
        cur=p
    if cur: out.append(cur)
    return out

async def send_long(message,text):
    for part in split_message(text): await message.answer(part)

def build_prompt(d,objects):
    return f'''Создай индивидуальную домашнюю игру/приключение на русском языке.

ПАРАМЕТРЫ: Кто играет: {d.get('players_type')}; Возраст: {d.get('ages')}; Участников: {d.get('count')}; Формат: {d.get('game_type')}; Тема: {d.get('theme')}; Время: {d.get('duration')}; Место: {d.get('place')}; Предметы дома: {objects}

Главный принцип: не проси покупать реквизит. Превращай обычные предметы пользователя в игровые объекты. Используй именно доступные предметы.

Возраст: 2–3 года — только очень простые короткие задания, поиск, движение, выбор и повторение; взрослый ведёт ребёнка; без сложных загадок, чтения и вычислений. 4–5 — простые загадки, поиск, сортировка, движение и воображение. 6–10 — логика, последовательности, таймер и простые шифры. 11+ — стратегия, роли, дедукция и повороты. В семейной игре взрослым дай роль ведущего/персонажа, но ребёнок остаётся главным участником.

Безопасность: никакого огня, плиты, горячего, розеток, лекарств, бытовой химии, острых/стеклянных/тяжёлых предметов, высоты, подоконников, балконов, опасных прыжков/лазания и бега там, где можно упасть или столкнуться. Маленькие дети — только под присмотром взрослого.

Структура: название; легенда; параметры; роли; превращение предметов в реквизит; подготовка 2–5 минут; готовая реплика начала; 3–6 этапов с целью, репликой ведущего, действиями и результатом; подсказки; готовый финал; безопасная награда без обязательных покупок; вариант усложнения/упрощения. Пиши так, чтобы родитель мог сразу провести игру.'''

async def generate_game(d,objects):
    r=await client.responses.create(model=OPENAI_MODEL,instructions='Ты опытный автор семейных домашних игр. Создавай весёлые, разнообразные и безопасные сценарии. Не требуй покупок и не предлагай опасные действия.',input=build_prompt(d,objects))
    return (r.output_text or '').strip()

def title_of(text):
    for line in text.splitlines():
        x=line.strip().lstrip('#').strip()
        if x: return x[:200]
    return 'Домашнее приключение'

async def show_question(message,index,data):
    if index>=len(QUESTIONS):
        set_user(message.from_user.id,'awaiting_objects',data)
        await message.answer('Отлично! Теперь напиши обычные предметы, которые есть под рукой.\n\nНапример: подушки, плед, стулья, кастрюля, крышка, мягкие игрушки, бумага, карандаши, фонарик.\n\nМожно списком через запятую.',reply_markup=cancel_kb()); return
    key,text,_=QUESTIONS[index]; data['_question_index']=index; set_user(message.from_user.id,f'question:{key}',data); await message.answer(text,reply_markup=q_kb(key))

@dp.message(CommandStart())
async def start(message):
    init_db(); set_user(message.from_user.id,'idle',{}); await message.answer('🏠 Добро пожаловать в «Домашнее приключение»!\n\nЯ превращу обычные вещи дома в реквизит для игры, подстрою задания под возраст и дам готовый сценарий.',reply_markup=main_menu())

@dp.message(Command('menu'))
async def menu(message): set_user(message.from_user.id,'idle',{}); await message.answer('Главное меню:',reply_markup=main_menu())

@dp.callback_query(F.data=='menu:create')
async def create(c): await c.answer(); set_user(c.from_user.id,'question:players_type',{'_question_index':0}); await c.message.answer(QUESTIONS[0][1],reply_markup=q_kb(QUESTIONS[0][0]))

@dp.callback_query(F.data=='menu:surprise')
async def surprise(c):
    await c.answer(); d={'players_type':'family','ages':'4-5','count':'3','game_type':'mixed','theme':'random','duration':'30','place':'apartment'}; set_user(c.from_user.id,'awaiting_objects',d)
    await c.message.answer('🎲 Я сам выбрал параметры!\n\nТеперь напиши обычные предметы, которые есть рядом. Например: подушки, плед, стулья, бумага, карандаши, мягкая игрушка, фонарик.',reply_markup=cancel_kb())

@dp.callback_query(F.data=='menu:cancel')
async def cancel(c): await c.answer(); set_user(c.from_user.id,'idle',{}); await c.message.answer('Хорошо, остановились. Что будем делать?',reply_markup=main_menu())

@dp.callback_query(F.data=='menu:games')
async def games(c):
    await c.answer(); rows=get_games(c.from_user.id)
    if not rows: await c.message.answer('📚 Здесь пока пусто. Создай первое домашнее приключение!',reply_markup=main_menu()); return
    kb=[[InlineKeyboardButton(text=f"🎮 {r['title'][:45]}",callback_data=f"game:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton(text='⬅️ В меню',callback_data='menu:cancel')]); await c.message.answer('📚 Твои последние игры:',reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith('game:'))
async def open_game(c):
    await c.answer(); row=get_game(c.from_user.id,int(c.data.split(':',1)[1]))
    if not row: await c.message.answer('Не нашла эту игру.',reply_markup=main_menu()); return
    await send_long(c.message,row['content']); await c.message.answer('Что дальше?',reply_markup=main_menu())

@dp.callback_query(F.data.startswith('q:'))
async def answer(c):
    await c.answer(); _,key,value=c.data.split(':',2); state,d=get_user(c.from_user.id); d[key]=value; idx=next(i for i,x in enumerate(QUESTIONS) if x[0]==key); await show_question(c.message,idx+1,d)

@dp.message(F.text)
async def text_input(message):
    state,d=get_user(message.from_user.id)
    if state!='awaiting_objects': await message.answer('Выбери действие в меню 👇',reply_markup=main_menu()); return
    objects=message.text.strip()
    if len(objects)<2: await message.answer('Напиши хотя бы несколько предметов, например: подушки, плед, бумага.'); return
    await message.answer('✨ Придумываю приключение… Это может занять немного времени.')
    try:
        game=await generate_game(d,objects)
        if not game: raise RuntimeError('Empty model response')
        save_game(message.from_user.id,title_of(game),game); set_user(message.from_user.id,'idle',{}); await send_long(message,game); await message.answer('💾 Я сохранила эту игру в «Мои игры».',reply_markup=main_menu())
    except Exception:
        logger.exception('Game generation failed'); await message.answer('Не получилось создать игру с первого раза 😔\nПроверь настройки OpenAI и попробуй ещё раз.',reply_markup=main_menu())

async def main():
    init_db(); logger.info('Home Adventure bot started'); await dp.start_polling(bot)

if __name__=='__main__': asyncio.run(main())
