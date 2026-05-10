import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

BOT_TOKEN = os.getenv("BOT_TOKEN")
admin_ids_str = os.getenv("1279277410", "")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()] if admin_ids_str else []

YOO_MONEY_CLIENT_ID = os.getenv("YOO_MONEY_CLIENT_ID")
YOO_MONEY_TOKEN = os.getenv("YOO_MONEY_TOKEN")
YOO_MONEY_FUNDRAISE_URL = os.getenv("YOO_MONEY_FUNDRAISE_URL") # Ссылка на виджет
YOO_MONEY_WALLET=os.getenv("YOO_MONEY_WALLET")
PAYMENT_DETAILS = os.getenv("PAYMENT_DETAILS", "карта 4276 0000 0000 0000")
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()] if admin_ids_str else []
print(f"Загруженные ADMIN_IDS: {ADMIN_IDS}")
# Веса для ежедневного пака (шансы)
STANDARD_PACK_PRICE = 49

SPRAY_REWARDS = {
    "common": 1,
    "rare": 7,
    "epic": 49,
    "mythic": 343,      # была легендарная
    "legendary": 2401    # была мифическая
}

DAILY_RARITY_WEIGHTS = {
    "common": 70,
    "rare": 20,
    "epic": 8,
    "mythic": 1.5,       # мифическая теперь чуть чаще
    "legendary": 0.5     # легендарная – самая редкая
}

PREMIUM_RARITY_WEIGHTS = {
    "common": 30,
    "rare": 40,
    "epic": 20,
    "mythic": 8,         # было legendary, стало mythic
    "legendary": 2       # было mythic, стало legendary
}

# Пути
CARDS_JSON = "cards.json"
CARDS_IMG_DIR = "cards"
FRAMES_DIR = "assets/frames"
DB_PATH = "cards.db"