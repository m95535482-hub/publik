import aiohttp

# Запасной пул предметов по умолчанию
ITEMS_POOL = [
    {"id": 1, "name": "Star Pouch", "icon": "⭐", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f31f.png", "price": 30},
    {"id": 2, "name": "Gift Box", "icon": "🎁", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f381.png", "price": 60},
    {"id": 3, "name": "Rubber Duck", "icon": "🦆", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f986.png", "price": 120},
    {"id": 4, "name": "Rocket Gift", "icon": "🚀", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f680.png", "price": 450},
    {"id": 5, "name": "Telegram Gem", "icon": "💎", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f48e.png", "price": 250},
    {"id": 6, "name": "Golden Crown", "icon": "👑", "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f451.png", "price": 800}
]

async def fetch_and_update_items_pool(api_key: str, collection_address: str):
    global ITEMS_POOL
    
    # Если токен или адрес не заполнены, оставляем запасной пул как есть
    if not api_key or api_key == "ТВОЙ_ТОКЕН_TONAPI" or not collection_address:
        return

    url = f"https://tonapi.io/v2/nft/collections/{collection_address}/items"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("nft_items", [])
                    if items:
                        new_pool = []
                        for item in items:
                            metadata = item.get("metadata", {})
                            new_pool.append({
                                "id": item.get("address"),
                                "name": metadata.get("name", "Unknown NFT"),
                                "icon": "🎁",
                                "image": metadata.get("image"),
                                "price": 100
                            })
                        if new_pool:
                            ITEMS_POOL = new_pool
    except Exception as e:
        print(f"Using fallback items pool due to error: {e}")