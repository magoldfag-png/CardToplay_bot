# handlers/premium.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from yoomoney import Quickpay
from config import YOO_MONEY_WALLET, STANDARD_PACK_PRICE
from database import add_pending_payment, add_user_card, get_card_info, get_pending_payments, mark_payment_done, add_pending_payment
from handlers.daily_pack import generate_premium_cards, generate_standard_cards, user_packs
from image_processor import generate_card_image
from handlers.craft import send_pack_first_card
import datetime
import logging

logger = logging.getLogger(__name__)

async def premium_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки '💎 Премиум пак'."""
    user = update.effective_user
    code = f"premium_{user.id}_{int(datetime.datetime.now().timestamp())}"
    add_pending_payment(user.id, code, pack_type="premium")

    quickpay = Quickpay(
        receiver=YOO_MONEY_WALLET,
        quickpay_form="shop",
        targets="Мега-Бустер (99₽)",
        paymentType="SB",
        sum=99,
        label=code,
        successURL="https://t.me/CardPackToPlay_bot"  # замени на свой юзернейм
    )
    payment_url = quickpay.base_url

    keyboard = [[InlineKeyboardButton("💳 Перейти к оплате", url=payment_url)]]
    await update.message.reply_text(
        "💰 Мега-Бустер за 99₽. После оплаты покажу твои 5 карт.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def standard_pack_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки '🃏 Стандартный пак'."""
    user = update.effective_user
    code = f"standard_{user.id}_{int(datetime.datetime.now().timestamp())}"
    add_pending_payment(user.id, code, pack_type="standard")

    quickpay = Quickpay(
        receiver=YOO_MONEY_WALLET,
        quickpay_form="shop",
        targets=f"Стандартный пак ({STANDARD_PACK_PRICE}₽)",
        paymentType="SB",
        sum=STANDARD_PACK_PRICE,
        label=code,
        successURL="https://t.me/CardPackToPlay_bot"
    )
    payment_url = quickpay.base_url

    keyboard = [[InlineKeyboardButton("💳 Перейти к оплате", url=payment_url)]]
    await update.message.reply_text(
        f"🃏 Стандартный пак за {STANDARD_PACK_PRICE}₽. После оплаты покажу твои 5 карт.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_payment_and_deliver(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка оплаченных заказов (премиум и стандартный)."""
    from yoomoney import Client
    from config import YOO_MONEY_TOKEN
    client = Client(YOO_MONEY_TOKEN)
    payments = get_pending_payments()
    if not payments:
        return

    for pay in payments:
        user_id = pay["user_id"]
        label = pay["payment_label"]
        pack_type = pay["pack_type"] if pay["pack_type"] else "premium" # если в БД есть поле
        try:
            history = client.operation_history(type="deposition", label=label)
            for op in history.operations:
                if op.status == 'success':
                    # Выбираем генератор в зависимости от типа пакета
                    if pack_type == "standard":
                        card_ids = generate_standard_cards(user_id)
                    else:  # premium
                        card_ids = generate_premium_cards()

                    for cid in card_ids:
                        add_user_card(user_id, cid)

                    # Готовим изображения и состояние пакета
                    cards_info = [get_card_info(cid) for cid in card_ids]
                    images = [generate_card_image(card) for card in cards_info]
                    for img in images:
                        img.seek(0)

                    user_packs[user_id] = {
                        "cards": cards_info,
                        "images": images,
                        "index": 0,
                        "source": pack_type
                    }

                    mark_payment_done(label)
                    await send_pack_first_card(context, user_id)
                    logger.info(f"{pack_type} пакет выдан пользователю {user_id}")
                    return
        except Exception as e:
            logger.error(f"Ошибка проверки {label}: {e}", exc_info=True)