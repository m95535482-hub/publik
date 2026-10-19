import os
import random
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import telebot

# Bot Token
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# Your personal Telegram ID to receive withdrawal requests
ADMIN_ID = 1218168630

bot = telebot.TeleBot(TOKEN)
app = FastAPI()

# Mount frontend static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Initialize SQLite Database
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Gifts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image_url TEXT NOT NULL,
            anim_url TEXT NOT NULL,
            price INTEGER NOT NULL
        )
    """)
    
    # User inventory table
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
    
    # Auto-populate basic gifts on first launch
    cursor.execute("SELECT COUNT(*) FROM gifts")
    if cursor.fetchone()[0] == 0:
        base_gifts = [
            ("Telegram Heart", "https://via.placeholder.com/150/FF0000", "https://via.placeholder.com/150/FF0000", 15),
            ("Teddy Bear", "https://via.placeholder.com/150/0000FF", "https://via.placeholder.com/150/0000FF", 25),
            ("Star Rocket", "https://via.placeholder.com/150/00FF00", "https://via.placeholder.com/150/00FF00", 50),
            ("Golden Crown", "https://via.placeholder.com/150/FFFF00", "https://via.placeholder.com/150/FFFF00", 100)
        ]
        cursor.executemany(
            "INSERT INTO gifts (name, image_url, anim_url, price) VALUES (?, ?, ?, ?)", 
            base_gifts
        )
        print("✅ Basic gifts successfully loaded into the database!")
        
    conn.commit()
    conn.close()

init_db()


def give_random_gift(user_id: int):
    """Select a random gift and add it to the user's inventory"""
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
# TELEGRAM BOT COMMANDS
# ==========================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Welcome to CatRoll Mini App!\n\n"
        "• Type `/buy` to get a test gift into your inventory.\n"
        "• Open the Mini App using the menu button to check your inventory and request withdrawals!",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['buy'])
def handle_buy_free(message):
    user_id = message.from_user.id
    gift_name = give_random_gift(user_id)
    
    if not gift_name:
        bot.send_message(message.chat.id, "❌ No available gifts found in the database.")
    else:
        bot.send_message(
            message.chat.id, 
            f"🎉 Congratulations! You received: **{gift_name}**!\n\n"
            f"The item has been added to your inventory in the Mini App. Open the app to request a withdrawal.",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['add'])
def handle_add_gift(message):
    """Add a gift manually via bot command (admin only)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ You do not have permissions to execute this command.")
        return

    try:
        text = message.text.replace('/add', '').strip()
        parts = [p.strip() for p in text.split('|')]
        
        if len(parts) != 4:
            bot.reply_to(message, "⚠️ Format: `/add Name | Image_URL | Animation_URL | Price`")
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
        
        bot.reply_to(message, f"✅ Gift **{name}** successfully added to the game!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error adding gift: {e}")


# ==========================================
# MINI APP API ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/api/gifts")
def get_gifts():
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
        return {"message": "Withdrawal request for this item has already been submitted!"}
        
    cursor.execute("UPDATE inventory SET status = 'withdraw_requested' WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    try:
        user_info = bot.get_chat(user_id)
        username = f"@{user_info.username}" if user_info.username else f"ID: `{user_id}`"
        
        bot.send_message(
            ADMIN_ID,
            f"🎁 **GIFT WITHDRAWAL REQUEST!**\n\n"
            f"👤 **Winner:** {username}\n"
            f"🏆 **Gift:** `{gift_name}`\n"
            f"🆔 **Item ID in DB:** `{item_id}`\n\n"
            f"👉 Open the user's profile and send them this gift manually in Telegram!",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to send notification to admin: {e}")
        
    return {"message": "Success! The withdrawal request has been sent to the admin."}