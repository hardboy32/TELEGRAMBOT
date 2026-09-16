from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def main_menu(config):
    buttons = []

    if config.get("buy_enabled", True):
        buttons.append(KeyboardButton("🛒 خرید سرویس"))

    if config.get("renew_enabled", True):
        buttons.append(KeyboardButton("🔄 تمدید"))

    if config.get("subscriptions_enabled", True):
        buttons.append(KeyboardButton("📦 اشتراک‌های من"))

    if config.get("status_enabled", True):
        buttons.append(KeyboardButton("📊 وضعیت اشتراک"))

    if config.get("referral_enabled", True):
        buttons.append(KeyboardButton("👥 دعوت دوستان"))

    if config.get("coupon_enabled", True):
        buttons.append(KeyboardButton("🎟️ کد تخفیف"))

    if config.get("order_history_enabled", True):
        buttons.append(KeyboardButton("📜 تاریخچه سفارش‌ها"))

    if config.get("account_enabled", True):
        buttons.append(KeyboardButton("👤 حساب من"))

    if config.get("support_enabled", True):
        buttons.append(KeyboardButton("☎️ پشتیبانی"))

    if config.get("tutorial_enabled", True):
        buttons.append(KeyboardButton("📚 آموزش"))

    if config.get("free_test_enabled", False):
        buttons.append(KeyboardButton("🎁 تست رایگان"))

    if config.get("festival_enabled", False):
        buttons.append(KeyboardButton("🎉 جشنواره"))

    rows = []

    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i + 2])

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True
    )


def join_keyboard(channel):
    username = channel.replace("@", "")

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📢 عضویت در کانال",
                    url=f"https://t.me/{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ بررسی عضویت",
                    callback_data="check_join"
                )
            ]
        ]
    )


def services_keyboard(services):
    rows = []

    for service in services:
        rows.append(
            [
                InlineKeyboardButton(
                    f"📦 {service['name']} | {service['volume_gb']}GB",
                    callback_data=f"service_{service['id']}"
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "❌ بستن",
                callback_data="user_home"
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


def confirm_order_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تأیید سفارش",
                    callback_data="confirm_order"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ لغو",
                    callback_data="user_home"
                )
            ]
        ]
    )


def payment_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💳 اطلاعات پرداخت",
                    callback_data="payment_info"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ لغو سفارش",
                    callback_data="user_home"
                )
            ]
        ]
    )


def subscriptions_keyboard(subscriptions):
    rows = []

    for sub in subscriptions:
        rows.append(
            [
                InlineKeyboardButton(
                    f"📦 {sub['service_name']} | @{sub['username']}",
                    callback_data=f"sub_{sub['id']}"
                )
            ]
        )

    return InlineKeyboardMarkup(rows)


def renew_keyboard(subscriptions):
    rows = []

    for sub in subscriptions:
        rows.append(
            [
                InlineKeyboardButton(
                    f"🔄 {sub['service_name']} | @{sub['username']}",
                    callback_data=f"renew_{sub['id']}"
                )
            ]
        )

    return InlineKeyboardMarkup(rows)


def back_home_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🏠 منوی اصلی",
                    callback_data="user_home"
                )
            ]
        ]
    )



def tutorials_keyboard(tutorials):
    rows = []

    for item in tutorials:
        rows.append(
            [
                InlineKeyboardButton(
                    item["title"],
                    callback_data=f"tutorial_{item['id']}"
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="user_home"
            )
        ]
    )

    return InlineKeyboardMarkup(rows)
