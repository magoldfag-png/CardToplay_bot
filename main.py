import subprocess
import sys

def install_requirements():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
from handlers.promo import promo_pika
from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from config import BOT_TOKEN
from database import init_db
from handlers.start import start
from handlers.daily_pack import daily_pack_button, handle_pack_navigation, handle_spray_from_pack
from handlers.collection import (
    collection_button,
    collection_rarity_menu,
    handle_collection_navigation,
    handle_collection_spray,
    handle_collection_spray_all,
    collection_rarity_back,
)
from handlers.shop import shop_menu, show_product, buy_product, shop_back
from handlers.raid import (
    raid_button, raid_cancel_intro, raid_confirm_intro, raid_sel_nav, raid_sel_toggle, raid_start,
    raid_fight, raid_retreat, raid_cancel
)
from handlers.battle import (
    campaign_button,
    select_level,
    navigate_cards,
    toggle_card,
    fight,
    campaign_back
)
from telegram.ext import TypeHandler
from telegram import Update
from database import update_activity
from handlers.profile import profile_command
from handlers.start import start, open_welcome_pack
from handlers.admin import admin_reset_market, admin_reset_purchase, approve, init_products
from handlers.craft import craft_menu, craft_card_menu, craft_card, craft_buy_pack, craft_menu_back
import logging
from telegram.ext import Application
from telegram.error import NetworkError, TelegramError
from database import sync_cards_from_json
from handlers.premium import check_payment_and_deliver
from handlers.admin import approve, force_welcome, reset_welcome, set_artifact, reset_levels  # admin.py дополнить
from handlers.reminders import send_reminders, reminder_daily_pack
from handlers.market import (market_button, sell_menu, sell_item_handler,
                             buy_menu, buy_card_handler, market_back)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from telegram.error import BadRequest, NetworkError, TelegramError
import logging


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, BadRequest):
        logger.error(f"Некорректный запрос: {err}")
        # Дополнительно можно вывести update, чтобы понять, где случилось
        logger.error(f"Update: {update}")
    elif isinstance(err, NetworkError):
        logger.warning(f"Сетевая ошибка: {err}")
    elif isinstance(err, TelegramError):
        logger.error(f"Ошибка Telegram: {err}")
    else:
        logger.error(f"Неизвестная ошибка: {err}", exc_info=err)


