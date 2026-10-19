import json
import os
import random
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="CatRoll Secure Backend")

DB_FILE = "database.json"


def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users_db, f, ensure_ascii=False, indent=4)


# Загружаем базу при старте сервера
users_db = load_db()

ITEMS_POOL = [
    {"id": 1, "name": "Star Pouch", "icon": "⭐", "price": 30},
    {"id": 2, "name": "Gift Box", "icon": "🎁", "price": 60},
    {"id": 3, "name": "Rubber Duck", "icon": "🦆", "price": 120},
    {"id": 4, "name": "Telegram Gem", "icon": "💎", "price": 250},
    {"id": 5, "name": "Rocket Gift", "icon": "🚀", "price": 450},
    {"id": 6, "name": "Golden Crown", "icon": "👑", "price": 800},
    {"id": 7, "name": "Cyber Cat NFT", "icon": "🐱", "price": 1500},
    {"id": 8, "name": "Diamond Diamond", "icon": "💠", "price": 2500},
]


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
        raise HTTPException(status_code=404, detail="User not found")

    now = time.time() * 1000
    cooldown = 24 * 60 * 60 * 1000
    if now - users_db[uid]["last_bonus"] < cooldown:
        raise HTTPException(status_code=400, detail="Cooldown active")

    users_db[uid]["last_bonus"] = now
    users_db[uid]["balance"] += 50
    save_db()
    return {
        "balance": users_db[uid]["balance"],
        "item": {"name": "Ежедневный Бонус", "icon": "🎁", "price": 50},
    }


@app.post("/api/spin-case")
def spin_case(data: SpinRequest):
    uid = data.user_id
    if uid not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    costs = {"starter": 50, "rare": 250, "legend": 1000}
    cost = costs.get(data.case_type, 50)

    if not data.is_demo:
        if users_db[uid]["balance"] < cost:
            raise HTTPException(status_code=400, detail="Not enough stars")
        users_db[uid]["balance"] -= cost

    winning_item = random.choice(ITEMS_POOL)
    save_db()
    return {"balance": users_db[uid]["balance"], "item": winning_item}


@app.post("/api/spin-wheel")
def spin_wheel(data: SpinRequest):
    uid = data.user_id
    if uid not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    cost = 100
    if not data.is_demo:
        if users_db[uid]["balance"] < cost:
            raise HTTPException(status_code=400, detail="Not enough stars")
        users_db[uid]["balance"] -= cost

    winning_item = random.choice(ITEMS_POOL)
    save_db()
    return {"balance": users_db[uid]["balance"], "item": winning_item}


@app.post("/api/inventory-action")
def inventory_action(data: InventoryAction):
    uid = data.user_id
    if uid not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    user = users_db[uid]
    if data.action == "claim":
        user["inventory"].append(
            {**data.item, "uid": time.time() * 1000 + random.random()}
        )
    elif data.action == "sell":
        user["balance"] += data.item["price"]

    save_db()
    return {"balance": user["balance"], "inventory": user["inventory"]}


@app.post("/api/sell-inventory-item")
def sell_inventory_item(data: SellItemRequest):
    uid = data.user_id
    if uid not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    user = users_db[uid]
    idx = next(
        (i for i, item in enumerate(user["inventory"]) if item["uid"] == data.uid),
        -1,
    )
    if idx != -1:
        item = user["inventory"].pop(idx)
        user["balance"] += item["price"]

    save_db()
    return {"balance": user["balance"], "inventory": user["inventory"]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)