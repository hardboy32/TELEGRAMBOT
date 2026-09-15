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
           
