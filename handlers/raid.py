import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from database import (get_user_collection, get_card_info, get_user, get_user_exp,
                      get_enemies, get_user_raid_info, use_raid_attempt, add_exp_and_coins, add_raid_trophy,
                      lose_card, get_raid_trophies)
from image_processor import generate_card_image
from config import ADMIN_IDS

RARITY_MULT = {"common": 1.0, "rare": 1.2, "epic": 1.5, "legendary": 2.0, "mythic": 3.0}
raid_state = {}

def card_battle_power(card):
    rarity = card["rarity"]
    return (card["strength"] * 2 + card["endurance"]) * RARITY_MULT.get(rarity, 1.0)

from telegram import ReplyKeyboardMarkup  # добавь в импорты, если ещё нет

async def raid_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Проверяем попытки только для обычных игроков
    if user.id not in ADMIN_IDS:
        attempts, _ = get_user_raid_info(user.id)
        if attempts <= 0:
            await update.message.reply_text("Ты исчерпал попытки на сегодня, малой. Приходи завтра.")
            return

    # Показываем обучение / предупреждение
    intro_text = (
        "🌪️ *Облава* — это три волны врагов.\n"
        "Ты соберёшь отряд из 5 карт. В каждой волне случайно выбранная карта из отряда сразится с врагом.\n\n"
        "🎲 Исход битвы не гарантирован! Шанс победить считается так:\n"
        "_твоя сила / (твоя сила + сила врага)_.\n"
        "Даже слабая карта может выиграть, а сильная — продуть.\n\n"
        "⚠️ *Если проиграешь бой — выбранная карта будет уничтожена и исчезнет из коллекции.*\n"
        "Можно сбежать после любой волны и сохранить награду.\n\n"
        "Готов рискнуть?"
    )
    keyboard = [
        [InlineKeyboardButton("⚔️ Продолжить", callback_data="raid_confirm_intro"),
         InlineKeyboardButton("🏃 Уйти", callback_data="raid_cancel_intro")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(intro_text, parse_mode="Markdown", reply_markup=reply_markup)

async def raid_confirm_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Проверяем, что есть минимум 5 разных карт
    collection = get_user_collection(user_id)
    unique_cards = list(set(card_id for card_id, _ in collection))
    if len(unique_cards) < 5:
        await query.edit_message_text("У тебя меньше 5 разных карт, малой. Собери больше.")
        return

    # Инициализируем состояние выбора отряда
    context.user_data["raid_select"] = {
        "selected": set(),
        "cards": unique_cards,
        "index": 0
    }
    # Удаляем сообщение с обучением
    await query.message.delete()
    # Показываем первую карту для выбора
    await show_raid_card_selection(query, context, user_id, edit=False)  # send new message

async def raid_cancel_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Удаляем сообщение с обучением
    await query.message.delete()
    # Отправляем главное меню (как при /start)
    keyboard = [
        ["🆓 Ежедневный пак", "📦 Коллекция", "🔨 Крафт"],
        ["🃏 Стандартный пак", "💎 Премиум пак", "⚔️ Сюжетка"],
        ["👤 Профиль", "🌪️ Облава"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await context.bot.send_message(chat_id=query.from_user.id, text="Барыга ждёт. Выбирай.", reply_markup=reply_markup)

async def raid_confirm_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    collection = get_user_collection(user_id)
    unique_cards = list(set(card_id for card_id, _ in collection))
    if len(unique_cards) < 5:
        await query.edit_message_text("У тебя меньше 5 разных карт, собери больше.")
        return

    context.user_data["raid_select"] = {
        "selected": set(),
        "cards": unique_cards,
        "index": 0
    }
    
    await query.message.delete()
    await show_raid_card_selection(await context.bot.send_message(user_id, "Загрузка..."), context, user_id, edit=False)

async def show_raid_card_selection(target, context, user_id, edit=False):
    """
    target: либо объект Message (при первом вызове из reply), либо CallbackQuery (при навигации/выборе).
    Если edit=True, редактируем сообщение. Если edit=False, отправляем новое.
    """
    state = context.user_data.get("raid_select")
    if not state:
        return
    cards = state["cards"]
    idx = state["index"]
    if idx >= len(cards):
        idx = len(cards) - 1
        state["index"] = idx
    card_id = cards[idx]
    card = get_card_info(card_id)
    if card is None:
        if edit:
            await target.edit_message_text("Карта пропала.")
        else:
            await target.reply_text("Карта пропала.")
        return

    power = card_battle_power(card)
    selected = state["selected"]
    is_selected = card_id in selected
    toggle_text = "✅ Убрать" if is_selected else "➕ Выбрать"

    caption = (
        f"Собери отряд для облавы (выбрано {len(selected)}/5)\n\n"
        f"{card['name']} ({card['rarity']})\nБоевая сила: {power:.1f}"
    )

    img = generate_card_image(card)
    img.seek(0)

    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"raid_sel_nav_{idx-1}"))
    else:
        nav.append(InlineKeyboardButton(" ", callback_data="noop"))
    nav.append(InlineKeyboardButton(f"{idx+1}/{len(cards)}", callback_data="noop"))
    if idx < len(cards) - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"raid_sel_nav_{idx+1}"))
    else:
        nav.append(InlineKeyboardButton(" ", callback_data="noop"))

    keyboard = [nav]
    keyboard.append([InlineKeyboardButton(toggle_text, callback_data=f"raid_sel_toggle_{card_id}")])
    if len(selected) == 5:
        keyboard.append([InlineKeyboardButton("⚔️ Начать облаву!", callback_data="raid_start")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="raid_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit and hasattr(target, 'edit_message_media'):
        # target is CallbackQuery
        await target.edit_message_media(
            media=InputMediaPhoto(media=img, caption=caption),
            reply_markup=reply_markup
        )
    else:
        # target is Message, отправляем новое фото
        await target.reply_photo(photo=img, caption=caption, reply_markup=reply_markup)

# Обработчики навигации и выбора
async def raid_sel_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    new_idx = int(query.data.split("_")[-1])
    state = context.user_data.get("raid_select")
    if state and 0 <= new_idx < len(state["cards"]):
        state["index"] = new_idx
    await show_raid_card_selection(query, context, query.from_user.id, edit=True)

async def raid_sel_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    card_id = int(query.data.split("_")[-1])
    state = context.user_data.get("raid_select")
    if not state:
        return
    if card_id in state["selected"]:
        state["selected"].remove(card_id)
    else:
        if len(state["selected"]) >= 5:
            await query.answer("Отряд полон, убери одну карту.")
            return
        state["selected"].add(card_id)
    await show_raid_card_selection(query, context, query.from_user.id, edit=True)

async def raid_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = context.user_data.get("raid_select")
    if not state or len(state["selected"]) != 5:
        await query.edit_message_text("Отряд не собран.")
        return
    squad = list(state["selected"])
    # Тратим попытку только для обычных игроков
    if user_id not in ADMIN_IDS:
        use_raid_attempt(user_id)
    raid_state[user_id] = {
        "squad": squad.copy(),
        "available": squad.copy(),
        "wave": 1,
        "wins": 0
    }
    await query.message.delete()
    await start_next_wave(user_id, context)

async def start_next_wave(user_id, context):
    state = raid_state.get(user_id)
    if not state:
        return
    if not state["available"]:
        await context.bot.send_message(user_id, "Твой отряд исчерпан. Облава провалена.")
        del raid_state[user_id]
        return

    chosen_card_id = random.choice(state["available"])
    card = get_card_info(chosen_card_id)
    if not card:
        await context.bot.send_message(user_id, "Ошибка, карта не найдена.")
        del raid_state[user_id]
        return

    squad_power = [card_battle_power(get_card_info(cid)) for cid in state["squad"]]
    avg_power = sum(squad_power) / len(squad_power) if squad_power else 10
    multipliers = {1: 0.8, 2: 1.1, 3: 1.4}
    multiplier = multipliers.get(state["wave"], 1.0)
    enemy_power = avg_power * multiplier

    enemies = get_enemies()
    enemy_name = random.choice(enemies)["name"] if enemies else "Безымянный враг"

    state["current_card"] = chosen_card_id
    state["enemy_name"] = enemy_name
    state["enemy_power"] = enemy_power

    card_power = card_battle_power(card)
    message_text = (
        f"⚡ Волна {state['wave']}\n"
        f"На тебя выходит {enemy_name} (Сила: {enemy_power:.1f})\n"
        f"Твоя карта: {card['name']} (Сила: {card_power:.1f})\n\n"
        f"Атакуешь или валишь?"
    )
    keyboard = [
        [InlineKeyboardButton("⚔️ Атаковать", callback_data="raid_fight"),
         InlineKeyboardButton("🏃 Свалить", callback_data="raid_retreat")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(user_id, message_text, reply_markup=reply_markup)

async def raid_fight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = raid_state.get(user_id)
    if not state:
        await query.edit_message_text("Облава уже завершена.")
        return

    card_id = state["current_card"]
    card = get_card_info(card_id)
    if not card:
        await query.edit_message_text("Ошибка.")
        return
    card_power = card_battle_power(card)
    enemy_power = state["enemy_power"]

    # Вероятность победы игрока
    win_prob = card_power / (card_power + enemy_power)
    roll = random.random()
    won = roll < win_prob

    # Убираем карту из доступных в любом случае
    state["available"].remove(card_id)

    if won:
        state["wins"] += 1
        win_chance = win_prob * 100
        if state["wave"] == 3:
            exp = 30
            coins = 20
            add_exp_and_coins(user_id, exp, coins)
            add_raid_trophy(user_id)
            await query.edit_message_text(
                f"🎉 Победа! Твоя карта {card['name']} одолела {state['enemy_name']}.\n"
                f"Шанс на победу был: {win_chance:.1f}%\n"
                f"🏆 Облава завершена!\n"
                f"Награда: +{exp} EXP, +{coins}💰, 🏅 Трофей Облавы."
            )
            del raid_state[user_id]
        else:
            state["wave"] += 1
            await query.edit_message_text(
                f"✅ Ты победил! {card['name']} справился с {state['enemy_name']}.\n"
                f"Шанс был: {win_chance:.1f}%\n"
                f"Готовься к следующей волне."
            )
            await start_next_wave(user_id, context)
    else:
        # Поражение, карта теряется
        lose_card(user_id, card_id)  # используем новую функцию из database
        lose_chance = (1 - win_prob) * 100
        await query.edit_message_text(
            f"💀 Ты проиграл! {card['name']} не справился с {state['enemy_name']}.\n"
            f"Шанс на победу был: {win_prob*100:.1f}%\n"
            f"Карта {card['name']} уничтожена."
        )
        del raid_state[user_id]

async def raid_retreat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = raid_state.get(user_id)
    if not state:
        await query.edit_message_text("Облава уже завершена.")
        return

    wins = state["wins"]
    if wins == 0:
        exp, coins = 0, 0
    elif wins == 1:
        exp, coins = 10, 5
    else:
        exp, coins = 20, 10

    if exp > 0:
        add_exp_and_coins(user_id, exp, coins)
    await query.edit_message_text(
        f"Ты свалил после {wins} волн. Получено: +{exp} EXP, +{coins}💰."
    )
    del raid_state[user_id]

async def raid_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("raid_select", None)
    await query.message.delete()
    await context.bot.send_message(query.from_user.id, "Облава отменена.")

async def raid_cancel_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Облава отменена. Заходи, когда решишься.")