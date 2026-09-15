import asyncio
import json

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .database import (
    get_pending_orders,
    get_order,
    approve_order,
    reject_order,
    save_subscription,
    get_services,
    add_service,
    toggle_service,
    get_users_count,
    get_orders_count,
    get_user,
    create_coupon,
    get_all_user_ids,
    get_referrer,
    record_successful_referral,
)


# =========================================================
# ابزارهای کمکی
# =========================================================

def is_admin(user_id, config):
    return user_id in config.get("admin_ids", [])


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
                "📦 مدیریت سرویس‌ها",
                callback_data="admin_services"
            ),
            InlineKeyboardButton(
                "🎟️ کدهای تخفیف",
                callback_data="admin_coupons"
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
                "🎛️ مدیریت دکمه‌ها",
                callback_data="admin_buttons"
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ تنظیمات پرداخت",
                callback_data="admin_payment"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 پیام همگانی",
                callback_data="admin_broadcast"
            )
        ],
    ])


def back_admin():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="admin_menu"
            )
        ]
    ])


def save_config(config):
    with open(
        "config.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            config,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# ثبت Handler ها
# =========================================================

def register(app, config):

    app.admin_state = {}

    # =====================================================
    # /admin
    # =====================================================

    @app.on_message(
        filters.private
        & filters.command("admin")
    )
    async def admin_start(client, message):

        if not is_admin(
            message.from_user.id,
            config
        ):
            await message.reply_text(
                "⛔️ شما دسترسی مدیریت ندارید."
            )
            return

        await message.reply_text(
            "👨‍💻 پنل مدیریت کافه هرمس\n\n"
            "یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=admin_menu()
        )

    # =====================================================
    # Callback های ادمین
    # =====================================================

    @app.on_callback_query(
        filters.regex(
            r"^(admin_|approve_|reject_|config_|service_toggle_|"
            r"service_add|toggle_)"
        )
    )
    async def admin_callbacks(client, query):

        user_id = query.from_user.id

        if not is_admin(
            user_id,
            config
        ):
            await query.answer(
                "⛔️ دسترسی ندارید.",
                show_alert=True
            )
            return

        data = query.data

        # =================================================
        # منوی اصلی
        # =================================================

        if data == "admin_menu":

            await query.message.edit_text(
                "👨‍💻 پنل مدیریت کافه هرمس\n\n"
                "یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=admin_menu()
            )

            await query.answer()
            return

        # =================================================
        # سفارش‌های در انتظار
        # =================================================

        if data == "admin_pending":

            orders = get_pending_orders()

            if not orders:

                await query.message.edit_text(
                    "✅ هیچ سفارش در انتظاری وجود ندارد.",
                    reply_markup=back_admin()
                )

                await query.answer()
                return

            text = "🧾 سفارش‌های در انتظار:\n\n"

            buttons = []

            for order in orders:

                text += (
                    f"🆔 سفارش #{order['id']}\n"
                    f"👤 کاربر: {order['user_id']}\n"
                    f"📦 سرویس: {order['service_name']}\n"
                    f"💵 مبلغ: "
                    f"{order['final_price']:,} تومان\n\n"
                )

                buttons.append([
                    InlineKeyboardButton(
                        f"🧾 سفارش #{order['id']}",
                        callback_data=(
                            f"admin_order_{order['id']}"
                        )
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="admin_menu"
                )
            ])

            await query.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            await query.answer()
            return

        # =================================================
        # نمایش سفارش
        # =================================================

        if data.startswith("admin_order_"):

            try:
                order_id = int(
                    data.replace(
                        "admin_order_",
                        "",
                        1
                    )
                )
            except Exception:

                await query.answer(
                    "شماره سفارش نامعتبر است.",
                    show_alert=True
                )
                return

            order = get_order(order_id)

            if not order:

                await query.answer(
                    "سفارش پیدا نشد.",
                    show_alert=True
                )
                return

            text = (
                f"🧾 سفارش #{order['id']}\n\n"
                f"👤 User ID: {order['user_id']}\n"
                f"👤 نام کاربری سرویس: "
                f"{order['username']}\n"
                f"📦 سرویس: {order['service_name']}\n"
                f"🔄 نوع سفارش: {order['order_type']}\n\n"
                f"💰 قیمت اصلی: "
                f"{order['original_price']:,} تومان\n"
                f"🎟️ تخفیف: "
                f"{order['discount_percent']}%\n"
                f"💵 مبلغ نهایی: "
                f"{order['final_price']:,} تومان\n\n"
                f"📌 وضعیت: {order['status']}"
            )

            buttons = []

            if order["status"] == "pending":

                buttons.append([
                    InlineKeyboardButton(
                        "✅ تأیید پرداخت",
                        callback_data=f"approve_{order_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ رد پرداخت",
                        callback_data=f"reject_{order_id}"
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    "🔙 سفارش‌ها",
                    callback_data="admin_pending"
                )
            ])

            await query.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            # اگر رسید وجود دارد،
            # آن را برای ادمین ارسال می‌کنیم.
            if order.get("receipt_file_id"):

                try:

                    await client.send_photo(
                        chat_id=user_id,
                        photo=order["receipt_file_id"],
                        caption=(
                            f"🧾 رسید سفارش #{order_id}\n\n"
                            f"👤 کاربر: {order['user_id']}\n"
                            f"💵 مبلغ: "
                            f"{order['final_price']:,} تومان"
                        )
                    )

                except Exception:
                    pass

            await query.answer()
            return

        # =================================================
        # تأیید پرداخت
        # =================================================

        if data.startswith("approve_"):

            try:
                order_id = int(
                    data.replace(
                        "approve_",
                        "",
                        1
                    )
                )
            except Exception:

                await query.answer(
                    "شماره سفارش نامعتبر است.",
                    show_alert=True
                )
                return

            order = get_order(order_id)

            if not order:

                await query.answer(
                    "سفارش پیدا نشد.",
                    show_alert=True
                )
                return

            if order["status"] != "pending":

                await query.answer(
                    "این سفارش قبلاً بررسی شده است.",
                    show_alert=True
                )
                return

            approve_order(order_id)

            # ---------------------------------------------
            # ثبت دعوت موفق
            # ---------------------------------------------

            reward_created = 0

            try:

                inviter_id = get_referrer(
                    order["user_id"]
                )

                if inviter_id:

                    reward_created = record_successful_referral(
                        inviter_id=inviter_id,
                        invited_id=order["user_id"],
                        order_id=order_id
                    )

            except Exception:
                reward_created = 0

            # ---------------------------------------------
            # پیام به مشتری
            # ---------------------------------------------

            try:

                await client.send_message(
                    order["user_id"],
                    (
                        "✅ پرداخت شما تأیید شد.\n\n"
                        f"🧾 شماره سفارش: #{order_id}\n"
                        f"📦 سرویس: {order['service_name']}\n"
                        f"👤 نام کاربری: {order['username']}\n\n"
                        "⏳ لطفاً منتظر ارسال کانفیگ باشید."
                    )
                )

            except Exception:
                pass

            # ---------------------------------------------
            # اطلاع پاداش دعوت
            # ---------------------------------------------

            if reward_created and inviter_id:

                try:

                    await client.send_message(
                        inviter_id,
                        (
                            "🎉 تبریک!\n\n"
                            "۵ دعوت موفق شما تکمیل شد.\n"
                            "🎁 پاداش شما: ۱۰GB\n\n"
                            "این پاداش برای شما ثبت شد و "
                            "ادمین باید حجم آن را روی سرویس اعمال کند."
                        )
                    )

                except Exception:
                    pass

                # اطلاع به ادمین‌ها
                for admin_id in config.get(
                    "admin_ids",
                    []
                ):

                    try:

                        await client.send_message(
                            admin_id,
                            (
                                "🎁 پاداش دعوت جدید\n\n"
                                f"👤 کاربر: {inviter_id}\n"
                                "🎁 پاداش: ۱۰GB\n\n"
                                "لطفاً حجم هدیه را روی سرویس "
                                "کاربر اعمال کنید."
                            )
                        )

                    except Exception:
                        pass

            # ---------------------------------------------
            # صفحه ثبت کانفیگ
            # ---------------------------------------------

            await query.message.edit_text(
                f"✅ سفارش #{order_id} تأیید شد.\n\n"
                "اکنون کانفیگ یا لینک اشتراک را ثبت کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "📤 ثبت کانفیگ",
                            callback_data=f"config_{order_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 پنل مدیریت",
                            callback_data="admin_menu"
                        )
                    ]
                ])
            )

            await query.answer(
                "پرداخت تأیید شد."
            )

            return

        # =================================================
        # رد پرداخت
        # =================================================

        if data.startswith("reject_"):

            try:
                order_id = int(
                    data.replace(
                        "reject_",
                        "",
                        1
                    )
                )
            except Exception:

                await query.answer(
                    "شماره سفارش نامعتبر است.",
                    show_alert=True
                )
                return

            order = get_order(order_id)

            if not order:

                await query.answer(
                    "سفارش پیدا نشد.",
                    show_alert=True
                )
                return

            if order["status"] != "pending":

                await query.answer(
                    "این سفارش قبلاً بررسی شده است.",
                    show_alert=True
                )
                return

            reject_order(order_id)

            try:

                await client.send_message(
                    order["user_id"],
                    (
                        "❌ پرداخت سفارش شما تأیید نشد.\n\n"
                        f"🧾 شماره سفارش: #{order_id}\n\n"
                        "در صورت اشتباه، با پشتیبانی تماس بگیرید."
                    )
                )

            except Exception:
                pass

            await query.message.edit_text(
                f"❌ سفارش #{order_id} رد شد.",
                reply_markup=back_admin()
            )

            await query.answer(
                "سفارش رد شد."
            )

            return

        # =================================================
        # ثبت کانفیگ
        # =================================================

        if data.startswith("config_"):

            try:
                order_id = int(
                    data.replace(
                        "config_",
                        "",
                        1
                    )
                )
            except Exception:

                await query.answer(
                    "شماره سفارش نامعتبر است.",
                    show_alert=True
                )
                return

            order = get_order(order_id)

            if not order:

                await query.answer(
                    "سفارش پیدا نشد.",
                    show_alert=True
                )
                return

            if order["status"] != "approved":

                await query.answer(
                    "ابتدا باید پرداخت سفارش تأیید شود.",
                    show_alert=True
                )
                return

            app.admin_state[user_id] = {
                "action": "config",
                "order_id": order_id
            }

            await query.message.edit_text(
                f"📤 ثبت کانفیگ سفارش #{order_id}\n\n"
                "لطفاً لینک اشتراک یا کانفیگ را همینجا ارسال کنید.\n\n"
                "مثال:\n"
                "`vless://...`\n\n"
                "یا لینک اشتراک Hermes.",
                reply_markup=back_admin()
            )

            await query.answer()
            return

        # =================================================
        # مدیریت سرویس‌ها
        # =================================================

        if data == "admin_services":

            services = get_services(
                active_only=False
            )

            text = "📦 مدیریت سرویس‌ها\n\n"

            buttons = []

            if services:

                for service in services:

                    status = (
                        "🟢"
                        if service["active"]
                        else "🔴"
                    )

                    text += (
                        f"{status} {service['name']}\n"
                        f"💾 حجم: {service['volume_gb']}GB\n"
                        f"💰 قیمت: "
                        f"{service['price']:,} تومان\n\n"
                    )

                    buttons.append([
                        InlineKeyboardButton(
                            (
                                f"{status} "
                                f"{service['name']}"
                            ),
                            callback_data=(
                                f"service_toggle_"
                                f"{service['id']}"
                            )
                        )
                    ])

            else:

                text += (
                    "هیچ سرویسی ثبت نشده است.\n"
                )

            buttons.append([
                InlineKeyboardButton(
                    "➕ افزودن سرویس",
                    callback_data="service_add"
                )
            ])

            buttons.append([
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="admin_menu"
                )
            ])

            await query.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            await query.answer()
            return

        # =================================================
        # افزودن سرویس
        # =================================================

        if data == "service_add":

            app.admin_state[user_id] = {
                "action": "add_service"
            }

            await query.message.edit_text(
                "➕ افزودن سرویس\n\n"
                "اطلاعات را به این شکل ارسال کنید:\n\n"
                "`نام سرویس | حجم GB | قیمت`\n\n"
                "مثال:\n"
                "`30GB | 30 | 150000`",
                reply_markup=back_admin()
            )

            await query.answer()
            return

        # =================================================
        # فعال / غیرفعال سرویس
        # =================================================

        if data.startswith("service_toggle_"):

            try:

                service_id = int(
                    data.replace(
                        "service_toggle_",
                        "",
                        1
                    )
                )

            except Exception:

                await query.answer(
                    "سرویس نامعتبر است.",
                    show_alert=True
                )
                return

            toggle_service(service_id)

            await query.answer(
                "وضعیت سرویس تغییر کرد."
            )

            # نمایش دوباره لیست سرویس‌ها
            services = get_services(
                active_only=False
            )

            text = "📦 مدیریت سرویس‌ها\n\n"

            buttons = []

            for service in services:

                status = (
                    "🟢"
                    if service["active"]
                    else "🔴"
                )

                text += (
                    f"{status} {service['name']}\n"
                    f"💾 حجم: {service['volume_gb']}GB\n"
                    f"💰 قیمت: "
                    f"{service['price']:,} تومان\n\n"
                )

                buttons.append([
                    InlineKeyboardButton(
                        (
                            f"{status} "
                            f"{service['name']}"
                        ),
                        callback_data=(
                            f"service_toggle_"
                            f"{service['id']}"
                        )
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    "➕ افزودن سرویس",
                    callback_data="service_add"
                )
            ])

            buttons.append([
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="admin_menu"
                )
            ])

            await query.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            return

        # =================================================
        # آمار
        # =================================================

        if data == "admin_stats":

            users = get_users_count()
            orders = get_orders_count()

            await query.message.edit_text(
                "📊 آمار ربات\n\n"
                f"👥 تعداد کاربران: {users}\n"
                f"🧾 تعداد سفارش‌ها: {orders}",
                reply_markup=back_admin()
            )

            await query.answer()
            return

        # =================================================
        # کاربران
        # =================================================

        if data == "admin_users":

            users = get_users_count()

            await query.message.edit_text(
                "👥 مدیریت کاربران\n\n"
                f"تعداد کاربران ثبت‌شده:\n"
                f"{users} نفر",
                reply_markup=back_admin()
            )

            await query.answer()
            return

        # =================================================
        # کد تخفیف
        # =================================================

        if data == "admin_coupons":

            app.admin_state[user_id] = {
                "action": "add_coupon"
            }

            await query.message.edit_text(
                "🎟️ مدیریت کد تخفیف\n\n"
                "برای ساخت کد جدید، این فرمت را بفرستید:\n\n"
                "`CODE | درصد | تعداد استفاده`\n\n"
                "مثال:\n"
                "`HERMES10 | 10 | 100`\n\n"
                "عدد 0 برای تعداد استفاده یعنی نامحدود.",
                reply_markup=back_admin()
            )

            await query.answer()
            return

        # =================================================
        # دکمه‌های کاربر
        # =================================================

        if data == "admin_buttons":

            keys = [
                ("buy_enabled", "🛒 خرید سرویس"),
                ("renew_enabled", "🔄 تمدید"),
                ("subscriptions_enabled", "📦 اشتراک‌ها"),
                ("status_enabled", "📊 وضعیت"),
                ("referral_enabled", "👥 دعوت دوستان"),
                ("coupon_enabled", "🎟️ کد تخفیف"),
                ("order_history_enabled", "📜 تاریخچه"),
                ("account_enabled", "👤 حساب"),
                ("support_enabled", "☎️ پشتیبانی"),
                ("tutorial_enabled", "📚 آموزش"),
                ("free_test_enabled", "🎁 تست رایگان"),
                ("festival_enabled", "🎉 جشنواره"),
            ]

            buttons = []

            for key, title in keys:

                status = config.get(
                    key,
                    True
                )

                icon = (
                    "🟢"
                    if status
                    else "🔴"
                )

                buttons.append([
                    InlineKeyboardButton(
                        f"{icon} {title}",
                        callback_data=f"toggle_{key}"
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="admin_menu"
                )
            ])

            await query.message.edit_text(
                "🎛️ روشن / خاموش کردن قابلیت‌ها\n\n"
                "🟢 فعال\n"
                "🔴 خاموش",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            await query.answer()
            return

        # =================================================
        # تغییر وضعیت دکمه
        # =================================================

        if data.startswith("toggle_"):

            key = data.replace(
                "toggle_",
                "",
                1
            )

            current = config.get(
                key,
                True
            )

            config[key] = not current

            try:

                save_config(config)

                await query.answer(
                    "وضعیت تغییر کرد."
                )

            except Exception:

                await query.answer(
                    "ذخیره تنظیمات انجام نشد.",
                    show_alert=True
                )

            return

        # =================================================
        # تنظیمات پرداخت
        # =================================================

        if data == "admin_payment":

            app.admin_state[user_id] = {
                "action": "payment"
            }

            await query.message.edit_text(
                "⚙️ تنظیمات پرداخت\n\n"
                "برای تغییر اطلاعات پرداخت این فرمت را بفرستید:\n\n"
                "`شماره کارت | نام صاحب کارت`\n\n"
                "مثال:\n"
                "`0000000000000000 | علی رضایی`",
                reply_markup=back_admin()
            )

            await query.answer()
            return

        # =================================================
        # پیام همگانی
        # =================================================

        if data == "admin_broadcast":

            app.admin_state[user_id] = {
                "action": "broadcast"
            }

            await query.message.edit_text(
                "📢 پیام همگانی\n\n"
                "متن پیامی که می‌خواهید برای کاربران ارسال شود را بفرستید.",
                reply_markup=back_admin()
            )

            await query.answer()
            return

    # =====================================================
    # پیام‌های متنی ادمین
    # =====================================================

    @app.on_message(
        filters.private
        & filters.text
    )
    async def admin_text(client, message):

        user_id = message.from_user.id

        if not is_admin(
            user_id,
            config
        ):
            return

        state = app.admin_state.get(user_id)

        if not state:
            return

        action = state.get("action")

        # =================================================
        # افزودن سرویس
        # =================================================

        if action == "add_service":

            try:

                parts = [
                    x.strip()
                    for x in message.text.split("|")
                ]

                if len(parts) != 3:
                    raise ValueError

                name = parts[0]
                volume = int(parts[1])
                price = int(parts[2])

                if not name:
                    raise ValueError

                if volume <= 0:
                    raise ValueError

                if price < 0:
                    raise ValueError

                add_service(
                    name,
                    volume,
                    price
                )

                await message.reply_text(
                    "✅ سرویس با موفقیت اضافه شد.",
                    reply_markup=admin_menu()
                )

                app.admin_state.pop(
                    user_id,
                    None
                )

            except Exception:

                await message.reply_text(
                    "❌ فرمت اشتباه است.\n\n"
                    "فرمت صحیح:\n"
                    "`نام سرویس | حجم | قیمت`\n\n"
                    "مثال:\n"
                    "`30GB | 30 | 150000`"
                )

            return

        # =================================================
        # ثبت کانفیگ
        # =================================================

        if action == "config":

            order_id = state["order_id"]

            order = get_order(order_id)

            if not order:

                await message.reply_text(
                    "❌ سفارش پیدا نشد."
                )

                app.admin_state.pop(
                    user_id,
                    None
                )

                return

            if order["status"] != "approved":

                await message.reply_text(
                    "❌ این سفارش هنوز تأیید پرداخت نشده است."
                )

                app.admin_state.pop(
                    user_id,
                    None
                )

                return

            config_text = message.text.strip()

            if not config_text:

                await message.reply_text(
                    "❌ کانفیگ نمی‌تواند خالی باشد."
                )
                return

            save_subscription(
                user_id=order["user_id"],
                order_id=order_id,
                service_name=order["service_name"],
                username=order["username"],
                subscription_url=config_text,
                config_text=config_text
            )

            try:

                await client.send_message(
                    order["user_id"],
                    (
                        "🎉 سرویس شما آماده شد!\n\n"
                        f"📦 سرویس: {order['service_name']}\n"
                        f"👤 نام کاربری: {order['username']}\n\n"
                        "🔗 لینک اشتراک / کانفیگ:\n\n"
                        f"{config_text}\n\n"
                        "📌 برای مشاهده سرویس خود می‌توانید "
                        "از بخش «اشتراک‌های من» استفاده کنید."
                    )
                )

            except Exception:
                pass

            await message.reply_text(
                f"✅ کانفیگ سفارش #{order_id} "
                "ثبت و برای مشتری ارسال شد.",
                reply_markup=admin_menu()
            )

            app.admin_state.pop(
                user_id,
                None
            )

            return

        # =================================================
        # ساخت کد تخفیف
        # =================================================

        if action == "add_coupon":

            try:

                parts = [
                    x.strip()
                    for x in message.text.split("|")
                ]

                if len(parts) != 3:
                    raise ValueError

                code = parts[0].upper()
                percent = int(parts[1])
                max_uses = int(parts[2])

                if not code:
                    raise ValueError

                if percent <= 0 or percent > 100:
                    raise ValueError

                if max_uses < 0:
                    raise ValueError

                create_coupon(
                    code=code,
                    percent=percent,
                    max_uses=max_uses
                )

                await message.reply_text(
                    "✅ کد تخفیف ساخته شد.\n\n"
                    f"🎟️ کد: `{code}`\n"
                    f"📉 تخفیف: {percent}%\n"
                    f"🔢 تعداد استفاده: "
                    f"{max_uses}",
                    reply_markup=admin_menu()
                )

                app.admin_state.pop(
                    user_id,
                    None
                )

            except Exception:

                await message.reply_text(
                    "❌ فرمت اشتباه است یا کد تکراری است.\n\n"
                    "مثال:\n"
                    "`HERMES10 | 10 | 100`"
                )

            return

        # =================================================
        # تنظیمات پرداخت
        # =================================================

        if action == "payment":

            try:

                parts = [
                    x.strip()
                    for x in message.text.split("|", 1)
                ]

                if len(parts) != 2:
                    raise ValueError

                if not parts[0] or not parts[1]:
                    raise ValueError

                config["payment_card"] = parts[0]
                config["payment_name"] = parts[1]

                save_config(config)

                await message.reply_text(
                    "✅ اطلاعات پرداخت بروزرسانی شد.",
                    reply_markup=admin_menu()
                )

                app.admin_state.pop(
                    user_id,
                    None
                )

            except Exception:

                await message.reply_text(
                    "❌ فرمت اشتباه است.\n\n"
                    "فرمت صحیح:\n"
                    "`شماره کارت | نام صاحب کارت`"
                )

            return

        # =================================================
        # پیام همگانی
        # =================================================

        if action == "broadcast":

            text = message.text.strip()

            if not text:

                await message.reply_text(
                    "❌ متن پیام خالی است."
                )
                return

            users = get_all_user_ids()

            sent = 0
            failed = 0

            for uid in users:

                try:

                    await client.send_message(
                        uid,
                        text
                    )

                    sent += 1

                    await asyncio.sleep(0.05)

                except Exception:

                    failed += 1

            await message.reply_text(
                "📢 ارسال پیام همگانی تمام شد.\n\n"
                f"✅ ارسال موفق: {sent}\n"
                f"❌ ناموفق: {failed}",
                reply_markup=admin_menu()
            )

            app.admin_state.pop(
                user_id,
                None
            )

            return
