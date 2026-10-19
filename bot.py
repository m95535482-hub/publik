import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Токен вашего бота от BotFather (замените на свой или используйте переменную окружения)
TOKEN = "8643024766:AAFkb8a0NzGGz6DJ2ksE2aqDwWsQbhTAybI"
# Ссылка на ваш запущенный сервер на Render
API_URL = "https://publik-4.onrender.com/api/add-item"
ADMIN_SECRET = "super_secret_key_123"

# Ваш Telegram ID (чтобы только вы могли добавлять подарки)
ADMIN_ID = 123456789  # Замените на ваш настоящий Telegram ID

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Это админ-панель CatRoll.\n"
        "Чтобы добавить предмет, отправьте команду в формате:\n"
        "/add Название | Ссылка_на_картинку | Ссылка_на_анимацию_mp4 | Цена\n\n"
        "Пример:\n"
        "/add Super Gift | https://img.com/pic.png | https://img.com/anim.mp4 | 300"
    )

@dp.message(Command("add"))
async def cmd_add_item(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для добавления предметов.")
        return

    # Парсим текст после команды /add
    args = message.text.replace("/add", "").strip()
    parts = [p.strip() for p in args.split("|")]

    if len(parts) < 4:
        await message.answer(
            "Неверный формат! Используйте:\n"
            "/add Название | Картинка | Анимация | Цена"
        )
        return

    name, image, animation, price_str = parts[0], parts[1], parts[2], parts[3]

    try:
        price = int(price_str)
    except ValueError:
        await message.answer("Цена должна быть числом!")
        return

    # Отправляем запрос на ваш FastAPI сервер
    payload = {
        "name": name,
        "image": image,
        "animation": animation,
        "price": price,
        "admin_secret": ADMIN_SECRET
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    await message.answer(
                        f"✅ Предмет успешно добавлен в игру!\n"
                        f"📦 Всего предметов в пуле: {data.get('total_items')}"
                    )
                else:
                    err = await resp.text()
                    await message.answer(f"❌ Ошибка сервера: {err}")
    except Exception as e:
        await message.answer(f"❌ Не удалось связаться с сервером: {e}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())