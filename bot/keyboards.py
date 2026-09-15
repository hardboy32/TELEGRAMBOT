from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu(config):
    buttons = []

    if config.get("buy_enabled", True):
        buttons.append([
            KeyboardButton("🛒 خرید سرویس")
        ])

    if config.get("renew_enabled", True):
        buttons.append([
            KeyboardButton("🔄 تمدید")
        ])

    if config.get("subscriptions_enabled", True):
        buttons.append([
            KeyboardButton("📦 اشتراک‌های من")
        ])

    if config.get("status_enabled", True):
        buttons.append([
            KeyboardButton("📊 وضعیت اشتراک")
        ])

    if config.get("referral_enabled", True):
        buttons.append([
            KeyboardButton("👥 دعوت دوستان")
        ])

    if config.get("coupon_enabled", True):
        buttons.append([
            KeyboardButton("🎟️ کد تخفیف")
        ])

    if config.get("order_history_enabled", True):
        buttons.append([
            KeyboardButton("📜 تاریخچه سفارش‌ها")
        ])

    if config.get("account_enabled", True):
        buttons.append([
            KeyboardButton("👤 حساب من")
        ])

    if config.get("support_enabled", True):
        buttons.append([
            KeyboardButton("☎️ پشتیبانی")
        ])

    if config.get("tutorial_enabled", True):
        buttons.append([
            KeyboardButton("📚 آموزش")
        ])

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
