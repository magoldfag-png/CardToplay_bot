from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import create_user, has_used_promo, use_promo, add_user_card, get_card_info
from image_processor import generate_card_image
from handlers.daily_pack import generate_standard_cards, display_generated_pack
import os

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username)

    welcome_bonus_given = False
    if not has_used_promo(user.id, "WELCOME"):
        # Сразу выдаём легендарку
        add_user_card(user.id, 16)
        use_promo(user.id, "WELCOME")
        welcome_bonus_given = True

    # Основное меню
    keyboard = [
        ["🆓 Ежедневный пак", "📦 Коллекция", "🔨 Крафт"],
        ["💎 Премиум пак", "⚔️ Сюжетка"],
        ["👤 Профиль", "🌪️ Облава", "💰 Рынок"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    caption_text = (
        "Ну чё, малой, поностальгируем? Я тут главный. "
        "Хочешь карточку — забирай халяву раз в день. "
        "А за остальное плати монетой."
    )

    photo_path = os.path.join("cards", "card_99.jpg")
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=caption_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(caption_text, reply_markup=reply_markup)

    # Если первый заход – показываем легендарку с кнопкой
    if welcome_bonus_given:
        card = get_card_info(23)
        if card:
            img = generate_card_image(card)
            img.seek(0)
            caption = "Барыга: «Держи легендарную карту, малой! Сколько еще похотливых девиц тебя ждут? Сложно представить. Держи пак карточек за мой счет, может там одна из таких девиц?)»"
            keyboard = [[InlineKeyboardButton("🎁 Открыть стандартный пак", callback_data="open_welcome_pack")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_photo(photo=img, caption=caption, reply_markup=reply_markup)

async def open_welcome_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает приветственный стандартный пак."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    # Генерируем 5 случайных карт
    card_ids = generate_standard_cards(user_id)
    # Показываем их с листанием
    await display_generated_pack(user_id, card_ids, context)
    # Удаляем сообщение с кнопкой
    await query.message.delete()