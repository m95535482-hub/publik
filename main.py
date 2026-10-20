import sqlite3
import random
import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import telebot
from telebot import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = "8643024766:AAFkb8a0NzGGz6DJ2ksE2aqDwWsQbhTAybI"
ADMIN_ID = 1218168630
WEBHOOK_HOST = "https://publik-4.onrender.com" 
CHANNEL_USERNAME = "@CaaatRoll"

bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI(title="CatRoll WebApp Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

PRICES = {
    "starter": 50,
    "rare": 250,
    "legend": 1000,
    "wheel": 100
}

ITEMS_POOL = [
    {"id": 1, "name": "Bronze Star", "icon": "fa-star", "price": 10},
    {"id": 2, "name": "Silver Pack", "icon": "fa-gift", "price": 25},
    {"id": 3, "name": "Gold Box", "icon": "fa-box", "price": 50},
    {"id": 4, "name": "Ruby Gem", "icon": "fa-gem", "price": 100},
    {"id": 5, "name": "Crown", "icon": "fa-crown", "price": 250},
    {"id": 6, "name": "Trophy", "icon": "fa-trophy", "price": 500}
]

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT 'Player',
            photo_url TEXT DEFAULT '',
            balance INTEGER DEFAULT 267000,
            total_spent INTEGER DEFAULT 0,
            last_daily INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            icon TEXT,
            price INTEGER,
            status TEXT DEFAULT 'normal'
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    json_bytes = await request.body()
    json_str = json_bytes.decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return {"status": "ok"}

@app.on_event("startup")
def on_startup():
    try:
        webhook_url = f"{WEBHOOK_HOST}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logging.info(f"✅ Webhook успешно зарегистрирован: {webhook_url}")
    except Exception as e:
        logging.error(f"❌ Ошибка установки Webhook: {e}")

# Точная серверная проверка подписки через Telegram API
def check_user_subscription(user_id: int) -> bool:
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception as e:
        logging.error(f"Ошибка проверки подписки для user_id={user_id}: {e}")
    return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "Player"
    
    photo_url = ""
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][0].file_id
            file_info = bot.get_file(file_id)
            photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    except Exception as e:
        logging.error(f"Не удалось получить аватарку: {e}")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, username, photo_url, balance, total_spent, last_daily) VALUES (?, ?, ?, ?, 0, 0)", 
            (user_id, username, photo_url, 267000)
        )
        balance = 267000
    else:
        cursor.execute(
            "UPDATE users SET username = ?, photo_url = ? WHERE user_id = ?",
            (username, photo_url, user_id)
        )
        balance = row[0]
        
    conn.commit()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    web_app_info = types.WebAppInfo(url=f"{WEBHOOK_HOST}/static/index.html")
    open_btn = types.InlineKeyboardButton(text="🐾 Открыть CatRoll", web_app=web_app_info)
    markup.add(open_btn)

    bot.send_message(
        message.chat.id,
        f"Привет, {username}! 🐾\n\n"
        f"Добро пожаловать в **CatRoll**!\n\n"
        f"⭐ Твой текущий баланс: **{balance} ⭐**",
        parse_mode="Markdown",
        reply_markup=markup
    )

class RollRequest(BaseModel):
    case_type: str = "starter"
    is_demo: bool = False

class InvoiceRequest(BaseModel):
    amount: int

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

@app.get("/api/user/{user_id}")
def get_user_profile(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, last_daily FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance, last_daily) VALUES (?, ?, 0)", (user_id, 267000))
        conn.commit()
        balance = 267000
        last_daily = 0
    else:
        balance, last_daily = row[0], row[1]
    conn.close()
    return {"user_id": user_id, "balance": balance, "last_daily": last_daily}

