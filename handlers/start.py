from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from database import create_user
import os

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username)

    keyboard = [
        ["🆓 Ежедневный пак", "📦 Коллекция", "🔨 Крафт"],
        ["🃏 Стандартный пак", "💎 Премиум пак"]
    ]  
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    with open(os.path.join("cards", "card_0.jpg"), "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=(
                "Ну чё, малой, поностальгируем? Я тут главный. "
                "Хочешь карточку — забирай халяву раз в день. "
                "А за остальное плати монетой.\n\n"
                "🔥 Для новичков: введи PIKA прямо в чат и получи бесплатный Мега-Бустер (только один раз)!"
            ),
            reply_markup=reply_markup
        )