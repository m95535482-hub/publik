import aiohttp

# Тестовый пул предметов с поддержкой картинки и видео-анимации (.mp4)
ITEMS_POOL = [
    {
        "id": 1, 
        "name": "Star Pouch", 
        "icon": "⭐", 
        "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f31f.png", 
        "animation": "", 
        "price": 30
    },
    {
        "id": 2, 
        "name": "Animated Gift Box", 
        "icon": "🎁", 
        "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f381.png", 
        "animation": "https://assets.mixkit.co/videos/preview/mixkit-digital-animation-of-screens-and-numbers-31958-large.mp4", 
        "price": 150
    },
    {
        "id": 3, 
        "name": "Rubber Duck", 
        "icon": "🦆", 
        "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f986.png", 
        "animation": "", 
        "price": 120
    },
    {
        "id": 4, 
        "name": "Cyber Neon", 
        "icon": "🚀", 
        "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f680.png", 
        "animation": "https://assets.mixkit.co/videos/preview/mixkit-looped-animation-of-a-futuristic-tunnel-41566-large.mp4", 
        "price": 500
    },
    {
        "id": 5, 
        "name": "Telegram Gem", 
        "icon": "💎", 
        "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f48e.png", 
        "animation": "", 
        "price": 250
    },
    {
        "id": 6, 
        "name": "Golden Crown", 
        "icon": "👑", 
        "image": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f451.png", 
        "animation": "", 
        "price": 800
    }
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
                    return ITEMS_POOL
                data = await resp.json()

        new_pool = []
        for idx, item in enumerate(data.get("nft_items", []), start=1):
            metadata = item.get("metadata", {})
            sale = item.get("sale")
            
            price_ton = 100
            if sale and "price" in sale:
                price_ton = round(int(sale["price"]["value"]) / 1e9, 2)
                
            previews = item.get("previews", [])
            best_image = previews[-1]["url"] if previews else metadata.get("image", "")
            if best_image.startswith("ipfs://"):
                best_image = best_image.replace("ipfs://", "https://ipfs.io/ipfs/")

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
            
    except Exception as e:
        print(f"Test pool error: {e}")

    return ITEMS_POOL