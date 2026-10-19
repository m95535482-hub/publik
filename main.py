import os
import random
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import telebot

# Токен вашего бота
TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
bot = telebot.TeleBot(TOKEN)

app = FastAPI()

# Подключение статических файлов (фронтенд Mini App)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Инициализация базы данных SQLite
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Таблица подарков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image_url TEXT NOT NULL,
            anim_url TEXT NOT NULL,
            price INTEGER NOT NULL
        )
    """)
    
    # Таблица инвентаря игроков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_name TEXT NOT NULL,
            image_url TEXT NOT NULL,
            anim_url TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

init_db()


# Вспомогательная функция выдачи случайного подарка игроку
def give_random_gift(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, image_url, anim_url FROM gifts")
    gifts = cursor.fetchall()
    
    if not gifts:
        conn.close()
        return None
    
    chosen = random.choice(gifts)
    gift_name, image_url, anim_url = chosen
    
    cursor.execute(
        "INSERT INTO inventory (user_id, gift_name, image_url, anim_url) VALUES (?, ?, ?, ?)",
        (user_id, gift_name, image_url, anim_url)
    )
    conn.commit()
    conn.close()
    
    return gift_name


# --- Команды Telegram Бота ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Привет! Добро пожаловать в игру.\n\n"
        "• `/buy` — получить бесплатный подарок в инвентарь (тестовый режим)\n"
        "• `/add Название | Ссылка_на_фото | Ссылка_на_анимацию | Цена` — добавить новый предмет (для админа)",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['buy'])
def handle_buy_free(message):
    """Тестовая команда без оплаты звёздами"""
    user_id = message.from_user.id
    gift_name = give_random_gift(user_id)
    
    if not gift_name:
        bot.send_message(message.chat.id, "❌ В базе данных пока нет доступных подарков. Добавьте их через `/add`.")
    else:
        bot.send_message(
            message.chat.id, 
            f"🎉 Вы бесплатно получили подарок: **{gift_name}**!\n"
            f"Он уже добавлен в ваш инвентарь в Mini App.",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['add'])
def handle_add_gift(message):
    """Добавление нового подарка в базу данных"""
    try:
        text = message.text.replace('/add', '').strip()
        parts = [p.strip() for p in text.split('|')]
        
        if len(parts) != 4:
            bot.reply_to(message, "⚠️ Неверный формат!\nИспользуйте: `/add Название | Ссылка_на_картинку | Ссылка_на_анимацию | Цена`")
            return
            
        name, image_url, anim_url, price = parts[0], parts[1], parts[2], int(parts[3])
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO gifts (name, image_url, anim_url, price) VALUES (?, ?, ?, ?)",
            (name, image_url, anim_url, price)
        )
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Подарок **{name}** успешно добавлен в игру!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при добавлении: {e}")


# --- API Маршруты для Mini App ---

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/api/gifts")
def get_gifts():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, image_url, anim_url, price FROM gifts")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"id": r[0], "name": r[1], "image_url": r[2], "anim_url": r[3], "price": r[4]}
        for r in rows
    ]

@app.get("/api/inventory/{user_id}")
def get_inventory(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, gift_name, image_url, anim_url FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"id": r[0], "gift_name": r[1], "image_url": r[2], "anim_url": r[3]}
        for r in rows
    ]