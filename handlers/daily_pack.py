from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import random
from database import (get_conn, get_user, update_last_free_pack, add_user_card, get_card_info,
                      get_card_quantity, remove_one_card, add_coins)
from config import DAILY_RARITY_WEIGHTS, PREMIUM_RARITY_WEIGHTS
from image_processor import generate_card_image
from telegram import InputMediaPhoto 
from config import DAILY_RARITY_WEIGHTS, ADMIN_IDS
from utils.player_levels import get_bonuses
from database import get_user_exp
# Храним текущий открытый пак для навигации: user_id -> {"cards": [], "images": [], "index": 0}
user_packs = {}


def get_adjusted_weights(user_id):
    exp, level = get_user_exp(user_id)
    bonuses = get_bonuses(level)
    weights = DAILY_RARITY_WEIGHTS.copy()
    if bonuses["rare_boost"] > 0:
        # Увеличиваем rare на boost% за счет common
        boost = bonuses["rare_boost"]
        weights["common"] = max(0, weights["common"] - boost)
        weights["rare"] += boost
    return weights

def weighted_choice(weights):
    rarities = list(weights.keys())
    probs = list(weights.values())
    return random.choices(rarities, weights=probs, k=1)[0]

def generate_daily_pack(user_id: int) -> list[int]:
    """Генерирует 3 случайные карты с DAILY_RARITY_WEIGHTS, добавляет пользователю, возвращает список card_id."""
    generated_ids = []
    for _ in range(3):
        rarity = weighted_choice(DAILY_RARITY_WEIGHTS)
        conn = get_conn()
        possible = conn.execute("SELECT id FROM cards WHERE rarity = ? AND id != 99", (rarity,)).fetchall()
        conn.close()
        if possible:
            card_id = random.choice(possible)["id"]
        else:
            # fallback: common
            conn = get_conn()
            possible = conn.execute("SELECT id FROM cards WHERE rarity = 'common' AND id != 99").fetchall()
            conn.close()
            card_id = random.choice(possible)["id"]
        generated_ids.append(card_id)
        add_user_card(user_id, card_id)
    return generated_ids

async def daily_pack_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_user(user.id)
    now = datetime.now()
    user_exp, user_level = get_user_exp(user.id)
    cards_to_generate = 3
    adjusted_weights = get_adjusted_weights(user.id)
    # Админам можно всегда, без ограничений по времени
    if user.id not in ADMIN_IDS:
        if user_data and user_data["last_free_pack_time"]:
            last = datetime.fromisoformat(user_data["last_free_pack_time"])
            if now - last < timedelta(hours=24):
                delta = timedelta(hours=24) - (now - last)
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                await update.message.reply_text(
                    f"♿ Братан, халява раз в сутки. Жди ещё {hours} часов {minutes} минут."
                )
                return

    # Генерация 3 случайных карт (без изменений)
    generated_ids = generate_daily_pack(user.id)
    

    # Добавляем карты пользователю
    cards_info = []
    images = []
    for cid in generated_ids:
        rarity = weighted_choice(adjusted_weights)

        add_user_card(user.id, cid)
        card = get_card_info(cid)
        cards_info.append(card)
        img_io = generate_card_image(card)
        images.append(img_io)

    # Сохраняем состояние пака
    user_packs[user.id] = {
        "cards": cards_info,
        "images": images,
        "index": 0,
        "source": "daily"
    }

    # Обновляем время только для обычных юзеров
    if user.id not in ADMIN_IDS:
        update_last_free_pack(user.id, now.isoformat())

    await show_pack_card(update, context, user.id)

