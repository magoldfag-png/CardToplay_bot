import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

BOT_TOKEN = "8713574808:AAFAubpsose9OpnjD2HJ-UlF2oW5jugIcNk" #test
#BOT_TOKEN = "8622336565:AAHiqfjeV4Tjr3dPgvoYHz4VzcgB2JM6d-w" # original
admin_ids_str = os.getenv("1279277410", "")
ADMIN_IDS =1279277410,471158717

YOO_MONEY_CLIENT_ID ="CD51A0477CA902D2D0C10ACBA3A602583D72BEAA354EB17703A3A058AD82E2E3"
YOO_MONEY_TOKEN ="4100119527268522.AE6CB86B7BC3AC98E26A93CBD8DF07923C96701A993145553DBCBBDA1A135E5EE339A44A19C77A74EB16331BBC608264239098680EF77B2A350DDBD6FB8CBFFB5ECE5A2C4246F158F8FEF5782B568EB5F6B45E63381CD77C5CF82ED71136AAB66FE5D674FBEEBD83A14FA4A8E66CD76F4E8214886A1D2B68B31830BDFE1DB166"
YOO_MONEY_FUNDRAISE_URL = "https://yoomoney.ru/fundraise/1HJ1FFMHUUL.260506"
YOO_MONEY_WALLET=4100119527268522
PAYMENT_DETAILS = os.getenv("PAYMENT_DETAILS", "карта 4276 0000 0000 0000")
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS =1279277410,471158717
print(f"Загруженные ADMIN_IDS: {ADMIN_IDS}")
# Веса для ежедневного пака (шансы)
STANDARD_PACK_PRICE = 49
DISCOUNT_PREMIUM_PRICE = 79
DISCOUNT_STANDARD_PRICE = 39
PRODUCT_PRICES = {
    "premium_1": 99,
    "premium_5": 349,
    "premium_10": 699,
    "standard_1": 49,
    "standard_5": 179,
    "standard_10": 299
}

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
DISCOUNT_START_HOUR = int(os.getenv("DISCOUNT_START_HOUR", "10"))
DISCOUNT_END_HOUR = int(os.getenv("DISCOUNT_END_HOUR", "22"))