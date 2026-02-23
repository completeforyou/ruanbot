# ruanbot/webapp_server.py
import os
import json
import random
import urllib.parse
import hmac
import hashlib
from aiohttp import web
from sqlalchemy import select

import config
from database import AsyncSessionLocal
from models.product import Product
from models.user import User

# --- 1. Security Check ---
def verify_telegram_data(init_data: str, token: str) -> bool:
    """Verifies that the request actually came from Telegram."""
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            return False
            
        hash_val = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        return calculated_hash == hash_val
    except Exception:
        return False

# --- 2. Endpoints ---
async def serve_index(request):
    """Serves the HTML spinning wheel page."""
    # This assumes your index.html is inside the 'webapp' folder
    return web.FileResponse('./webapp/index.html')

async def get_wheel_data(request):
    """Sends the active lottery products to the frontend, calculating exact chances."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Product).filter_by(is_active=True, type='lottery').filter(Product.stock > 0)
        )
        products = result.scalars().all()
    
    # Calculate the total chance of all items
    total_win_chance = sum(p.chance for p in products)
    lose_chance = max(0.0, 1.0 - total_win_chance) # Whatever is left over from 100%
    
    items = [{"id": p.id, "name": p.name, "cost": p.cost, "chance": p.chance} for p in products]
    items.append({"id": -1, "name": "谢谢惠顾", "cost": 0, "chance": lose_chance}) # The exact losing slice size
    
    return web.json_response(items)

async def spin_wheel(request):
    """Handles the actual spin logic securely with proportional probability."""
    data = await request.json()
    init_data = data.get("initData")
    
    if not verify_telegram_data(init_data, config.TOKEN):
        return web.json_response({"error": "Unauthorized"}, status=401)
        
    parsed_data = dict(urllib.parse.parse_qsl(init_data))
    user_data = json.loads(parsed_data.get("user", "{}"))
    user_id = user_data.get("id")
    
    if not user_id:
        return web.json_response({"error": "User missing"}, status=400)

    async with AsyncSessionLocal() as session:
        result_user = await session.execute(select(User).filter_by(id=user_id).with_for_update())
        db_user = result_user.scalars().first()
        
        if not db_user:
            return web.json_response({"error": "User not found in DB"}, status=404)

        result_prod = await session.execute(
            select(Product).filter_by(is_active=True, type='lottery').filter(Product.stock > 0)
        )
        products = result_prod.scalars().all()
        
        if not products:
            return web.json_response({"error": "No active lotteries"}, status=400)

        spin_cost = int(products[0].cost)
        
        if db_user.vouchers < spin_cost:
            return web.json_response({"error": f"Insufficient Vouchers. Needs {spin_cost} 🎟"}, status=400)

        db_user.vouchers -= spin_cost
        
        # --- NEW ROULETTE MATH ---
        # Roll a number between 0.00 and 1.00
        roll = random.random()
        cumulative = 0.0
        winning_index = len(products) # Default to the last index (the "Lose" slice)
        won_product = None
        
        for i, p in enumerate(products):
            cumulative += p.chance
            if roll < cumulative:
                winning_index = i
                won_product = p
                p.stock -= 1
                break
                
        await session.commit()
        
    return web.json_response({"winning_index": winning_index, "message": "Success"})

# --- 3. Startup Function ---
async def start_web_server():
    """Starts the aiohttp server on the port Railway provides."""
    app = web.Application()
    app.router.add_get('/', serve_index)
    app.router.add_get('/api/wheel_data', get_wheel_data)
    app.router.add_post('/api/spin', spin_wheel)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Railway passes the required port in the 'PORT' environment variable
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    print(f"🌐 Web App Server running on port {port}")