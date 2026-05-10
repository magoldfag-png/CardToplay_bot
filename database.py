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