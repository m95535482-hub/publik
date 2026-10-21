import sqlite3
import time
import random
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

ITEMS_POOL = [
    {"id": 1, "name": "Bronze Star", "icon": "fa-star", "price": 10, "weight": 40},
    {"id": 2, "name": "Silver Pack", "icon": "fa-gift", "price": 25, "weight": 30},
    {"id": 3, "name": "Gold Box", "icon": "fa-box", "price": 50, "weight": 15},
    {"id": 4, "name": "Ruby Gem", "icon": "fa-gem", "price": 100, "weight": 10},
    {"id": 5, "name": "Crown", "icon": "fa-crown", "price": 250, "weight": 4},
    {"id": 6, "name": "Trophy", "icon": "fa-trophy", "price": 500, "weight": 1}
]

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            photo_url TEXT,
            balance INTEGER DEFAULT 100,
            last_daily INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            name TEXT,
            icon TEXT,
            price INTEGER,
            status TEXT DEFAULT 'in_inventory'
        )
    """)
    conn.commit()
    # Установка баланса 267000 звезд для администратора
    cursor.execute("UPDATE users SET balance = 267000 WHERE id = 1218168630")
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=FileResponse)
def read_index():
    return "static/index.html"

@app.get("/api/user/{user_id}")
def get_user(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, last_daily FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        init_bal = 267000 if user_id == 1218168630 else 100
        cursor.execute("INSERT INTO users (id, balance, last_daily) VALUES (?, ?, 0)", (user_id, init_bal))
        conn.commit()
        balance, last_daily = init_bal, 0
    else:
        balance, last_daily = row
    conn.close()
    return {"balance": balance, "last_daily": last_daily}

class UserUpdate(BaseModel):
    username: str
    photo_url: str = ""

@app.post("/api/user/{user_id}")
def update_user(user_id: int, data: UserUpdate):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET username = ?, photo_url = ? WHERE id = ?", (data.username, data.photo_url, user_id))
    conn.commit()
    conn.close()
    return {"success": True}

class RollRequest(BaseModel):
    case_type: str
    is_demo: bool = False

@app.post("/api/roll/{user_id}")
def roll_case(user_id: int, data: RollRequest):
    costs = {"starter": 50, "rare": 250, "legend": 1000, "wheel": 100}
    cost = costs.get(data.case_type, 50)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if not data.is_demo:
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row or row[0] < cost:
            conn.close()
            raise HTTPException(status_code=400, detail="INSUFFICIENT_FUNDS")
        cursor.execute("UPDATE users SET balance = balance - ?, total_spent = total_spent + ? WHERE id = ?", (cost, cost, user_id))

    total_weight = sum(item["weight"] for item in ITEMS_POOL)
    r = random.uniform(0, total_weight)
    current_w = 0
    won_item = ITEMS_POOL[0]
    for item in ITEMS_POOL:
        current_w += item["weight"]
        if r <= current_w:
            won_item = item
            break

    item_id = None
    if not data.is_demo:
        cursor.execute("INSERT INTO inventory (user_id, item_id, name, icon, price, status) VALUES (?, ?, ?, ?, ?, 'in_inventory')",
                       (user_id, won_item["id"], won_item["name"], won_item["icon"], won_item["price"]))
        item_id = cursor.lastrowid

    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    new_balance = cursor.fetchone()[0]

    conn.commit()
    conn.close()

    return {"success": True, "won_item": won_item, "balance": new_balance, "item_id": item_id}

@app.post("/api/daily-spin/{user_id}")
def daily_spin(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT last_daily FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    last_daily = row[0] if row else 0
    now = int(time.time() * 1000)

    if now - last_daily < 24 * 60 * 60 * 1000:
        conn.close()
        raise HTTPException(status_code=400, detail="COOLDOWN_ACTIVE")

    rand_val = random.random()
    if rand_val < 0.38:
        won_item = {"id": "stars_3", "name": "3 Stars", "icon": "fa-star", "price": 3, "is_stars": True, "amount": 3}
    elif rand_val < 0.58:
        won_item = {"id": "stars_4", "name": "4 Stars", "icon": "fa-star", "price": 4, "is_stars": True, "amount": 4}
    elif rand_val < 0.72:
        won_item = {"id": "stars_5", "name": "5 Stars", "icon": "fa-star", "price": 5, "is_stars": True, "amount": 5}
    elif rand_val < 0.83:
        won_item = {"id": "stars_6", "name": "6 Stars", "icon": "fa-star", "price": 6, "is_stars": True, "amount": 6}
    elif rand_val < 0.91:
        won_item = {"id": "stars_7", "name": "7 Stars", "icon": "fa-star", "price": 7, "is_stars": True, "amount": 7}
    elif rand_val < 0.96:
        won_item = {"id": "stars_8", "name": "8 Stars", "icon": "fa-star", "price": 8, "is_stars": True, "amount": 8}
    elif rand_val < 0.985:
        won_item = {"id": "stars_9", "name": "9 Stars", "icon": "fa-star", "price": 9, "is_stars": True, "amount": 9}
    else:
        rare_item = random.choice(ITEMS_POOL)
        won_item = {"id": rare_item["id"], "name": rare_item["name"], "icon": rare_item["icon"], "price": rare_item["price"], "is_stars": False}

    item_id = None
    if won_item.get("is_stars"):
        cursor.execute("UPDATE users SET balance = balance + ?, last_daily = ? WHERE id = ?", (won_item["amount"], now, user_id))
    else:
        cursor.execute("UPDATE users SET last_daily = ? WHERE id = ?", (now, user_id))
        cursor.execute("INSERT INTO inventory (user_id, item_id, name, icon, price, status) VALUES (?, ?, ?, ?, ?, 'in_inventory')",
                       (user_id, won_item["id"], won_item["name"], won_item["icon"], won_item["price"]))
        item_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {"success": True, "won_item": won_item, "next_daily": now + 24*60*60*1000, "item_id": item_id}

@app.get("/api/check-sub/{user_id}")
def check_subscription(user_id: int):
    return {"subscribed": True}

@app.get("/api/inventory/{user_id}")
def get_inventory(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, item_id, name, icon, price, status FROM inventory WHERE user_id = ? AND status != 'sold'", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    items = [{"id": r[0], "item_id": r[1], "name": r[2], "icon": r[3], "price": r[4], "status": r[5]} for r in rows]
    return items

@app.post("/api/sell/{item_id}")
def sell_item(item_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, price, status FROM inventory WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if not row or row[2] == 'sold':
        conn.close()
        raise HTTPException(status_code=400, detail="ITEM_NOT_FOUND")
    user_id, price = row[0], row[1]
    cursor.execute("UPDATE inventory SET status = 'sold' WHERE id = ?", (item_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, user_id))
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    new_balance = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return {"success": True, "balance": new_balance}

@app.post("/api/withdraw/{item_id}")
def withdraw_item(item_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET status = 'withdraw_requested' WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Withdrawal requested successfully"}

@app.get("/api/leaderboard/{user_id}")
def get_leaderboard(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, photo_url, total_spent FROM users ORDER BY total_spent DESC LIMIT 10")
    top_users = cursor.fetchall()

    top_list = []
    found = False
    for idx, u in enumerate(top_users):
        is_me = (u[0] == user_id)
        if is_me: found = True
        top_list.append({
            "rank": idx + 1,
            "username": u[1] or f"User {u[0]}",
            "photo_url": u[2] or "",
            "total_spent": u[3],
            "is_me": is_me
        })

    my_rank = 99
    if not found:
        cursor.execute("SELECT COUNT(*) FROM users WHERE total_spent > (SELECT total_spent FROM users WHERE id = ?)", (user_id,))
        res = cursor.fetchone()
        my_rank = (res[0] if res else 0) + 1

    conn.close()
    return {"top": top_list, "my_rank": my_rank}

class InvoiceRequest(BaseModel):
    amount: int

@app.post("/api/create-invoice/{user_id}")
def create_invoice(user_id: int, data: InvoiceRequest):
    invoice_link = f"https://t.me/invoice_mock_{data.amount}"
    return {"success": True, "invoice_link": invoice_link}