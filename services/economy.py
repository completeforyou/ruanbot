# services/economy.py
from database import Session, SystemConfig, User
from sqlalchemy import update
from datetime import datetime

def get_or_create_user(user_id: int, username: str, full_name: str):
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            user = User(id=user_id, username=username, full_name=full_name)
            session.add(user)
            session.commit()
            print(f"🆕 New user created: {full_name} ({user_id})")
    finally:
        session.close()

def add_points(user_id: int, amount: float):
    """
    Atomic update: Safely increments points directly in the DB.
    """
    session = Session()
    try:
        # SQL equivalent: UPDATE users SET points = points + amount WHERE id = user_id
        stmt = update(User).where(User.id == user_id).values(points=User.points + amount)
        session.execute(stmt)
        session.commit()
        print(f"💰 Points Added! User: {user_id}, Amount: +{amount}")
    except Exception as e:
        session.rollback()
        print(f"❌ DB Error adding points: {e}")
    finally:
        session.close()

def increment_stats(user_id: int):
    """
    Atomic update for message counts.
    """
    session = Session()
    try:
        stmt = update(User).where(User.id == user_id).values(
            msg_count_total=User.msg_count_total + 1,
            last_msg_date=datetime.utcnow()
        )
        session.execute(stmt)
        session.commit()
    except Exception as e:
        print(f"❌ DB Error stats: {e}")
    finally:
        session.close()

def get_user_balance(user_id: int) -> float:
    """
    Fetches the current point balance for a user.
    """
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        return user.points if user else 0.0
    finally:
        session.close()

def get_user_vouchers(user_id: int) -> int:
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        return user.vouchers if user else 0
    finally:
        session.close()

def add_vouchers(user_id: int, amount: int):
    session = Session()
    try:
        # Check if user exists first to be safe
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            stmt = update(User).where(User.id == user_id).values(vouchers=User.vouchers + amount)
            session.execute(stmt)
            session.commit()
            print(f"🎟 Voucher Update: User {user_id} +{amount}")
        else:
            print(f"❌ Failed to add vouchers: User {user_id} not found.")
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        session.close()

def get_voucher_cost() -> int:
    session = Session()
    try:
        config = session.query(SystemConfig).filter_by(id=1).first()
        return config.voucher_cost if config else 500
    finally:
        session.close()

def set_voucher_cost(cost: int):
    session = Session()
    try:
        config = session.query(SystemConfig).filter_by(id=1).first()
        if not config:
            config = SystemConfig(id=1)
            session.add(config)
        config.voucher_cost = cost
        session.commit()
        return True
    finally:
        session.close()

def process_check_in(user_id: int, username: str, full_name: str):
    """
    Handles user check-in.
    Returns: (Success: bool, Message: str, PointsAdded: float)
    """
    session = Session()
    try:
        # 1. Get User
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            user = User(id=user_id, username=username, full_name=full_name)
            session.add(user)
        
        # 2. Get Config (Or create default)
        config = session.query(SystemConfig).filter_by(id=1).first()
        if not config:
            config = SystemConfig(id=1, check_in_points=10.0, check_in_limit=1)
            session.add(config)
            session.commit() # Save default config immediately

        # 3. Check Date (Reset count if it's a new day)
        now = datetime.now()
        if user.last_check_in_date:
            if user.last_check_in_date.date() < now.date():
                user.daily_check_in_count = 0
        
        # 4. Check Limit
        if user.daily_check_in_count >= config.check_in_limit:
            return False, f"📅 您今天已经签到 {config.check_in_limit} 次了!", 0.0
        
        # 5. Award Points
        points_to_add = config.check_in_points
        user.points += points_to_add
        user.daily_check_in_count += 1
        user.last_check_in_date = now
        
        session.commit()
        return True, "✅ 签到成功!", points_to_add
        
    except Exception as e:
        print(f"Check-in Error: {e}")
        return False, "❌ System error.", 0.0
    finally:
        session.close()

def set_check_in_config(points: float, limit: int):
    session = Session()
    try:
        config = session.query(SystemConfig).filter_by(id=1).first()
        if not config:
            config = SystemConfig(id=1)
            session.add(config)
        
        config.check_in_points = points
        config.check_in_limit = limit
        session.commit()
        return True
    finally:
        session.close()

def set_voucher_buy_status(enabled: bool):
    """Admin: Toggles the ability to buy vouchers."""
    session = Session()
    try:
        config = session.query(SystemConfig).filter_by(id=1).first()
        if not config:
            config = SystemConfig(id=1)
            session.add(config)
        
        config.voucher_buy_enabled = enabled
        session.commit()
        return True
    except Exception as e:
        print(f"Error setting voucher status: {e}")
        return False
    finally:
        session.close()

def is_voucher_buy_enabled() -> bool:
    """Checks if voucher buying is allowed."""
    session = Session()
    try:
        config = session.query(SystemConfig).filter_by(id=1).first()
        # Default to True if config doesn't exist yet
        return config.voucher_buy_enabled if config else True
    finally:
        session.close()