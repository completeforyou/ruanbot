# services/economy.py
from database import Session, User
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