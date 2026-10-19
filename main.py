import os
import random
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import telebot

# Токен вашего бота
TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")

# Ваш личный Telegram ID для получения заявок на вывод
ADMIN_ID = 1218168630

bot = telebot.TeleBot(TOKEN)
app = FastAPI()

# Подключение статической папки фронтенда (Mini App)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Инициализация базы данных SQLite
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Таблица доступных подарков в магазине/рулетке
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image_url TEXT NOT NULL,
            anim_url TEXT NOT NULL,
            price INTEGER NOT NULL
        )
    """)
    
    # Таблица инвентаря пользователей
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
    
    # Автоматическое наполнение базовыми подарками при первом запуске
    cursor.execute("SELECT COUNT(*) FROM gifts")
    if cursor.fetchone()[0] == 0:
        base_gifts = [
            ("Сердечко Telegram", "https://via.placeholder.com/150/FF0000", "https://via.placeholder.com/150/FF0000", 15),
            ("Плюшевый Мишка", "https://via.placeholder.com/150/0000FF", "https://via.placeholder.com/150/0000FF", 25),
            ("Звездная Ракета", "https://via.placeholder.com/150/00FF00", "https://via.placeholder.com/150/00FF00", 50),
            ("Золотая Корона", "https://via.placeholder.com/150/FFFF00", "https://via.placeholder.com/150/FFFF00", 100)
        ]
        cursor.executemany(
            "INSERT INTO gifts (name, image_url, anim_url, price) VALUES (?, ?, ?, ?)", 
            base_gifts
        )
        print("✅ Базовые подарки успешно загружены в базу данных!")
        
    conn.commit()
    conn.close()

# Запускаем инициализацию БД
init_db()


def give_random_gift(user_id: int):
    """Функция выбора случайного подарка и добавления его в инвентарь игрока"""
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


# ==========================================
# КОМАНДЫ TELEGRAM БОТА
# ==========================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Привет! Добро пожаловать в CatRoll Mini App!\n\n"
        "• Напишите `/buy` — получить тестовый подарок в инвентарь.\n"
        "• Запустите Mini App через кнопку меню, чтобы посмотреть свой инвентарь и заказать вывод подарков!",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['buy'])
def handle_buy_free(message):
    user_id = message.from_user.id
    gift_name = give_random_gift(user_id)
    
    if not gift_name:
        bot.send_message(message.chat.id, "❌ В базе данных нет доступных подарков.")
    else:
        bot.send_message(
            message.chat.id, 
            f"🎉 Поздравляем! Вы получили: **{gift_name}**!\n\n"
            f"Предмет уже добавлен в ваш инвентарь в Mini App. Откройте приложение, чтобы заказать его вывод.",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['add'])
def handle_add_gift(message):
    """Добавление подарка вручную через команду бота (для администратора)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ У вас нет прав для выполнения этой команды.")
        return

    try:
        text = message.text.replace('/add', '').strip()
        parts = [p.strip() for p in text.split('|')]
        
        if len(parts) != 4:
            bot.reply_to(message, "⚠️ Формат: `/add Название | Ссылка_на_фото | Ссылка_на_анимацию | Цена`")
            return
            
        name, image_url, anim_url, price = parts[0], parts[1], parts[2], int(parts[3])
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO gifts (name, image_url, anim_url, price) VALUES (?, ?, ?, ?)",
            (name, image_url, anim_url, price)
        )
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Подарок **{name}** успешно добавлен в игру!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка добавления: {e}")


# ==========================================
# API ЭНДПОИНТЫ ДЛЯ MINI APP (ФРОНТЕНДА)
# ==========================================

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/api/gifts")
def get_gifts():
    """Получение списка всех доступных подарков"""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, image_url, anim_url, price FROM gifts")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"id": r[0], "name": r[1], "image_url": r[2], "anim_url": r[3], "price": r[4]}
        for r in rows
    ]

@app.get("/api/inventory/{user_id}")
def get_inventory(user_id: int):
    """Получение инвентаря конкретного пользователя"""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, gift_name, image_url, anim_url, status FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"id": r[0], "gift_name": r[1], "image_url": r[2], "anim_url": r[3], "status": r[4]}
        for r in rows
    ]

@app.post("/api/withdraw/{item_id}")
def withdraw_item(item_id: int):
    """Обработка кнопки 'Вывести' из Mini App"""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id, gift_name, status FROM inventory WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Предмет не найден")
        
    user_id, gift_name, status = row
    
    if status == 'withdraw_requested':
        conn.close()
        return {"message": "Заявка на вывод этого предмета уже отправлена!"}
        
    # Обновляем статус предмета в базе
    cursor.execute("UPDATE inventory SET status = 'withdraw_requested' WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    # Отправка уведомления вам в ЛС
    try:
        user_info = bot.get_chat(user_id)
        username = f"@{user_info.username}" if user_info.username else f"ID: `{user_id}`"
        
        bot.send_message(
            ADMIN_ID,
            f"🎁 **ЗАЯВКА НА ВЫВОД ПОДАРКА!**\n\n"
            f"👤 **Победитель:** {username}\n"
            f"🏆 **Подарок:** `{gift_name}`\n"
            f"🆔 **ID предмета в базе:** `{item_id}`\n\n"
            f"👉 Откройте профиль пользователя и отправьте ему этот подарок в Telegram!",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Ошибка при отправке уведомления администратору: {e}")
        
    return {"message": "Успешно! Заявка передана администратору."}