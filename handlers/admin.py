from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS, PREMIUM_RARITY_WEIGHTS
from handlers.daily_pack import generate_standard_cards, weighted_choice, user_packs, show_pack_card
from database import add_user_card, get_card_info, get_conn
import random
from database import set_artifacts, reset_levels as db_reset_levels
from database import reset_market, reset_purchase_timer

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


async def reset_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        target_id = int(context.args[0]) if context.args else update.effective_user.id
    except:
        await update.message.reply_text("Используй: /reset_welcome <user_id>")
        return
    conn = get_conn()
    conn.execute("DELETE FROM promo_usage WHERE user_id = ? AND promo_code = 'WELCOME'", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"Промокод WELCOME для {target_id} сброшен. Теперь при /start ему снова перепадёт.")

async def force_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        target_id = int(context.args[0]) if context.args else update.effective_user.id
    except:
        await update.message.reply_text("Используй: /force_welcome <user_id>")
        return
    generate_standard_cards(target_id)   # 5 случайных карт
    add_user_card(target_id, 16)         # легендарка "Алхимический Сосуд"
    await update.message.reply_text(f"Стандартный пак и легендарка выданы {target_id} (без записи промокода).")

async def init_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    conn = get_conn()
    c = conn.cursor()
    # Очистим и вставим заново (можно заменить на INSERT OR REPLACE, если хочешь сохранять)
    c.execute("DELETE FROM products")
    products_data = [
        ("premium_1", "Мега-Бустер (1 пак)", 99, "premium", 1, "5 карт, минимум 1 редкая, повышенные шансы"),
        ("premium_5", "Мега-Бустер x5", 349, "premium", 5, "5 паков Мега-Бустер по цене 4 (скидка 30%)"),
        ("premium_10", "Мега-Бустер x10", 699, "premium", 10, "10 паков Мега-Бустер по цене 7 (скидка 30%)"),
        ("standard_1", "Стандартный пак (1 пак)", 49, "standard", 1, "5 карт, обычные шансы"),
        ("standard_5", "Стандартный пак x5", 179, "standard", 5, "5 паков по цене 4 (скидка 25%)"),
        ("standard_10", "Стандартный пак x10", 299, "standard", 10, "10 паков по цене 6 (скидка 40%)")
    ]
    c.executemany("INSERT INTO products (id, name, price, pack_type, pack_count, description) VALUES (?,?,?,?,?,?)", products_data)
    conn.commit()
    conn.close()
    await update.message.reply_text("Таблица продуктов заполнена.")

async def admin_reset_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    reset_market()
    await update.message.reply_text("Рынок сброшен, завтра сгенерится новый.")

async def admin_reset_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        target_id = int(context.args[0])
    except:
        await update.message.reply_text("Использование: /reset_purchase <user_id>")
        return
    reset_purchase_timer(target_id)
    await update.message.reply_text(f"Таймер покупки для {target_id} сброшен.")