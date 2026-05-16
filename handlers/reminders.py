from datetime import datetime, timedelta
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_users_for_reminders, set_reminder_sent
import logging
from telegram import Update
from database import get_user, update_last_free_pack, add_user_card, get_card_info
from handlers.daily_pack import generate_daily_pack, user_packs, show_pack_card
from handlers.craft import send_pack_first_card
from image_processor import generate_card_image
import random

logger = logging.getLogger(__name__)

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    users = get_users_for_reminders()
    for user in users:
        user_id = user["user_id"]
        last_activity = user["last_activity_time"]
        if not last_activity:
            continue
        try:
            last_dt = datetime.fromisoformat(last_activity)
        except ValueError:
            continue

        # Проверка на 48 часов молчания
        if now - last_dt >= timedelta(hours=48):
            last_48 = user["last_reminder_48_sent"]
            if not last_48 or datetime.fromisoformat(last_48) < last_dt:
                text = (
                    "Эй, малой! Ты совсем зарылся? Барыга уже забыл, как ты выглядишь. "
                    "Халява стынет! Жми кнопку, пока я не обнулил твой тайник."
                )
                keyboard = [[InlineKeyboardButton("🆓 Забрать халяву", callback_data="daily_pack_reminder")]]
                try:
                    await context.bot.send_message(user_id, text, reply_markup=InlineKeyboardMarkup(keyboard))
                    set_reminder_sent(user_id, "48")
                except Exception as e:
                    logger.error(f"Ошибка отправки 48ч для {user_id}: {e}")
                continue  # не отправлять 24ч после 48ч

        # Проверка на 24 часа
        if now - last_dt >= timedelta(hours=24):
            last_24 = user["last_reminder_24_sent"]
            if not last_24 or datetime.fromisoformat(last_24) < last_dt:
                text = "Слышь, братан, халява ждёт! Заходи за бесплатным паком, пока я добрый."
                keyboard = [[InlineKeyboardButton("🆓 Забрать халяву", callback_data="daily_pack_reminder")]]
                try:
                    await context.bot.send_message(user_id, text, reply_markup=InlineKeyboardMarkup(keyboard))
                    set_reminder_sent(user_id, "24")
                except Exception as e:
                    logger.error(f"Ошибка отправки 24ч для {user_id}: {e}")

async def reminder_daily_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Проверка кулдауна (как в daily_pack_button)
    user_data = get_user(user_id)
    now = datetime.now()
    if user_data and user_data["last_free_pack_time"]:
        last = datetime.fromisoformat(user_data["last_free_pack_time"])
        if now - last < timedelta(hours=24):
            delta = timedelta(hours=24) - (now - last)
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            await query.edit_message_text(
                f"♿ Братан, халява раз в сутки. Жди ещё {hours} часов {minutes} минут."
            )
            return

    # Генерируем и показываем пак
    card_ids = generate_daily_pack(user_id)
    cards_info = [get_card_info(cid) for cid in card_ids]
    images = [generate_card_image(card) for card in cards_info]
    for img in images:
        img.seek(0)

    user_packs[user_id] = {
        "cards": cards_info,
        "images": images,
        "index": 0,
        "source": "daily"
    }
    update_last_free_pack(user_id, now.isoformat())
    await query.message.delete()
    await send_pack_first_card(context, user_id)