async def show_pack_card(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, edit=False):
    pack = user_packs.get(user_id)
    if not pack:
        return
    idx = pack["index"]
    card = pack["cards"][idx]
    img = pack["images"][idx]
    total = len(pack["cards"])
    qty = get_card_quantity(user_id, card["id"])

    caption = (
        f"🃏 Глянь, чо выпало!\n"
        f"СИЛА {card['strength']} | ВЫНОСЛИВОСТЬ {card['endurance']}\n"
        f"Способность: {card['ability_name']}"
    )

    keyboard = [
        [
            InlineKeyboardButton("◀️", callback_data=f"nav_pack_{idx-1}"),
            InlineKeyboardButton(f"{idx+1}/{total}", callback_data="noop"),
            InlineKeyboardButton("▶️", callback_data=f"nav_pack_{idx+1}")
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    # Управление стрелками
    if idx == 0:
        keyboard[0][0] = InlineKeyboardButton(" ", callback_data="noop")
    if idx == total - 1:
        keyboard[0][2] = InlineKeyboardButton(" ", callback_data="noop")

    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit and update.callback_query:
        img.seek(0) 
        await update.callback_query.edit_message_media(
            media=InputMediaPhoto(media=img, caption=caption),
            reply_markup=reply_markup
        )
    else:
        img.seek(0) 
        await update.message.reply_photo(
            photo=img,
            caption=caption,
            reply_markup=reply_markup
        )

async def handle_pack_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    pack = user_packs.get(user_id)
    if not pack:
        await query.message.delete()
        await context.bot.send_message(chat_id=user_id, text="Пак куда-то делся, братан. Попробуй заново.")
        return
    data = query.data
    if data.startswith("nav_pack_"):
        new_idx = int(data.split("_")[-1])
        total = len(pack["cards"])
        if 0 <= new_idx < total:
            pack["index"] = new_idx
            await show_pack_card(update, context, user_id, edit=True)

async def handle_spray_from_pack(update, context):
    """Распыление прямо из открытого пака (с проверкой >1 копии)."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data  # spray_pack_{card_id}_{index}
    _, _, card_id_str, idx_str = data.split("_")
    card_id = int(card_id_str)
    qty = get_card_quantity(user_id, card_id)
    if qty < 2:
        await query.answer("Единственный экземпляр, малой. Я тебе его пальну? Не, не пойдёт.", show_alert=True)
        return
    reward = remove_one_card(user_id, card_id)
    if reward:
        add_coins(user_id, reward)
        await query.answer(f"Ну, с дымком. Держи свои {reward} монет.", show_alert=True)
        # Обновить количество на текущей карточке
        pack = user_packs.get(user_id)
        if pack:
            await show_pack_card(update, context, user_id, edit=True)

def generate_premium_cards(user_id: int):
    """Генерирует 5 карт: гарантировано минимум 1 редкая."""
    cards_generated = []
    rare_ids = [row["id"] for row in get_conn().execute("SELECT id FROM cards WHERE rarity = 'rare' AND id != 99").fetchall()]
    if rare_ids:
        cards_generated.append(random.choice(rare_ids))
    else:
        common_ids = [row["id"] for row in get_conn().execute("SELECT id FROM cards WHERE rarity = 'common' AND id != 99").fetchall()]
        cards_generated.append(random.choice(common_ids))
    for _ in range(4):
        rarity = weighted_choice(PREMIUM_RARITY_WEIGHTS)
        possible = [row["id"] for row in get_conn().execute("SELECT id FROM cards WHERE rarity = ? AND id != 99", (rarity,)).fetchall()]
        if not possible:
            possible = [row["id"] for row in get_conn().execute("SELECT id FROM cards WHERE rarity = 'common' AND id != 99").fetchall()]
        cards_generated.append(random.choice(possible))
    for cid in cards_generated:
        add_user_card(user_id, cid)
    return cards_generated
# handlers/daily_pack.py

def generate_standard_cards(user_id: int):
    """Генерирует 5 случайных карт с обычными шансами (как ежедневный пак, но 5 штук)."""
    generated_ids = []
    for _ in range(5):
        rarity = weighted_choice(DAILY_RARITY_WEIGHTS)
        conn = get_conn()
        possible = conn.execute("SELECT id FROM cards WHERE rarity = ? AND id != 99", (rarity,)).fetchall()
        conn.close()
        if possible:
            card_id = random.choice(possible)["id"]
        else:
            conn = get_conn()
            possible = conn.execute("SELECT id FROM cards WHERE rarity = 'common' AND id != 99").fetchall()
            conn.close()
            card_id = random.choice(possible)["id"]
        generated_ids.append(card_id)
        add_user_card(user_id, card_id)
    return generated_ids

async def display_generated_pack(user_id: int, card_ids: list[int], context: ContextTypes.DEFAULT_TYPE):
    """Показывает открытый пак с перелистыванием для сгенерированных карт."""
    cards_info = [get_card_info(cid) for cid in card_ids]
    images = [generate_card_image(card) for card in cards_info]
    for img in images:
        img.seek(0)
    user_packs[user_id] = {
        "cards": cards_info,
        "images": images,
        "index": 0,
        "source": "standard"   # можно заменить на "welcome_bonus"
    }
    await send_pack_first_card(context, user_id)

async def send_pack_first_card(context, user_id):
    """Вспомогательная функция для отправки первой карты открытого пака."""
    pack = user_packs.get(user_id)
    if not pack:
        return
    idx = pack["index"]
    card = pack["cards"][idx]
    img = pack["images"][idx]
    total = len(pack["cards"])
    img.seek(0)
    caption = (
        f"🃏 Глянь, чо выпало!\n"
        f"СИЛА {card['strength']} | ВЫНОСЛИВОСТЬ {card['endurance']}\n"
        f"Способность: {card['ability_name']}"
    )
    keyboard = [
        [
            InlineKeyboardButton("◀️", callback_data=f"nav_pack_{idx-1}"),
            InlineKeyboardButton(f"{idx+1}/{total}", callback_data="noop"),
            InlineKeyboardButton("▶️", callback_data=f"nav_pack_{idx+1}")
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    if idx == 0:
        keyboard[0][0] = InlineKeyboardButton(" ", callback_data="noop")
    if idx == total - 1:
        keyboard[0][2] = InlineKeyboardButton(" ", callback_data="noop")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_photo(chat_id=user_id, photo=img, caption=caption, reply_markup=reply_markup)