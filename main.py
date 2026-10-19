import os
import random
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import telebot

# Токен бота
TOKEN = os.getenv("BOT_TOKEN", "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")

# Ваш юзернейм администратора в Telegram
ADMIN_USERNAME = "Bruhki"

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
            anim_url TEXT NOT NULL,
            status TEXT DEFAULT 'in_inventory'
        )
    """)
    
    # Автоматическое добавление базовых подарков при первом запуске
    cursor.execute("SELECT COUNT(*) FROM gifts")
    if cursor.fetchone()[0] == 0:
        base_gifts = [
            ("Star Pouch", "⭐", "⭐", 30),
            ("Gift Box", "🎁", "🎁", 60),
            ("Rubber Duck", "🦆", "🦆", 120),
            ("Telegram Gem", "💎", "💎", 250),
            ("Rocket Gift", "🚀", "🚀", 450),
            ("Golden Crown", "👑", "👑", 800),
            ("Cyber Cat NFT", "🐱", "🐱", 1500),
            ("Diamond", "💠", "💠", 2500)
        ]
        cursor.executemany(
            "INSERT INTO gifts (name, image_url, anim_url, price) VALUES (?, ?, ?, ?)", 
            base_gifts
        )
        print("✅ Базовые подарки успешно загружены в базу данных!")
        
    conn.commit()
    conn.close()

init_db()

def give_random_gift(user_id: int):
    """Выбор случайного подарка из базы и добавление в инвентарь игрока"""
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
        "Welcome to CatRoll Mini App!\n\n"
        "• Type `/buy` to get a test gift into your inventory.\n"
        "• Open the Mini App using the menu button to check your inventory and request withdrawals!",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['buy'])
def handle_buy_free(message):
    user_id = message.from_user.id
    gift_name = give_random_gift(user_id)
    
    if not gift_name:
        bot.send_message(message.chat.id, "❌ No available gifts found in the database.")
    else:
        bot.send_message(
            message.chat.id, 
            f"🎉 Congratulations! You received: **{gift_name}**!\n\n"
            f"The item has been added to your inventory in the Mini App.",
            parse_mode="Markdown"
        )


# --- API Эндпоинты для Mini App ---

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
    cursor.execute("SELECT id, gift_name, image_url, anim_url, status FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"id": r[0], "gift_name": r[1], "image_url": r[2], "anim_url": r[3], "status": r[4]}
        for r in rows
    ]

@app.post("/api/roll/{user_id}")
def api_roll(user_id: int):
    gift_name = give_random_gift(user_id)
    if not gift_name:
        raise HTTPException(status_code=400, detail="No gifts available")
    return {"gift_name": gift_name}

@app.post("/api/withdraw/{item_id}")
def withdraw_item(item_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id, gift_name, status FROM inventory WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")
        
    user_id, gift_name, status = row
    
    if status == 'withdraw_requested':
        conn.close()
        return {"message": "Withdrawal request already submitted!"}
        
    cursor.execute("UPDATE inventory SET status = 'withdraw_requested' WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    try:
        # Автоматическое определение числового ID администратора по юзернейму
        admin_info = bot.get_chat(ADMIN_USERNAME)
        admin_chat_id = admin_info.id
        
        user_info = bot.get_chat(user_id)
        username = f"@{user_info.username}" if user_info.username else f"ID: `{user_id}`"
        
        bot.send_message(
            admin_chat_id,
            f"🎁 **GIFT WITHDRAWAL REQUEST!**\n\n"
            f"👤 **Winner:** {username}\n"
            f"🏆 **Gift:** `{gift_name}`\n"
            f"🆔 **Item ID in DB:** `{item_id}`\n\n"
            f"👉 Open the user's profile and send them this gift manually in Telegram!",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to send notification to admin: {e}")
        raise HTTPException(status_code=500, detail=f"Telegram error: {str(e)}")
        
    return {"message": "Success! The withdrawal request has been sent to the admin."}