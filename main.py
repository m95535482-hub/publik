import sqlite3
import random
import logging
import threading
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import telebot
from telebot import types

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Настройки бота и администратора ---
BOT_TOKEN = "8643024766:AAFkb8a0NzGGz6DJ2ksE2aqDwWsQbhTAybI"
ADMIN_ID = 1218168630

bot = telebot.TeleBot(BOT_TOKEN)

app = FastAPI(title="CatRoll WebApp Backend")

# CORS для стабильной работы внутри Telegram WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение статических файлов (index.html)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==========================================
# СТРОГАЯ БЕЗОПАСНОСТЬ: ФИКСИРОВАННЫЕ ЦЕНЫ НА СЕРВЕРЕ
# ==========================================
PRICES = {
    "starter": 50,   # Сейф Starter
    "rare": 250,     # Сейф Rare
    "legend": 1000,  # Сейф Royal
    "wheel": 100     # Колесо Фортуны
}

ITEMS_POOL = [
    {"id": 1, "name": "Bronze Star", "icon": "fa-star", "price": 10},
    {"id": 2, "name": "Silver Pack", "icon": "fa-gift", "price": 25},
    {"id": 3, "name": "Gold Box", "icon": "fa-box", "price": 50},
    {"id": 4, "name": "Ruby Gem", "icon": "fa-gem", "price": 100},
    {"id": 5, "name": "Crown", "icon": "fa-crown", "price": 250},
    {"id": 6, "name": "Trophy", "icon": "fa-trophy", "price": 500}
]

# --- Инициализация Базы Данных ---
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 267000
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

# --- Логика Telegram Бот Команд ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "User"
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 267000))
        conn.commit()
        balance = 267000
    else:
        balance = row[0]
    conn.close()

    markup = types.InlineKeyboardMarkup()
    web_app_info = types.WebAppInfo(url="https://your-domain.com/static/index.html") # Замените на ваш URL
    open_btn = types.InlineKeyboardButton(text="🐾 Открыть CatRoll", web_app=web_app_info)
    markup.add(open_btn)

    bot.send_message(
        message.chat.id,
        f"Привет, {username}! 🐾\n\n"
        f"Добро пожаловать в **CatRoll** — играй, открывай сейфы и крути Колесо Фортуны!\n\n"
        f"⭐ Твой текущий баланс: **{balance:,} ⭐**",
        parse_mode="Markdown",
        reply_markup=markup
    )

def start_bot_polling():
    logging.info("Запуск поллинга Telegram бота...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logging.error(f"Ошибка в поллинге бота: {e}")

# Запуск бота в отдельном потоке, чтобы не блокировать FastAPI
bot_thread = threading.Thread(target=start_bot_polling, daemon=True)
bot_thread.start()

# --- Модели данных Pydantic ---
class RollRequest(BaseModel):
    case_type: str = "starter"  # 'starter', 'rare', 'legend', 'wheel'
    is_demo: bool = False

class InvoiceRequest(BaseModel):
    amount: int

# --- API Эндпоинты Приложения ---

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

@app.get("/api/user/{user_id}")
def get_user_profile(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 267000))
        conn.commit()
        balance = 267000
    else:
        balance = row[0]
    conn.close()
    return {"user_id": user_id, "balance": balance}

@app.post("/api/roll/{user_id}")
async def roll_item(user_id: int, req: RollRequest):
    # БЕЗОПАСНОСТЬ: Сервер берет цену из своего словаря, игнорируя любые данные с клиента
    cost = PRICES.get(req.case_type, 50)
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    current_balance = row[0] if row else 267000

    if not req.is_demo:
        # БЕЗОПАСНОСТЬ: Серверная проверка недостаточности средств
        if current_balance < cost:
            conn.close()
            raise HTTPException(status_code=400, detail="Недостаточно звезд на балансе")
            
        current_balance -= cost
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (current_balance, user_id))
        conn.commit()

    # Генерация выигранного предмета
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

    # Отправка уведомления администратору в Telegram
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
        logging.error(f"Ошибка создания счета Telegram Stars: {e}")
        return {
            "success": True, 
            "invoice_link": f"https://t.me/CaaatRoll_Bot?start=topup_{req.amount}"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)