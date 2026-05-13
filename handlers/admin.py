from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS, PREMIUM_RARITY_WEIGHTS
from handlers.daily_pack import weighted_choice, user_packs, show_pack_card
from database import add_user_card, get_card_info, get_conn
import random
from database import set_artifacts, reset_levels as db_reset_levels

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /approve <user_id> — только для админов."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Не, малой, ты не главный.")
        return
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /approve <user_id>")
        return

    # Генерация 5 карт с гарантией минимум 1 редкая
    cards_generated = []
    # Сначала гарантированная редкая
    rare_ids = [row["id"] for row in get_conn().execute("SELECT id FROM cards WHERE rarity = 'rare' AND id != 99").fetchall()]
    if rare_ids:
        cards_generated.append(random.choice(rare_ids))
    else:
        # fallback
        common_ids = [row["id"] for row in get_conn().execute("SELECT id FROM cards WHERE rarity = 'common' AND id != 99").fetchall()]
        cards_generated.append(random.choice(common_ids))

    # Остальные 4 карты по повышенным шансам
    for _ in range(4):
        rarity = weighted_choice(PREMIUM_RARITY_WEIGHTS)
        possible = [row["id"] for row in get_conn().execute("SELECT id FROM cards WHERE rarity = ? AND id != 99", (rarity,)).fetchall()]
        if not possible:
            # fallback to common
            possible = [row["id"] for row in get_conn().execute("SELECT id FROM cards WHERE rarity = 'common' AND id != 99").fetchall()]
        cards_generated.append(random.choice(possible))

    # Добавляем карты пользователю
    for cid in cards_generated:
        add_user_card(target_id, cid)
    cards_info = [get_card_info(cid) for cid in cards_generated]
    from image_processor import generate_card_image
    images = [generate_card_image(card) for card in cards_info]

    user_packs[target_id] = {
        "cards": cards_info,
        "images": images,
        "index": 0,
        "source": "premium"
    }

    # Отправляем сообщение целевому пользователю
    await context.bot.send_message(target_id, "Барыга: Эй, малой, бабки упали, держи премиум-пакет!")
    # Используем функцию показа пака, но нужно передать объект сообщения
    # Мы не можем вызвать show_pack_card напрямую, т.к. она ожидает update.
    # Поэтому отправляем первое фото с клавиатурой, используя метод show_pack_card через message.
    # Проще: скопируем логику отправки.
    pack = user_packs[target_id]
    idx = 0
    card = pack["cards"][idx]
    img = pack["images"][idx]
    total = len(pack["cards"])
    qty = 1  # только что добавлены
    caption = (
        f"🃏 Глянь, чо выпало!\n"
        f"СИЛА {card['strength']} | ВЫНОСЛИВОСТЬ {card['endurance']}\n"
        f"Способность: {card['ability_name']}"
    )
    keyboard = [
        [
            InlineKeyboardButton("◀️", callback_data=f"nav_pack_{idx-1}"),
            InlineKeyboardButton(f"{idx+1}/{total}", callback_data="noop"),
            InlineKeyboardButton("▶️", callback_data=f"nav_pack_{idx+1}")
        ],
        [
            InlineKeyboardButton("🔥 Распылить", callback_data=f"spray_pack_{card['id']}_{idx}"),
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    if idx == 0:
        keyboard[0][0] = InlineKeyboardButton(" ", callback_data="noop")
    if idx == total - 1:
        keyboard[0][2] = InlineKeyboardButton(" ", callback_data="noop")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_photo(chat_id=target_id, photo=img, caption=caption, reply_markup=reply_markup)

    await update.message.reply_text(f"Мега-бустер для юзера {target_id} готов.")

async def set_artifact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Не дорос.")
        return
    try:
        target_id = int(context.args[0])
        qty = int(context.args[1])
    except:
        await update.message.reply_text("Использование: /set_artifact <user_id> <quantity>")
        return
    set_artifacts(target_id, qty)
    await update.message.reply_text(f"Артефакты для {target_id} установлены в {qty}.")

async def reset_levels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Не дорос.")
        return
    try:
        target_id = int(context.args[0])
    except:
        await update.message.reply_text("Использование: /reset_levels <user_id>")
        return
    db_reset_levels(target_id)
    await update.message.reply_text(f"Прогресс уровней для {target_id} сброшен.")
    
async def add_exp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except:
        await update.message.reply_text("Используй: /add_exp <user_id> <amount>")
        return
    add_exp(target_id, amount)  # используем database.add_exp
    await update.message.reply_text(f"Добавлено {amount} EXP игроку {target_id}.")