import aiohttp

ITEMS_POOL = []

async def fetch_and_update_items_pool(tonapi_key: str, collection_address: str):
    """ Функция обращается к TonAPI, получает подарки, присваивает им ID и наполняет массив ITEMS_POOL. """
    global ITEMS_POOL
    if not tonapi_key or tonapi_key == "ТВОЙ_ТОКЕН_TONAPI" or not collection_address:
        print("ℹ️ TonAPI ключ или адрес коллекции не настроены, используем дефолтный пул подарков.")
        ITEMS_POOL = [
            {"id": 1, "name": "Star Pouch", "icon": "⭐", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f31f.png", "price": 30},
            {"id": 2, "name": "Gift Box", "icon": "🎁", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f381.png", "price": 60},
            {"id": 3, "name": "Rubber Duck", "icon": "🦆", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f986.png", "price": 120},
            {"id": 4, "name": "Rocket Gift", "icon": "🚀", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f680.png", "price": 450},
            {"id": 5, "name": "Telegram Gem", "icon": "💎", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f48e.png", "price": 250},
            {"id": 6, "name": "Golden Crown", "icon": "👑", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f451.png", "price": 800},
            {"id": 7, "name": "Cyber Cat NFT", "icon": "🐱", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f431.png", "price": 1500},
            {"id": 8, "name": "Diamond NFT", "icon": "💠", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4a0.png", "price": 2500}
        ]
        return ITEMS_POOL

    url = f"https://tonapi.io/v2/nfts/collections/{collection_address}/items"
    headers = {"Authorization": f"Bearer {tonapi_key}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    print(f"Ошибка загрузки из TonAPI: {resp.status}")
                    return ITEMS_POOL
                data = await resp.json()

        new_pool = []
        for idx, item in enumerate(data.get("nft_items", []), start=1):
            metadata = item.get("metadata", {})
            sale = item.get("sale")
            
            price_ton = 30
            if sale and "price" in sale:
                try:
                    price_ton = round(int(sale["price"]["value"]) / 1e9, 2)
                except:
                    pass
            
            new_pool.append({
                "id": idx,
                "name": metadata.get("name", "Unknown Gift"),
                "icon": "🎁",
                "image": metadata.get("image", ""),
                "animation": metadata.get("animation_url", ""),
                "price": price_ton
            })
            
        if new_pool:
            ITEMS_POOL.clear()
            ITEMS_POOL.extend(new_pool)
            print(f"✅ Успешно загружено {len(ITEMS_POOL)} подарков в ITEMS_POOL.")
    except Exception as e:
        print(f"⚠️ Ошибка подключения к TonAPI: {e}")
        
    return ITEMS_POOL