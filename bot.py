import os, json, sqlite3, asyncio
from dotenv import load_dotenv
load_dotenv()
from typing import Optional
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from openai import AsyncOpenAI

BOT_TOKEN=os.getenv('BOT_TOKEN')
OPENAI_API_KEY=os.getenv('OPENAI_API_KEY')
DB=os.getenv('DB_PATH','games.sqlite3')
if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError('Set BOT_TOKEN and OPENAI_API_KEY environment variables')

client=AsyncOpenAI(api_key=OPENAI_API_KEY)
bot=Bot(BOT_TOKEN)
dp=Dispatcher()

QUESTIONS=[
 ('players_type','Кто будет играть?',['👶 Только дети','👨‍👩‍👧 Дети + взрослые','👩 Только взрослые']),
 ('ages','Возраст участников?',['2–3 года','4–5 лет','6–7 лет','8–10 лет','11–13 лет','14+']),
 ('count','Сколько участников?',['2','3','4','5+']),
 ('game_type','Какой формат?',['🗺 Квест','🎲 Настольная игра','🎭 Ролевая игра','🎯 Смешанный']),
 ('theme','Тематика?',['🧙 Фэнтези','🏰 Средневековье','🏴‍☠️ Пираты','🕵️ Детектив','🚀 Космос','🦖 Динозавры','🧚 Волшебный мир','🏙 Современность','🎃 Хэллоуин','🎄 Новый год','🎲 Случайная']),
 ('duration','Сколько времени?',['15–20 минут','30 минут','45 минут','60 минут','1,5–2 часа']),
 ('place','Где играем?',['Квартира','Дом','Дача','Другое']),
]

def db():
    c=sqlite3.connect(DB); c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, state TEXT, data TEXT)'); c.commit(); return c

def get_user(uid):
    c=db(); r=c.execute('SELECT state,data FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return (r[0],json.loads(r[1])) if r else (None,{})

def set_user(uid,state,data):
    c=db(); c.execute('INSERT INTO users(id,state,data) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,data=excluded.data',(uid,state,json.dumps(data,ensure_ascii=False))); c.commit(); c.close()

def kb(options):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x,callback_data=x)] for x in options])

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text='🎮 Создать игру',callback_data='new')],
      [InlineKeyboardButton(text='🎲 Удиви меня',callback_data='surprise')],
      [InlineKeyboardButton(text='📚 Мои игры',callback_data='games')],
    ])

@dp.message(CommandStart())
async def start(m:Message):
    set_user(m.from_user.id,'menu',{})
    await m.answer('🏰 Добро пожаловать в «Домашнее приключение»!\n\nЯ превращу вашу квартиру и обычные предметы в настоящее приключение. Ничего специально покупать не нужно.\n\nГотовы?',reply_markup=menu())

@dp.callback_query(F.data=='new')
async def new(c:CallbackQuery):
    data={}; set_user(c.from_user.id,'q0',data); await c.message.edit_text(QUESTIONS[0][1],reply_markup=kb(QUESTIONS[0][2])); await c.answer()

@dp.callback_query(F.data=='surprise')
async def surprise(c:CallbackQuery):
    data={'players_type':'Дети + взрослые','ages':'5–7 лет','count':'3','game_type':'🎯 Смешанный','theme':'🎲 Случайная','duration':'30 минут','place':'Квартира'}
    set_user(c.from_user.id,'props',data); await c.message.edit_text('🎒 Напишите предметы, которые можно использовать дома.\n\nНапример: подушки, плед, коробка, игрушки, фонарик, шапка, мяч.'); await c.answer()

@dp.callback_query(F.data=='games')
async def games(c:CallbackQuery):
    await c.message.edit_text('📚 В MVP сохранение истории подключается автоматически после первой игры.\n\nНажмите «Создать игру», чтобы начать.',reply_markup=menu()); await c.answer()

@dp.callback_query()
async def answer(c:CallbackQuery):
    state,data=get_user(c.from_user.id)
    if not state.startswith('q'): return
    idx=int(state[1:]); key=QUESTIONS[idx][0]; data[key]=c.data
    nxt=idx+1
    if nxt < len(QUESTIONS):
        set_user(c.from_user.id,f'q{nxt}',data); await c.message.edit_text(QUESTIONS[nxt][1],reply_markup=kb(QUESTIONS[nxt][2]))
    else:
        set_user(c.from_user.id,'props',data); await c.message.edit_text('🎒 Отлично! Теперь напишите предметы, которые можно использовать.\n\nПример: шапка, подушки, плед, коробка, игрушечный меч, фонарик.')
    await c.answer()

@dp.message()
async def text(m:Message):
    state,data=get_user(m.from_user.id)
    if state!='props':
        await m.answer('Нажмите /start, чтобы начать.',reply_markup=menu()); return
    data['props']=m.text
    set_user(m.from_user.id,'generating',data)
    await m.answer('✨ Собираю приключение... Придумываю сюжет, роли, испытания и финал.')
    system='''Ты профессиональный сценарист семейных домашних игр. Создавай уникальные, увлекательные и безопасные игры для квартиры/дома. Используй предметы пользователя как реквизит, не требуй покупок. Учитывай возраст: для 2-5 лет задания простые, короткие, понятные и с участием взрослого; сложность увеличивай сюжетом, а не сложными загадками. Не используй огонь, горячее, плиту, розетки, лекарства, химию, острые/стеклянные предметы, высоту, подоконники, опасный бег или лазание. Структура: название, параметры, роли, реквизит, подготовка ведущего, вступление, цель, 3-6 этапов с репликами и действиями, подсказки, финал, награда. Пиши живо и красочно, но практично. Ведущему отдельно указывай, что спрятать и где. Ответ на русском.'''
    prompt='Параметры игры:\n'+json.dumps(data,ensure_ascii=False,indent=2)+'\n\nСделай готовый сценарий, который можно сразу проводить.'
    try:
        r=await client.responses.create(model='gpt-5.6-luna',input=[{'role':'system','content':system},{'role':'user','content':prompt}],max_output_tokens=5000)
        game=r.output_text
    except Exception as e:
        game='Не удалось создать игру. Попробуйте ещё раз через минуту.'
    set_user(m.from_user.id,'menu',data)
    await m.answer(game,reply_markup=menu())

async def main():
    db(); await dp.start_polling(bot)

if __name__=='__main__': asyncio.run(main())
