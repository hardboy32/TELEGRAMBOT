import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("data/bot.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# مقداردهی اولیه دیتابیس
# =========================================================

def init_db():

    conn = get_connection()
    cur = conn.cursor()

    # کاربران
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

    # سرویس‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            volume_gb INTEGER NOT NULL,
            price INTEGER NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    # سفارش‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER,
            service_name TEXT,
            order_type TEXT DEFAULT 'buy',
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

    # اشتراک‌ها
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

    # کدهای تخفیف
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

    # تنظیمات
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # دعوت‌های موفق
    cur.execute("""
        CREATE TABLE IF NOT EXISTS referral_success (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER NOT NULL,
            invited_id INTEGER NOT NULL UNIQUE,
            order_id INTEGER UNIQUE,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# کاربران
# =========================================================

def add_or_update_user(
    user_id,
    username=None,
    first_name=None,
    referral_by=None
):

    conn = get_connection()
    cur = conn.cursor()

    old = cur.execute(
        "SELECT id, referral_by FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if old:

        current_referral = old["referral_by"]

        if current_referral is None and referral_by:
            current_referral = referral_by

        cur.execute("""
            UPDATE users
            SET username = ?,
                first_name = ?,
                referral_by = ?
            WHERE id = ?
        """, (
            username,
            first_name,
            current_referral,
            user_id
        ))

    else:

        cur.execute("""
            INSERT INTO users (
                id,
                username,
                first_name,
                joined_at,
                referral_by
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            username,
            first_name,
            datetime.now().isoformat(),
            referral_by
        ))

    conn.commit()
    conn.close()


def get_user(user_id):

    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    return dict(row) if row else None


def get_all_user_ids():

    conn = get_connection()

    rows = conn.execute(
        "SELECT id FROM users"
    ).fetchall()

    conn.close()

    return [row["id"] for row in rows]


def get_users_count():

    conn = get_connection()

    row = conn.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()

    conn.close()

    return row["count"]


# =========================================================
# سرویس‌ها
# =========================================================

def add_service(name, volume_gb, price):

    conn = get_connection()

    conn.execute("""
        INSERT INTO services (
            name,
            volume_gb,
            price,
            active
        )
        VALUES (?, ?, ?, 1)
    """, (
        name,
        volume_gb,
        price
    ))

    conn.commit()
    conn.close()


def get_services(active_only=True):

    conn = get_connection()

    if active_only:

        rows = conn.execute("""
            SELECT *
            FROM services
            WHERE active = 1
            ORDER BY volume_gb ASC
        """).fetchall()

    else:

        rows = conn.execute("""
            SELECT *
            FROM services
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_service(service_id):

    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM services WHERE id = ?",
        (service_id,)
    ).fetchone()

    conn.close()

    return dict(row) if row else None


def toggle_service(service_id):

    conn = get_connection()

    conn.execute("""
        UPDATE services
        SET active = CASE
            WHEN active = 1 THEN 0
            ELSE 1
        END
        WHERE id = ?
    """, (service_id,))

    conn.commit()
    conn.close()


# =========================================================
# سفارش‌ها
# =========================================================

def create_order(
    user_id,
    service_id,
    service_name,
    order_type,
    username,
    original_price,
    discount_percent,
    final_price,
    coupon=None
):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO orders (
            user_id,
            service_id,
            service_name,
            order_type,
            username,
            original_price,
            discount_percent,
            final_price,
            coupon,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        user_id,
        service_id,
        service_name,
        order_type,
        username,
        original_price,
        discount_percent,
        final_price,
        coupon,
        datetime.now().isoformat()
    ))

    order_id = cur.lastrowid

    conn.commit()
    conn.close()

    return order_id


def get_order(order_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM orders
        WHERE id = ?
    """, (order_id,)).fetchone()

    conn.close()

    return dict(row) if row else None


def get_pending_orders():

    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM orders
        WHERE status = 'pending'
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_orders_count():

    conn = get_connection()

    row = conn.execute("""
        SELECT COUNT(*) AS count
        FROM orders
    """).fetchone()

    conn.close()

    return row["count"]


def set_receipt(order_id, receipt_file_id):

    conn = get_connection()

    conn.execute("""
        UPDATE orders
        SET receipt_file_id = ?
        WHERE id = ?
    """, (
        receipt_file_id,
        order_id
    ))

    conn.commit()
    conn.close()


def approve_order(order_id):

    conn = get_connection()

    conn.execute("""
        UPDATE orders
        SET status = 'approved',
            approved_at = ?
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        order_id
    ))

    conn.commit()
    conn.close()


def reject_order(order_id):

    conn = get_connection()

    conn.execute("""
        UPDATE orders
        SET status = 'rejected'
        WHERE id = ?
    """, (order_id,))

    conn.commit()
    conn.close()


def get_user_orders(user_id):

    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# =========================================================
# اشتراک‌ها
# =========================================================

def save_subscription(
    user_id,
    order_id,
    service_name,
    username,
    subscription_url,
    config_text
):

    conn = get_connection()

    now = datetime.now().isoformat()

    # اگر برای این سفارش قبلاً اشتراک ثبت شده،
    # همان را بروزرسانی می‌کنیم.
    old = conn.execute("""
        SELECT id
        FROM subscriptions
        WHERE order_id = ?
    """, (order_id,)).fetchone()

    if old:

        conn.execute("""
            UPDATE subscriptions
            SET service_name = ?,
                username = ?,
                subscription_url = ?,
                config_text = ?,
                status = 'active',
                updated_at = ?
            WHERE order_id = ?
        """, (
            service_name,
            username,
            subscription_url,
            config_text,
            now,
            order_id
        ))

    else:

        conn.execute("""
            INSERT INTO subscriptions (
                user_id,
                order_id,
                service_name,
                username,
                subscription_url,
                config_text,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (
            user_id,
            order_id,
            service_name,
            username,
            subscription_url,
            config_text,
            now,
            now
        ))

    conn.commit()
    conn.close()


def get_user_subscriptions(user_id):

    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM subscriptions
        WHERE user_id = ?
        AND status = 'active'
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_subscription(subscription_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM subscriptions
        WHERE id = ?
    """, (subscription_id,)).fetchone()

    conn.close()

    return dict(row) if row else None


def update_subscription_status(
    subscription_id,
    status
):

    conn = get_connection()

    conn.execute("""
        UPDATE subscriptions
        SET status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        status,
        datetime.now().isoformat(),
        subscription_id
    ))

    conn.commit()
    conn.close()


# =========================================================
# کد تخفیف
# =========================================================

def create_coupon(
    code,
    percent,
    max_uses=0,
    expires_at=None
):

    conn = get_connection()

    conn.execute("""
        INSERT INTO coupons (
            code,
            percent,
            max_uses,
            used_count,
            active,
            expires_at
        )
        VALUES (?, ?, ?, 0, 1, ?)
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

    row = conn.execute("""
        SELECT *
        FROM coupons
        WHERE code = ?
    """, (
        code.upper(),
    )).fetchone()

    conn.close()

    return dict(row) if row else None


def use_coupon(code):

    conn = get_connection()

    conn.execute("""
        UPDATE coupons
        SET used_count = used_count + 1
        WHERE code = ?
    """, (
        code.upper(),
    ))

    conn.commit()
    conn.close()


def deactivate_coupon(code):

    conn = get_connection()

    conn.execute("""
        UPDATE coupons
        SET active = 0
        WHERE code = ?
    """, (
        code.upper(),
    ))

    conn.commit()
    conn.close()


# =========================================================
# تنظیمات
# =========================================================

def set_setting(key, value):

    conn = get_connection()

    conn.execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (
        key,
        str(value)
    ))

    conn.commit()
    conn.close()


def get_setting(key, default=None):

    conn = get_connection()

    row = conn.execute("""
        SELECT value
        FROM settings
        WHERE key = ?
    """, (key,)).fetchone()

    conn.close()

    if not row:
        return default

    return row["value"]


# =========================================================
# دعوت دوستان
# =========================================================

def get_referrer(user_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT referral_by
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    conn.close()

    if not row:
        return None

    return row["referral_by"]


def record_successful_referral(
    inviter_id,
    invited_id,
    order_id
):

    if inviter_id == invited_id:
        return 0

    conn = get_connection()

    # هر کاربر فقط یک بار می‌تواند
    # برای یک دعوت‌کننده ثبت شود.
    old = conn.execute("""
        SELECT id
        FROM referral_success
        WHERE invited_id = ?
    """, (invited_id,)).fetchone()

    if old:

        conn.close()
        return 0

    # سفارش هم نباید دوباره ثبت شود.
    old_order = conn.execute("""
        SELECT id
        FROM referral_success
        WHERE order_id = ?
    """, (order_id,)).fetchone()

    if old_order:

        conn.close()
        return 0

    conn.execute("""
        INSERT INTO referral_success (
            inviter_id,
            invited_id,
            order_id,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        inviter_id,
        invited_id,
        order_id,
        datetime.now().isoformat()
    ))

    conn.execute("""
        UPDATE users
        SET referral_success = referral_success + 1
        WHERE id = ?
    """, (inviter_id,))

    row = conn.execute("""
        SELECT referral_success
        FROM users
        WHERE id = ?
    """, (inviter_id,)).fetchone()

    count = row["referral_success"] if row else 0

    # هر 5 دعوت موفق یک جایزه
    if count >= 5:

        conn.execute("""
            UPDATE users
            SET referral_success = referral_success - 5,
                referral_reward_count =
                    referral_reward_count + 1
            WHERE id = ?
        """, (inviter_id,))

        reward = 1

    else:

        reward = 0

    conn.commit()
    conn.close()

    return reward


def get_referral_count(user_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT referral_success
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    conn.close()

    if not row:
        return 0

    return row["referral_success"]


def get_referral_reward_count(user_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT referral_reward_count
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    conn.close()

    if not row:
        return 0

    return row["referral_reward_count"]


# =========================================================
# هشدار کمبود حجم
# =========================================================

def get_low_volume_warned(subscription_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT low_volume_warned
        FROM users
        WHERE id = (
            SELECT user_id
            FROM subscriptions
            WHERE id = ?
        )
    """, (subscription_id,)).fetchone()

    conn.close()

    return bool(row["low_volume_warned"]) if row else False


def set_low_volume_warned(
    user_id,
    value=1
):

    conn = get_connection()

    conn.execute("""
        UPDATE users
        SET low_volume_warned = ?
        WHERE id = ?
    """, (
        value,
        user_id
    ))

    conn.commit()
    conn.close()


def reset_low_volume_warning(user_id):

    set_low_volume_warned(
        user_id,
        0
    )
