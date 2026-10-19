import asyncio
import json
import os
import random
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- НАСТРОЙКИ БОТА И АДМИНКИ ---
TOKEN = "8643024766:AAFkb8a0NzGGz6DJ2ksE2aqDwWsQbhTAybI"
ADMIN_SECRET = "super_secret_key_123"
ADMIN_ID = 0  # Сюда можно вписать ваш Telegram ID, чтобы только вы могли добавлять подарки (или оставить 0 для теста)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ПУЛ ПРЕДМЕТОВ И БАЗА ДАННЫХ ---
ITEMS_FILE = "items_db.json"
DB_FILE = "database.json"

DEFAULT_ITEMS = [
    {"id": 1, "name": "Star Pouch", "icon": "⭐", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f31f.png", "animation": "", "price": 30},
    {"id": 2, "name": "Animated Gift Box", "icon": "🎁", "image": "https://images.emojiterra.com/google/android-11/512px/1f381.png", "animation": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3ZtOGlnczJmMXZmbWNkM3E1c296NmcxYmpxbW1ubGRyYjNtdXhzaSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/L1R16I0SVbipNMCxyP/giphy.gif", "price": 150},
    {"id": 3, "name": "Rubber Duck", "icon": "🦆", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f986.png", "animation": "", "price": 120},
    {"id": 4, "name": "Cyber Neon", "icon": "🚀", "image": "https://images.emojiterra.com/google/android-11/512px/1f680.png", "animation": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2F3OXFvNHZ3NnlvOHo5bWhhbXg5eWoxcTN4NTRuam55anE5b2V6byZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xT9IgzoKnwFNmISR8I/giphy.gif", "price": 500},
    {"id": 5, "name": "Telegram Gem", "icon": "💎", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f48e.png", "animation": "", "price": 250},
    {"id": 6, "name": "Golden Crown", "icon": "👑", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f451.png", "animation": "", "price": 800}
]

def load_items():
    if os.path.exists(ITEMS_FILE):
        try:
            with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_ITEMS
    return DEFAULT_ITEMS

ITEMS_POOL = load_items()

def save_items_to_disk():
    with open(ITEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(ITEMS_POOL, f, ensure_ascii=False, indent=4)

def add_new_item_to_pool(name: str, image: str, animation: str, price: int):
    global ITEMS_POOL
    new_id = len(ITEMS_POOL) + 1
    new_item = {
        "id": new_id,
        "name": name,
        "icon": "🎁",
        "image": image,
        "animation": animation,
        "price": price
    }
    ITEMS_POOL.append(new_item)
    save_items_to_disk()
    return new_item

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

# --- LIFESPAN (Запуск бота при старте FastAPI) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запускаем телеграм-бота в фоновом режиме
    asyncio.create_task(dp.start_polling(bot))
    yield

app = FastAPI(title="CatRoll Secure Backend", lifespan=lifespan)

# --- МОДЕЛИ ЗАПРОСОВ ---
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

class NewItemRequest(BaseModel):
    name: str
    image: str
    animation: str = ""
    price: int = 100
    admin_secret: str

def get_weighted_random_item(items):
    if not items:
        return None
    animated_items = [item for item in items if item.get("animation")]
    regular_items = [item for item in items if not item.get("animation")]

    if animated_items and regular_items:
        if random.random() < 0.7:  # 70% шанс на анимированный подарок для тестов
            return random.choice(animated_items)
        else:
            return random.choice(regular_items)
    return random.choice(items)

# --- API МАРШРУТЫ ---
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

@app.post("/api/spin-case")
def spin_case(data: SpinRequest):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {"balance": 200000, "inventory": [], "last_bonus": 0}

    cost = 100
    if not data.is_demo and users_db[uid]["balance"] < cost:
        raise HTTPException(status_code=400, detail="Недостаточно звезд для прокрутки!")

    if not data.is_demo:
        users_db[uid]["balance"] -= cost

    if not ITEMS_POOL:
        raise HTTPException(status_code=500, detail="Items pool is empty")
    
    winning_item = get_weighted_random_item(ITEMS_POOL)
    save_db()
    return {"balance": users_db[uid]["balance"], "item": winning_item}

@app.post("/api/spin-wheel")
def spin_wheel(data: SpinRequest):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {"balance": 200000, "inventory": [], "last_bonus": 0}

    cost = 50
    if not data.is_demo and users_db[uid]["balance"] < cost:
        raise HTTPException(status_code=400, detail="Недостаточно звезд для прокрутки!")

    if not data.is_demo:
        users_db[uid]["balance"] -= cost

    if not ITEMS_POOL:
        raise HTTPException(status_code=500, detail="Items pool is empty")
    
    winning_item = get_weighted_random_item(ITEMS_POOL)
    save_db()
    return {"balance": users_db[uid]["balance"], "item": winning_item}

@app.post("/api/inventory-action")
def inventory_action(data: InventoryAction):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {"balance": 200000, "inventory": [], "last_bonus": 0}
    
    user = users_db[uid]
    if data.action == "claim":
        user["inventory"].append({**data.item, "uid": time.time() * 1000 + random.random()})

    save_db()
    return {"balance": user["balance"], "inventory": user["inventory"]}

@app.post("/api/sell-inventory-item")
def sell_inventory_item(data: SellItemRequest):
    uid = data.user_id
    if uid not in users_db:
        users_db[uid] = {"balance": 200000, "inventory": [], "last_bonus": 0}
    
    user = users_db[uid]
    idx = next((i for i, item in enumerate(user["inventory"]) if item["uid"] == data.uid), -1)
    if idx != -1:
        item = user["inventory"].pop(idx)
        user["balance"] += item.get("price", 100)

    save_db()
    return {"balance": user["balance"], "inventory": user["inventory"]}

@app.post("/api/add-item")
def api_add_item(data: NewItemRequest):
    if data.admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Неверный секретный ключ админа!")
    
    item = add_new_item_to_pool(data.name, data.image, data.animation, data.price)
    return {"status": "success", "added_item": item, "total_items": len(ITEMS_POOL)}


# --- ЛОГИКА TELEGRAM БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Это панель управления CatRoll.\n\n"
        "Чтобы добавить новый подарок в игру, отправьте команду:\n"
        "<code>/add Название | Ссылка_картинка | Ссылка_анимация_mp4 | Цена</code>\n\n"
        "Пример:\n"
        "<code>/add New Gift | https://img.com/pic.png | https://img.com/anim.mp4 | 300</code>",
        parse_mode="HTML"
    )

@dp.message(Command("add"))
async def cmd_add_item(message: types.Message):
    # Если указан ADMIN_ID, проверяем его (если ADMIN_ID = 0, проверка отключена для удобства теста)
    if ADMIN_ID != 0 and message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для добавления предметов.")
        return

    args = message.text.replace("/add", "").strip()
    parts = [p.strip() for p in args.split("|")]

    if len(parts) < 4:
        await message.answer(
            "⚠️ Неверный формат!\n"
            "Используйте: <code>/add Название | Картинка | Анимация | Цена</code>",
            parse_mode="HTML"
        )
        return

    name, image, animation, price_str = parts[0], parts[1], parts[2], parts[3]

    try:
        price = int(price_str)
    except ValueError:
        await message.answer("⚠️ Цена должна быть целым числом!")
        return

    # Сохраняем локально через функцию сервера
    try:
        item = add_new_item_to_pool(name, image, animation, price)
        await message.answer(
            f"✅ <b>Предмет успешно добавлен в игру!</b>\n\n"
            f"🎁 <b>Название:</b> {item['name']}\n"
            f"💰 <b>Цена:</b> {item['price']} ⭐\n"
            f"📦 <b>Всего предметов в пуле:</b> {len(ITEMS_POOL)}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении: {e}")