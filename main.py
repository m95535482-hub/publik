import json
import os
import random
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Импортируем наш массив и функцию из Items_poll.py
from Items_poll import ITEMS_POOL, fetch_and_update_items_pool

# Настройки для TonAPI
TONAPI_KEY = "ТВОЙ_ТОКЕН_TONAPI"
COLLECTION_ADDRESS = "АДРЕС_КОЛЛЕКЦИИ_В_TON"

# Загружаем данные из TonAPI при старте сервера через lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetch_and_update_items_pool(TONAPI_KEY, COLLECTION_ADDRESS)
    yield

app = FastAPI(title="CatRoll Secure Backend", lifespan=lifespan)

DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

users_db = load_db()

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users_db, f, ensure_ascii=False, indent=4)

class UserRequest(BaseModel):
    user_id: str

class SpinRequest(BaseModel):
    user_id: str
    case_type: str = "starter"
    is_demo: bool = False

class InventoryAction(BaseModel):
    user_id: str
    action: str
    item: dict

class SellItemRequest(BaseModel):
    user_id: str
    uid: float

@app.get("/")
def serve_frontend():
    return FileResponse("index.html")

@app.post("/api/init")
def init_user(data: UserRequest):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {
            "balance": 200000,
            "inventory": [],
            "last_bonus": 0,
        }
        save_db()
    return users_db[uid]

@app.post("/api/bonus")
def claim_bonus(data: UserRequest):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {
            "balance": 200000,
            "inventory": [],
            "last_bonus": 0,
        }

    now = time.time() * 1000
    cooldown = 24 * 60 * 60 * 1000

    if now - users_db[uid].get("last_bonus", 0) < cooldown:
        raise HTTPException(status_code=400, detail="Cooldown active")

    users_db[uid]["last_bonus"] = now

    if not ITEMS_POOL:
        raise HTTPException(status_code=500, detail="Items pool is empty")
    winning_item = random.choice(ITEMS_POOL)
    save_db()

    return {
        "balance": users_db[uid]["balance"],
        "last_bonus": now,
        "item": winning_item
    }

@app.post("/api/spin-case")
def spin_case(data: SpinRequest):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {
            "balance": 200000,
            "inventory": [],
            "last_bonus": 0,
        }

    if not ITEMS_POOL:
        raise HTTPException(status_code=500, detail="Items pool is empty")
    
    winning_item = random.choice(ITEMS_POOL)
    save_db()
    return {"balance": users_db[uid]["balance"], "item": winning_item}

@app.post("/api/spin-wheel")
def spin_wheel(data: SpinRequest):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {
            "balance": 200000,
            "inventory": [],
            "last_bonus": 0,
        }

    if not ITEMS_POOL:
        raise HTTPException(status_code=500, detail="Items pool is empty")
    
    winning_item = random.choice(ITEMS_POOL)
    save_db()
    return {"balance": users_db[uid]["balance"], "item": winning_item}

@app.post("/api/inventory-action")
def inventory_action(data: InventoryAction):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {
            "balance": 200000,
            "inventory": [],
            "last_bonus": 0,
        }
    
    user = users_db[uid]
    if data.action == "claim":
        user["inventory"].append({**data.item, "uid": time.time() * 1000 + random.random()})
    elif data.action == "sell":
        user["balance"] += data.item.get("price", 0)

    save_db()
    return {"balance": user["balance"], "inventory": user["inventory"]}

@app.post("/api/sell-inventory-item")
def sell_inventory_item(data: SellItemRequest):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {
            "balance": 200000,
            "inventory": [],
            "last_bonus": 0,
        }
    
    user = users_db[uid]
    idx = next((i for i, item in enumerate(user["inventory"]) if item["uid"] == data.uid), -1)
    if idx != -1:
        item = user["inventory"].pop(idx)
        user["balance"] += item.get("price", 0)

    save_db()
    return {"balance": user["balance"], "inventory": user["inventory"]}