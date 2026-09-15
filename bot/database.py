import sqlite3
import os
from datetime import datetime


DB_PATH = "data/hermes.db"


def get_connection():
    os.makedirs("data", exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT,
            referral_by INTEGER,
            referral_success INTEGER DEFAULT 0,
            referral_reward_count INTEGER DEFAULT 0,
            low_volume_warned INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            volume_gb INTEGER NOT NULL,
            price INTEGER NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER,
            order_type TEXT DEFAULT 'purchase',
            username TEXT,
            original_price INTEGER DEFAULT 0,
            discount_percent INTEGER DEFAULT 0,
            final_price INTEGER DEFAULT 0,
            coupon TEXT,
            receipt_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            approved_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id INTEGER,
            service_name TEXT,
            username TEXT,
            subscription_url TEXT,
            config_text TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            percent INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 0,
            used_count INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            expires_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id, username, first_name, referral_by=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    exists = cur.fetchone()

    if not exists:
        cur.execute("""
            INSERT INTO users
            (id, username, first_name, joined_at, referral_by)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            username or "",
            first_name or "",
            now(),
            referral_by
        ))

    else:
        cur.execute("""
            UPDATE users
            SET username = ?, first_name = ?
            WHERE id = ?
        """, (
            username or "",
            first_name or "",
            user_id
        ))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    result = cur.fetchone()

    conn.close()
    return result


def get_services(active_only=True):
    conn = get_connection()
    cur = conn.cursor()

    if active_only:
        cur.execute("SELECT * FROM services WHERE active = 1 ORDER BY volume_gb")
    else:
        cur.execute("SELECT * FROM services ORDER BY volume_gb")

    result = cur.fetchall()
    conn.close()
    return result


def get_service(service_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM services WHERE id = ?", (service_id,))
    result = cur.fetchone()

    conn.close()
    return result


def add_service(name, volume_gb, price):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO services (name, volume_gb, price)
        VALUES (?, ?, ?)
    """, (name, volume_gb, price))

    conn.commit()
    service_id = cur.lastrowid
    conn.close()

    return service_id


def update_service(service_id, name, volume_gb, price, active=1):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE services
        SET name = ?, volume_gb = ?, price = ?, active = ?
        WHERE id = ?
    """, (
        name,
        volume_gb,
        price,
        active,
        service_id
    ))

    conn.commit()
    conn.close()


def delete_service(service_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE services SET active = 0 WHERE id = ?",
        (service_id,)
    )

    conn.commit()
    conn.close()


def create_order(
    user_id,
    service_id,
    order_type,
    username,
    original_price,
    discount_percent,
    final_price,
    coupon
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO orders
        (
            user_id,
            service_id,
            order_type,
            username,
            original_price,
            discount_percent,
            final_price,
            coupon,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        service_id,
        order_type,
        username,
        original_price,
        discount_percent,
        final_price,
        coupon,
        now()
    ))

    conn.commit()
    order_id = cur.lastrowid
    conn.close()

    return order_id


def get_order(order_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            orders.*,
            services.name AS service_name,
            services.volume_gb
        FROM orders
        LEFT JOIN services ON services.id = orders.service_id
        WHERE orders.id = ?
    """, (order_id,))

    result = cur.fetchone()

    conn.close()
    return result


def set_receipt(order_id, file_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE orders
        SET receipt_file_id = ?, status = 'waiting_admin'
        WHERE id = ?
    """, (file_id, order_id))

    conn.commit()
    conn.close()


def set_order_status(order_id, status):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE orders
        SET status = ?, approved_at = ?
        WHERE id = ?
    """, (status, now() if status == "approved" else None, order_id))

    conn.commit()
    conn.close()


def get_pending_orders():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            orders.*,
            services.name AS service_name,
            services.volume_gb
        FROM orders
        LEFT JOIN services ON services.id = orders.service_id
        WHERE orders.status = 'waiting_admin'
        ORDER BY orders.id DESC
    """)

    result = cur.fetchall()
    conn.close()

    return result


def get_user_orders(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            orders.*,
            services.name AS service_name,
            services.volume_gb
        FROM orders
        LEFT JOIN services ON services.id = orders.service_id
        WHERE orders.user_id = ?
        ORDER BY orders.id DESC
    """, (user_id,))

    result = cur.fetchall()
    conn.close()

    return result


def add_subscription(
    user_id,
    order_id,
    service_name,
    username,
    subscription_url,
    config_text
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO subscriptions
        (
            user_id,
            order_id,
            service_name,
            username,
            subscription_url,
            config_text,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        order_id,
        service_name,
        username,
        subscription_url,
        config_text,
        now(),
        now()
    ))

    conn.commit()
    conn.close()


def get_user_subscriptions(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM subscriptions
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))

    result = cur.fetchall()
    conn.close()

    return result


def get_subscription(subscription_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM subscriptions
        WHERE id = ?
    """, (subscription_id,))

    result = cur.fetchone()
    conn.close()

    return result


def create_coupon(code, percent, max_uses=0, expires_at=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO coupons
        (code, percent, max_uses, expires_at)
        VALUES (?, ?, ?, ?)
    """, (
        code.upper(),
        percent,
        max_uses,
        expires_at
    ))

    conn.commit()
    conn.close()


def get_coupon(code):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM coupons
        WHERE code = ?
        AND active = 1
    """, (code.upper(),))

    result = cur.fetchone()
    conn.close()

    return result


def use_coupon(code):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE coupons
        SET used_count = used_count + 1
        WHERE code = ?
    """, (code.upper(),))

    conn.commit()
    conn.close()


def register_successful_referral(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT referral_by
        FROM users
        WHERE id = ?
    """, (user_id,))

    user = cur.fetchone()

    if not user or not user["referral_by"]:
        conn.close()
        return None

    inviter_id = user["referral_by"]

    cur.execute("""
        UPDATE users
        SET referral_success = referral_success + 1
        WHERE id = ?
    """, (inviter_id,))

    cur.execute("""
        SELECT referral_success
        FROM users
        WHERE id = ?
    """, (inviter_id,))

    count = cur.fetchone()["referral_success"]

    conn.commit()
    conn.close()

    return inviter_id, count


def reset_referral_reward(inviter_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET referral_success = referral_success - 5,
            referral_reward_count = referral_reward_count + 1
        WHERE id = ?
        AND referral_success >= 5
    """, (inviter_id,))

    conn.commit()
    conn.close()


def get_all_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users ORDER BY id DESC")
    result = cur.fetchall()

    conn.close()
    return result


def set_setting(key, value):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (key, str(value)))

    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT value FROM settings WHERE key = ?",
        (key,)
    )

    result = cur.fetchone()
    conn.close()

    return result["value"] if result else default
