import logging
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from yoomoney import Client, Quickpay
from config import (
    YOO_MONEY_TOKEN,
    YOO_MONEY_WALLET,
    DISCOUNT_PREMIUM_PRICE,
    DISCOUNT_STANDARD_PRICE,
)
from database import (
    get_pending_payments,
    add_pending_payment,
    mark_payment_done,
    get_user_exp,
    get_card_info,
    add_user_card,
    get_pending_old_payments,
    expire_payment,
)
from handlers.daily_pack import (
    generate_premium_cards,
    generate_standard_cards,
    user_packs,
)
from image_processor import generate_card_image
from handlers.craft import send_pack_first_card

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # секунд между попытками при ошибке сети

async def check_payment_and_deliver(context: ContextTypes.DEFAULT_TYPE):
    """Фоновый таск: проверка оплаченных счетов и напоминание о неоплаченных (со скидкой)."""
        # 1. Обработка просроченных платежей (скидка) с ограничениями
    from config import DISCOUNT_START_HOUR, DISCOUNT_END_HOUR
    from database import get_last_discount_time, set_last_discount_time

    now = datetime.datetime.now()
    if DISCOUNT_START_HOUR <= now.hour < DISCOUNT_END_HOUR:
        old_payments = get_pending_old_payments(minutes=15)
        for old_pay in old_payments:
            user_id = old_pay["user_id"]
            # Проверяем, можно ли отправить скидку этому пользователю
            last_time = get_last_discount_time(user_id)
            if last_time:
                try:
                    last_dt = datetime.datetime.fromisoformat(last_time)
                    if (now - last_dt) < datetime.timedelta(hours=24):
                        continue  # недостаточно времени с последней скидки
                except ValueError:
                    pass  # если дата битая, разрешаем

            original_label = old_pay["payment_label"]
            pack_type = old_pay["pack_type"]
            discount_price = DISCOUNT_PREMIUM_PRICE if pack_type == "premium" else DISCOUNT_STANDARD_PRICE

            new_label = f"discount_{user_id}_{int(datetime.datetime.now().timestamp())}"
            quickpay = Quickpay(
                receiver=YOO_MONEY_WALLET,
                quickpay_form="shop",
                targets=f"Скидочный пак ({discount_price}₽)",
                paymentType="SB",
                sum=discount_price,
                label=new_label,
                successURL="https://t.me/your_bot?start=success"
            )
            payment_url = quickpay.base_url

            add_pending_payment(user_id, new_label, pack_type=pack_type, is_discount=1)
            expire_payment(original_label)

            try:
                await context.bot.send_message(
                    user_id,
                    f"⏳ Похоже, ты забыл про свой заказ, малой. Держи персональную скидку 20% на 24 часа!\n"
                    f"Новая цена: {discount_price}₽ вместо {99 if pack_type=='premium' else 49}₽.\n"
                    f"Ссылка действительна сутки."
                )
                await context.bot.send_message(
                    user_id,
                    f"Оплати сейчас: {payment_url}"
                )
                set_last_discount_time(user_id, now.isoformat())
            except Exception as e:
                logger.error(f"Ошибка отправки скидки пользователю {user_id}: {e}")
    # 2. Проверка успешных платежей
    payments = get_pending_payments()
    if not payments:
        return

    client = Client(YOO_MONEY_TOKEN)

    for pay in payments:
        user_id = pay["user_id"]
        label = pay["payment_label"]
        pack_type = pay["pack_type"] if "pack_type" in pay.keys() else "premium"
        pack_count = pay["pack_count"] if "pack_count" in pay.keys() else 1

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Запрос истории операций по метке (асинхронно в потоке)
                import asyncio
                loop = asyncio.get_running_loop()
                history = await loop.run_in_executor(
                    None,
                    lambda: client.operation_history(type="deposition", label=label)
                )
                for op in history.operations:
                    if op.status == 'success':
                        # Выдача паков
                        first_pack_cards = []
                        all_cards = []

                        for i in range(pack_count):
                            if pack_type == "standard":
                                new_cards = generate_standard_cards(user_id)
                            else:
                                new_cards = generate_premium_cards(user_id)
                            all_cards.extend(new_cards)
                            if i == 0:
                                first_pack_cards = new_cards

                        # Подготовка отображения первого пака
                        cards_info = [get_card_info(cid) for cid in first_pack_cards]
                        images = [generate_card_image(card) for card in cards_info]
                        for img in images:
                            img.seek(0)

                        user_packs[user_id] = {
                            "cards": cards_info,
                            "images": images,
                            "index": 0,
                            "source": f"{pack_type}_pack"
                        }

                        mark_payment_done(label)
                        await send_pack_first_card(context, user_id)

                        if pack_count > 1:
                            await context.bot.send_message(
                                user_id,
                                f"🎁 Всего ты получил {pack_count} паков! Остальные карты уже в коллекции, смотри."
                            )

                        logger.info(f"{pack_type} пак(ы) x{pack_count} выданы пользователю {user_id} после {attempt} попытки")
                        return  # успешно обработали платёж
                break  # если нет успешных операций, выходим из цикла попыток
            except Exception as e:
                logger.warning(f"Попытка {attempt}/{MAX_RETRIES} для {label} провалилась: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Исчерпаны попытки для {label}, платёж пока не обработан")