def main():
    init_db()
    sync_cards_from_json()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(error_handler)
    async def activity_updater(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user:
            update_activity(user.id)

    app.add_handler(TypeHandler(Update, activity_updater), group=-1)

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.job_queue.run_repeating(check_payment_and_deliver, interval=30, first=10)
    app.add_handler(MessageHandler(filters.Regex(r'^PIKA$'), promo_pika))
    app.job_queue.run_repeating(send_reminders, interval=3600, first=10)  # каждый час
    app.add_handler(CallbackQueryHandler(reminder_daily_pack, pattern='^daily_pack_reminder$'))
    app.add_handler(MessageHandler(filters.Regex("^💎 Премиум пак$"), shop_menu))
    app.add_handler(CallbackQueryHandler(show_product, pattern='^shop_product_'))
    app.add_handler(CallbackQueryHandler(buy_product, pattern='^shop_buy_'))
    app.add_handler(CallbackQueryHandler(shop_back, pattern='^shop_back$'))
    app.add_handler(CommandHandler("reset_market", admin_reset_market))
    app.add_handler(CommandHandler("reset_purchase", admin_reset_purchase))
    # Кнопки главного меню (ReplyKeyboard)
    app.add_handler(MessageHandler(filters.Regex("^🆓 Ежедневный пак$"), daily_pack_button))
    app.add_handler(MessageHandler(filters.Regex("^📦 Коллекция$"), collection_button))
    app.add_handler(MessageHandler(filters.Regex("^🔨 Крафт$"), craft_menu))
    app.add_handler(CallbackQueryHandler(open_welcome_pack, pattern="^open_welcome_pack$"))
    # Callback-запросы крафта (важен порядок)
    app.add_handler(CallbackQueryHandler(craft_card_menu, pattern="^craft_card_menu$"))
    app.add_handler(CallbackQueryHandler(craft_card, pattern="^craft_(common|rare|epic|legendary|mythic)$"))    
    app.add_handler(CallbackQueryHandler(craft_buy_pack, pattern="^craft_buy_pack$"))
    app.add_handler(CallbackQueryHandler(craft_menu_back, pattern="^craft_menu_back$"))
    # Callback-запросы
    app.add_handler(CommandHandler("init_products", init_products))
    app.add_handler(CallbackQueryHandler(collection_rarity_back, pattern="^coll_rarity_back$"))
    app.add_handler(MessageHandler(filters.Regex("^💰 Рынок$"), market_button))
    app.add_handler(CallbackQueryHandler(sell_menu, pattern="^market_sell_menu$"))
    app.add_handler(CallbackQueryHandler(sell_item_handler, pattern="^market_sell_artifact$"))
    app.add_handler(CallbackQueryHandler(sell_item_handler, pattern="^market_sell_trophy$"))
    app.add_handler(CallbackQueryHandler(buy_menu, pattern="^market_buy_menu$"))
    app.add_handler(CallbackQueryHandler(buy_card_handler, pattern=r"^market_buy_\d+$"))
    app.add_handler(CallbackQueryHandler(market_back, pattern="^market_back$"))
    app.add_handler(CallbackQueryHandler(handle_pack_navigation, pattern="^nav_pack_"))
    app.add_handler(CallbackQueryHandler(handle_collection_navigation, pattern="^coll_nav_"))
    app.add_handler(CallbackQueryHandler(handle_collection_spray_all, pattern="^coll_sprayall_"))
    app.add_handler(CallbackQueryHandler(handle_collection_spray, pattern="^coll_spray_(?!all)"))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(collection_rarity_menu, pattern="^coll_rarity_"))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("set_artifact", set_artifact))
    app.add_handler(CommandHandler("reset_levels", reset_levels))
    app.add_handler(MessageHandler(filters.Regex("^⚔️ Сюжетка$"), campaign_button))
    app.add_handler(CallbackQueryHandler(select_level, pattern=r'^campaign_select_\d+$'))
    app.add_handler(CallbackQueryHandler(navigate_cards, pattern=r'^battle_nav_\d+$'))
    app.add_handler(CallbackQueryHandler(toggle_card, pattern=r'^battle_toggle_\d+$'))
    app.add_handler(CallbackQueryHandler(fight, pattern='^battle_fight$'))
    app.add_handler(CallbackQueryHandler(campaign_back, pattern='^battle_back$'))
    app.add_handler(MessageHandler(filters.Regex("^👤 Профиль$"), profile_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("reset_welcome", reset_welcome))
    app.add_handler(CommandHandler("force_welcome", force_welcome))
    app.add_handler(MessageHandler(filters.Regex("^🌪️ Облава$"), raid_button))
    app.add_handler(CallbackQueryHandler(raid_sel_nav, pattern=r'^raid_sel_nav_\d+$'))
    app.add_handler(CallbackQueryHandler(raid_sel_toggle, pattern=r'^raid_sel_toggle_\d+$'))
    app.add_handler(CallbackQueryHandler(raid_start, pattern='^raid_start$'))
    app.add_handler(CallbackQueryHandler(raid_fight, pattern='^raid_fight$'))
    app.add_handler(CallbackQueryHandler(raid_retreat, pattern='^raid_retreat$'))
    app.add_handler(CallbackQueryHandler(raid_cancel, pattern='^raid_cancel$'))
    app.add_handler(CallbackQueryHandler(raid_confirm_intro, pattern='^raid_confirm_intro$'))
    app.add_handler(CallbackQueryHandler(raid_cancel_intro, pattern='^raid_cancel_intro$'))
    # Заглушка для noop
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))

    app.run_polling()

async def main_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    # Удаляем клавиатуру и возвращаем к обычной клавиатуре
    await query.delete_message()
    keyboard = [
        ["🆓 Ежедневный пак", "📦 Коллекция", "🔨 Крафт"],
        ["💎 Премиум пак", "⚔️ Сюжетка"],
        ["👤 Профиль", "🌪️ Облава", "💰 Рынок"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await context.bot.send_message(chat_id=query.from_user.id, text="Барыга снова в деле. Выбирай.", reply_markup=reply_markup)

async def noop_callback(update, context):
    await update.callback_query.answer()

if __name__ == "__main__":
    main()