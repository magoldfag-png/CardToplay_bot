import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from database import (get_user_collection, get_card_info, get_user_level_wins,
                      record_win, add_exp_and_coins, add_artifact,
                      get_user, get_level, get_all_levels, get_user_exp)
from image_processor import generate_card_image
from utils.player_levels import check_level_up, get_power_multiplier

RARITY_MULT = {"common": 1.0, "rare": 1.2, "epic": 1.5, "legendary": 2.0, "mythic": 3.0}

# Состояние выбора карт для битвы: user_id -> {"level_id": int, "selected": set, "cards": list[card_id], "index": int}
campaign_select = {}

def card_battle_power(card):
    """Вычисляет боевую силу карты."""
    rarity = card["rarity"]
    return (card["strength"] * 2 + card["endurance"]) * RARITY_MULT.get(rarity, 1.0)


async def campaign_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список уровней."""
    levels = get_all_levels()
    user_id = update.effective_user.id
    text = "Выбери уровень:\n\n"
    keyboard = []
    for lvl in levels:
        wins = get_user_level_wins(user_id, lvl["id"])
        text += f"• {lvl['name']} (сила {lvl['power']}) — пройдено {wins} раз\n"
        keyboard.append([InlineKeyboardButton(lvl['name'], callback_data=f"campaign_select_{lvl['id']}")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def select_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает выбор отряда для уровня."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    level_id = int(query.data.split("_")[-1])
    collection = get_user_collection(user_id)
    unique_cards = list(set(card_id for card_id, _ in collection))
    if len(unique_cards) < 5:
        await query.edit_message_text("У тебя меньше 5 разных карт, малой. Собери больше.")
        return

    campaign_select[user_id] = {
        "level_id": level_id,
        "selected": set(),
        "cards": unique_cards,
        "index": 0
    }
    await show_card_selection(query, context, user_id)


async def show_card_selection(query, context, user_id):
    """Отображает одну карту с возможностью выбора."""
    state = campaign_select.get(user_id)
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
        await query.edit_message_text("Карта исчезла, начни заново.")
        return

    power = card_battle_power(card)
    selected = state["selected"]
    is_selected = card_id in selected
    toggle_text = "✅ Убрать" if is_selected else "➕ Выбрать"

    caption = (
        f"Выбор отряда (выбрано {len(selected)}/5)\n\n"
        f"{card['name']} ({card['rarity']})\n"
        f"Боевая сила: {power:.1f}\n"
        f"СИЛА {card['strength']} | ВЫН. {card['endurance']}"
    )

    img = generate_card_image(card)
    img.seek(0)

    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"battle_nav_{idx-1}"))
    else:
        nav.append(InlineKeyboardButton(" ", callback_data="noop"))
    nav.append(InlineKeyboardButton(f"{idx+1}/{len(cards)}", callback_data="noop"))
    if idx < len(cards) - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"battle_nav_{idx+1}"))
    else:
        nav.append(InlineKeyboardButton(" ", callback_data="noop"))

    keyboard = [nav]
    keyboard.append([InlineKeyboardButton(toggle_text, callback_data=f"battle_toggle_{card_id}")])
    if len(selected) == 5:
        keyboard.append([InlineKeyboardButton("⚔️ В БОЙ!", callback_data="battle_fight")])
    keyboard.append([InlineKeyboardButton("🔙 Назад к уровням", callback_data="battle_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_media(
        media=InputMediaPhoto(media=img, caption=caption),
        reply_markup=reply_markup
    )


async def navigate_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = campaign_select.get(user_id)
    if not state:
        await query.edit_message_text("Выбор карт сброшен.")
        return
    new_idx = int(query.data.split("_")[-1])
    if 0 <= new_idx < len(state["cards"]):
        state["index"] = new_idx
    await show_card_selection(query, context, user_id)


async def toggle_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = campaign_select.get(user_id)
    if not state:
        return
    card_id = int(query.data.split("_")[-1])
    if card_id in state["selected"]:
        state["selected"].remove(card_id)
    else:
        if len(state["selected"]) >= 5:
            await query.answer("Сначала отмени одну из выбранных карт.")
            return
        state["selected"].add(card_id)
    await show_card_selection(query, context, user_id)


async def fight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = campaign_select.pop(user_id, None)
    if not state or len(state["selected"]) != 5:
        await query.edit_message_text("Отряд не готов.")
        return

    level = get_level(state["level_id"])
    if not level:
        await query.edit_message_text("Уровень не найден.")
        return

    # Подсчёт базовой силы отряда
    total_power = 0.0
    cards_info = []
    for card_id in state["selected"]:
        card = get_card_info(card_id)
        if card:
            total_power += card_battle_power(card)
            cards_info.append(card)

    # Учитываем бонус уровня игрока
    _, player_level = get_user_exp(user_id)
    multiplier = get_power_multiplier(player_level)
    total_power *= multiplier

    victory = total_power >= level["power"]

    result_text = ""
    if victory:
        # Награды
        wins = get_user_level_wins(user_id, level["id"]) + 1  # включая текущую победу
        if wins == 1:
            exp = level["reward_exp_first"]
            coins = level["reward_coins_first"]
        elif wins == 2:
            exp = level["reward_exp_first"] // 2
            coins = level["reward_coins_first"] // 2
        elif wins == 3:
            exp = level["reward_exp_first"] // 4
            coins = level["reward_coins_first"] // 4
        else:
            exp = 3
            coins = 1

        add_exp_and_coins(user_id, exp, coins)
        record_win(user_id, level["id"])
        await check_level_up(user_id, context)

        result_text = (
            f"🏆 Победа! Сила твоего отряда: {total_power:.1f} против {level['power']}.\n"
            f"Награда: +{exp} EXP, +{coins}💰"
        )

        # Артефакт на уровнях 4-5
        if level["id"] in [4, 5] and random.random() < level["artifact_chance"]:
            add_artifact(user_id)
            result_text += "\n\n🔥 Ты нашёл АРТЕФАКТ! Барыга щедро обменяет его на редкую карту."
    else:
        result_text = f"💀 Поражение... Сила {total_power:.1f} меньше {level['power']}. Тренируйся."

    await query.message.delete()
    await context.bot.send_message(chat_id=user_id, text=result_text)


async def campaign_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    campaign_select.pop(user_id, None)

    levels = get_all_levels()
    text = "Выбери уровень:\n\n"
    keyboard = []
    for lvl in levels:
        wins = get_user_level_wins(user_id, lvl["id"])
        text += f"• {lvl['name']} (сила {lvl['power']}) — пройдено {wins} раз\n"
        keyboard.append([InlineKeyboardButton(lvl['name'], callback_data=f"campaign_select_{lvl['id']}")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.delete()
    await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)