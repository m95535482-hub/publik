import os
import random
import sqlite3
import threading
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import telebot

# Токен вашего бота
TOKEN = "8643024766:AAFkb8a0NzGGz6DJ2ksE2aqDwWsQbhTAybI"

# Данные администратора
ADMIN_ID = 1218168630
ADMIN_USERNAME = "Bruhki"

bot = telebot.TeleBot(TOKEN)
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Таблица пользователей и их баланса звёзд
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)
    
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
    
    # Таблица инвентаря
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
    
    # Базовые подарки
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
    conn.commit()
    conn.close()

init_db()

# Фоновый поток для работы бота
def run_bot():
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"Bot polling error: {e}")

threading.Thread(target=run_bot, daemon=True).start()

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
        "Welcome to CatRoll Mini App!\n\n"
        "• Open the Mini App using the menu button to play, check inventory, top up stars, and request withdrawals!",
        parse_mode="Markdown"
    )

# --- API Эндпоинты ---

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/api/user/{user_id}")
def get_user(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    conn.commit()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    conn.close()
    return {"user_id": user_id, "balance": balance}

@app.post("/api/topup/{user_id}")
def topup_balance(user_id: int, data: dict):
    amount = data.get("amount", 0)
    allowed_amounts = [100, 200, 500, 1000, 2500]
    
    if amount not in allowed_amounts:
        raise HTTPException(status_code=400, detail="Invalid topup amount")
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    new_balance = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    return {"success": True, "balance": new_balance}

@app.get("/api/gifts")
def get_gifts():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, image_url, anim_url, price FROM gifts")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "image_url": r[2], "anim_url": r[3], "price": r[4]} for r in rows]

@app.get("/api/inventory/{user_id}")
def get_inventory(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, gift_name, image_url, anim_url, status FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "gift_name": r[1], "image_url": r[2], "anim_url": r[3], "status": r[4]} for r in rows]

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
    
    success = False
    error_message = ""
    
    text_msg = (
        f"🎁 **GIFT WITHDRAWAL REQUEST!**\n\n"
        f"👤 **Winner ID:** `{user_id}`\n"
        f"🏆 **Gift:** `{gift_name}`\n"
        f"🆔 **Item ID in DB:** `{item_id}`\n\n"
        f"👉 Open the user's profile and send them this gift manually in Telegram!"
    )

    try:
        bot.send_message(ADMIN_ID, text_msg, parse_mode="Markdown")
        success = True
    except Exception as e1:
        error_message += f"ID error: {e1}; "

    if not success:
        try:
            admin_chat = bot.get_chat(ADMIN_USERNAME)
            bot.send_message(admin_chat.id, text_msg, parse_mode="Markdown")
            success = True
        except Exception as e2:
            error_message += f"Username error: {e2}"

    if not success:
        print(f"Failed to send notification to admin. {error_message}")
        raise HTTPException(status_code=500, detail=f"Telegram notification error: {error_message}")
        
    return {"message": "Success! The withdrawal request has been sent to the admin."}