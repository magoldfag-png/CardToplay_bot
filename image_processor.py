import os
import io
from config import CARDS_IMG_DIR

def generate_card_image(card):
    """
    Возвращает BytesIO с готовым изображением карты в формате JPG.
    card: объект Row с полем id (и другими, но здесь они не нужны).
    """
    card_id = card["id"]
    # Расширение теперь .jpg (можно также поддержать .jpeg или проверять наличие)
    file_path = os.path.join(CARDS_IMG_DIR, f"card_{card_id}.jpg")
    
    # На случай, если файл вдруг в PNG — можно добавить проверку
    if not os.path.exists(file_path):
        file_path = os.path.join(CARDS_IMG_DIR, f"card_{card_id}.png")
    
    with open(file_path, "rb") as f:
        img_bytes = f.read()
    
    img_io = io.BytesIO(img_bytes)
    img_io.seek(0)
    return img_io