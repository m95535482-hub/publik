import os
import random
import sqlite3
import threading
import time
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import telebot
from telebot.types import LabeledPrice

TOKEN = "8643024766:AAFkb8a0NzGGz6DJ2ksE2aqDwWsQbhTAybI"

ADMIN_ID = 1218168630
ADMIN_USERNAME = "Bruhki"

bot = telebot.TeleBot(TOKEN)
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image_url TEXT NOT NULL,
            anim_url TEXT NOT NULL,
            price INTEGER NOT NULL
        )
    """)
    
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

# --- ОБРАБОТЧИКИ ОПЛАТЫ TELEGRAM STARS ---

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    payment_info = message.successful_payment
    user_id = message.from_user.id
    stars_amount = payment_info.total_amount
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (stars_amount, user_id))
    conn.commit()
    conn.close()
    
    try:
        bot.send_message(user_id, f"✅ Оплата прошла успешно! Вам начислено **{stars_amount} ⭐**.", parse_mode="Markdown")
    except Exception as e:
        print(f"Failed to send confirmation message: {e}")

def run_bot():
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(3)

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

# --- API ЭНДПОИНТЫ ---

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

@app.post("/api/create-invoice/{user_id}")
def create_invoice(user_id: int, data: dict):
    amount = data.get("amount", 0)
    allowed_amounts = [100, 200, 500, 1000, 2500]
    
    if amount not in allowed_amounts:
        raise HTTPException(status_code=400, detail="Invalid topup amount")
        
    prices = [LabeledPrice(label=f"{amount} Telegram Stars", amount=amount)]
    
    try:
        # Исправлено: аргумент называется 'payload', а не 'invoice_payload'
        invoice_link = bot.create_invoice_link(
            title=f"Пополнение {amount} Stars",
            description=f"Пополнение баланса в CatRoll на {amount} звёзд",
            payload=f"topup_{user_id}_{amount}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        return {"success": True, "invoice_link": invoice_link}
    except Exception as e:
        print(f"Invoice creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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