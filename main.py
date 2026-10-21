import os
import time
import random
import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import telebot

BOT_TOKEN = "8643024766:AAFkb8a0NzGGz6DJ2ksE2aqDwWsQbhTAybI"
CHANNEL_ID = "@CaaatRoll"
ADMIN_ID = 1218168630

bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

DB_PATH = "database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            photo_url TEXT,
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

ITEMS_POOL = [
    {"id": 1, "name": "Bronze Star", "icon": "fa-star", "price": 10, "weight": 50},
    {"id": 2, "name": "Silver Pack", "icon": "fa-gift", "price": 25, "weight": 30},
    {"id": 3, "name": "Gold Box", "icon": "fa-box", "price": 50, "weight": 12},
    {"id": 4, "name": "Ruby Gem", "icon": "fa-gem", "price": 100, "weight": 5},
    {"id": 5, "name": "Crown", "icon": "fa-crown", "price": 250, "weight": 2},
    {"id": 6, "name": "Trophy", "icon": "fa-trophy", "price": 500, "weight": 1}
]

def pick_random_item():
    weights = [item["weight"] for item in ITEMS_POOL]
    return random.choices(ITEMS_POOL, weights=weights, k=1)[0]

def check_tg_subscription(user_id: int) -> bool:
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        print(f"Sub check error: {e}")
        return False

class UserUpdate(BaseModel):
    username: Optional[str] = None
    photo_url: Optional[str] = None

class RollRequest(BaseModel):
    case_type: str
    is_demo: bool = False

class InvoiceRequest(BaseModel):
    amount: int

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)", (user_id, f"User_{user_id}", 267000))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return dict(user)

@app.post("/api/user/{user_id}")
async def update_user(user_id: int, data: UserUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET username = COALESCE(?, username), photo_url = COALESCE(?, photo_url) WHERE user_id = ?", 
                   (data.username, data.photo_url, user_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/check-sub/{user_id}")
async def check_sub_api(user_id: int):
    is_subbed = check_tg_subscription(user_id)
    return {"subscribed": is_subbed}

@app.post("/api/daily-spin/{user_id}")
async def daily_spin(user_id: int):
    if not check_tg_subscription(user_id):
        raise HTTPException(status_code=403, detail="NOT_SUBSCRIBED")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    now_ms = int(time.time() * 1000)
    cooldown = 24 * 60 * 60 * 1000

    if row and (now_ms - row["last_daily"]) < cooldown:
        conn.close()
        raise HTTPException(status_code=400, detail="COOLDOWN_ACTIVE")

    won_item = pick_random_item()
    cursor.execute("INSERT INTO inventory (user_id, name, icon, price) VALUES (?, ?, ?, ?)",
                   (user_id, won_item["name"], won_item["icon"], won_item["price"]))
    item_id = cursor.lastrowid

    cursor.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (now_ms, user_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "won_item": won_item,
        "item_id": item_id,
        "next_daily": now_ms + cooldown
    }

@app.post("/api/roll/{user_id}")
async def roll(user_id: int, req: RollRequest):
    costs = {"starter": 50, "rare": 250, "legend": 1000, "wheel": 100}
    cost = costs.get(req.case_type, 50)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance, total_spent FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    if not req.is_demo and user["balance"] < cost:
        conn.close()
        raise HTTPException(status_code=400, detail="INSUFFICIENT_FUNDS")

    won_item = pick_random_item()
    item_id = None

    if not req.is_demo:
        new_balance = user["balance"] - cost
        new_spent = user["total_spent"] + cost
        cursor.execute("UPDATE users SET balance = ?, total_spent = ? WHERE user_id = ?", (new_balance, new_spent, user_id))
        cursor.execute("INSERT INTO inventory (user_id, name, icon, price) VALUES (?, ?, ?, ?)",
                       (user_id, won_item["name"], won_item["icon"], won_item["price"]))
        item_id = cursor.lastrowid
        conn.commit()
        current_balance = new_balance
    else:
        current_balance = user["balance"]

    conn.close()
    return {
        "success": True,
        "won_item": won_item,
        "balance": current_balance,
        "item_id": item_id
    }

@app.get("/api/inventory/{user_id}")
async def get_inventory(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory WHERE user_id = ? ORDER BY id DESC", (user_id,))
    items = cursor.fetchall()
    conn.close()
    return [dict(i) for i in items]

@app.post("/api/sell/{item_id}")
async def sell_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")

    user_id = item["user_id"]
    price = item["price"]

    cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
    conn.commit()

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    new_bal = cursor.fetchone()["balance"]
    conn.close()

    return {"success": True, "balance": new_bal}

@app.post("/api/withdraw/{item_id}")
async def withdraw_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")

    cursor.execute("UPDATE inventory SET status = 'withdraw_requested' WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

    try:
        bot.send_message(
            ADMIN_ID,
            f"🔔 **Запрос на вывод предмета!**\n"
            f"User ID: `{item['user_id']}`\n"
            f"Предмет: {item['name']} ({item['price']} ⭐)\n"
            f"Item ID: `{item['id']}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to notify admin: {e}")

    return {"success": True, "message": "Withdrawal request sent"}

@app.get("/api/leaderboard/{user_id}")
async def leaderboard(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, photo_url, total_spent FROM users ORDER BY total_spent DESC LIMIT 10")
    top_users = cursor.fetchall()

    cursor.execute("SELECT user_id, total_spent FROM users ORDER BY total_spent DESC")
    all_users = cursor.fetchall()
    
    my_rank = 1
    for idx, u in enumerate(all_users):
        if u["user_id"] == user_id:
            my_rank = idx + 1
            break

    conn.close()
    
    top_list = []
    for u in top_users:
        u_dict = dict(u)
        u_dict["is_me"] = (u_dict["user_id"] == user_id)
        top_list.append(u_dict)

    return {"top": top_list, "my_rank": my_rank}

@app.post("/api/create-invoice/{user_id}")
async def create_invoice(user_id: int, req: InvoiceRequest):
    try:
        link = bot.create_invoice_link(
            title=f"Stars Top Up - {req.amount} ⭐",
            description="Balance replenishment in CatRoll App",
            payload=f"topup_{user_id}_{req.amount}_{int(time.time())}",
            provider_token="",
            currency="XTR",
            prices=[telebot.types.LabeledPrice("Stars", req.amount)]
        )
        return {"success": True, "invoice_link": link}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    json_str = await request.body()
    update = telebot.types.Update.de_json(json_str.decode('utf-8'))
    bot.process_new_updates([update])
    return JSONResponse(status_code=200, content={"status": "ok"})

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    pmt = message.successful_payment
    payload = pmt.invoice_payload
    if payload.startswith("topup_"):
        parts = payload.split("_")
        u_id = int(parts[1])
        amount = int(parts[2])

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, u_id))
        conn.commit()
        conn.close()

        bot.send_message(u_id, f"🎉 Баланс успешно пополнен на {amount} ⭐!")