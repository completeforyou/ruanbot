# services/economy.py
from database import Session, SystemConfig, User
from sqlalchemy import update, desc
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
            msg_count_daily=User.msg_count_daily + 1,
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

def reset_daily_msg_counts(context=None):
    """
    Resets msg_count_daily for ALL users to 0. 
    Can be run as a scheduled job.
    """
    session = Session()
    try:
        session.query(User).update({User.msg_count_daily: 0})
        session.commit()
        print("🔄 Daily message counts have been reset.")
    except Exception as e:
        print(f"❌ Error resetting daily counts: {e}")
        session.rollback()
    finally:
        session.close()

def get_leaderboard(sort_by='points', limit=30):
    """
    Fetches top users sorted by 'points' or 'daily_msg'.
    Returns a list of User objects.
    """
    session = Session()
    try:
        if sort_by == 'daily_msg':
            users = session.query(User).order_by(desc(User.msg_count_daily)).limit(limit).all()
        else:
            # Default to points
            users = session.query(User).order_by(desc(User.points)).limit(limit).all()
        return users
    finally:
        session.close()

def get_system_config():
    """Returns a dictionary of all system settings."""
    session = Session()
    try:
        config = session.query(SystemConfig).filter_by(id=1).first()
        if not config:
            config = SystemConfig(id=1)
            session.add(config)
            session.commit()
            session.refresh(config)
            
        return {
            'check_in_points': config.check_in_points,
            'check_in_limit': config.check_in_limit,
            'voucher_cost': config.voucher_cost,
            'voucher_buy_enabled': config.voucher_buy_enabled,
            'invite_reward_points': config.invite_reward_points,
            'max_daily_points': config.max_daily_points,
            'spam_threshold': config.spam_threshold,
            'spam_limit': config.spam_limit,
            'media_delete_time': getattr(config, 'media_delete_time', 60)
        }
    finally:
        session.close()

def update_system_config(**kwargs):
    """
    Generic updater. Example: update_system_config(invite_reward_points=50)
    """
    session = Session()
    try:
        config = session.query(SystemConfig).filter_by(id=1).first()
        if not config:
            config = SystemConfig(id=1)
            session.add(config)
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        session.commit()
        return True
    except Exception as e:
        print(f"Config Update Error: {e}")
        return False
    finally:
        session.close()

def get_voucher_cost() -> int:
    return get_system_config()['voucher_cost']

def is_voucher_buy_enabled() -> bool:
    return get_system_config()['voucher_buy_enabled']

def set_voucher_buy_status(enabled: bool):
    return update_system_config(voucher_buy_enabled=enabled)

def set_voucher_cost(cost: int):
    return update_system_config(voucher_cost=cost)

def set_check_in_config(points: float, limit: int):
    return update_system_config(check_in_points=points, check_in_limit=limit)

def process_check_in(user_id: int, username: str, full_name: str):
    # Update this to use the new config fetcher
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            user = User(id=user_id, username=username, full_name=full_name)
            session.add(user)
        
        # Get Config
        sys_conf = session.query(SystemConfig).filter_by(id=1).first()
        if not sys_conf:
            sys_conf = SystemConfig(id=1, check_in_points=10.0, check_in_limit=1)
            session.add(sys_conf)
            session.commit()

        # Check Date
        now = datetime.now()
        if user.last_check_in_date:
            if user.last_check_in_date.date() < now.date():
                user.daily_check_in_count = 0
        
        # Check Limit
        if user.daily_check_in_count >= sys_conf.check_in_limit:
            return False, f"📅 您今天已经签到 {sys_conf.check_in_limit} 次了!", 0.0
        
        # Award
        points_to_add = sys_conf.check_in_points
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