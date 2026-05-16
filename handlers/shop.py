from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_all_products, get_product, add_pending_payment, get_user_exp
from config import YOO_MONEY_WALLET, PRODUCT_PRICES
from yoomoney import Quickpay
import datetime

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсальный вход в магазин (выбор типа пака)."""
    query = update.callback_query if hasattr(update, 'callback_query') else None
    if query:
        await query.answer()
        target = query.message
        user_id = query.from_user.id
    else:
        target = update.message
        user_id = update.effective_user.id

    products = get_all_products()
    keyboard = []
    for p in products:
        btn_text = f"{p['name']} — {p['price']}₽"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"shop_product_{p['id']}")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await target.reply_text("Выбирай товар, малой:", reply_markup=reply_markup)

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Извлекаем product_id из callback_data "shop_product_<id>"
    # Пример: data = "shop_product_premium_1"
    data = query.data
    product_id = data.replace("shop_product_", "", 1)
    import sqlite3
    conn = sqlite3.connect("cards.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name FROM products").fetchall()
    conn.close()
    print("Все товары в БД:")
    for r in rows:
        print(r["id"], r["name"])
    print(f"DEBUG show_product: callback_data={query.data}, extracted product_id={product_id}")  # временно
    product = get_product(product_id)
    if not product:
        await query.edit_message_text(f"Товар не найден: {product_id}")
        return

    if not product:
        await query.edit_message_text("Товар не найден.")
        return

    # Проверка скидки за уровень (для premium_1)
    user_id = query.from_user.id
    exp, lvl = get_user_exp(user_id)
    price = product["price"]
    if product_id == "premium_1" and lvl >= 5:
        price = 79

    description = product["description"]
    text = (
        f"📦 {product['name']}\n"
        f"Цена: {price}₽\n"
        f"Состав: {product['pack_count']} пак(ов) по 5 карт\n"
        f"Описание: {description}\n\n"
        f"Нажми «Оплатить», чтобы получить ссылку."
    )
    keyboard = [
        [InlineKeyboardButton(f"💳 Оплатить {price}₽", callback_data=f"shop_buy_{product_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="shop_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = query.data.replace("shop_buy_", "", 1)
    print(product_id + " show")
    product = get_product(product_id)
    if not product:
        await query.edit_message_text("Товар не найден.")
        return

    user_id = query.from_user.id
    exp, lvl = get_user_exp(user_id)
    price = product["price"]
    if product_id == "premium_1" and lvl >= 5:
        price = 79

    # Создаём платёж
    code = f"shop_{user_id}_{product_id}_{int(datetime.datetime.now().timestamp())}"
    add_pending_payment(user_id, code, pack_type=product["pack_type"], pack_count=product["pack_count"])

    quickpay = Quickpay(
        receiver=YOO_MONEY_WALLET,
        quickpay_form="shop",
        targets=product["name"],
        paymentType="SB",
        sum=price,
        label=code,
        successURL="https://t.me/your_bot?start=success"
    )
    payment_url = quickpay.base_url

    keyboard = [[InlineKeyboardButton("💳 Перейти к оплате", url=payment_url)]]
    await query.edit_message_text(
        f"Оплати {price}₽ по ссылке. Как только деньги упадут, получишь {product['pack_count']} пак(ов).",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def shop_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await shop_menu(update, context)