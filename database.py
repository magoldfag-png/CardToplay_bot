import sqlite3
import json
from datetime import datetime
from config import DB_PATH, CARDS_JSON, SPRAY_REWARDS

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Создаёт таблицы, если их нет, и загружает карты из cards.json."""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    rarity TEXT,
                    strength INTEGER,
                    endurance INTEGER,
                    ability_name TEXT,
                    ability_description TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    registered_date TEXT,
                    last_free_pack_time TEXT,
                    coins INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_cards (
                    user_id INTEGER,
                    card_id INTEGER,
                    quantity INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, card_id)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pending_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                payment_label TEXT UNIQUE,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_usage (
                user_id INTEGER,
                promo_code TEXT,
                used_at TEXT,
                PRIMARY KEY (user_id, promo_code)
            )''')
    c.execute('''CREATE TABLE IF NOT EXISTS levels (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                power INTEGER NOT NULL,
                reward_exp_first INTEGER NOT NULL,
                reward_coins_first INTEGER NOT NULL,
                artifact_chance REAL DEFAULT 0.0
            )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_levels (
                    user_id INTEGER,
                    level_id INTEGER,
                    wins_count INTEGER DEFAULT 1,
                    last_win_time TEXT,
                    PRIMARY KEY (user_id, level_id)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    registered_date TEXT,
                    last_free_pack_time TEXT,
                    coins INTEGER DEFAULT 0,
                    exp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_artifacts (
                    user_id INTEGER PRIMARY KEY,
                    quantity INTEGER DEFAULT 0
                )''')
    c.execute("SELECT COUNT(*) FROM levels")
    if c.fetchone()[0] == 0:
        # Если таблица пуста – просто вставляем
        levels_data = [
            (1, "Тёмная подворотня", 45, 60, 10, 0),
            (2, "Склад краденых коробок", 80, 100, 20, 0),
            (3, "Прокуренный офис", 120, 150, 30, 0),
            (4, "Нелегальный игорный клуб", 170, 200, 50, 0.005),
            (5, "Особняк местного авторитета", 240, 290, 100, 0.01)
        ]
        c.executemany(
            "INSERT INTO levels (id, name, power, reward_exp_first, reward_coins_first, artifact_chance) "
            "VALUES (?,?,?,?,?,?)",
            levels_data
        )
    else:
        # Если таблица уже существует – обновляем все записи (перезаписываем)
        c.execute("DELETE FROM levels")   # чистим старые, чтобы не плодить дубли
        levels_data = [
            (1, "Тёмная подворотня", 45, 60, 10, 0),
            (2, "Склад краденых коробок", 80, 100, 20, 0),
            (3, "Прокуренный офис", 120, 150, 30, 0),
            (4, "Нелегальный игорный клуб", 170, 200, 50, 0.005),
            (5, "Особняк местного авторитета", 240, 290, 100, 0.01)
        ]
        c.executemany(
            "INSERT INTO levels (id, name, power, reward_exp_first, reward_coins_first, artifact_chance) "
            "VALUES (?,?,?,?,?,?)",
            levels_data
        )
# Добавляем новые поля в users (если ещё нет)
    try:
        c.execute("ALTER TABLE users ADD COLUMN exp INTEGER DEFAULT 0")
    except:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
    except:
        pass
    # В init_db добавить:
 # Вместо простого вызова:
# c.execute("ALTER TABLE pending_payments ADD COLUMN pack_type TEXT DEFAULT 'premium'")

    # Сделай так:
    try:
        c.execute("ALTER TABLE pending_payments ADD COLUMN pack_type TEXT DEFAULT 'premium'")
    except sqlite3.OperationalError:
        pass  # колонка уже есть, всё нормально
    # Загружаем карты, если таблица пуста
    c.execute("SELECT COUNT(*) FROM cards")
    if c.fetchone()[0] == 0:
        with open(CARDS_JSON, "r", encoding="utf-8") as f:
            cards_data = json.load(f)
        for card in cards_data:
            c.execute('''INSERT OR IGNORE INTO cards (id, name, rarity, strength, endurance, ability_name, ability_description)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (card["id"], card["name"], card["rarity"],
                       card["strength"], card["endurance"],
                       card.get("ability_name", ""), card.get("ability_description", "")))
        # Добавляем карту Барыги (id=99), если её нет в JSON
        c.execute('''INSERT OR IGNORE INTO cards (id, name, rarity, strength, endurance, ability_name, ability_description)
                     VALUES (99, "Барыга", "legendary", 99, 99, "Харизма", "Забирает все твои деньги")''')
    conn.commit()
    conn.close()

def get_pending_payments():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM pending_payments WHERE status = 'pending'").fetchall()
    conn.close()
    return rows

def add_pending_payment(user_id, label, pack_type="premium"):
    conn = get_conn()
    conn.execute("INSERT INTO pending_payments (user_id, payment_label, created_at, pack_type) VALUES (?, ?, ?, ?)",
                 (user_id, label, datetime.now().isoformat(), pack_type))
    conn.commit()
    conn.close()

def mark_payment_done(payment_label):
    conn = get_conn()
    conn.execute("UPDATE pending_payments SET status = 'done' WHERE payment_label = ?", (payment_label,))
    conn.commit()
    conn.close()

def sync_cards_from_json():
    """Обновляет карты в базе данных значениями из cards.json, не трогая пользователей."""
    import os
    if not os.path.exists(CARDS_JSON):
        print("cards.json не найден, синхронизация пропущена")
        return
    with open(CARDS_JSON, "r", encoding="utf-8") as f:
        cards_data = json.load(f)
    conn = get_conn()
    c = conn.cursor()
    for card in cards_data:
        # Пропускаем Барыгу, если он есть в JSON
        if card["id"] == 99:
            continue
        c.execute('''UPDATE cards SET 
                     name = ?, rarity = ?, strength = ?, endurance = ?,
                     ability_name = ?, ability_description = ?
                     WHERE id = ?''',
                  (card["name"], card["rarity"], card["strength"], card["endurance"],
                   card.get("ability_name", ""), card.get("ability_description", ""),
                   card["id"]))
    conn.commit()
    conn.close()
    print("Редкости карт синхронизированы с cards.json")

def get_user(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def create_user(user_id, username):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO users (user_id, username, registered_date) VALUES (?, ?, ?)",
                 (user_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_last_free_pack(user_id, dt):
    conn = get_conn()
    conn.execute("UPDATE users SET last_free_pack_time = ? WHERE user_id = ?", (dt, user_id))
    conn.commit()
    conn.close()

def add_coins(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_card_info(card_id):
    conn = get_conn()
    card = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    conn.close()
    return card

def add_user_card(user_id, card_id):
    """Добавляет одну копию карты пользователю."""
    conn = get_conn()
    conn.execute("""INSERT INTO user_cards (user_id, card_id, quantity)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id, card_id) DO UPDATE SET quantity = quantity + 1""",
                 (user_id, card_id))
    conn.commit()
    conn.close()

def get_user_collection(user_id):
    """Возвращает список (card_id, quantity) для всех карт с quantity > 0."""
    conn = get_conn()
    rows = conn.execute("SELECT card_id, quantity FROM user_cards WHERE user_id = ? AND quantity > 0", (user_id,)).fetchall()
    conn.close()
    return rows

def get_card_quantity(user_id, card_id):
    conn = get_conn()
    row = conn.execute("SELECT quantity FROM user_cards WHERE user_id = ? AND card_id = ?", (user_id, card_id)).fetchone()
    conn.close()
    return row["quantity"] if row else 0

def remove_one_card(user_id, card_id):
    """Уменьшает количество на 1, удаляет запись, если стало 0."""
    conn = get_conn()
    cur = conn.execute("SELECT quantity FROM user_cards WHERE user_id = ? AND card_id = ?", (user_id, card_id)).fetchone()
    if not cur:
        return
    qty = cur["quantity"]
    if qty <= 1:
        conn.execute("DELETE FROM user_cards WHERE user_id = ? AND card_id = ?", (user_id, card_id))
    else:
        conn.execute("UPDATE user_cards SET quantity = quantity - 1 WHERE user_id = ? AND card_id = ?", (user_id, card_id))
    conn.commit()
    conn.close()
    # Возвращаем награду
    card = get_card_info(card_id)
    return SPRAY_REWARDS.get(card["rarity"], 1)

def has_used_promo(user_id: int, promo_code: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM promo_usage WHERE user_id = ? AND promo_code = ?",
        (user_id, promo_code)
    ).fetchone()
    conn.close()
    return row is not None

def use_promo(user_id: int, promo_code: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO promo_usage (user_id, promo_code, used_at) VALUES (?, ?, ?)",
        (user_id, promo_code, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# Уровни и кампания

def get_level(level_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM levels WHERE id = ?", (level_id,)).fetchone()
    conn.close()
    return row

def get_all_levels():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM levels ORDER BY id").fetchall()
    conn.close()
    return rows

def get_user_level_wins(user_id, level_id):
    conn = get_conn()
    row = conn.execute("SELECT wins_count FROM user_levels WHERE user_id = ? AND level_id = ?", (user_id, level_id)).fetchone()
    conn.close()
    return row["wins_count"] if row else 0

def record_win(user_id, level_id):
    conn = get_conn()
    now = datetime.now().isoformat()
    conn.execute("INSERT INTO user_levels (user_id, level_id, wins_count, last_win_time) VALUES (?, ?, 1, ?) "
                 "ON CONFLICT(user_id, level_id) DO UPDATE SET wins_count = wins_count + 1, last_win_time = ?",
                 (user_id, level_id, now, now))
    conn.commit()
    conn.close()

def add_exp_and_coins(user_id, exp, coins):
    conn = get_conn()
    conn.execute("UPDATE users SET exp = exp + ?, coins = coins + ? WHERE user_id = ?", (exp, coins, user_id))
    conn.commit()
    conn.close()

def add_artifact(user_id):
    conn = get_conn()
    conn.execute("INSERT INTO user_artifacts (user_id, quantity) VALUES (?, 1) "
                 "ON CONFLICT(user_id) DO UPDATE SET quantity = quantity + 1", (user_id,))
    conn.commit()
    conn.close()

def get_artifacts(user_id):
    conn = get_conn()
    row = conn.execute("SELECT quantity FROM user_artifacts WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["quantity"] if row else 0

def set_artifacts(user_id, qty):
    conn = get_conn()
    conn.execute("INSERT INTO user_artifacts (user_id, quantity) VALUES (?, ?) "
                 "ON CONFLICT(user_id) DO UPDATE SET quantity = ?", (user_id, qty, qty))
    conn.commit()
    conn.close()

def reset_levels(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM user_levels WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_exp(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET exp = exp + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_user_exp(user_id):
    conn = get_conn()
    row = conn.execute("SELECT exp, level FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return row["exp"], row["level"]
    return 0, 1

def set_user_level(user_id, level):
    conn = get_conn()
    conn.execute("UPDATE users SET level = ? WHERE user_id = ?", (level, user_id))
    conn.commit()
    conn.close()