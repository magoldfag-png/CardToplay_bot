# handlers/premium.py
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from yoomoney import Quickpay
from config import YOO_MONEY_WALLET, STANDARD_PACK_PRICE
from database import add_pending_payment, add_user_card, get_card_info, get_pending_payments, mark_payment_done, add_pending_payment
from handlers.daily_pack import generate_premium_cards, generate_standard_cards, user_packs
from image_processor import generate_card_image
from handlers.daily_pack import send_pack_first_card
import datetime
import logging
from yoomoney import Client
import time

logger = logging.getLogger(__name__)


MAX_RETRIES = 3
RETRY_DELAY = 5  # секунд между попытками

async def premium_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки '💎 Премиум пак'."""
    user = update.effective_user
    code = f"premium_{user.id}_{int(datetime.datetime.now().timestamp())}"
    add_pending_payment(user.id, code, pack_type="premium")

    quickpay = Quickpay(
        receiver=4100119527268522,
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
        "💰 Мега-Бустер за 99₽ с повышенными шансами на ЛЕГЕНДАРНУЮ карту. После оплаты покажу твои 5 карт.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def standard_pack_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки '🃏 Стандартный пак'."""
    user = update.effective_user
    code = f"standard_{user.id}_{int(datetime.datetime.now().timestamp())}"
    add_pending_payment(user.id, code, pack_type="standard")

    quickpay = Quickpay(
        receiver=4100119527268522,
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
        f"🃏 Стандартный пак за {STANDARD_PACK_PRICE}₽ с обычнами шансами. После оплаты покажу твои 5 карт.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_payment_and_deliver(context: ContextTypes.DEFAULT_TYPE):
    payments = get_pending_payments()
    if not payments:
        return

    # Создаём клиента один раз (он потокобезопасен для чтения)
    client = Client(4100119527268522)

    for pay in payments:
        user_id = pay["user_id"]
        label = pay["payment_label"]
        pack_type = pay["pack_type"] if "pack_type" in pay.keys() else "premium"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Запускаем синхронный запрос в отдельном потоке, чтобы не блокировать event loop
                loop = asyncio.get_running_loop()
                history = await loop.run_in_executor(
                    None,
                    lambda: client.operation_history(type="deposition", label=label)
                )
                for op in history.operations:
                    if op.status == 'success':
                        # Выдача бустера
                        if pack_type == "standard":
                            card_ids = generate_standard_cards(user_id)
                        else:
                            card_ids = generate_premium_cards(user_id)

                        for cid in card_ids:
                            add_user_card(user_id, cid)

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
                        logger.info(f"{pack_type} пакет выдан пользователю {user_id} после {attempt} попытки")
                        return  # успешно обработали
                break  # нет успешных операций – выходим из цикла попыток
            except Exception as e:
                logger.warning(f"Попытка {attempt}/{MAX_RETRIES} для {label} провалилась: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)  # асинхронная задержка
                else:
                    logger.error(f"Исчерпаны попытки для {label}, платёж пока не обработан")