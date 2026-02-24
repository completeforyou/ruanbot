# services/verification.py
import time
import random
import string
from io import BytesIO
from captcha.image import ImageCaptcha

_pending_verifications = {}

def generate_gif_captcha(user_id: int):
    """
    Generates a rapid-flashing animated GIF captcha.
    Optimized to defeat OCR bots while remaining readable to humans.
    """
    # 1. Generate the correct 4-character string (No ambiguous characters)
    characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    correct_ans = ''.join(random.choices(characters, k=4))
    
    # 2. Setup the generator
    # We use a slightly wider canvas to give the characters room to warp
    image_generator = ImageCaptcha(width=300, height=100)
    frames = []
    
    # 3. Generate MORE frames for a chaotic, unreadable-by-bot sequence
    # 8 frames ensures the noise lines constantly shift positions.
    for _ in range(8):
        # The library automatically applies random warp, noise curves, and dots per frame
        frame = image_generator.generate_image(correct_ans)
        frames.append(frame)
        
    # 4. Stitch into a high-speed GIF
    gif_io = BytesIO()
    # duration=100 means 10 frames per second. Fast enough to blur the noise for humans,
    # but completely breaks frame-by-frame OCR analysis.
    frames[0].save(
        gif_io, 
        format='GIF', 
        save_all=True, 
        append_images=frames[1:], 
        duration=100, 
        loop=0
    )
    gif_io.seek(0)
    gif_io.name = "captcha.gif"
    
    # 5. Create a pool of 6 answers
    answers = [correct_ans]
    while len(answers) < 6:
        fake = ''.join(random.choices(characters, k=4))
        if fake not in answers:
            answers.append(fake)
            
    random.shuffle(answers)
    
    _pending_verifications[user_id] = {
        "time": time.time(),
        "correct": correct_ans
    }
    
    return gif_io, answers

def get_verification(user_id: int):
    return _pending_verifications.get(user_id)

def clear_verification(user_id: int):
    if user_id in _pending_verifications:
        del _pending_verifications[user_id]