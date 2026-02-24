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

_bot_instance = None

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
    
    total_win_chance = sum(p.chance for p in products)
    
    # NEW: Normalize chances if they exceed 100% (1.0)
    if total_win_chance > 1.0:
        for p in products:
            p.chance = p.chance / total_win_chance
        total_win_chance = 1.0
        
    lose_chance = max(0.0, 1.0 - total_win_chance) 
    
    items = [{"id": p.id, "name": p.name, "cost": p.cost, "chance": p.chance} for p in products]
    items.append({"id": -1, "name": "谢谢惠顾", "cost": 0, "chance": lose_chance}) 
    
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
    user_name = user_data.get("first_name", "Unknown")
    
    if not user_id:
        return web.json_response({"error": "User missing"}, status=400)

    async with AsyncSessionLocal() as session:
        result_user = await session.execute(select(User).filter_by(id=user_id).with_for_update())
        db_user = result_user.scalars().first()
        
        if not db_user:
            return web.json_response({"error": "User not found in DB"}, status=404)

        # FIX: Added .with_for_update() to prevent race conditions on stock!
        result_prod = await session.execute(
            select(Product).filter_by(is_active=True, type='lottery').filter(Product.stock > 0).with_for_update()
        )
        products = result_prod.scalars().all()
        
        if not products:
            return web.json_response({"error": "现在无抽奖"}, status=400)

        spin_cost = int(products[0].cost)
        
        if db_user.vouchers < spin_cost:
            return web.json_response({"error": f"兑奖券不够, 需要 {spin_cost} 🎟"}, status=400)

        db_user.vouchers -= spin_cost
        
        # Normalize chances if admin misconfigured them to be > 100%
        total_win_chance = sum(p.chance for p in products)
        if total_win_chance > 1.0:
            for p in products:
                p.chance = p.chance / total_win_chance

        roll = random.random()
        cumulative = 0.0
        winning_id = -1 # Default to the "Lose" ID
        won_product = None
        
        for p in products:
            cumulative += p.chance
            if roll < cumulative:
                winning_id = p.id # FIX: We now save the ID, not the array index!
                won_product = p
                p.stock -= 1
                if p.stock <= 0:
                    await session.delete(p)
                break
                
        await session.commit()

    if won_product and _bot_instance and config.ADMIN_IDS:
        notify_msg = (
            f"🎰 转盘中奖通知\n"
            f"👤 用户: <a href='tg://user?id={user_id}'>{user_name}</a> (<code>{user_id}</code>)\n"
            f"🎁 赢取: {won_product.name}\n"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await _bot_instance.send_message(chat_id=admin_id, text=notify_msg, parse_mode='HTML')
            except Exception as e:
                print(f"Could not notify admin {admin_id}: {e}")   

    # FIX: Return the ID so the frontend doesn't get confused if the array shifts
    return web.json_response({"winning_id": winning_id, "message": "Success"})

# --- 3. Startup Function ---
async def start_web_server(bot):
    """Starts the aiohttp server on the port Railway provides."""
    global _bot_instance
    _bot_instance = bot

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