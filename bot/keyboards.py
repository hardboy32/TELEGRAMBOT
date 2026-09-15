from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup


def main_menu(settings):
    buttons = []

    row = []

    if settings.get("buy", True):
        row.append(InlineKeyboardButton("🛒 خرید سرویس", callback_data="buy"))

    if settings.get("renew", True):
        row.append(InlineKeyboardButton("🔄 تمدید سرویس", callback_data="renew"))

    if row:
        buttons.append(row)

    row = []

    if settings.get("subscriptions", True):
        row.append(
            InlineKeyboardButton(
                "📦 اشتراک‌های من",
                callback_data="my_subscriptions"
            )
        )

    if settings.get("status", True):
        row.append(
            InlineKeyboardButton(
                "📊 وضعیت اشتراک",
                callback_data="status"
            )
        )

    if row:
        buttons.append(row)

    row = []

    if settings.get("referral", True):
        row.append(
            InlineKeyboardButton(
                "👥 دعوت دوستان",
                callback_data="referral"
            )
        )

    if settings.get("coupon", True):
        row.append(
            InlineKeyboardButton(
                "🎟️ کد تخفیف",
                callback_data="coupon"
            )
        )

    if row:
        buttons.append(row)

    row = []

    if settings.get("history", True):
        row.append(
            InlineKeyboardButton(
                "📜 تاریخچه سفارش",
                callback_data="history"
            )
        )

    if settings.get("account", True):
        row.append(
            InlineKeyboardButton(
                "👤 حساب کاربری",
                callback_data="account"
            )
        )

    if row:
        buttons.append(row)

    row = []

    if settings.get("support", True):
        row.append(
            InlineKeyboardButton(
                "☎️ پشتیبانی",
                callback_data="support"
            )
        )

    if settings.get("tutorial", True):
        row.append(
            InlineKeyboardButton(
                "📚 آموزش اتصال",
                callback_data="tutorial"
            )
        )

    if row:
        buttons.append(row)

    if settings.get("free_test", False):
        buttons.append([
            InlineKeyboardButton(
                "🎁 تست رایگان",
                callback_data="free_test"
            )
        ])

    if settings.get("festival", False):
        buttons.append([
            InlineKeyboardButton(
                "🎉 جشنواره",
                callback_data="festival"
            )
        ])

    return InlineKeyboardMarkup(buttons)


def back_button():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="main_menu"
            )
        ]
    ])


def channel_join_button(channel_username):
    channel_username = channel_username.replace("@", "")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 عضویت در کانال",
                url=f"https://t.me/{channel_username}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ بررسی عضویت",
                callback_data="check_join"
            )
        ]
    ])


def services_keyboard(services, prefix="service"):
    buttons = []

    for service in services:
        buttons.append([
            InlineKeyboardButton(
                f"📦 {service['name']} - {service['price']:,} تومان",
                callback_data=f"{prefix}:{service['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="main_menu"
        )
    ])

    return InlineKeyboardMarkup(buttons)


def order_payment_button(order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📸 ارسال رسید پرداخت",
                callback_data=f"receipt:{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ لغو سفارش",
                callback_data=f"cancel_order:{order_id}"
            )
        ]
    ])


def admin_order_buttons(order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تأیید پرداخت",
                callback_data=f"admin_approve:{order_id}"
            ),
            InlineKeyboardButton(
                "❌ رد پرداخت",
                callback_data=f"admin_reject:{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "📤 ثبت کانفیگ",
                callback_data=f"admin_config:{order_id}"
            )
        ]
    ])


def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🧾 سفارش‌های در انتظار",
                callback_data="admin_pending"
            )
        ],
        [
            InlineKeyboardButton(
                "🛍 مدیریت سرویس‌ها",
                callback_data="admin_services"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 کاربران",
                callback_data="admin_users"
            ),
            InlineKeyboardButton(
                "📊 آمار",
                callback_data="admin_stats"
            )
        ],
        [
            InlineKeyboardButton(
                "🎟️ کدهای تخفیف",
                callback_data="admin_coupons"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 پیام همگانی",
                callback_data="admin_broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                "🎛️ مدیریت دکمه‌ها",
                callback_data="admin_buttons"
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ تنظیمات",
                callback_data="admin_settings"
            )
        ]
    ])


def admin_service_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ افزودن سرویس",
                callback_data="admin_add_service"
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ ویرایش سرویس",
                callback_data="admin_edit_service"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 حذف سرویس",
                callback_data="admin_delete_service"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="admin_menu"
            )
        ]
    ])


def admin_button_settings(settings):
    names = {
        "buy": "🛒 خرید سرویس",
        "renew": "🔄 تمدید سرویس",
        "subscriptions": "📦 اشتراک‌های من",
        "status": "📊 وضعیت اشتراک",
        "referral": "👥 دعوت دوستان",
        "coupon": "🎟️ کد تخفیف",
        "history": "📜 تاریخچه سفارش",
        "account": "👤 حساب کاربری",
        "support": "☎️ پشتیبانی",
        "tutorial": "📚 آموزش اتصال",
        "free_test": "🎁 تست رایگان",
        "festival": "🎉 جشنواره"
    }

    buttons = []

    for key, title in names.items():
        status = "🟢 روشن" if settings.get(key, False) else "🔴 خاموش"

        buttons.append([
            InlineKeyboardButton(
                f"{title} | {status}",
                callback_data=f"toggle:{key}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="admin_menu"
        )
    ])

    return InlineKeyboardMarkup(buttons)
