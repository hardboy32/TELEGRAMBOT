from pyrogram import filters, StopPropagation
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot.database import get_services
from bot.helpers import admin, format_price
from bot.user_handlers import user_states


PURCHASE_BUTTON = "🛒 خرید سرویس"


def _purchase_keyboard(services):
    rows = []

    for service in services:
        price = format_price(service["price"])
        label = (
            f"📦 {service['volume_gb']}GB | "
            f"💰 {price} تومان"
        )

        rows.append(
            [
                KeyboardButton(label)
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


def _purchase_text():
    return (
        "🛒 خرید سرویس جدید\n\n"
        "🌍 تمامی سرورها مولتی‌لوکیشن (چندسروره) هستند.\n"
        "👤 کاربر نامحدود\n"
        "⏳ زمان نامحدود\n\n"
        "📦 حجم و قیمت پلن موردنظر را انتخاب کنید:"
    )


def register(app, config):

    @app.on_message(
        filters.private
        & filters.text
        & filters.regex("^🛒 خرید سرویس$"),
        group=-19
    )
    async def purchase_display(client, message):

        user_id = message.from_user.id

        services = get_services(True)

        if not services:
            return

        services_map = {}

        for service in services:
            price = format_price(service["price"])
            label = (
                f"📦 {service['volume_gb']}GB | "
                f"💰 {price} تومان"
            )
            services_map[label] = service["id"]

        previous = user_states.get(user_id) or {}

        user_states[user_id] = {
            "step": "pick_service",
            "services_map": services_map,
            "order_type": "buy"
        }

        if previous.get("coupon"):
            user_states[user_id]["coupon"] = previous["coupon"]
            user_states[user_id]["discount"] = previous.get(
                "discount",
                0
            )

        await message.reply_text(
            _purchase_text(),
            reply_markup=_purchase_keyboard(services)
        )

        raise StopPropagation
