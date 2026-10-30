import sqlite3
import os
from datetime import datetime


DB_PATH = "data/cafe_hermes.db"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class _BackupAwareConnection(sqlite3.Connection):
    """Schedule a remote snapshot after every committed database change."""

    def commit(self):
        super().commit()
        try:
            from bot.remote_storage import schedule_sync
            schedule_sync()
        except Exception:
            # Startup, tests, and offline operation must not fail because
            # remote storage is unavailable; the file watcher is the fallback.
            pass


def get_connection():
    os.makedirs("data", exist_ok=True)

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        factory=_BackupAwareConnection
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


    cur.execute("""
        CREATE TABLE IF NOT EXISTS customer_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            base_amount INTEGER NOT NULL,
            balance_before INTEGER NOT NULL DEFAULT 0,
            total_amount INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at TEXT NOT NULL,
            paid_at TEXT,
            created_by INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoice_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            amount INTEGER NOT NULL CHECK(amount > 0),
            receipt_file_id TEXT,
            created_at TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id)
        )
    """)

    order_columns = {row["name"] for row in cur.execute("PRAGMA table_info(orders)").fetchall()}
    if "balance_before" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN balance_before INTEGER NOT NULL DEFAULT 0")
    if "expected_total" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN expected_total INTEGER NOT NULL DEFAULT 0")
    cur.execute("""
        UPDATE orders
        SET expected_total = MAX(0, final_price + COALESCE(balance_before, 0))
        WHERE expected_total = 0 AND final_price > 0
    """)

    # Backward-compatible invoice migrations.
    invoice_columns = {row["name"] for row in cur.execute("PRAGMA table_info(invoices)").fetchall()}
    if "approval_required" not in invoice_columns:
        cur.execute("ALTER TABLE invoices ADD COLUMN approval_required INTEGER NOT NULL DEFAULT 1")
    if "paid_amount" not in invoice_columns:
        cur.execute("ALTER TABLE invoices ADD COLUMN paid_amount INTEGER NOT NULL DEFAULT 0")
    if "invoice_type" not in invoice_columns:
        cur.execute("ALTER TABLE invoices ADD COLUMN invoice_type TEXT NOT NULL DEFAULT 'payment'")

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
        # A user may first open the bot without a referral link and later
        # arrive through one. Preserve an existing attribution, but fill a
        # previously empty referral only once.
        cur.execute("""
            UPDATE users
            SET username = ?,
                first_name = ?,
                referral_by = CASE
                    WHEN referral_by IS NULL AND ? IS NOT NULL
                    THEN ?
                    ELSE referral_by
                END
            WHERE id = ?
        """, (
            username,
            first_name,
            referral_by,
            referral_by,
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


def record_invoice_partial_payment(invoice_id, amount, created_by=None):
    amount = int(amount)
    if amount <= 0:
        raise ValueError("مبلغ پرداخت باید بیشتر از صفر باشد.")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    row = cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if (not row or row["status"] != "pending"
            or not str(row["receipt_file_id"] or "").strip()):
        conn.rollback()
        conn.close()
        return None
    invoice = dict(row)
    old_paid = int(invoice.get("paid_amount") or 0)
    remaining = max(0, int(invoice["total_amount"]) - old_paid)
    if amount > remaining:
        conn.rollback()
        conn.close()
        raise ValueError("مبلغ واردشده از مانده فاکتور بیشتر است.")
    new_paid = old_paid + amount
    completed = new_paid >= int(invoice["total_amount"])
    cur.execute("""
        INSERT INTO invoice_payments (invoice_id, amount, receipt_file_id, created_at, created_by)
        VALUES (?, ?, ?, ?, ?)
    """, (invoice_id, amount, invoice.get("receipt_file_id"), now(), created_by))
    if completed:
        cur.execute("""
            UPDATE invoices
            SET status = 'paid', paid_at = ?, paid_amount = ?, receipt_file_id = NULL
            WHERE id = ? AND status = 'pending'
        """, (now(), new_paid, invoice_id))
        old_balance = int(invoice.get("balance_before") or 0)
        current_row = cur.execute(
            "SELECT COALESCE(SUM(amount), 0) AS balance FROM customer_ledger WHERE user_id = ?",
            (invoice["user_id"],)
        ).fetchone()
        current_balance = int(current_row["balance"] or 0)
        if old_balance > 0 and current_balance > 0:
            settlement = -min(old_balance, current_balance)
        elif old_balance < 0 and current_balance < 0:
            settlement = min(-old_balance, -current_balance, int(invoice["base_amount"]))
        else:
            settlement = 0
        if settlement:
            cur.execute("""
                INSERT INTO customer_ledger (user_id, amount, description, created_at, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (invoice["user_id"], settlement,
                  "تسویه مانده حساب در فاکتور #" + str(invoice_id), now(), created_by))
    else:
        cur.execute("""
            UPDATE invoices
            SET paid_amount = ?, receipt_file_id = NULL
            WHERE id = ? AND status = 'pending'
        """, (new_paid, invoice_id))
    conn.commit()
    conn.close()
    return {
        "paid_amount": new_paid,
        "remaining": max(0, int(invoice["total_amount"]) - new_paid),
        "completed": completed,
        "user_id": invoice["user_id"]
    }


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
    cur.execute("BEGIN IMMEDIATE")

    # Prevent parallel payment snapshots from charging/settling the same balance.
    open_order = cur.execute(
        "SELECT id FROM orders WHERE user_id = ? AND status = 'pending' LIMIT 1",
        (user_id,)
    ).fetchone()
    open_invoice = cur.execute("""
        SELECT id FROM invoices
        WHERE user_id = ? AND status = 'pending' AND approval_required = 1
        LIMIT 1
    """, (user_id,)).fetchone()
    if open_order or open_invoice:
        conn.rollback()
        conn.close()
        raise ValueError("برای این حساب یک پرداخت در انتظار وجود دارد؛ ابتدا همان پرداخت را تکمیل یا لغو کنید.")

    # Validate and consume a coupon in the same transaction as order creation.
    # This prevents races at the usage limit and avoids consuming a coupon if
    # the order itself cannot be inserted.
    if coupon:
        coupon_row = cur.execute("""
            SELECT id, percent FROM coupons
            WHERE code = ? AND active = 1
              AND (expires_at IS NULL OR expires_at = '' OR expires_at >= ?)
              AND (max_uses = 0 OR used_count < max_uses)
        """, (str(coupon).upper(), now())).fetchone()
        if not coupon_row:
            conn.rollback()
            conn.close()
            raise ValueError("کد تخفیف دیگر معتبر نیست یا ظرفیت استفاده از آن تمام شده است.")
        if int(discount_percent) != int(coupon_row["percent"]):
            conn.rollback()
            conn.close()
            raise ValueError("میزان تخفیف سفارش با کد تخفیف مطابقت ندارد.")
        cur.execute("""
            UPDATE coupons SET used_count = used_count + 1
            WHERE id = ? AND active = 1
              AND (max_uses = 0 OR used_count < max_uses)
        """, (coupon_row["id"],))
        if cur.rowcount != 1:
            conn.rollback()
            conn.close()
            raise ValueError("ظرفیت استفاده از کد تخفیف تمام شده است.")

    row = cur.execute(
        "SELECT COALESCE(SUM(amount), 0) AS balance FROM customer_ledger WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    balance = int(row["balance"] or 0)
    expected_total = max(0, int(final_price) + balance)
    cur.execute("""
        INSERT INTO orders (
            user_id, service_id, service_name, order_type, username,
            original_price, discount_percent, final_price, coupon,
            status, created_at, balance_before, expected_total
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
    """, (
        user_id, service_id, service_name, order_type, username,
        original_price, discount_percent, final_price, coupon,
        now(), balance, expected_total
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
          AND receipt_file_id IS NOT NULL
          AND TRIM(receipt_file_id) != ''
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

    cur = conn.cursor()
    cur.execute("""
        UPDATE orders
        SET receipt_file_id = ?
        WHERE id = ?
          AND status = 'pending'
    """, (file_id, order_id))
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return bool(changed)


def approve_order(order_id, created_by=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    row = cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if (not row or row["status"] != "pending"
            or not str(row["receipt_file_id"] or "").strip()):
        conn.rollback()
        conn.close()
        return False
    order = dict(row)
    cur.execute("""
        UPDATE orders SET status = 'approved', approved_at = ?
        WHERE id = ? AND status = 'pending'
    """, (now(), order_id))
    if cur.rowcount != 1:
        conn.rollback()
        conn.close()
        return False
    old_balance = int(order.get("balance_before") or 0)
    current_row = cur.execute(
        "SELECT COALESCE(SUM(amount), 0) AS balance FROM customer_ledger WHERE user_id = ?",
        (order["user_id"],)
    ).fetchone()
    current_balance = int(current_row["balance"] or 0)
    if old_balance > 0 and current_balance > 0:
        settlement = -min(old_balance, current_balance)
    elif old_balance < 0 and current_balance < 0:
        settlement = min(-old_balance, -current_balance, int(order["final_price"]))
    else:
        settlement = 0
    if settlement:
        cur.execute("""
            INSERT INTO customer_ledger (user_id, amount, description, created_at, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (order["user_id"], settlement,
              "تسویه مانده حساب در سفارش #" + str(order_id), now(), created_by))
    conn.commit()
    conn.close()
    return True


def reject_order(order_id):
    """Reject a pending order once and release its reserved coupon use."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    row = cur.execute(
        "SELECT status, coupon FROM orders WHERE id = ?",
        (order_id,)
    ).fetchone()
    if not row or row["status"] != "pending":
        conn.rollback()
        conn.close()
        return False

    cur.execute("""
        UPDATE orders SET status = 'rejected'
        WHERE id = ? AND status = 'pending'
    """, (order_id,))
    if cur.rowcount != 1:
        conn.rollback()
        conn.close()
        return False

    if row["coupon"]:
        cur.execute("""
            UPDATE coupons
            SET used_count = MAX(0, used_count - 1)
            WHERE code = ?
        """, (str(row["coupon"]).upper(),))

    conn.commit()
    conn.close()
    return True


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
    cur.execute("BEGIN IMMEDIATE")

    # A single order can activate only one subscription. This also makes
    # repeated admin clicks / retries idempotent.
    if order_id is not None:
        existing = cur.execute(
            "SELECT id FROM subscriptions WHERE order_id = ? ORDER BY id ASC LIMIT 1",
            (order_id,)
        ).fetchone()
        if existing:
            conn.commit()
            conn.close()
            return int(existing["id"])

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

def get_subscription_by_order(order_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM subscriptions
        WHERE order_id = ?
        ORDER BY id ASC
        LIMIT 1
    """, (order_id,)).fetchone()
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




def delete_pending_order(order_id, user_id=None):
    """Atomically delete only an unapproved pending order."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    sql = "SELECT user_id, coupon FROM orders WHERE id = ? AND status = 'pending'"
    params = [order_id]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    order = cur.execute(sql, params).fetchone()
    if not order:
        conn.rollback()
        conn.close()
        return False
    if order["coupon"]:
        cur.execute(
            "UPDATE coupons SET used_count = MAX(0, used_count - 1) WHERE code = ?",
            (str(order["coupon"]).upper(),)
        )
    cur.execute("DELETE FROM orders WHERE id = ? AND status = 'pending'", (order_id,))
    deleted = cur.rowcount == 1
    conn.commit()
    conn.close()
    return deleted


def delete_order(order_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    order = cur.execute(
        "SELECT status, coupon FROM orders WHERE id = ?",
        (order_id,)
    ).fetchone()

    if not order:
        conn.rollback()
        conn.close()
        return False

    linked_subscription = cur.execute(
        "SELECT 1 FROM subscriptions WHERE order_id = ? LIMIT 1", (order_id,)
    ).fetchone()
    if linked_subscription and order["status"] == "approved":
        conn.rollback()
        conn.close()
        return False

    # A pending order reserves one coupon use. Releasing/deleting that order
    # must return the reservation so abandoned orders do not exhaust coupons.
    if order["status"] == "pending" and order["coupon"]:
        cur.execute("""
            UPDATE coupons
            SET used_count = MAX(0, used_count - 1)
            WHERE code = ?
        """, (str(order["coupon"]).upper(),))

    cur.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    deleted = cur.rowcount == 1
    conn.commit()
    conn.close()
    return deleted


def update_order_status(order_id, status):
    if status == "approved":
        return approve_order(order_id)
    if status == "rejected":
        return reject_order(order_id)
    if status != "pending":
        raise ValueError("وضعیت سفارش نامعتبر است.")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    order = cur.execute(
        "SELECT status, coupon FROM orders WHERE id = ?",
        (order_id,)
    ).fetchone()
    if not order:
        conn.rollback()
        conn.close()
        return False
    if order["status"] == "pending":
        conn.commit()
        conn.close()
        return True
    if order["status"] != "rejected":
        conn.rollback()
        conn.close()
        return False

    # Reopening a rejected order must reserve its coupon use again.
    if order["coupon"]:
        coupon = cur.execute("""
            SELECT id FROM coupons
            WHERE code = ? AND active = 1
              AND (expires_at IS NULL OR expires_at = '' OR expires_at >= ?)
              AND (max_uses = 0 OR used_count < max_uses)
        """, (str(order["coupon"]).upper(), now())).fetchone()
        if not coupon:
            conn.rollback()
            conn.close()
            return False
        cur.execute("""
            UPDATE coupons SET used_count = used_count + 1
            WHERE id = ? AND active = 1
              AND (max_uses = 0 OR used_count < max_uses)
        """, (coupon["id"],))
        if cur.rowcount != 1:
            conn.rollback()
            conn.close()
            return False

    cur.execute("""
        UPDATE orders SET status = 'pending'
        WHERE id = ? AND status = 'rejected'
    """, (order_id,))
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return bool(changed)


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
        SELECT * FROM coupons
        WHERE code = ? AND active = 1
          AND (expires_at IS NULL OR expires_at = '' OR expires_at >= ?)
          AND (max_uses = 0 OR used_count < max_uses)
    """, (code.upper(), now())).fetchone()
    conn.close()
    return dict(row) if row else None


def use_coupon(code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    row = cur.execute("""
        SELECT * FROM coupons
        WHERE code = ? AND active = 1
          AND (expires_at IS NULL OR expires_at = '' OR expires_at >= ?)
          AND (max_uses = 0 OR used_count < max_uses)
    """, (code.upper(), now())).fetchone()
    if not row:
        conn.rollback()
        conn.close()
        return False
    cur.execute("""
        UPDATE coupons SET used_count = used_count + 1
        WHERE id = ? AND active = 1
          AND (max_uses = 0 OR used_count < max_uses)
    """, (row["id"],))
    ok = cur.rowcount == 1
    if ok:
        conn.commit()
    else:
        conn.rollback()
    conn.close()
    return ok


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
    # The users counter is incremented transactionally with each unique
    # referral and is also the value reset_user_info clears.
    conn = get_connection()
    row = conn.execute(
        "SELECT referral_success FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return int(row["referral_success"] or 0) if row else 0


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

    # Remove the matching referral rows too, otherwise the UNIQUE key blocks
    # those invited users from being counted again after an intentional reset.
    cur.execute("DELETE FROM referral_success WHERE inviter_id = ?", (user_id,))
    cur.execute(
        "DELETE FROM referral_rewards WHERE user_id = ? AND status = 'pending'",
        (user_id,)
    )

    conn.commit()
    conn.close()
    return True


# Customer ledger: positive balance means customer owes money; negative means
# the customer has credit. Every movement is immutable and timestamped.
def get_customer_balance(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS balance FROM customer_ledger WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return int(row["balance"] or 0)


def add_customer_ledger_entry(user_id, amount, description, created_by=None):
    amount = int(amount)
    if amount == 0:
        raise ValueError("مبلغ گردش حساب نمی‌تواند صفر باشد.")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO customer_ledger (user_id, amount, description, created_at, created_by)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, amount, str(description).strip(), now(), created_by))
    entry_id = cur.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def get_customer_ledger(user_id, limit=30):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM customer_ledger WHERE user_id = ?
        ORDER BY id DESC LIMIT ?
    """, (user_id, int(limit))).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_invoice(user_id, title, base_amount, description="", service_id=None,
                   created_by=None, approval_required=True):
    base_amount = int(base_amount)
    if base_amount < 0:
        raise ValueError("مبلغ فاکتور نمی‌تواند منفی باشد.")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    if approval_required:
        open_order = cur.execute(
            "SELECT id FROM orders WHERE user_id = ? AND status = 'pending' LIMIT 1",
            (user_id,)
        ).fetchone()
        open_invoice = cur.execute("""
            SELECT id FROM invoices
            WHERE user_id = ? AND status = 'pending' AND approval_required = 1
            LIMIT 1
        """, (user_id,)).fetchone()
        if open_order or open_invoice:
            conn.rollback()
            conn.close()
            raise ValueError("برای این حساب یک پرداخت در انتظار وجود دارد؛ ابتدا همان پرداخت را تکمیل یا لغو کنید.")

    row = cur.execute(
        "SELECT COALESCE(SUM(amount), 0) AS balance FROM customer_ledger WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    balance = int(row["balance"] or 0)
    total = max(0, base_amount + balance)
    invoice_type = "payment" if approval_required else "notice"
    invoice_status = "pending" if approval_required else "notice"
    cur.execute("""
        INSERT INTO invoices
        (user_id, service_id, title, description, base_amount, balance_before,
         total_amount, status, created_at, created_by, approval_required, paid_amount,
         invoice_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (user_id, service_id, title, description, base_amount, balance,
          total, invoice_status, now(), created_by,
          1 if approval_required else 0, invoice_type))
    invoice_id = cur.lastrowid
    conn.commit()
    conn.close()
    return invoice_id


def get_invoice(invoice_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_invoices(user_id, limit=20):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM invoices WHERE user_id = ?
        ORDER BY id DESC LIMIT ?
    """, (user_id, int(limit))).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_invoice_receipt(invoice_id, file_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE invoices SET receipt_file_id = ?
        WHERE id = ? AND status = 'pending'
    """, (file_id, invoice_id))
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return bool(changed)


def mark_invoice_paid(invoice_id, created_by=None, paid_amount=None):
    """Settle an invoice once, and apply the captured prior balance exactly once."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    row = cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not row or row["status"] != "pending":
        conn.rollback()
        conn.close()
        return False
    invoice = dict(row)
    amount = invoice["total_amount"] if paid_amount is None else int(paid_amount)
    if amount < invoice["total_amount"] or amount < 0:
        conn.rollback()
        conn.close()
        return False
    cur.execute("""
        INSERT INTO invoice_payments (invoice_id, amount, receipt_file_id, created_at, created_by)
        VALUES (?, ?, ?, ?, ?)
    """, (invoice_id, amount, invoice.get("receipt_file_id"), now(), created_by))
    cur.execute("""
        UPDATE invoices SET status = 'paid', paid_at = ?, paid_amount = ?, receipt_file_id = NULL
        WHERE id = ? AND status = 'pending'
    """, (now(), amount, invoice_id))
    if cur.rowcount != 1:
        conn.rollback()
        conn.close()
        return False
    old_balance = int(invoice["balance_before"] or 0)
    current_row = cur.execute(
        "SELECT COALESCE(SUM(amount), 0) AS balance FROM customer_ledger WHERE user_id = ?",
        (invoice["user_id"],)
    ).fetchone()
    current_balance = int(current_row["balance"] or 0)
    # Settle only the captured balance that still exists; another invoice/order
    # may already have settled it.
    if old_balance > 0 and current_balance > 0:
        settlement = -min(old_balance, current_balance)
    elif old_balance < 0 and current_balance < 0:
        settlement = min(-old_balance, -current_balance, int(invoice["base_amount"]))
    else:
        settlement = 0
    if settlement:
        cur.execute("""
            INSERT INTO customer_ledger (user_id, amount, description, created_at, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (invoice["user_id"], settlement,
              "تسویه مانده حساب در فاکتور #" + str(invoice_id), now(), created_by))
    conn.commit()
    conn.close()
    return True