@app.get("/api/leaderboard/{user_id}")
def get_leaderboard(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, photo_url, total_spent FROM users ORDER BY total_spent DESC LIMIT 10")
    top_users = cursor.fetchall()
    
    cursor.execute("""
        SELECT rank FROM (
            SELECT user_id, ROW_NUMBER() OVER (ORDER BY total_spent DESC) as rank 
            FROM users
        ) WHERE user_id = ?
    """, (user_id,))
    user_rank_row = cursor.fetchone()
    my_rank = user_rank_row[0] if user_rank_row else "-"
    conn.close()
    
    return {
        "top": [
            {
                "username": u[1] or "Player",
                "photo_url": u[2] or "",
                "total_spent": u[3],
                "is_me": u[0] == user_id
            } for u in top_users
        ],
        "my_rank": my_rank
    }

# Отдельная ручная проверка подписки с веб-интерфейса
@app.get("/api/check-sub/{user_id}")
def check_sub_status(user_id: int):
    is_subbed = check_user_subscription(user_id)
    return {"subscribed": is_subbed}

# Защищенный ежедневный спин
@app.post("/api/daily-spin/{user_id}")
async def daily_spin(user_id: int):
    if not check_user_subscription(user_id):
        raise HTTPException(
            status_code=403, 
            detail="NOT_SUBSCRIBED"
        )

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    current_time = int(time.time() * 1000)
    cooldown = 24 * 60 * 60 * 1000
    
    last_daily = row[0] if row else 0
    if current_time - last_daily < cooldown:
        conn.close()
        raise HTTPException(
            status_code=400, 
            detail="COOLDOWN_ACTIVE"
        )

    cursor.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    won_item = random.choice(ITEMS_POOL)
    cursor.execute(
        "INSERT INTO inventory (user_id, name, icon, price, status) VALUES (?, ?, ?, ?, 'normal')",
        (user_id, won_item["name"], won_item["icon"], won_item["price"])
    )
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()

    return {
        "success": True,
        "won_item": won_item,
        "item_id": item_id,
        "next_daily": current_time + cooldown
    }

@app.post("/api/roll/{user_id}")
async def roll_item(user_id: int, req: RollRequest):
    cost = PRICES.get(req.case_type, 50)
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, total_spent FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    current_balance = row[0] if row else 267000
    current_spent = row[1] if row else 0

    if not req.is_demo:
        if current_balance < cost:
            conn.close()
            raise HTTPException(status_code=400, detail="Недостаточно звезд на балансе")
            
        current_balance -= cost
        new_spent = current_spent + cost
        cursor.execute("UPDATE users SET balance = ?, total_spent = ? WHERE user_id = ?", (current_balance, new_spent, user_id))
        conn.commit()

    won_item = random.choice(ITEMS_POOL)
    item_id = None

    if not req.is_demo:
        cursor.execute(
            "INSERT INTO inventory (user_id, name, icon, price, status) VALUES (?, ?, ?, ?, 'normal')",
            (user_id, won_item["name"], won_item["icon"], won_item["price"])
        )
        conn.commit()
        item_id = cursor.lastrowid

    conn.close()
    return {
        "success": True,
        "cost_deducted": cost,
        "balance": current_balance,
        "item_id": item_id,
        "won_item": won_item
    }

@app.get("/api/inventory/{user_id}")
def get_user_inventory(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, icon, price, status FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "icon": r[2], "price": r[3], "status": r[4]} for r in rows]

@app.post("/api/sell/{item_id}")
def sell_inventory_item(item_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, price FROM inventory WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Предмет не найден")
    
    user_id, price = item
    cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    new_balance = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return {"success": True, "balance": new_balance}

@app.post("/api/withdraw/{item_id}")
def withdraw_inventory_item(item_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, name, price FROM inventory WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Предмет не найден")

    user_id, item_name, price = item
    cursor.execute("UPDATE inventory SET status = 'withdraw_requested' WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

    try:
        bot.send_message(
            ADMIN_ID,
            f"🔔 **Запрос на вывод предмета!**\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"🎁 Предмет: {item_name} ({price} ⭐)\n"
            f"🆔 Item ID: `{item_id}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения админу: {e}")

    return {"success": True, "message": "Запрос на вывод отправлен администратору"}

@app.post("/api/create-invoice/{user_id}")
def create_stars_invoice(user_id: int, req: InvoiceRequest):
    try:
        invoice_link = bot.create_invoice_link(
            title="Пополнение Stars",
            description=f"Пакет {req.amount} Telegram Stars для CatRoll",
            payload=f"topup_{user_id}_{req.amount}",
            provider_token="",
            currency="XTR",
            prices=[telebot.types.LabeledPrice(label=f"{req.amount} Stars", amount=req.amount)]
        )
        return {"success": True, "invoice_link": invoice_link}
    except Exception as e:
        return {
            "success": True, 
            "invoice_link": f"https://t.me/CaaatRoll_Bot?start=topup_{req.amount}"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)