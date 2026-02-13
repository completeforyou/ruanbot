# services/verification.py
import time
import random

_pending_verifications = {}

def generate_math_question(user_id: int):
    """
    Generates a double-digit addition problem and 4 close options.
    """
    # Generate double-digit numbers
    num1 = random.randint(10, 99)
    num2 = random.randint(10, 99)
    correct_ans = num1 + num2

    answers = [correct_ans]
    
    # Smarter error pool to trick guessers:
    # +/- 10 or 20 (same last digit, catches people who only add the ones place)
    # +/- 1 or 2 (extremely close, catches quick guessers)
    error_pool = [-20, -10, -2, -1, 1, 2, 10, 20]
    
    while len(answers) < 4:
        wrong = correct_ans + random.choice(error_pool)
        
        # Make sure the wrong answer isn't a duplicate and is a positive number
        if wrong not in answers and wrong > 0:
            answers.append(wrong)
    
    # Shuffle the options so the correct answer isn't always in the same spot
    random.shuffle(answers)
    
    # Save the challenge data
    _pending_verifications[user_id] = {
        "time": time.time(),
        "correct": correct_ans
    }
    
    question_text = f"{num1} + {num2} = ?"
    return question_text, answers

def get_verification(user_id: int):
    return _pending_verifications.get(user_id)

def clear_verification(user_id: int):
    if user_id in _pending_verifications:
        del _pending_verifications[user_id]