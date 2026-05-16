from telegram import Update
from telegram.ext import ContextTypes
from database import get_user_exp, get_artifacts
from utils.player_levels import get_level_and_progress, get_bonuses
from database import get_raid_trophies


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    exp, level = get_user_exp(user.id)
    lvl, needed, progress = get_level_and_progress(exp)
    bonuses = get_bonuses(lvl)
    artifacts = get_artifacts(user.id)
    trophies = get_raid_trophies(user.id)

    text = f"🎖 Профиль игрока\n\n"
    text += f"Уровень: {lvl}\n"
    text += f"Опыт: {exp} / {needed}\n\n"
    text += "⚡ Бонусы уровня:\n"
    text += f"• Сила отряда: +{bonuses['power_bonus']}%\n"
    if bonuses['rare_boost'] > 0:
        text += f"• Шанс редкой карты в бесплатном паке: +{bonuses['rare_boost']}%\n"
    text += f"• Кэшбэк при распылении: {bonuses['cashback']} монет\n"
    text += f"• Скидка на премиум-пак: {bonuses['premium_discount']}%\n"
    text += f"\n💎 Артефакты: {artifacts} шт."
    text += f"\n🏅 Трофеи облав: {trophies} шт."
    await update.message.reply_text(text)