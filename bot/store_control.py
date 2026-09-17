import json

from pyrogram import filters, StopPropagation
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from bot.database import (
    get_user_subscriptions
)

from bot.helpers import (
    admin,
    save_config
)


def _is_purchase_open(config):
    return bool(
        config.get(
            "purchase_open",
            True
        )
    )


def _is_renew_open(config):
    return bool(
        config.get(
            "renew_open",
            True
        )
    )


def _save(config):
    try:
        save_config(
            config,
            "config.json"
        )
        return True
    except Exception as e:
        print(
            f"Store control save error: {e}"
        )
        return False


def _control_keyboard(config):
    purchase = _is_purchase_open(config)
    renew = _is_renew_open(config)

    purchase_status = (
        "🟢 باز"
        if purchase
        else "🔴 بسته"
    )

    renew_status = (
        "🟢 باز"
        if renew
        else "🔴 بسته"
    )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🛒 خرید: {purchase_status}",
                    callback_data="store_toggle_purchase"
                )
            ],
            [
                InlineKeyboardButton(
                    f"🔄 تمدید: {renew_status}",
                    callback_data="store_toggle_renew"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 بروزرسانی",
                    callback_data="store_control"
                )
            ]
        ]
    )


def _control_text(config):
    purchase = _is_purchase_open(config)
    renew = _is_renew_open(config)

    purchase_status = (
        "🟢 باز است"
        if purchase
        else "🔴 فعلاً بسته است"
    )

    renew_status = (
        "🟢 باز است"
        if renew
        else "🔴 فعلاً بسته است"
    )

    return (
        "⏸ کنترل فروش\n\n"
        f"🛒 خرید سرویس: {purchase_status}\n"
        f"🔄 تمدید سرویس: {renew_status}\n\n"
        "از دکمه‌های زیر وضعیت هرکدام را "
        "مستقل تغییر دهید."
    )


def register(app, config):

    # =========================================================
    # کنترل فروش برای ادمین
    # =========================================================

    @app.on_message(
        filters.private
        & filters.text
        & filters.regex("^⏸ کنترل فروش$"),
        group=-20
    )
    async def store_control_message(
        client,
        message
    ):

        if not admin(
            message.from_user.id,
            config
        ):
            return

        await message.reply_text(
            _control_text(config),
            reply_markup=_control_keyboard(config)
        )

        raise StopPropagation

    # =========================================================
    # خرید
    # =========================================================

    @app.on_message(
        filters.private
        & filters.text
        & filters.regex("^🛒 خرید سرویس$"),
        group=-20
    )
    async def purchase_gate(
        client,
        message
    ):

        if not _is_purchase_open(config):

            await message.reply_text(
                "⛔ فروش فعلاً بسته است.\n\n"
                "لطفاً کمی بعد دوباره تلاش کنید."
            )

            raise StopPropagation

    # =========================================================
    # تمدید
    # =========================================================

    @app.on_message(
        filters.private
        & filters.text
        & filters.regex("^🔄 تمدید$"),
        group=-20
    )
    async def renew_gate(
        client,
        message
    ):

        if not _is_renew_open(config):

            await message.reply_text(
                "⛔ تمدید فعلاً بسته است.\n\n"
                "لطفاً کمی بعد دوباره تلاش کنید."
            )

            raise StopPropagation

    # =========================================================
    # اشتراک‌های من
    # =========================================================

    @app.on_message(
        filters.private
        & filters.text
        & filters.regex("^📦 اشتراک‌های من$"),
        group=-20
    )
    async def my_subscriptions(
        client,
        message
    ):

        user_id = message.from_user.id

        subscriptions = get_user_subscriptions(
            user_id
        )

        if not subscriptions:

            await message.reply_text(
                "📦 شما هنوز اشتراکی ندارید."
            )

            raise StopPropagation

        rows = []

        text_lines = [
            "📦 اشتراک‌های شما:\n"
        ]

        for index, sub in enumerate(
            subscriptions,
            start=1
        ):

            service_name = (
                sub.get("service_name")
                or "سرویس"
            )

            username = (
                sub.get("username")
                or "بدون نام کاربری"
            )

            status = (
                sub.get("status")
                or "unknown"
            )

            if status == "active":
                status_text = "🟢 فعال"

            elif status in (
                "expired",
                "inactive",
                "disabled"
            ):
                status_text = "🔴 غیرفعال"

            elif status == "pending":
                status_text = "🟡 در انتظار"

            else:
                status_text = f"🔵 {status}"

            text_lines.append(
                f"{index}. 📦 {service_name}\n"
                f"   👤 @{username}\n"
                f"   وضعیت: {status_text}\n"
            )

            subscription_url = (
                sub.get("subscription_url")
            )

            if subscription_url:

                rows.append(
                    [
                        InlineKeyboardButton(
                            (
                                f"{index}️⃣ "
                                f"📦 {service_name} | "
                                f"@{username}"
                            ),
                            url=subscription_url
                        )
                    ]
                )

        await message.reply_text(
            "\n".join(text_lines),
            reply_markup=(
                InlineKeyboardMarkup(rows)
                if rows
                else None
            )
        )

        raise StopPropagation

    # =========================================================
    # نمایش پنل کنترل
    # =========================================================

    @app.on_callback_query(
        filters.regex("^store_control$"),
        group=-20
    )
    async def store_control_callback(
        client,
        query
    ):

        if not admin(
            query.from_user.id,
            config
        ):
            await query.answer(
                "دسترسی ندارید.",
                show_alert=True
            )
            return

        await query.answer()

        try:

            await query.message.edit_text(
                _control_text(config),
                reply_markup=_control_keyboard(
                    config
                )
            )

        except Exception as e:

            print(
                f"Store control edit error: {e}"
            )

    # =========================================================
    # باز / بسته کردن خرید
    # =========================================================

    @app.on_callback_query(
        filters.regex("^store_toggle_purchase$"),
        group=-20
    )
    async def toggle_purchase(
        client,
        query
    ):

        if not admin(
            query.from_user.id,
            config
        ):
            await query.answer(
                "دسترسی ندارید.",
                show_alert=True
            )
            return

        await query.answer()

        current = _is_purchase_open(
            config
        )

        config["purchase_open"] = not current

        _save(config)

        await query.message.edit_text(
            _control_text(config),
            reply_markup=_control_keyboard(
                config
            )
        )

    # =========================================================
    # باز / بسته کردن تمدید
    # =========================================================

    @app.on_callback_query(
        filters.regex("^store_toggle_renew$"),
        group=-20
    )
    async def toggle_renew(
        client,
        query
    ):

        if not admin(
            query.from_user.id,
            config
        ):
            await query.answer(
                "دسترسی ندارید.",
                show_alert=True
            )
            return

        await query.answer()

        current = _is_renew_open(
            config
        )

        config["renew_open"] = not current

        _save(config)

        await query.message.edit_text(
            _control_text(config),
            reply_markup=_control_keyboard(
                config
            )
        )
