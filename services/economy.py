# services/economy.py
from database import Session, User
from datetime import datetime

def get_or_create_user(user_id: int, username: str, full_name: str):
    session = Session()
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        user = User(id=user_id, username=username, full_name=full_name)
        session.add(user)
        session.commit()
    session.close()

def add_points(user_id: int, amount: float):
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.points += amount
            session.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        session.close()

def increment_stats(user_id: int):
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.msg_count_total += 1
            user.last_msg_date = datetime.utcnow()
            session.commit()
    finally:
        session.close()