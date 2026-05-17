import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (get_artifacts_count, get_trophies_count,
                      sell_item, get_daily_market, generate_daily_market,
                      get_last_card_purchase_time, buy_card_market,
                      get_card_info, get_user)
from config import ADMIN_IDS  # если нужно

async def market_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в рынок."""
    text = "💲 Рынок за углом. Что надо, малой?"
    keyboard = [
        [InlineKeyboardButton("📤 Продать", callback_data="market_sell_menu"),
         InlineKeyboardButton("📥 Купить карту", callback_data="market_buy_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def sell_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    arts = get_artifacts_count(user_id)
    trophies = get_trophies_count(user_id)
    if arts == 0 and trophies == 0:
        await query.edit_message_text("Продавать нечего, малой. Добудь артефакты в сюжетке или облаве.")
        return
    text = f"У тебя {arts} артефактов и {trophies} трофеев. Что продаём?"
    keyboard = []
    if arts > 0:
        keyboard.append([InlineKeyboardButton("Продать артефакт за 50💰", callback_data="market_sell_artifact")])
    if trophies > 0:
        keyboard.append([InlineKeyboardButton("Продать трофей за 150💰", callback_data="market_sell_trophy")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="market_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def sell_item_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    item_type = query.data.split("_")[-1]  # artifact / trophy
    price = sell_item(user_id, item_type)
    if price is None:
        await query.answer("Недостаточно предметов.", show_alert=True)
        return
    await query.edit_message_text(f"Сделка закрыта. Держи {price} монет. {', малой.' if price<150 else ', жирно!'}")

async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    # Проверка времени последней покупки
    last_time = get_last_card_purchase_time(user_id)
    now = datetime.datetime.now()
    if last_time:
        try:
            last_dt = datetime.datetime.fromisoformat(last_time)
            if now - last_dt < datetime.timedelta(hours=24):
                delta = datetime.timedelta(hours=24) - (now - last_dt)
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                await query.edit_message_text(f"Ты уже купил карту сегодня, малой. Приходи через {hours} ч {minutes} мин.")
                return
        except ValueError:
            pass  # если дата битая, разрешаем

    today = now.strftime("%Y-%m-%d")
    market = get_daily_market(today)
    if market is None:
        generate_daily_market(today)
        market = get_daily_market(today)
        if not market:
            await query.edit_message_text("Сегодня рынок не работает, заходи позже.")
            return

    text = "Сегодня на рынке:\n\n"
    keyboard = []
    for row in market:
        card = get_card_info(row["card_id"])
        if card is None:
            continue
        price = row["price"]
        text += f"{card['name']} ({card['rarity']}) — {price}💰\n"
        keyboard.append([InlineKeyboardButton(f"Купить {card['name']} за {price}💰", callback_data=f"market_buy_{card['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="market_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def buy_card_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    card_id = int(query.data.split("_")[-1])
    # Получаем цену из daily_market
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    market = get_daily_market(today)
    price = None
    for row in market:
        if row["card_id"] == card_id:
            price = row["price"]
            break
    if price is None:
        await query.answer("Карта не найдена на рынке.", show_alert=True)
        return

    # Повторная проверка таймера
    last_time = get_last_card_purchase_time(user_id)
    now = datetime.datetime.now()
    if last_time:
        try:
            last_dt = datetime.datetime.fromisoformat(last_time)
            if now - last_dt < datetime.timedelta(hours=24):
                delta = datetime.timedelta(hours=24) - (now - last_dt)
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                await query.answer(f"Не, братан, ещё {hours} ч {minutes} мин. Не жульничай.", show_alert=True)
                return
        except ValueError:
            pass

    # Проверка баланса и покупка
    success = buy_card_market(user_id, card_id, price)
    if not success:
        await query.answer("Не хватает звонких монет, братан. Продай что-нибудь или покрути бустеры.", show_alert=True)
        return
    await query.edit_message_text(f"Карта твоя, малой. Приходи завтра за новой.")

async def market_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await market_button(update, context)  # возврат к главному меню рынка