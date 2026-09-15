from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu(config):
    buttons = []

    row = []

    if config.get("buy_enabled", True):
        row.append(
            KeyboardButton("🛒 خرید سرویس")
        )

    if config.get("renew_enabled", True):
        row.append(
            KeyboardButton("🔄 تمدید")
        )

    if row:
        buttons.append(row)

    row = []

    if config.get("subscriptions_enabled", True):
        row.append(
            KeyboardButton("📦 اشتراک‌های من")
        )

    if config.get("status_enabled", True):
        row.append(
            KeyboardButton("📊 وضعیت اشتراک")
        )

    if row:
        buttons.append(row)

    row = []

    if config.get("referral_enabled", True):
        row.append(
            KeyboardButton("👥 دعوت دوستان")
        )

    if config.get("coupon_enabled", True):
        row.append(
            KeyboardButton("🎟️ کد تخفیف")
        )

    if row:
        buttons.append(row)

    row = []

    if config.get("order_history_enabled", True):
        row.append(
            KeyboardButton("📜 تاریخچه سفارش‌ها")
        )

    if config.get("account_enabled", True):
        row.append(
            KeyboardButton("👤 حساب من")
        )

    if row:
        buttons.append(row)

    row = []

    if config.get("support_enabled", True):
        row.append(
            KeyboardButton("☎️ پشتیبانی")
        )

    if config.get("tutorial_enabled", True):
        row.append(
            KeyboardButton("📚 آموزش")
        )

    if row:
        buttons.append(row)

    if config.get("free_test_enabled", False):
        buttons.append([
            KeyboardButton("🎁 تست رایگان")
        ])

    if config.get("festival_enabled", False):
        buttons.append([
            KeyboardButton("🎉 جشنواره")
        ])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
        is_persistent=True
    )
