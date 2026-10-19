import aiohttp

# Запасной пул предметов с иконками и картинками по умолчанию
ITEMS_POOL = [
    {"id": 1, "name": "Star Pouch", "icon": "⭐", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f31f.png", "animation": "", "price": 30},
    {"id": 2, "name": "Gift Box", "icon": "🎁", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f381.png", "animation": "", "price": 60},
    {"id": 3, "name": "Rubber Duck", "icon": "🦆", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f986.png", "animation": "", "price": 120},
    {"id": 4, "name": "Rocket Gift", "icon": "🚀", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f680.png", "animation": "", "price": 450},
    {"id": 5, "name": "Telegram Gem", "icon": "💎", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f48e.png", "animation": "", "price": 250},
    {"id": 6, "name": "Golden Crown", "icon": "👑", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f451.png", "animation": "", "price": 800}
]

async def fetch_and_update_items_pool(api_key: str, collection_address: str):
    global ITEMS_POOL
    
    if not api_key or api_key == "ТВОЙ_ТОКЕН_TONAPI" or not collection_address:
        return ITEMS_POOL

    url = f"https://tonapi.io/v2/nft/collections/{collection_address}/items"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    print(f"Помилка завантаження з TonAPI: {resp.status}")
                    return ITEMS_POOL
                data = await resp.json()

        new_pool = []

        for idx, item in enumerate(data.get("nft_items", []), start=1):
            metadata = item.get("metadata", {})
            sale = item.get("sale")
            
            # 1. Ціна
            price_ton = 100
            if sale and "price" in sale:
                price_ton = round(int(sale["price"]["value"]) / 1e9, 2)
                
            # 2. Найкраща картинка з прев'ю TonAPI
            previews = item.get("previews", [])
            best_image = previews[-1]["url"] if previews else metadata.get("image", "")
            
            if best_image.startswith("ipfs://"):
                best_image = best_image.replace("ipfs://", "https://ipfs.io/ipfs/")

            # 3. Анімація: перевіряємо всі можливі поля
            animation = metadata.get("video") or metadata.get("animation_url") or metadata.get("content_url") or ""
            
            if animation.startswith("ipfs://"):
                animation = animation.replace("ipfs://", "https://ipfs.io/ipfs/")
                
            new_pool.append({
                "id": idx,
                "name": metadata.get("name", "Unknown Gift"),
                "icon": "🎁",
                "image": best_image,
                "animation": animation,
                "price": price_ton
            })
            
        if new_pool:
            ITEMS_POOL.clear()
            ITEMS_POOL.extend(new_pool)
            print(f"✅ Успішно завантажено {len(ITEMS_POOL)} подарунків у ITEMS_POOL.")
            
    except Exception as e:
        print(f"Error fetching items from TonAPI: {e}")

    return ITEMS_POOL