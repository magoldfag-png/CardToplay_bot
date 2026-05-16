from telegram import InputMediaPhoto, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import SPRAY_REWARDS
from database import (get_conn, get_user_collection, get_card_info, get_card_quantity, get_user_exp,
                      remove_one_card, add_coins)
from image_processor import generate_card_image

# Состояние просмотра коллекции:
# user_id -> {"rarity": str, "card_ids": list[int], "index": int}
collection_state = {}
async def build_rarity_keyboard(user_id):
    """Строит текст и клавиатуру со списком редкостей, где у пользователя есть карты."""
    collection = get_user_collection(user_id)
    if not collection:
        return None, None
    rarity_cards = {}
    for card_id, qty in collection:
        card = get_card_info(card_id)
        if card is None:
            continue
        r = card["rarity"]
        rarity_cards.setdefault(r, []).append((card_id, qty))
    if not rarity_cards:
        return None, None
    rarity_names = {
        "common": "Обычная",
        "rare": "Редкая",
        "epic": "Эпическая",
        "mythic": "Мифическая",
        "legendary": "Легендарная"
    }
    keyboard = []
    for rarity in ["common", "rare", "epic", "mythic", "legendary"]:
        if rarity not in rarity_cards:
            continue
        unique_count = len(rarity_cards[rarity])
        total_copies = sum(qty for _, qty in rarity_cards[rarity])
        display_name = rarity_names.get(rarity, rarity)
        keyboard.append([
            InlineKeyboardButton(
                f"{display_name} ({unique_count} видов, {total_copies} шт.)",
                callback_data=f"coll_rarity_{rarity}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    return "Какую редкость глянем, барыга?", InlineKeyboardMarkup(keyboard)

async def collection_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text, markup = await build_rarity_keyboard(user.id)
    if text is None:
        await update.message.reply_text("Твой тайник пуст, малой. Сгоняй за паками.")
        return
    await update.message.reply_text(text, reply_markup=markup)

async def collection_rarity_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает первую карту выбранной редкости."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data  # coll_rarity_{rarity}
    rarity = data.split("_", 2)[2]

    # Получаем все карты этой редкости у пользователя (сортировка по id)
    collection = get_user_collection(user_id)
    card_ids = []
    for card_id, qty in collection:
        card = get_card_info(card_id)
        if card and card["rarity"] == rarity:
            card_ids.append(card_id)
    if not card_ids:
        await query.edit_message_text("Нет карт этой редкости, малой.")
        return

    card_ids.sort()
    collection_state[user_id] = {
        "rarity": rarity,
        "card_ids": card_ids,
        "index": 0
    }
    await show_collection_card(query, context, user_id)

async def show_collection_card(query, context, user_id):
    """Показывает текущую карту в коллекции (по rarity и индексу)."""
    state = collection_state.get(user_id)
    if not state:
        return
    idx = state["index"]
    card_ids = state["card_ids"]
    if idx >= len(card_ids):
        idx = len(card_ids) - 1
        state["index"] = idx
    card_id = card_ids[idx]
    card = get_card_info(card_id)
    qty = get_card_quantity(user_id, card_id)
    img = generate_card_image(card)
    img.seek(0)

    caption = (
        f"🃏 Коллекция — {card['rarity'].capitalize()}\n"
        f"{card['name']}\n"
        f"СИЛА {card['strength']} | ВЫНОСЛИВОСТЬ {card['endurance']}\n"
        f"Способность: {card['ability_name']}\n"
        f"🔥 x{qty}"
    )

    total = len(card_ids)
    # Навигационные кнопки
    nav_row = []
    if idx > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"coll_nav_{idx-1}"))
    else:
        nav_row.append(InlineKeyboardButton(" ", callback_data="noop"))
    nav_row.append(InlineKeyboardButton(f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"coll_nav_{idx+1}"))
    else:
        nav_row.append(InlineKeyboardButton(" ", callback_data="noop"))

    # Кнопки действий
    action_row = []
    if qty > 1:
        action_row.append(InlineKeyboardButton("🔥 Распылить", callback_data=f"coll_spray_{card_id}_{idx}"))
    if qty > 9:
        action_row.append(InlineKeyboardButton("💨 Распылить всё, оставить 1", callback_data=f"coll_sprayall_{card_id}_{idx}"))
    # Назад к выбору редкости
    action_row.append(InlineKeyboardButton("🔙 К редкостям", callback_data="coll_rarity_back"))

    keyboard = [nav_row]
    if action_row:
        keyboard.append(action_row)
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем текущее сообщение (так как пришло из callback)
    await query.edit_message_media(
        media=InputMediaPhoto(media=img, caption=caption),
        reply_markup=reply_markup
    )

async def handle_collection_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data  # coll_nav_{new_idx}
    new_idx = int(data.split("_")[-1])
    state = collection_state.get(user_id)
    if not state:
        await query.edit_message_text("Коллекция сбежала, попробуй заново.")
        return
    if 0 <= new_idx < len(state["card_ids"]):
        state["index"] = new_idx
    await show_collection_card(query, context, user_id)

async def handle_collection_spray(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data  # coll_spray_{card_id}_{index}
    _, _, card_id_str, idx_str = data.split("_")
    card_id = int(card_id_str)
    qty = get_card_quantity(user_id, card_id)
    if qty <= 1:
        await query.answer("Единственный экземпляр, малой. Я тебе его пальну? Не, не пойдёт.", show_alert=True)
        return
    reward = remove_one_card(user_id, card_id)
    if reward:

        reward = remove_one_card(user_id, card_id)
        if reward:
            add_coins(user_id, reward)
            # бонус кэшбэка
            exp, lvl = get_user_exp(user_id)
            if lvl >= 4:
                add_coins(user_id, 1)
                await query.answer(f"Ну, с дымком. Держи {reward} монет + 1 кэшбэк.")
            else:
                add_coins(user_id, reward)
                await query.answer(f"Ну, с дымком. Держи свои {reward} монет.", show_alert=True)
        # Если после распыления карта кончилась совсем, убираем её из card_ids
        new_qty = get_card_quantity(user_id, card_id)
        state = collection_state.get(user_id)
        if state:
            if new_qty == 0:
                # удаляем card_id из списка
                if card_id in state["card_ids"]:
                    state["card_ids"].remove(card_id)
                if not state["card_ids"]:
                    # редкость опустела – возвращаемся к списку редкостей
                    await collection_rarity_back(update, context)
                    return
                # корректируем индекс
                if state["index"] >= len(state["card_ids"]):
                    state["index"] = len(state["card_ids"]) - 1
                reward = remove_one_card(user_id, card_id)

            # обновляем отображение текущей карты
        await show_collection_card(query, context, user_id)

async def handle_collection_spray_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Распыляет все копии карты кроме одной."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data  # coll_sprayall_{card_id}_{index}
    _, _, card_id_str, idx_str = data.split("_")
    card_id = int(card_id_str)
    qty = get_card_quantity(user_id, card_id)
    if qty <= 1:
        await query.answer("Нечего распылять, малой.", show_alert=True)
        return
    # Оставляем 1, распыляем qty - 1
    extra = qty - 1
    # Награда за каждую распылённую карту
    card = get_card_info(card_id)
    reward = SPRAY_REWARDS.get(card["rarity"], 1) * extra
    # Удаляем extra карт, оставляем 1 (установим quantity=1)
    conn = get_conn()
    conn.execute("UPDATE user_cards SET quantity = 1 WHERE user_id = ? AND card_id = ?", (user_id, card_id))
    conn.commit()
    conn.close()
    add_coins(user_id, reward)
    await query.answer(f"Бахнул {extra} копий. Держи {reward} монет.", show_alert=True)
    # Обновляем состояние коллекции: количество копий теперь 1
    # Если сейчас просматривали эту карту, просто обновим отображение (кнопка «Распылить всё» исчезнет)
    await show_collection_card(query, context, user_id)

async def collection_rarity_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    collection_state.pop(user_id, None)  # очищаем состояние

    # Получаем текст и клавиатуру со списком редкостей
    text, markup = await build_rarity_keyboard(user_id)
    
    if text is None:
        # Если коллекция опустела, удаляем фото и шлём сообщение
        await query.message.delete()
        await context.bot.send_message(chat_id=user_id, text="Тайник опустел, малой.")
        return
    
    # Удаляем старое фото-сообщение и отправляем новое текстовое
    await query.message.delete()
    await context.bot.send_message(chat_id=user_id, text=text, reply_markup=markup)