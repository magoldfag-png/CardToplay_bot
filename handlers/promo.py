from telegram import Update
from telegram.ext import ContextTypes
from database import has_used_promo, use_promo, add_user_card, get_card_info
from handlers.daily_pack import generate_premium_cards, user_packs
from image_processor import generate_card_image
from handlers.daily_pack import send_pack_first_card

async def promo_pika(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if has_used_promo(user.id, "PIKA"):
        await update.message.reply_text(
            "Ты уже активировал этот промокод, малой. Халява только раз!"
        )
        return

    # Генерируем Мега-Бустер (5 карт с повышенными шансами)
    card_ids = generate_premium_cards()
    for cid in card_ids:
        add_user_card(user.id, cid)

    cards_info = [get_card_info(cid) for cid in card_ids]
    images = [generate_card_image(card) for card in cards_info]
    for img in images:
        img.seek(0)

    user_packs[user.id] = {
        "cards": cards_info,
        "images": images,
        "index": 0,
        "source": "promo_pika"
    }

    use_promo(user.id, "PIKA")
    await send_pack_first_card(context, user.id)
    # Опционально: можно удалить сообщение пользователя с "PIKA"
    # await update.message.delete()