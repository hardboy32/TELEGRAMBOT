import os
from pyrogram import filters, StopPropagation
from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from bot.helpers import admin, format_price, save_config

from bot.backup import (
    create_backup,
    inspect_backup,
    restore_backup
)

from bot.database import (
    get_pending_orders,
    get_order,
    approve_order,
    reject_order,
    save_subscription,
    add_service,
    get_services,
    toggle_service,
    get_users_count,
    get_orders_count,
    get_all_user_ids,
    create_coupon,
    get_pending_rewards,
    mark_reward_applied,
    get_referrer,
    record_successful_referral,
    get_referral_count
)


admin_states = {}


def admin_reply_menu():
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("⚙️ پنل مدیریت")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


def admin_panel_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🧾 سفارش‌های در انتظار",
                    callback_data="admin_pending"
                )
            ],
            [
                InlineKeyboardButton(
                    "📦 مدیریت سرویس‌ها",
                    callback_data="admin_services"
                )
            ],
            [
                InlineKeyboardButton(
                    "👥 کاربران",
                    callback_data="admin_users"
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 آمار",
                    callback_data="admin_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎟️ کد تخفیف",
                    callback_data="admin_coupon"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎁 پاداش‌های دعوت",
                    callback_data="admin_rewards"
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
                    "⚙️ تنظیمات دکمه‌ها",
                    callback_data="admin_buttons"
                )
            ],
            [
                InlineKeyboardButton(
                    "💳 تنظیمات پرداخت",
                    callback_data="admin_payment"
                )
            ],
            [
                InlineKeyboardButton(
                    "💾 پشتیبان‌گیری",
                    callback_data="admin_backup"
                )
            ],
            [
                InlineKeyboardButton(
                    "♻️ بازگردانی بکاپ",
                    callback_data="admin_restore"
                )
            ]
        ]
    )


def restore_confirm_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تأیید بازگردانی",
                    callback_data="admin_restore_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ لغو",
                    callback_data="admin_home"
                )
            ]
        ]
    )


def back_admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="admin_home"
                )
            ]
        ]
    )


def service_admin_keyboard(services):
    rows = []

    for service in services:
        status = "🟢" if service["active"] else "🔴"

        rows.append(
            [
                InlineKeyboardButton(
                    f"{status} {service['name']} | "
                    f"{service['volume_gb']}GB",
                    callback_data=f"admin_service_{service['id']}"
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "➕ افزودن سرویس",
                callback_data="admin_add_service"
            )
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                "⬅️ بازگشت",
                callback_data="admin_home"
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


def order_keyboard(order_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تأیید پرداخت",
                    callback_data=f"admin_approve_{order_id}"
                ),
                InlineKeyboardButton(
                    "❌ رد پرداخت",
                    callback_data=f"admin_reject_{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ ثبت کانفیگ",
                    callback_data=f"admin_config_{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="admin_pending"
                )
            ]
        ]
    )


