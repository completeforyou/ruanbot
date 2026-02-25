# services/economy.py
from database import AsyncSessionLocal
from models.user import User
from models.settings import SystemConfig
from sqlalchemy import update, desc, select, func
from datetime import datetime

# --- CACHE ---
_config_cache = None

_known_users = set()

async def get_or_create_user(user_id: int, username: str, full_name: str):
    # Check our fast memory first
    if user_id in _known_users:
        return
        
    # Optional Safety Check: If memory gets too big, clear it
    if len(_known_users) > 10000:
        _known_users.clear()
        
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalars().first()
            if not user:
                user = User(id=user_id, username=username, full_name=full_name)
                session.add(user)
                await session.commit()
                print(f"🆕 New user created: {full_name} ({user_id})")
            
            # Remember them!
            _known_users.add(user_id) 
            
        except Exception as e:
            await session.rollback()
            print(f"❌ DB Error get_or_create: {e}")

async def add_points(user_id: int, amount: float):
    async with AsyncSessionLocal() as session:
        try:
            stmt = update(User).where(User.id == user_id).values(points=User.points + amount)
            await session.execute(stmt)
            await session.commit()
            print(f"💰 Points Added! User: {user_id}, Amount: +{amount}")
        except Exception as e:
            await session.rollback()
            print(f"❌ DB Error adding points: {e}")

async def increment_stats(user_id: int):
    async with AsyncSessionLocal() as session:
        try:
            stmt = update(User).where(User.id == user_id).values(
                msg_count_total=User.msg_count_total + 1,
                msg_count_daily=User.msg_count_daily + 1,
                last_msg_date=datetime.utcnow()
            ).returning(User.msg_count_total)
            
            result = await session.execute(stmt)
            new_total = result.scalar()
            await session.commit()
            return new_total or 0
        except Exception as e:
            print(f"❌ DB Error stats: {e}")
            await session.rollback()
            return 0

async def get_user_balance(user_id: int) -> float:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        user = result.scalars().first()
        return user.points if user else 0.0

async def get_user_vouchers(user_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        user = result.scalars().first()
        return user.vouchers if user else 0

async def add_vouchers(user_id: int, amount: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalars().first()
            if user:
                stmt = update(User).where(User.id == user_id).values(vouchers=User.vouchers + amount)
                await session.execute(stmt)
                await session.commit()
                print(f"🎟 Voucher Update: User {user_id} +{amount}")
            else:
                print(f"❌ Failed to add vouchers: User {user_id} not found.")
        except Exception as e:
            print(f"DB Error: {e}")
            await session.rollback()

async def reset_daily_msg_counts(context=None):
    async with AsyncSessionLocal() as session:
        try:
            # We now reset both daily messages AND daily points
            stmt = update(User).values(msg_count_daily=0, points_earned_daily=0.0)
            await session.execute(stmt)
            await session.commit()
            print("🔄 Daily message counts and daily points have been reset.")
        except Exception as e:
            print(f"❌ Error resetting daily counts: {e}")
            await session.rollback()

async def award_chat_points(user_id: int, amount: float, max_daily_points: int) -> bool:
    """Awards points securely, checking against the daily limit."""
    async with AsyncSessionLocal() as session:
        try:
            # .with_for_update() locks the row so rapid messages don't bypass the limit
            result = await session.execute(select(User).filter_by(id=user_id).with_for_update())
            user = result.scalars().first()
            
            if not user:
                return False

            # Check if adding these points exceeds the limit
            if user.points_earned_daily + amount <= max_daily_points:
                user.points += amount
                user.points_earned_daily += amount
                await session.commit()
                print(f"💰 Chat Points Added! User: {user_id}, Amount: +{amount} (Daily: {user.points_earned_daily}/{max_daily_points})")
                return True
            else:
                # Limit reached, roll back the lock
                await session.rollback()
                return False
                
        except Exception as e:
            await session.rollback()
            print(f"❌ DB Error awarding chat points: {e}")
            return False

async def get_leaderboard(sort_by='points', limit=10, offset=0):
    async with AsyncSessionLocal() as session:
        if sort_by in ['daily_msg', 'msg']:
            stmt = select(User).order_by(desc(User.msg_count_daily)).limit(limit).offset(offset)
        else:
            stmt = select(User).order_by(desc(User.points)).limit(limit).offset(offset)
        
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        results = []
        for u in users:
            results.append({
                'full_name': u.full_name,
                'points': u.points,
                'msg_count_daily': u.msg_count_daily
            })
        return results

async def get_total_ranked_users(max_limit=30):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count(User.id)))
        count = result.scalar() or 0
        return min(count, max_limit)

async def get_system_config():
    global _config_cache
    if _config_cache:
        return _config_cache

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(SystemConfig).filter_by(id=1))
            config = result.scalars().first()
            if not config:
                config = SystemConfig(id=1)
                session.add(config)
                await session.commit()
                await session.refresh(config)
                
            _config_cache = {
                'check_in_points': config.check_in_points,
                'check_in_limit': config.check_in_limit,
                'voucher_cost': config.voucher_cost,
                'voucher_buy_enabled': config.voucher_buy_enabled,
                'invite_reward_points': config.invite_reward_points,
                'max_daily_points': config.max_daily_points,
                'spam_threshold': config.spam_threshold,
                'spam_limit': config.spam_limit,
                'media_delete_time': config.media_delete_time,
                'admin_media_exempt': config.admin_media_exempt
            }
            return _config_cache
        except Exception as e:
            print(f"❌ Error fetching config: {e}")
            return {}

async def update_system_config(**kwargs):
    global _config_cache
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(SystemConfig).filter_by(id=1))
            config = result.scalars().first()
            if not config:
                config = SystemConfig(id=1)
                session.add(config)
            
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            await session.commit()
            _config_cache = None 
            return True
        except Exception as e:
            print(f"Config Update Error: {e}")
            await session.rollback()
            return False

async def get_voucher_cost() -> int:
    conf = await get_system_config()
    return conf.get('voucher_cost', 500)

async def is_voucher_buy_enabled() -> bool:
    conf = await get_system_config()
    return conf.get('voucher_buy_enabled', False)

async def set_voucher_buy_status(enabled: bool):
    return await update_system_config(voucher_buy_enabled=enabled)

async def set_voucher_cost(cost: int):
    return await update_system_config(voucher_cost=cost)

async def set_check_in_config(points: float, limit: int):
    return await update_system_config(check_in_points=points, check_in_limit=limit)

async def process_check_in(user_id: int, username: str, full_name: str):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalars().first()
            
            if not user:
                user = User(id=user_id, username=username, full_name=full_name)
                session.add(user)
            
            sys_conf = await get_system_config()
            check_in_limit = sys_conf.get('check_in_limit', 1)
            check_in_points = sys_conf.get('check_in_points', 10.0)

            now = datetime.utcnow()
            if user.last_check_in_date:
                if user.last_check_in_date.date() < now.date():
                    user.daily_check_in_count = 0
            
            if user.daily_check_in_count >= check_in_limit:
                return False, f"📅 您今天已经签到 {check_in_limit} 次了!", 0.0
            
            points_to_add = check_in_points
            user.points += points_to_add
            user.daily_check_in_count += 1
            user.last_check_in_date = now
            
            await session.commit()
            return True, "✅ 签到成功!", points_to_add
            
        except Exception as e:
            print(f"Check-in Error: {e}")
            await session.rollback()
            return False, "❌ System error.", 0.0

async def remove_points(user_id: int, amount: float):
    async with AsyncSessionLocal() as session:
        try:
            # We lock the row during the update to prevent math errors if they are chatting rapidly
            result = await session.execute(select(User).filter_by(id=user_id).with_for_update())
            user = result.scalars().first()
            if user:
                # Ensure points never drop below 0
                user.points = max(0.0, user.points - amount)
                await session.commit()
                print(f"💸 Points Removed! User: {user_id}, Amount: -{amount}")
                return True
        except Exception as e:
            await session.rollback()
            print(f"❌ DB Error removing points: {e}")
        return False

async def remove_vouchers(user_id: int, amount: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).filter_by(id=user_id).with_for_update())
            user = result.scalars().first()
            if user:
                # Ensure vouchers never drop below 0
                user.vouchers = max(0, user.vouchers - amount)
                await session.commit()
                print(f"🎟 Vouchers Removed! User: {user_id}, Amount: -{amount}")
                return True
        except Exception as e:
            await session.rollback()
            print(f"❌ DB Error removing vouchers: {e}")
        return False
    
async def reset_all_points() -> bool:
    """Resets every user's points to 0.0 in the database."""
    async with AsyncSessionLocal() as session:
        try:
            # Update all rows in the User table
            stmt = update(User).values(points=0.0)
            await session.execute(stmt)
            await session.commit()
            print("⚠️ MONTHLY WIPE: All user points have been reset to 0.")
            return True
        except Exception as e:
            print(f"❌ Error resetting all points: {e}")
            await session.rollback()
            return False