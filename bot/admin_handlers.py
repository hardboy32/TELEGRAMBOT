from pyrogram import filters
from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from bot.helpers import (
    admin,
    format_price
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
    get_referral_count,
    get_user
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
                    f"{status} {service['name']} | {service['volume_gb']}GB",
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
    names = [
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

    for key, title in names:
        state = "🟢" if config.get(key, False) else "🔴"

        rows.append(
            [
                InlineKeyboardButton(
                    f"{state} {title}",
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

    @app.on_message(
        filters.private & filters.command("admin")
    )
    async def admin_command(client, message):

        if not admin(
            message.from_user.id,
            config
        ):
            return

        await message.reply_text(
            "⚙️ پنل مدیریت",
            reply_markup=admin_reply_menu()
        )

        await message.reply_text(
            "از منوی مدیریت انتخاب کنید:",
            reply_markup=admin_panel_keyboard()
        )

    @app.on_message(
        filters.private & filters.text
    )
    async def admin_text(client, message):

        user_id = message.from_user.id

        if not admin(
            user_id,
            config
        ):
            return

        text = message.text.strip()

        if text == "⚙️ پنل مدیریت":

            await message.reply_text(
                "⚙️ پنل مدیریت",
                reply_markup=admin_panel_keyboard()
            )

            return

        state = admin_states.get(user_id)

        if state:

            step = state.get("step")

            if step == "service_name":

                state["name"] = text
                state["step"] = "service_volume"

                await message.reply_text(
                    "💾 حجم سرویس را به GB وارد کنید:"
                )

                return

            if step == "service_volume":

                try:
                    volume = int(text)

                    if volume <= 0:
                        raise ValueError

                except ValueError:

                    await message.reply_text(
                        "❌ حجم باید یک عدد مثبت باشد."
                    )

                    return

                state["volume"] = volume
                state["step"] = "service_price"

                await message.reply_text(
                    "💰 قیمت سرویس را به تومان وارد کنید:"
                )

                return

            if step == "service_price":

                try:
                    price = int(text)

                    if price < 0:
                        raise ValueError

                except ValueError:

                    await message.reply_text(
                        "❌ قیمت نامعتبر است."
                    )

                    return

                service_id = add_service(
                    state["name"],
                    state["volume"],
                    price
                )

                admin_states.pop(
                    user_id,
                    None
                )

                await message.reply_text(
                    f"✅ سرویس اضافه شد.\n\n"
                    f"🆔 شناسه: {service_id}\n"
                    f"📦 نام: {state['name']}\n"
                    f"💾 حجم: {state['volume']}GB\n"
                    f"💰 قیمت: {format_price(price)} تومان"
                )

                return

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

                    return

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
                        f"📦 سرویس: {order['service_name']}\n"
                        f"👤 نام کاربری: @{order['username']}\n\n"
                        "⚙️ کانفیگ شما:\n\n"
                        f"{config_text}\n\n"
                        "✅ اشتراک شما فعال شد."
                    )

                except Exception as e:

                    print(
                        f"User config send error: {e}"
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

                            reward_id = create_referral_reward(
                                referrer
                            )

                            try:

                                await client.send_message(
                                    referrer,
                                    "🎉 تبریک!\n\n"
                                    "شما ۵ دعوت موفق داشتید.\n"
                                    "🎁 یک پاداش ۱۰GB برای شما ثبت شد.\n\n"
                                    "پاداش توسط مدیریت اعمال می‌شود."
                                )

                            except Exception:
                                pass

                await message.reply_text(
                    f"✅ کانفیگ سفارش #{order_id} ثبت و سفارش تأیید شد."
                )

                return

            if step == "coupon":

                parts = text.split()

                if len(parts) < 2:

                    await message.reply_text(
                        "فرمت صحیح:\n"
                        "CODE PERCENT [MAX_USES]"
                    )

                    return

                code = parts[0].upper()

                try:
                    percent = int(parts[1])
                    max_uses = int(parts[2]) if len(parts) > 2 else 0

                    if not 1 <= percent <= 100:
                        raise ValueError

                    if max_uses < 0:
                        raise ValueError

                except ValueError:

                    await message.reply_text(
                        "❌ اطلاعات کد تخفیف نامعتبر است."
                    )

                    return

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

                    await message.reply_text(
                        "✅ کد تخفیف ساخته شد.\n\n"
                        f"🎟️ کد: {code}\n"
                        f"📉 تخفیف: {percent}%\n"
                        f"🔢 حداکثر استفاده: "
                        f"{max_uses if max_uses else 'نامحدود'}"
                    )

                else:

                    await message.reply_text(
                        "❌ این کد قبلاً وجود دارد."
                    )

                return

            if step == "payment_card":

                config["payment_card"] = text

                admin_states[user_id] = {
                    "step": "payment_name"
                }

                await message.reply_text(
                    "👤 نام صاحب کارت را وارد کنید:"
                )

                return

            if step == "payment_name":

                config["payment_name"] = text

                admin_states.pop(
                    user_id,
                    None
                )

                await message.reply_text(
                    "✅ اطلاعات پرداخت در اجرای فعلی ذخیره شد."
                )

                return

            if step == "broadcast":

                admin_states.pop(
                    user_id,
                    None
                )

                user_ids = get_all_user_ids()

                success = 0
                failed = 0

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
                    f"✅ ارسال موفق: {success}\n"
                    f"❌ ناموفق: {failed}"
                )

                return

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

        await query.message.edit_text(
            "⚙️ پنل مدیریت",
            reply_markup=admin_panel_keyboard()
        )

        await query.answer()

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
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⬅️ بازگشت",
                                callback_data="admin_home"
                            )
                        ]
                    ]
                )
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
            f"👤 کاربر: {order['user_id']}\n"
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

            except Exception:
                pass

        await query.answer()

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
            return

        approve_order(order_id)

        await query.message.reply_text(
            f"✅ پرداخت سفارش #{order_id} تأیید شد.\n\n"
            "حالا روی «⚙️ ثبت کانفیگ» بزنید و "
            "کانفیگ/لینک اشتراک را وارد کنید."
        )

        try:

            await client.send_message(
                order["user_id"],
                "✅ پرداخت شما تأیید شد.\n\n"
                f"🧾 سفارش: #{order_id}\n\n"
                "⏳ در حال آماده‌سازی کانفیگ شما..."
            )

        except Exception:
            pass

        await query.answer(
            "پرداخت تأیید شد."
        )

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
            return

        reject_order(order_id)

        try:

            await client.send_message(
                order["user_id"],
                "❌ رسید پرداخت شما رد شد.\n\n"
                f"🧾 سفارش: #{order_id}\n\n"
                "در صورت اشتباه، دوباره با پشتیبانی تماس بگیرید."
            )

        except Exception:
            pass

        await query.message.reply_text(
            f"❌ سفارش #{order_id} رد شد."
        )

        await query.answer(
            "سفارش رد شد."
        )

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

        await query.answer(
            "🟢 سرویس فعال شد."
            if new_state
            else "🔴 سرویس غیرفعال شد."
        )

        services = get_services(False)

        await query.message.edit_text(
            "📦 مدیریت سرویس‌ها",
            reply_markup=service_admin_keyboard(
                services
            )
        )

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
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ بازگشت",
                            callback_data="admin_home"
                        )
                    ]
                ]
            )
        )

        await query.answer()

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
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ بازگشت",
                            callback_data="admin_home"
                        )
                    ]
                ]
            )
        )

        await query.answer()

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
            "اگر تعداد استفاده نامحدود است، 0 بزنید."
        )

        await query.answer()

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
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⬅️ بازگشت",
                                callback_data="admin_home"
                            )
                        ]
                    ]
                )
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
            "پاداش به عنوان اعمال‌شده ثبت شد."
        )

        await query.message.reply_text(
            "✅ پاداش ثبت شد.\n\n"
            "حجم ۱۰GB باید در پنل هرمس به صورت دستی "
            "برای کاربر اعمال شود."
        )

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
            reply_markup=buttons_keyboard(
                config
            )
        )

        await query.answer()

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

        await query.message.edit_text(
            "⚙️ تنظیمات دکمه‌های کاربر",
            reply_markup=buttons_keyboard(
                config
            )
        )

        await query.answer(
            "تنظیمات تغییر کرد."
        )

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