def buttons_keyboard(config):
    items = [
        ("buy_enabled", "🛒 خرید سرویس"),
        ("renew_enabled", "🔄 تمدید"),
        ("subscriptions_enabled", "📦 اشتراک‌های من"),
        ("status_enabled", "📊 وضعیت اشتراک"),
        ("referral_enabled", "👥 دعوت دوستان"),
        ("coupon_enabled", "🎟️ کد تخفیف"),
        ("order_history_enabled", "📜 تاریخچه سفارش‌ها"),
        ("account_enabled", "👤 حساب من"),
        ("support_enabled", "☎️ پشتیبانی"),
        ("tutorial_enabled", "📚 آموزش"),
        ("free_test_enabled", "🎁 تست رایگان"),
        ("festival_enabled", "🎉 جشنواره")
    ]

    rows = []

    for key, title in items:
        enabled = bool(config.get(key, False))
        status = "🟢" if enabled else "🔴"

        rows.append(
            [
                InlineKeyboardButton(
                    f"{status} {title}",
                    callback_data=f"admin_toggle_{key}"
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "⬅️ بازگشت",
                callback_data="admin_home"
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


def register(app, config):

    # =========================================================
    # /start برای ادمین
    # =========================================================

    @app.on_message(
        filters.private & filters.command("start"),
        group=-1
    )
    async def admin_start(client, message):

        user_id = message.from_user.id

        if not admin(user_id, config):
            return

        await message.reply_text(
            "👋 سلام ادمین عزیز.\n\n"
            "⚙️ پنل مدیریت برای شما فعال است.",
            reply_markup=admin_reply_menu()
        )

        await message.reply_text(
            "⚙️ پنل مدیریت",
            reply_markup=admin_panel_keyboard()
        )

        raise StopPropagation

    # =========================================================
    # /admin
    # =========================================================

    @app.on_message(
        filters.private & filters.command("admin"),
        group=-1
    )
    async def admin_command(client, message):

        user_id = message.from_user.id

        if not admin(user_id, config):
            return

        await message.reply_text(
            "⚙️ پنل مدیریت",
            reply_markup=admin_reply_menu()
        )

        await message.reply_text(
            "از منوی مدیریت انتخاب کنید:",
            reply_markup=admin_panel_keyboard()
        )

        raise StopPropagation

    # =========================================================
    # پیام‌های متنی ادمین
    # =========================================================

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(["start", "admin"]),
        group=-1
    )
    async def admin_text(client, message):

        user_id = message.from_user.id

        if not admin(user_id, config):
            return

        text = message.text.strip()

        # =====================================================
        # دکمه ثابت پنل مدیریت
        # =====================================================

        if text == "⚙️ پنل مدیریت":

            admin_states.pop(
                user_id,
                None
            )

            await message.reply_text(
                "⚙️ پنل مدیریت",
                reply_markup=admin_panel_keyboard()
            )

            raise StopPropagation

        state = admin_states.get(user_id)

        # =====================================================
        # اگر ادمین در هیچ حالت مدیریتی نیست،
        # پیام باید توسط user_handlers پردازش شود.
        #
        # این قسمت عمداً StopPropagation ندارد.
        # بنابراین ادمین می‌تواند مثل کاربر خرید کند.
        # =====================================================

        if not state:
            return

        step = state.get("step")

        # =====================================================
        # ساخت سرویس - نام
        # =====================================================

        if step == "service_name":

            state["name"] = text
            state["step"] = "service_volume"

            await message.reply_text(
                "💾 حجم سرویس را به GB وارد کنید:"
            )

            raise StopPropagation

        # =====================================================
        # ساخت سرویس - حجم
        # =====================================================

        if step == "service_volume":

            try:
                volume = int(text)

                if volume <= 0:
                    raise ValueError

            except ValueError:

                await message.reply_text(
                    "❌ حجم باید یک عدد مثبت باشد."
                )

                raise StopPropagation

            state["volume"] = volume
            state["step"] = "service_price"

            await message.reply_text(
                "💰 قیمت سرویس را به تومان وارد کنید:"
            )

            raise StopPropagation

        # =====================================================
        # ساخت سرویس - قیمت
        # =====================================================

        if step == "service_price":

            try:
                price = int(text)

                if price < 0:
                    raise ValueError

            except ValueError:

                await message.reply_text(
                    "❌ قیمت باید یک عدد صحیح مثبت باشد."
                )

                raise StopPropagation

            name = state["name"]
            volume = state["volume"]

            service_id = add_service(
                name,
                volume,
                price
            )

            admin_states.pop(
                user_id,
                None
            )

            await message.reply_text(
                "✅ سرویس با موفقیت اضافه شد.\n\n"
                f"🆔 شناسه: {service_id}\n"
                f"📦 نام: {name}\n"
                f"💾 حجم: {volume}GB\n"
                f"💰 قیمت: {format_price(price)} تومان",
                reply_markup=admin_reply_menu()
            )

            raise StopPropagation

        # =====================================================
        # ثبت کانفیگ
        # =====================================================

        if step == "config":

            order_id = state["order_id"]

            order = get_order(order_id)

            if not order:

                admin_states.pop(
                    user_id,
                    None
                )

                await message.reply_text(
                    "❌ سفارش پیدا نشد."
                )

                raise StopPropagation

            config_text = text

            save_subscription(
                user_id=order["user_id"],
                order_id=order["id"],
                service_name=order["service_name"],
                username=order["username"],
                subscription_url=None,
                config_text=config_text
            )

            approve_order(order_id)

            admin_states.pop(
                user_id,
                None
            )

            try:

                await client.send_message(
                    order["user_id"],
                    "🎉 سفارش شما تأیید شد!\n\n"
                    f"🧾 سفارش: #{order_id}\n"
                    f"📦 سرویس: {order['service_name']}\n"
                    f"👤 نام کاربری: @{order['username']}\n\n"
                    "⚙️ کانفیگ شما:\n\n"
                    f"{config_text}\n\n"
                    "✅ اشتراک شما فعال شد."
                )

            except Exception as e:

                print(
                    f"Config send error: {e}"
                )

            referrer = get_referrer(
                order["user_id"]
            )

            if referrer:

                recorded = record_successful_referral(
                    referrer,
                    order["user_id"],
                    order["id"]
                )

                if recorded:

                    count = get_referral_count(
                        referrer
                    )

                    if count > 0 and count % 5 == 0:

                        from bot.database import create_referral_reward

                        create_referral_reward(
                            referrer
                        )

                        try:

                            await client.send_message(
                                referrer,
                                "🎉 تبریک!\n\n"
                                "۵ دعوت موفق برای شما ثبت شد.\n"
                                "🎁 پاداش ۱۰GB برای شما ایجاد شد.\n\n"
                                "این حجم توسط مدیریت به صورت دستی اعمال می‌شود."
                            )

                        except Exception:
                            pass

            await message.reply_text(
                f"✅ کانفیگ سفارش #{order_id} ثبت شد.\n"
                "و برای مشتری ارسال گردید.",
                reply_markup=admin_reply_menu()
            )

            raise StopPropagation

        # =====================================================
        # ساخت کد تخفیف
        # =====================================================

        if step == "coupon":

            parts = text.split()

            if len(parts) < 2:

                await message.reply_text(
                    "❌ فرمت صحیح:\n\n"
                    "CODE PERCENT MAX_USES\n\n"
                    "مثال:\n"
                    "HERMES20 20 100"
                )

                raise StopPropagation

            code = parts[0].upper()

            try:

                percent = int(parts[1])

                max_uses = (
                    int(parts[2])
                    if len(parts) >= 3
                    else 0
                )

                if percent < 1 or percent > 100:
                    raise ValueError

                if max_uses < 0:
                    raise ValueError

            except ValueError:

                await message.reply_text(
                    "❌ اطلاعات کد تخفیف نامعتبر است."
                )

                raise StopPropagation

            result = create_coupon(
                code,
                percent,
                max_uses
            )

            admin_states.pop(
                user_id,
                None
            )

            if result:

                max_text = (
                    str(max_uses)
                    if max_uses > 0
                    else "نامحدود"
                )

                await message.reply_text(
                    "✅ کد تخفیف ساخته شد.\n\n"
                    f"🎟️ کد: {code}\n"
                    f"📉 تخفیف: {percent}%\n"
                    f"🔢 تعداد استفاده: {max_text}",
                    reply_markup=admin_reply_menu()
                )

            else:

                await message.reply_text(
                    "❌ این کد تخفیف قبلاً وجود دارد.",
                    reply_markup=admin_reply_menu()
                )

            raise StopPropagation

        # =====================================================
        # کارت پرداخت
        # =====================================================

        if step == "payment_card":

            config["payment_card"] = text

            admin_states[user_id] = {
                "step": "payment_name"
            }

            await message.reply_text(
                "👤 نام صاحب کارت را وارد کنید:"
            )

            raise StopPropagation

        # =====================================================
        # نام صاحب کارت
        # =====================================================

        if step == "payment_name":

            config["payment_name"] = text

            save_config(config)

            admin_states.pop(
                user_id,
                None
            )

            await message.reply_text(
                "✅ اطلاعات پرداخت ذخیره شد.",
                reply_markup=admin_reply_menu()
            )

            raise StopPropagation

        # =====================================================
        # پیام همگانی
        # =====================================================

        if step == "broadcast":

            admin_states.pop(
                user_id,
                None
            )

            user_ids = get_all_user_ids()

            success = 0
            failed = 0

            await message.reply_text(
                f"📢 ارسال پیام به {len(user_ids)} کاربر شروع شد..."
            )

            for target_id in user_ids:

                try:

                    await client.send_message(
                        target_id,
                        text
                    )

                    success += 1

                except Exception:

                    failed += 1

            await message.reply_text(
                "📢 پیام همگانی تمام شد.\n\n"
                f"✅ موفق: {success}\n"
                f"❌ ناموفق: {failed}",
                reply_markup=admin_reply_menu()
            )

            raise StopPropagation

        # اگر حالت مدیریتی ناشناخته بود
        admin_states.pop(
            user_id,
            None
        )

        raise StopPropagation

    # =========================================================
    # پنل اصلی
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_home$")
    )
    async def admin_home(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            await query.answer(
                "❌ دسترسی ندارید.",
                show_alert=True
            )
            return

        admin_states.pop(
            query.from_user.id,
            None
        )

        await query.message.edit_text(
            "⚙️ پنل مدیریت",
            reply_markup=admin_panel_keyboard()
        )

        await query.answer()

    # =========================================================
    # سفارش‌های در انتظار
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_pending$")
    )
    async def admin_pending(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        orders = get_pending_orders()

        if not orders:

            await query.message.edit_text(
                "🧾 هیچ سفارش در انتظاری وجود ندارد.",
                reply_markup=back_admin_keyboard()
            )

            await query.answer()
            return

        rows = []

        for order in orders:

            rows.append(
                [
                    InlineKeyboardButton(
                        f"#{order['id']} | "
                        f"{order['service_name']} | "
                        f"{format_price(order['final_price'])}",
                        callback_data=f"admin_order_{order['id']}"
                    )
                ]
            )

        rows.append(
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="admin_home"
                )
            ]
        )

        await query.message.edit_text(
            "🧾 سفارش‌های در انتظار:",
            reply_markup=InlineKeyboardMarkup(rows)
        )

        await query.answer()

    # =========================================================
    # جزئیات سفارش
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^admin_order_\d+$")
    )
    async def admin_order(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        order_id = int(
            query.data.split("_")[-1]
        )

        order = get_order(order_id)

        if not order:

            await query.answer(
                "❌ سفارش پیدا نشد.",
                show_alert=True
            )

            return

        text = (
            "🧾 جزئیات سفارش\n\n"
            f"🆔 شماره: #{order['id']}\n"
            f"👤 شناسه کاربر: {order['user_id']}\n"
            f"📦 سرویس: {order['service_name']}\n"
            f"👤 نام کاربری: @{order['username']}\n"
            f"💰 قیمت اصلی: "
            f"{format_price(order['original_price'])} تومان\n"
            f"🎟️ تخفیف: {order['discount_percent']}%\n"
            f"💵 مبلغ نهایی: "
            f"{format_price(order['final_price'])} تومان\n"
            f"🔵 وضعیت: {order['status']}\n"
            f"📅 تاریخ: {order['created_at']}"
        )

        await query.message.edit_text(
            text,
            reply_markup=order_keyboard(order_id)
        )

        if order.get("receipt_file_id"):

            try:

                await client.send_photo(
                    query.from_user.id,
                    order["receipt_file_id"],
                    caption=f"🧾 رسید سفارش #{order_id}"
                )

            except Exception as e:

                print(
                    f"Receipt send error: {e}"
                )

        await query.answer()

    # =========================================================
    # تأیید پرداخت
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^admin_approve_\d+$")
    )
    async def admin_approve(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        order_id = int(
            query.data.split("_")[-1]
        )

        order = get_order(order_id)

        if not order:

            await query.answer(
                "❌ سفارش پیدا نشد.",
                show_alert=True
            )

            return

        if order["status"] != "pending":

            await query.answer(
                "⚠️ این سفارش قبلاً بررسی شده.",
                show_alert=True
            )

            return

        approve_order(order_id)

        try:

            await client.send_message(
                order["user_id"],
                "✅ پرداخت شما تأیید شد.\n\n"
                f"🧾 سفارش: #{order_id}\n\n"
                "⏳ حالا ادمین باید کانفیگ شما را ثبت کند."
            )

        except Exception as e:

            print(
                f"Approve notification error: {e}"
            )

        await query.message.reply_text(
            f"✅ پرداخت سفارش #{order_id} تأیید شد.\n\n"
            "حالا روی «⚙️ ثبت کانفیگ» بزنید."
        )

        await query.answer(
            "پرداخت تأیید شد."
        )

    # =========================================================
    # رد پرداخت
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^admin_reject_\d+$")
    )
    async def admin_reject(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        order_id = int(
            query.data.split("_")[-1]
        )

        order = get_order(order_id)

        if not order:

            await query.answer(
                "❌ سفارش پیدا نشد.",
                show_alert=True
            )

            return

        if order["status"] != "pending":

            await query.answer(
                "⚠️ این سفارش قبلاً بررسی شده.",
                show_alert=True
            )

            return

        reject_order(order_id)

        try:

            await client.send_message(
                order["user_id"],
                "❌ رسید پرداخت شما رد شد.\n\n"
                f"🧾 سفارش: #{order_id}\n\n"
                "در صورت نیاز دوباره سفارش ثبت کنید."
            )

        except Exception as e:

            print(
                f"Reject notification error: {e}"
            )

        await query.message.reply_text(
            f"❌ سفارش #{order_id} رد شد."
        )

        await query.answer(
            "سفارش رد شد."
        )

    # =========================================================
    # ثبت کانفیگ
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^admin_config_\d+$")
    )
    async def admin_config(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        order_id = int(
            query.data.split("_")[-1]
        )

        order = get_order(order_id)

        if not order:

            await query.answer(
                "❌ سفارش پیدا نشد.",
                show_alert=True
            )

            return

        admin_states[
            query.from_user.id
        ] = {
            "step": "config",
            "order_id": order_id
        }

        await query.message.reply_text(
            f"⚙️ ثبت کانفیگ سفارش #{order_id}\n\n"
            "لینک اشتراک یا کانفیگ را همینجا ارسال کنید:"
        )

        await query.answer()

    # =========================================================
    # مدیریت سرویس‌ها
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_services$")
    )
    async def admin_services(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        services = get_services(False)

        await query.message.edit_text(
            "📦 مدیریت سرویس‌ها",
            reply_markup=service_admin_keyboard(
                services
            )
        )

        await query.answer()

    # =========================================================
    # فعال/غیرفعال کردن سرویس
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^admin_service_\d+$")
    )
    async def admin_service_toggle(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        service_id = int(
            query.data.split("_")[-1]
        )

        new_state = toggle_service(
            service_id
        )

        services = get_services(False)

        await query.message.edit_text(
            "📦 مدیریت سرویس‌ها",
            reply_markup=service_admin_keyboard(
                services
            )
        )

        await query.answer(
            "🟢 سرویس فعال شد."
            if new_state
            else "🔴 سرویس غیرفعال شد."
        )

    # =========================================================
    # افزودن سرویس
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_add_service$")
    )
    async def admin_add_service(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        admin_states[
            query.from_user.id
        ] = {
            "step": "service_name"
        }

        await query.message.reply_text(
            "➕ افزودن سرویس\n\n"
            "نام سرویس را وارد کنید:"
        )

        await query.answer()

    # =========================================================
    # کاربران
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_users$")
    )
    async def admin_users(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        count = get_users_count()

        await query.message.edit_text(
            "👥 کاربران\n\n"
            f"تعداد کاربران ثبت‌شده: {count}",
            reply_markup=back_admin_keyboard()
        )

        await query.answer()

    # =========================================================
    # آمار
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_stats$")
    )
    async def admin_stats(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        users = get_users_count()
        orders = get_orders_count()
        pending = len(
            get_pending_orders()
        )
        services = len(
            get_services(True)
        )

        await query.message.edit_text(
            "📊 آمار ربات\n\n"
            f"👥 کاربران: {users}\n"
            f"🧾 کل سفارش‌ها: {orders}\n"
            f"⏳ سفارش‌های در انتظار: {pending}\n"
            f"📦 سرویس‌های فعال: {services}",
            reply_markup=back_admin_keyboard()
        )

        await query.answer()

    # =========================================================
    # کد تخفیف
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_coupon$")
    )
    async def admin_coupon(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        admin_states[
            query.from_user.id
        ] = {
            "step": "coupon"
        }

        await query.message.reply_text(
            "🎟️ ساخت کد تخفیف\n\n"
            "فرمت:\n"
            "CODE PERCENT MAX_USES\n\n"
            "مثال:\n"
            "HERMES20 20 100\n\n"
            "برای استفاده نامحدود، عدد 0 را بزنید."
        )

        await query.answer()

    # =========================================================
    # پاداش دعوت
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_rewards$")
    )
    async def admin_rewards(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        rewards = get_pending_rewards()

        if not rewards:

            await query.message.edit_text(
                "🎁 پاداش در انتظاری وجود ندارد.",
                reply_markup=back_admin_keyboard()
            )

            await query.answer()
            return

        rows = []

        for reward in rewards:

            rows.append(
                [
                    InlineKeyboardButton(
                        f"🎁 #{reward['id']} | "
                        f"کاربر {reward['user_id']} | 10GB",
                        callback_data=f"admin_reward_{reward['id']}"
                    )
                ]
            )

        rows.append(
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="admin_home"
                )
            ]
        )

        await query.message.edit_text(
            "🎁 پاداش‌های در انتظار:",
            reply_markup=InlineKeyboardMarkup(rows)
        )

        await query.answer()

    # =========================================================
    # اعمال پاداش
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^admin_reward_\d+$")
    )
    async def admin_reward(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        reward_id = int(
            query.data.split("_")[-1]
        )

        mark_reward_applied(
            reward_id
        )

        await query.answer(
            "پاداش ثبت شد."
        )

        await query.message.reply_text(
            "✅ پاداش به عنوان اعمال‌شده ثبت شد.\n\n"
            "⚠️ حجم ۱۰GB باید در پنل هرمس "
            "به صورت دستی برای کاربر اعمال شود."
        )

    # =========================================================
    # پیام همگانی
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_broadcast$")
    )
    async def admin_broadcast(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        admin_states[
            query.from_user.id
        ] = {
            "step": "broadcast"
        }

        await query.message.reply_text(
            "📢 متن پیام همگانی را ارسال کنید:"
        )

        await query.answer()

    # =========================================================
    # تنظیمات دکمه‌ها
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_buttons$")
    )
    async def admin_buttons(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        await query.message.edit_text(
            "⚙️ تنظیمات دکمه‌های کاربر",
            reply_markup=buttons_keyboard(config)
        )

        await query.answer()

    # =========================================================
    # روشن/خاموش کردن دکمه
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^admin_toggle_.+$")
    )
    async def admin_toggle(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        key = query.data.replace(
            "admin_toggle_",
            "",
            1
        )

        if key not in config:

            await query.answer(
                "❌ تنظیمات پیدا نشد.",
                show_alert=True
            )

            return

        config[key] = not bool(
            config.get(key, False)
        )

        save_config(config)

        await query.message.edit_text(
            "⚙️ تنظیمات دکمه‌های کاربر",
            reply_markup=buttons_keyboard(config)
        )

        await query.answer(
            "✅ تنظیمات تغییر کرد."
        )

    # =========================================================
    # تنظیمات پرداخت
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_payment$")
    )
    async def admin_payment(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        admin_states[
            query.from_user.id
        ] = {
            "step": "payment_card"
        }

        await query.message.reply_text(
            "💳 شماره کارت جدید را وارد کنید:"
        )

        await query.answer()

    # =========================================================
    # پشتیبان‌گیری
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_backup$")
    )
    async def admin_backup(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            await query.answer(
                "❌ دسترسی ندارید.",
                show_alert=True
            )
            return

        await query.answer(
            "در حال ساخت بکاپ..."
        )

        try:

            zip_path = create_backup(config)

            await client.send_document(
                query.from_user.id,
                zip_path,
                caption=(
                    "💾 بکاپ کامل کافه هرمس\n\n"
                    "این فایل شامل دیتابیس کاربران، "
                    "سفارش‌ها، اشتراک‌ها و تنظیمات است.\n\n"
                    "حتماً آن را در Saved Messages "
                    "یا جای امن ذخیره کنید.\n"
                    "اگر Infrlo قطع شد، با همین فایل "
                    "می‌توانید همه چیز را برگردانید."
                )
            )

            await query.message.reply_text(
                "✅ بکاپ ساخته شد و برایتان ارسال گردید.",
                reply_markup=admin_reply_menu()
            )

        except Exception as e:

            await query.message.reply_text(
                f"❌ خطا در ساخت بکاپ:\n{e}",
                reply_markup=admin_reply_menu()
            )

    # =========================================================
    # شروع بازگردانی
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_restore$")
    )
    async def admin_restore(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            await query.answer(
                "❌ دسترسی ندارید.",
                show_alert=True
            )
            return

        admin_states[
            query.from_user.id
        ] = {
            "step": "restore_backup"
        }

        await query.message.reply_text(
            "♻️ بازگردانی بکاپ\n\n"
            "فایل zip بکاپ را همینجا ارسال کنید.\n\n"
            "⚠️ با تأیید نهایی، اطلاعات فعلی "
            "با اطلاعات داخل بکاپ جایگزین می‌شود.\n"
            "قبل از جایگزینی، یک کپی از دیتابیس فعلی "
            "به صورت خودکار نگه داشته می‌شود."
        )

        await query.answer()

    # =========================================================
    # دریافت فایل بکاپ
    # =========================================================

    @app.on_message(
        filters.private & filters.document,
        group=-1
    )
    async def admin_restore_file(client, message):

        user_id = message.from_user.id

        if not admin(user_id, config):
            return

        state = admin_states.get(user_id)

        if not state or state.get("step") != "restore_backup":
            return

        doc = message.document

        file_name = (doc.file_name or "").lower()

        if not file_name.endswith(".zip"):

            await message.reply_text(
                "❌ فقط فایل zip بکاپ قبول است."
            )

            raise StopPropagation

        if doc.file_size and doc.file_size > 20 * 1024 * 1024:

            await message.reply_text(
                "❌ حجم فایل بیش از ۲۰ مگابایت است."
            )

            raise StopPropagation

        os.makedirs("data/backups", exist_ok=True)

        saved = await client.download_media(
            message.document,
            file_name="data/backups/incoming_restore.zip"
        )

        info = inspect_backup(saved)

        if not info.get("ok"):

            await message.reply_text(
                f"❌ {info.get('message', 'بکاپ نامعتبر است.')}"
            )

            raise StopPropagation

        admin_states[user_id] = {
            "step": "restore_confirm",
            "zip_path": saved
        }

        config_text = (
            "بله"
            if info.get("has_config")
            else "خیر"
        )

        await message.reply_text(
            "📦 مشخصات بکاپ:\n\n"
            f"👥 کاربران: {info['users']}\n"
            f"🧾 سفارش‌ها: {info['orders']}\n"
            f"📦 سرویس‌ها: {info['services']}\n"
            f"🔗 اشتراک‌ها: {info['subscriptions']}\n"
            f"⚙️ فایل تنظیمات: {config_text}\n\n"
            "اگر مورد تأیید است، بازگردانی را تأیید کنید.",
            reply_markup=restore_confirm_keyboard()
        )

        raise StopPropagation

    # =========================================================
    # تأیید بازگردانی
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_restore_confirm$")
    )
    async def admin_restore_confirm(client, query):

        user_id = query.from_user.id

        if not admin(user_id, config):
            await query.answer(
                "❌ دسترسی ندارید.",
                show_alert=True
            )
            return

        state = admin_states.get(user_id)

        if not state or state.get("step") != "restore_confirm":
            await query.answer(
                "❌ درخواست بازگردانی منقضی شده.",
                show_alert=True
            )
            return

        zip_path = state.get("zip_path")

        result = restore_backup(zip_path, config)

        admin_states.pop(user_id, None)

        if not result.get("ok"):

            await query.message.reply_text(
                f"❌ {result.get('message', 'بازگردانی ناموفق بود.')}",
                reply_markup=admin_reply_menu()
            )

            await query.answer()
            return

        await query.message.reply_text(
            "✅ بکاپ با موفقیت بازگردانی شد.\n\n"
            f"👥 کاربران: {result.get('users', 0)}\n"
            f"🧾 سفارش‌ها: {result.get('orders', 0)}\n"
            f"📦 سرویس‌ها: {result.get('services', 0)}\n"
            f"🔗 اشتراک‌ها: {result.get('subscriptions', 0)}\n\n"
            "اطلاعات قبلی در پوشه data با پسوند "
            "before_restore نگه داشته شد.",
            reply_markup=admin_reply_menu()
        )

        await query.answer(
            "بازگردانی انجام شد."
        )
