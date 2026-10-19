import os
import json
import time
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

app = FastAPI()

DB_FILE = "database.json"

# Пул предметов (общий для всех мини-игр)
ITEMS_POOL = [
    {"id": 1, "name": "Star Pouch", "icon": "⭐", "price": 30},
    {"id": 2, "name": "Gift Box", "icon": "🎁", "price": 60},
    {"id": 3, "name": "Rubber Duck", "icon": "🦆", "price": 120},
    {"id": 4, "name": "Rocket Gift", "icon": "🚀", "price": 450},
    {"id": 5, "name": "Telegram Gem", "icon": "💎", "price": 250},
    {"id": 6, "name": "Golden Crown", "icon": "👑", "price": 800},
    {"id": 7, "name": "Cyber Cat NFT", "icon": "🐱", "price": 1500},
    {"id": 8, "name": "Diamond NFT", "icon": "💠", "price": 2500}
]

def load_db() -> Dict[str, Any]:
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_db(data: Dict[str, Any]):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class UserInitRequest(BaseModel):
    user_id: str

class CaseSpinRequest(BaseModel):
    user_id: str
    case_type: str
    is_demo: bool = False

class WheelSpinRequest(BaseModel):
    user_id: str
    is_demo: bool = False

class BonusRequest(BaseModel):
    user_id: str

class InventoryActionRequest(BaseModel):
    user_id: str
    action: str  # 'claim' или 'sell'
    item: Dict[str, Any]

class SellItemRequest(BaseModel):
    user_id: str
    uid: int

@app.post("/api/init")
def init_user(req: UserInitRequest):
    db = load_db()
    user_id = req.user_id
    if user_id not in db:
        db[user_id] = {
            "balance": 2000,  # Стартовый капитал
            "inventory": [],
            "last_bonus": 0
        }
        save_db(db)
    
    return {
        "balance": db[user_id]["balance"],
        "inventory": db[user_id]["inventory"],
        "last_bonus": db[user_id]["last_bonus"]
    }

@app.post("/api/bonus")
def claim_bonus(req: BonusRequest):
    db = load_db()
    user_id = req.user_id
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    
    now = int(time.time() * 1000)
    cooldown = 24 * 60 * 60 * 1000  # 24 часа в миллисекундах
    last_bonus = db[user_id].get("last_bonus", 0)
    
    if now - last_bonus < cooldown:
        raise HTTPException(status_code=400, detail="Cooldown is active")
    
    # Обновляем время последнего бонуса на сервере
    db[user_id]["last_bonus"] = now
    save_db(db)
    
    # Выбираем случайный подарок для классического ролла
    import random
    winning_item = random.choice(ITEMS_POOL)
    
    return {
        "last_bonus": now,
        "item": winning_item
    }

@app.post("/api/spin-case")
def spin_case(req: CaseSpinRequest):
    db = load_db()
    user_id = req.user_id
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    
    costs = {"starter": 50, "rare": 250, "legend": 1000}
    cost = costs.get(req.case_type, 50)
    
    if not req.is_demo:
        if db[user_id]["balance"] < cost:
            raise HTTPException(status_code=400, detail="Not enough stars")
        db[user_id]["balance"] -= cost
        save_db(db)
        
    import random
    winning_item = random.choice(ITEMS_POOL)
    
    return {
        "balance": db[user_id]["balance"],
        "item": winning_item
    }

@app.post("/api/spin-wheel")
def spin_wheel(req: WheelSpinRequest):
    db = load_db()
    user_id = req.user_id
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    
    cost = 100
    if not req.is_demo:
        if db[user_id]["balance"] < cost:
            raise HTTPException(status_code=400, detail="Not enough stars")
        db[user_id]["balance"] -= cost
        save_db(db)
        
    import random
    winning_item = random.choice(ITEMS_POOL)
    
    return {
        "balance": db[user_id]["balance"],
        "item": winning_item
    }

@app.post("/api/inventory-action")
def inventory_action(req: InventoryActionRequest):
    db = load_db()
    user_id = req.user_id
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = db[user_id]
    item = req.item
    
    if req.action == "sell":
        user["balance"] += item["price"]
    elif req.action == "claim":
        item_with_uid = {**item, "uid": int(time.time() * 1000)}
        user["inventory"].append(item_with_uid)
        
    save_db(db)
    return {
        "balance": user["balance"],
        "inventory": user["inventory"]
    }

@app.post("/api/sell-inventory-item")
def sell_inventory_item(req: SellItemRequest):
    db = load_db()
    user_id = req.user_id
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = db[user_id]
    new_inv = []
    sold_price = 0
    
    for item in user["inventory"]:
        if item.get("uid") == req.uid:
            sold_price = item["price"]
        else:
            new_inv.append(item)
            
    user["inventory"] = new_inv
    user["balance"] += sold_price
    save_db(db)
    
    return {
        "balance": user["balance"],
        "inventory": user["inventory"]
    }

@app.get("/")
def serve_index():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)