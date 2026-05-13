# utils/player_levels.py
from database import get_user_exp, set_user_level
import logging

logger = logging.getLogger(__name__)

async def check_level_up(user_id, context):
    """Проверяет, не повысился ли уровень. Если да — уведомляет."""
    exp, old_level = get_user_exp(user_id)  # old_level пока старый, но мы прочитали актуальный?
    # get_user_exp теперь возвращает exp и level из БД, но после add_exp уровень ещё не обновлён.
    # Поэтому мы должны получить текущий exp, вычислить новый уровень, сравнить с сохранённым в БД,
    # и если изменился — обновить и отправить сообщение.
    
    # Прочитаем актуальный exp и level
    from database import get_conn  # избегаем циклических импортов
    conn = get_conn()
    row = conn.execute("SELECT exp, level FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return
    exp = row["exp"]
    old_level = row["level"]
    new_level, _, _ = get_level_and_progress(exp)
    if new_level > old_level:
        set_user_level(user_id, new_level)
        bonuses = get_bonuses(new_level)
        power_bonus = bonuses["power_bonus"]
        # отправляем уведомление
        try:
            await context.bot.send_message(
                user_id,
                f"Опа! Ты теперь малый {new_level} уровня. Сила отряда выросла на {power_bonus}%, уважаю."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о повышении уровня: {e}")
            
LEVEL_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 250,
    4: 500,
    5: 800
}

def get_level_and_progress(exp):
    """
    Возвращает (текущий уровень, опыт до следующего уровня, процент).
    """
    if exp >= 800:
        return 5, 800, 100.0
    if exp >= 500:
        lvl = 4
        needed = 800
    elif exp >= 250:
        lvl = 3
        needed = 500
    elif exp >= 100:
        lvl = 2
        needed = 250
    else:
        lvl = 1
        needed = 100
    progress = int(exp)
    return lvl, needed, min(100.0, round(exp / needed * 100, 1))

def get_bonuses(level):
    bonuses = {
        "power_bonus": 0,
        "rare_boost": 0,
        "cashback": 0,
        "premium_discount": 0
    }
    if level >= 2:
        bonuses["power_bonus"] = 15
    if level >= 3:
        bonuses["power_bonus"] = 30
        bonuses["rare_boost"] = 5
    if level >= 4:
        bonuses["power_bonus"] = 45
        bonuses["cashback"] = 1
    if level >= 5:
        bonuses["power_bonus"] = 60
        bonuses["premium_discount"] = 20
    return bonuses

def get_power_multiplier(level):
    return 1 + (level - 1) * 0.15