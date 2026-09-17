import sqlite3
import os
import asyncio
from datetime import datetime


DB_PATH = "data/cafe_hermes.db"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection():
    os.makedirs("data", exist_ok=True)

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS referral_success (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER NOT NULL,
            invited_id INTEGER NOT NULL,
            order_id INTEGER,
            created_at TEXT,
            UNIQUE(inviter_id, invited_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            volume_gb INTEGER DEFAULT 10,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            applied_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tutorials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            body_text TEXT DEFAULT '',
            file_id TEXT,
            video_file_id TEXT,
            sort_order INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    """)

    # seed default platforms if empty
    existing = cur.execute(
        "SELECT COUNT(*) AS c FROM tutorials"
    ).fetchone()["c"]

    if existing == 0:
        defaults = [
            ("android", "📱 آموزش استفاده در اندروید", 1),
            ("pc", "💻 آموزش استفاده در کامپیوتر", 2),
            ("iphone", "🍎 آموزش استفاده در آیفون", 3),
        ]
        for key, title, order in defaults:
            cur.execute("""
                INSERT INTO tutorials (
                    key, title, body_text, sort_order, active
                ) VALUES (?, ?, ?, ?, 1)
            """, (
                key,
                title,
                "هنوز محتوایی برای این آموزش تنظیم نشده.\nادمین می‌تواند از پنل مدیریت آن را تکمیل کند.",
                order
            ))

    conn.commit()
    conn.close()


def add_or_update_user(
    user_id,
    username=None,
    first_name=None,
    referral_by=None
):
    conn = get_connection()
    cur = conn.cursor()

    existing = cur.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if existing:
        cur.execute("""
            UPDATE users
            SET username = ?,
                first_name = ?
            WHERE id = ?
        """, (
            username,
            first_name,
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
            now(),
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


def add_service(name, volume_gb, price):
    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
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

    service_id = cur.lastrowid

    conn.commit()
    conn.close()

    return service_id


def get_services(active_only=True):
    conn = get_connection()

    if active_only:
        rows = conn.execute("""
            SELECT *
            FROM services
            WHERE active = 1
            ORDER BY id ASC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM services
            ORDER BY id ASC
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

    row = conn.execute(
        "SELECT active FROM services WHERE id = ?",
        (service_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    new_value = 0 if row["active"] else 1

    conn.execute(
        "UPDATE services SET active = ? WHERE id = ?",
        (new_value, service_id)
    )

    conn.commit()
    conn.close()

    return bool(new_value)



def update_service(service_id, name=None, volume_gb=None, price=None):
    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM services WHERE id = ?",
        (service_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    service = dict(row)

    new_name = name if name is not None else service["name"]
    new_volume = volume_gb if volume_gb is not None else service["volume_gb"]
    new_price = price if price is not None else service["price"]

    conn.execute("""
        UPDATE services
        SET name = ?, volume_gb = ?, price = ?
        WHERE id = ?
    """, (new_name, new_volume, new_price, service_id))

    conn.commit()
    conn.close()

    return True


def delete_service(service_id):
    conn = get_connection()

    conn.execute(
        "DELETE FROM services WHERE id = ?",
        (service_id,)
    )

    conn.commit()
    conn.close()

    return True


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
        now()
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
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_orders_count():
    conn = get_connection()

    row = conn.execute(
        "SELECT COUNT(*) AS count FROM orders"
    ).fetchone()

    conn.close()

    return row["count"]


def set_receipt(order_id, file_id):
    conn = get_connection()

    conn.execute("""
        UPDATE orders
        SET receipt_file_id = ?
        WHERE id = ?
    """, (
        file_id,
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
        now(),
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


def save_subscription(
    user_id,
    order_id,
    service_name,
    username,
    subscription_url=None,
    config_text=None
):
    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
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
        now(),
        now()
    ))

    subscription_id = cur.lastrowid

    conn.commit()
    conn.close()

    return subscription_id


def get_user_subscriptions(user_id):
    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM subscriptions
        WHERE user_id = ?
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


def update_subscription_status(subscription_id, status):
    conn = get_connection()

    conn.execute("""
        UPDATE subscriptions
        SET status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        status,
        now(),
        subscription_id
    ))

    conn.commit()
    conn.close()




def delete_order(order_id):
    conn = get_connection()
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return True


def update_order_status(order_id, status):
    conn = get_connection()
    if status == "approved":
        conn.execute(
            "UPDATE orders SET status = ?, approved_at = ? WHERE id = ?",
            (status, now(), order_id)
        )
    else:
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id)
        )
    conn.commit()
    conn.close()
    return True


def delete_subscription(subscription_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM subscriptions WHERE id = ?",
        (subscription_id,)
    )
    conn.commit()
    conn.close()
    return True


def update_subscription_fields(
    subscription_id,
    service_name=None,
    username=None,
    config_text=None,
    subscription_url=None,
    status=None
):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE id = ?",
        (subscription_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    s = dict(row)
    conn.execute("""
        UPDATE subscriptions
        SET service_name = ?,
            username = ?,
            config_text = ?,
            subscription_url = ?,
            status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        service_name if service_name is not None else s["service_name"],
        username if username is not None else s["username"],
        config_text if config_text is not None else s["config_text"],
        subscription_url if subscription_url is not None else s["subscription_url"],
        status if status is not None else s["status"],
        now(),
        subscription_id
    ))
    conn.commit()
    conn.close()
    return True

def create_coupon(
    code,
    percent,
    max_uses=0,
    expires_at=None
):
    conn = get_connection()

    try:
        conn.execute("""
            INSERT INTO coupons (
                code,
                percent,
                max_uses,
                expires_at,
                active
            )
            VALUES (?, ?, ?, ?, 1)
        """, (
            code.upper(),
            percent,
            max_uses,
            expires_at
        ))

        conn.commit()

        result = True

    except sqlite3.IntegrityError:
        result = False

    conn.close()

    return result


def get_coupon(code):
    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM coupons
        WHERE code = ?
          AND active = 1
    """, (code.upper(),)).fetchone()

    conn.close()

    return dict(row) if row else None


def use_coupon(code):
    conn = get_connection()

    cur = conn.cursor()

    row = cur.execute("""
        SELECT *
        FROM coupons
        WHERE code = ?
          AND active = 1
    """, (code.upper(),)).fetchone()

    if not row:
        conn.close()
        return False

    if row["max_uses"] > 0 and row["used_count"] >= row["max_uses"]:
        conn.close()
        return False

    cur.execute("""
        UPDATE coupons
        SET used_count = used_count + 1
        WHERE id = ?
    """, (row["id"],))

    conn.commit()
    conn.close()

    return True


def deactivate_coupon(code):
    conn = get_connection()

    conn.execute("""
        UPDATE coupons
        SET active = 0
        WHERE code = ?
    """, (code.upper(),))

    conn.commit()
    conn.close()


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
    conn = get_connection()

    try:
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
            now()
        ))

        conn.execute("""
            UPDATE users
            SET referral_success = referral_success + 1
            WHERE id = ?
        """, (inviter_id,))

        conn.commit()

        result = True

    except sqlite3.IntegrityError:
        result = False

    conn.close()

    return result


def get_referral_count(user_id):
    conn = get_connection()

    row = conn.execute("""
        SELECT COUNT(*) AS count
        FROM referral_success
        WHERE inviter_id = ?
    """, (user_id,)).fetchone()

    conn.close()

    return row["count"]


def get_referral_reward_count(user_id):
    conn = get_connection()

    row = conn.execute("""
        SELECT COUNT(*) AS count
        FROM referral_rewards
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    conn.close()

    return row["count"]


def create_referral_reward(user_id):
    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO referral_rewards (
            user_id,
            volume_gb,
            status,
            created_at
        )
        VALUES (?, 10, 'pending', ?)
    """, (
        user_id,
        now()
    ))

    reward_id = cur.lastrowid

    conn.commit()
    conn.close()

    return reward_id


def get_pending_rewards():
    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM referral_rewards
        WHERE status = 'pending'
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def mark_reward_applied(reward_id):
    conn = get_connection()

    conn.execute("""
        UPDATE referral_rewards
        SET status = 'applied',
            applied_at = ?
        WHERE id = ?
    """, (
        now(),
        reward_id
    ))

    conn.commit()
    conn.close()


def get_low_volume_warned(user_id):
    conn = get_connection()

    row = conn.execute("""
        SELECT low_volume_warned
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    conn.close()

    return bool(row["low_volume_warned"]) if row else False


def set_low_volume_warned(user_id):
    conn = get_connection()

    conn.execute("""
        UPDATE users
        SET low_volume_warned = 1
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()


def reset_low_volume_warning(user_id):
    conn = get_connection()

    conn.execute("""
        UPDATE users
        SET low_volume_warned = 0
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()



def get_users_page(offset=0, limit=10):
    conn = get_connection()

    rows = conn.execute("""
        SELECT id, username, first_name, joined_at
        FROM users
        ORDER BY joined_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_tutorials(active_only=True):
    conn = get_connection()

    if active_only:
        rows = conn.execute("""
            SELECT *
            FROM tutorials
            WHERE active = 1
            ORDER BY sort_order ASC, id ASC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM tutorials
            ORDER BY sort_order ASC, id ASC
        """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_tutorial(tutorial_id):
    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM tutorials
        WHERE id = ?
    """, (tutorial_id,)).fetchone()

    conn.close()

    return dict(row) if row else None


def get_tutorial_by_key(key):
    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM tutorials
        WHERE key = ?
    """, (key,)).fetchone()

    conn.close()

    return dict(row) if row else None


def update_tutorial_field(tutorial_id, field, value):
    allowed = {
        "title",
        "body_text",
        "file_id",
        "video_file_id",
        "sort_order",
        "active"
    }

    if field not in allowed:
        return False

    conn = get_connection()

    conn.execute(
        f"UPDATE tutorials SET {field} = ? WHERE id = ?",
        (value, tutorial_id)
    )

    conn.commit()
    conn.close()

    return True


def add_tutorial(key, title, body_text=""):
    conn = get_connection()
    cur = conn.cursor()

    row = cur.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS m FROM tutorials"
    ).fetchone()

    order = int(row["m"]) + 1

    try:
        cur.execute("""
            INSERT INTO tutorials (
                key, title, body_text, sort_order, active
            ) VALUES (?, ?, ?, ?, 1)
        """, (key, title, body_text, order))

        tutorial_id = cur.lastrowid
        conn.commit()
        conn.close()
        return tutorial_id

    except sqlite3.IntegrityError:
        conn.close()
        return None


def toggle_tutorial(tutorial_id):
    conn = get_connection()

    row = conn.execute(
        "SELECT active FROM tutorials WHERE id = ?",
        (tutorial_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    new_value = 0 if row["active"] else 1

    conn.execute(
        "UPDATE tutorials SET active = ? WHERE id = ?",
        (new_value, tutorial_id)
    )

    conn.commit()
    conn.close()

    return bool(new_value)


def delete_tutorial(tutorial_id):
    conn = get_connection()

    conn.execute(
        "DELETE FROM tutorials WHERE id = ?",
        (tutorial_id,)
    )

    conn.commit()
    conn.close()


def get_user_orders_admin(user_id):
    """alias - same as get_user_orders"""
    return get_user_orders(user_id)


def delete_user_subscriptions(user_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM subscriptions WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    return True


def reset_user_info(user_id):
    """
    ریست اطلاعات کاربر:
    - اشتراک‌ها حذف می‌شوند
    - هشدار حجم کم صفر می‌شود
    - شمارنده‌های دعوت صفر می‌شود
    سفارش‌ها برای تاریخچه نگه داشته می‌شوند.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM subscriptions WHERE user_id = ?",
        (user_id,)
    )

    cur.execute("""
        UPDATE users
        SET referral_success = 0,
            referral_reward_count = 0,
            low_volume_warned = 0
        WHERE id = ?
    """, (user_id,))

    # pending referral rewards for this user
    cur.execute(
        "DELETE FROM referral_rewards WHERE user_id = ? AND status = 'pending'",
        (user_id,)
    )

    conn.commit()
    conn.close()
    return True
