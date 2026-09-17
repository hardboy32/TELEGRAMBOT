from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def main_menu(config, is_admin=False):

    buttons = []

    # خرید همیشه نمایش داده می‌شود.
    # باز یا بسته بودن فروش جداگانه کنترل می‌شود.
    buttons.append(
        KeyboardButton("🛒 خرید سرویس")
    )

    # تمدید همیشه نمایش داده می‌شود.
    # باز یا بسته بودن تمدید جداگانه کنترل می‌شود.
    buttons.append(
        KeyboardButton("🔄 تمدید")
    )

    # اشتراک‌های من
    # وضعیت اشتراک هم داخل همین قسمت نمایش داده می‌شود.
    if config.get(
        "subscriptions_enabled",
        True
    ):
        buttons.append(
            KeyboardButton("📦 اشتراک‌های من")
        )

    if config.get(
        "referral_enabled",
        True
    ):
        buttons.append(
            KeyboardButton("👥 دعوت دوستان")
        )

    if config.get(
        "coupon_enabled",
        True
    ):
        buttons.append(
            KeyboardButton("🎟️ کد تخفیف")
        )

    if config.get(
        "order_history_enabled",
        True
    ):
        buttons.append(
            KeyboardButton("📜 تاریخچه سفارش‌ها")
        )

    if config.get(
        "account_enabled",
        True
    ):
        buttons.append(
            KeyboardButton("👤 حساب من")
        )

    if config.get(
        "support_enabled",
        True
    ):
        buttons.append(
            KeyboardButton("☎️ پشتیبانی")
        )

    if config.get(
        "tutorial_enabled",
        True
    ):
        buttons.append(
            KeyboardButton("📚 آموزش")
        )

    if is_admin:

        buttons.append(
            KeyboardButton("⚙️ پنل مدیریت")
        )

        buttons.append(
            KeyboardButton("⏸ کنترل فروش")
        )

    if config.get(
        "free_test_enabled",
        False
    ):
        buttons.append(
            KeyboardButton("🎁 تست رایگان")
        )

    if config.get(
        "festival_enabled",
        False
    ):
        buttons.append(
            KeyboardButton("🎉 جشنواره")
        )

    rows = []

    for i in range(
        0,
        len(buttons),
        2
    ):
        rows.append(
            buttons[i:i + 2]
        )

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True
    )


def join_keyboard(channel):

    username = channel.replace(
        "@",
        ""
    )

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


def services_reply_keyboard(services):

    rows = []

    for service in services:

        rows.append(
            [
                KeyboardButton(
                    f"📦 {service['name']} | "
                    f"{service['volume_gb']}GB"
                )
            ]
        )

    rows.append(
        [
            KeyboardButton("⬅️ بازگشت")
        ]
    )

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True
    )


def confirm_reply_keyboard():
    return confirm_order_keyboard()


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
                    "❌ لغو سفارش",
                    callback_data="user_home"
                )
            ]
        ]
    )


def payment_reply_keyboard(
    is_admin=False
):

    rows = [
        [
            KeyboardButton(
                "❌ لغو سفارش"
            )
        ],
        [
            KeyboardButton(
                "🏠 منوی اصلی"
            )
        ]
    ]

    if is_admin:

        rows.append(
            [
                KeyboardButton(
                    "⚙️ پنل مدیریت"
                )
            ]
        )

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True
    )


def tutorials_reply_keyboard(
    tutorials
):

    rows = []

    for item in tutorials:

        rows.append(
            [
                KeyboardButton(
                    item["title"]
                )
            ]
        )

    rows.append(
        [
            KeyboardButton("⬅️ بازگشت")
        ]
    )

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True
    )


def subscriptions_reply_keyboard(
    subscriptions,
    prefix="📦"
):

    rows = []

    for sub in subscriptions:

        username = (
            sub.get("username")
            or "بدون نام کاربری"
        )

        rows.append(
            [
                KeyboardButton(
                    f"{prefix} "
                    f"{sub['service_name']} | "
                    f"@{username}"
                )
            ]
        )

    rows.append(
        [
            KeyboardButton("⬅️ بازگشت")
        ]
    )

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True
    )


def order_admin_keyboard(
    order_id
):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تأیید",
                    callback_data=f"approve_{order_id}"
                ),
                InlineKeyboardButton(
                    "❌ رد",
                    callback_data=f"reject_{order_id}"
                )
            ]
        ]
    )


def services_keyboard(services):
    return services_reply_keyboard(
        services
    )


def payment_keyboard(is_admin=False):
    return payment_reply_keyboard(
        is_admin
    )


def subscriptions_keyboard(
    subscriptions
):
    return subscriptions_reply_keyboard(
        subscriptions,
        "📦"
    )


def renew_keyboard(subscriptions):
    return subscriptions_reply_keyboard(
        subscriptions,
        "🔄"
    )


def tutorials_keyboard(tutorials):
    return tutorials_reply_keyboard(
        tutorials
    )


def back_home_keyboard():

    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "🏠 منوی اصلی"
                )
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )
