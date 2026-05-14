from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_user, add_user_card, get_card_info, add_coins, get_conn
from config import SPRAY_REWARDS
from handlers.daily_pack import generate_daily_pack, weighted_choice, user_packs
from image_processor import generate_card_image
import random
from handlers.daily_pack import generate_daily_pack, weighted_choice, user_packs, send_pack_first_card
CRAFT_PRICES = {
    rarity: int(price * 1.1)
    for rarity, price in SPRAY_REWARDS.items()
}
PACK_PRICE = 70
RARITY_NAMES = {
    "common": "Обычная",
    "rare": "Редкая",
    "epic": "Эпическая",
    "mythic": "Мифическая",
    "legendary": "Легендарная"
}

async def craft_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки '🔨 Крафт'."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    coins = user["coins"] if user else 0
    text = f"💰 Вот твои пожитки: {coins} монет.\nЧё крафтить будем, малой?"

    keyboard = [
        [InlineKeyboardButton("🃏 Создать карту", callback_data="craft_card_menu")],
        [InlineKeyboardButton(f"🎁 Купить пак ({PACK_PRICE}💰)", callback_data="craft_buy_pack")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def craft_card_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора редкости для крафта."""
    query = update.callback_query
    await query.answer()
    keyboard = []
    for rarity, price in CRAFT_PRICES.items():
        name = RARITY_NAMES[rarity]
        keyboard.append([InlineKeyboardButton(f"{name} ({price}💰)", callback_data=f"craft_{rarity}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="craft_menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выбирай редкость:", reply_markup=reply_markup)

async def craft_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создаёт случайную карту выбранной редкости за монеты."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    rarity = query.data.split("_")[1]  # craft_<rarity>
    price = CRAFT_PRICES[rarity]
    user = get_user(user_id)
    if not user or user["coins"] < price:
        need = price - (user["coins"] if user else 0)
        await query.edit_message_text(f"Не, братан, у тебя лаванды не хватает. Нужно ещё {need}💰.")
        return

    add_coins(user_id, -price)
    # Выбираем случайную карту этой редкости
    conn = get_conn()
    possible = conn.execute("SELECT id FROM cards WHERE rarity = ? AND id != 99", (rarity,)).fetchall()
    conn.close()
    if not possible:
        await query.edit_message_text("Нет карт такой редкости, братан.")
        return
    card_id = random.choice(possible)["id"]
    add_user_card(user_id, card_id)
    card = get_card_info(card_id)
    img = generate_card_image(card)
    img.seek(0)
    caption = (
        f"Держи свою карту, малой. С тебя {price}💰.\n"
        f"🃏 {card['name']}\n"
        f"СИЛА {card['strength']} | ВЫНОСЛИВОСТЬ {card['endurance']}\n"
        f"Способность: {card['ability_name']}"
    )
    await query.message.delete()
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_photo(chat_id=user_id, photo=img, caption=caption, reply_markup=reply_markup)

async def craft_buy_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка пакета за 70 монет."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if not user or user["coins"] < PACK_PRICE:
        need = PACK_PRICE - (user["coins"] if user else 0)
        await query.edit_message_text(f"Не хватает монет, малой. Нужно ещё {need}💰.")
        return
    add_coins(user_id, -PACK_PRICE)
    # Генерируем пак (как ежедневный)
    card_ids = generate_daily_pack(user_id)
    cards_info = [get_card_info(cid) for cid in card_ids]
    images = [generate_card_image(card) for card in cards_info]
    for img in images:
        img.seek(0)
    user_packs[user_id] = {
        "cards": cards_info,
        "images": images,
        "index": 0,
        "source": "crafted_pack"
    }
    await query.message.delete()
    # Отправляем первую карту пака с интерфейсом
    await send_pack_first_card(context, user_id)



async def craft_menu_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню крафта."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user = get_user(user_id)
    coins = user["coins"] if user else 0
    text = f"💰 Вот твои пожитки: {coins} монет.\nЧё крафтить будем, малой?"

    keyboard = [
        [InlineKeyboardButton("🃏 Создать карту", callback_data="craft_card_menu")],
        [InlineKeyboardButton(f"🎁 Купить пак ({PACK_PRICE}💰)", callback_data="craft_buy_pack")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)