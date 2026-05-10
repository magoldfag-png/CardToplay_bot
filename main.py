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
from handlers.premium import premium_button
from handlers.admin import approve
from handlers.craft import craft_menu, craft_card_menu, craft_card, craft_buy_pack, craft_menu_back
import logging
from telegram.ext import Application
from telegram.error import NetworkError, TelegramError
from database import sync_cards_from_json
from handlers.premium import check_payment_and_deliver
from handlers.premium import premium_button, standard_pack_button

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, NetworkError):
        logger.warning(f"Сетевая ошибка: {context.error}")
    elif isinstance(context.error, TelegramError):
        logger.error(f"Ошибка Telegram: {context.error}")
    else:
        logger.error(f"Неизвестная ошибка: {context.error}", exc_info=context.error)
def main():
    init_db()
    sync_cards_from_json()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(error_handler)
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.job_queue.run_repeating(check_payment_and_deliver, interval=30, first=10)

    # Кнопки главного меню (ReplyKeyboard)
    app.add_handler(MessageHandler(filters.Regex("^🆓 Ежедневный пак$"), daily_pack_button))
    app.add_handler(MessageHandler(filters.Regex("^📦 Коллекция$"), collection_button))
    app.add_handler(MessageHandler(filters.Regex("^💎 Премиум пак$"), premium_button))
    app.add_handler(MessageHandler(filters.Regex("^🔨 Крафт$"), craft_menu))
    app.add_handler(MessageHandler(filters.Regex("^💎 Премиум пак$"), premium_button))
    app.add_handler(MessageHandler(filters.Regex("^🃏 Стандартный пак$"), standard_pack_button))

    # Callback-запросы крафта (важен порядок)
    app.add_handler(CallbackQueryHandler(craft_card_menu, pattern="^craft_card_menu$"))
    app.add_handler(CallbackQueryHandler(craft_card, pattern="^craft_(common|rare|epic|legendary|mythic)$"))    
    app.add_handler(CallbackQueryHandler(craft_buy_pack, pattern="^craft_buy_pack$"))
    app.add_handler(CallbackQueryHandler(craft_menu_back, pattern="^craft_menu_back$"))
    # Callback-запросы
    app.add_handler(CallbackQueryHandler(handle_pack_navigation, pattern="^nav_pack_"))
    app.add_handler(CallbackQueryHandler(handle_collection_navigation, pattern="^coll_nav_"))
    app.add_handler(CallbackQueryHandler(handle_collection_spray_all, pattern="^coll_sprayall_"))
    app.add_handler(CallbackQueryHandler(handle_collection_spray, pattern="^coll_spray_(?!all)"))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(collection_rarity_menu, pattern="^coll_rarity_"))
    app.add_handler(CallbackQueryHandler(collection_rarity_back, pattern="^coll_rarity_back$"))


    # Заглушка для noop
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))

    app.run_polling()

async def main_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    # Удаляем клавиатуру и возвращаем к обычной клавиатуре
    await query.delete_message()
    # Отправляем короткое сообщение с главным меню
    keyboard = [
        ["🆓 Ежедневный пак", "📦 Коллекция", "🔨 Крафт"],
        ["🃏 Стандартный пак", "💎 Премиум пак"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await context.bot.send_message(chat_id=query.from_user.id, text="Барыга снова в деле. Выбирай.", reply_markup=reply_markup)

async def noop_callback(update, context):
    await update.callback_query.answer()

if __name__ == "__main__":
    main()