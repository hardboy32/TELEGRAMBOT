import os
from pyrogram import filters, StopPropagation, enums
from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from bot.helpers import admin, format_price, save_config
from bot.keyboards import main_menu
from bot.remote_storage import store_media_message


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
    get_service,
    toggle_service,
    update_service,
    delete_service,
    get_users_count,
    get_orders_count,
    get_all_user_ids,
    create_coupon,
    get_pending_rewards,
    mark_reward_applied,
    get_referrer,
    record_successful_referral,
    get_referral_count,
    get_users_page,
    get_user,
    get_user_orders,
    get_user_subscriptions,
    get_subscription,
    delete_order,
    update_order_status,
    delete_subscription,
    update_subscription_fields,
    update_subscription_status,
    reset_user_info,
    get_tutorials,
    get_tutorial,
    update_tutorial_field,
    add_tutorial,
    toggle_tutorial,
    delete_tutorial
)


admin_states = {}


def admin_reply_menu():
    """
    کیبورد ثابت پایین صفحه برای پنل مدیریت
    """
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("🧾 سفارش‌های در انتظار"),
                KeyboardButton("📦 مدیریت سرویس‌ها")
            ],
            [
                KeyboardButton("👥 کاربران"),
                KeyboardButton("📊 آمار")
            ],
            [
                KeyboardButton("🎟️ کد تخفیف"),
                KeyboardButton("🎁 پاداش‌های دعوت")
            ],
            [
                KeyboardButton("📢 پیام همگانی"),
                KeyboardButton("⚙️ تنظیمات دکمه‌ها")
            ],
            [
                KeyboardButton("💳 تنظیمات پرداخت"),
                KeyboardButton("📚 مدیریت آموزش")
            ],
            [
                KeyboardButton("💾 پشتیبان‌گیری"),
                KeyboardButton("♻️ بازگردانی بکاپ")
            ],
            [
                KeyboardButton("🏠 منوی کاربر")
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
                    "📚 مدیریت آموزش",
                    callback_data="admin_tutorials"
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


def admin_tutorials_keyboard(tutorials):
    rows = []

    for item in tutorials:
        status = "🟢" if item["active"] else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{status} {item['title']}",
                    callback_data=f"admin_tut_{item['id']}"
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "➕ افزودن دکمه آموزش",
                callback_data="admin_tut_add"
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


def admin_tutorial_item_keyboard(tutorial_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✏️ ویرایش متن",
                    callback_data=f"admin_tut_text_{tutorial_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📎 تنظیم فایل نصب",
                    callback_data=f"admin_tut_file_{tutorial_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎬 تنظیم ویدیو",
                    callback_data=f"admin_tut_video_{tutorial_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 روشن/خاموش",
                    callback_data=f"admin_tut_toggle_{tutorial_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 حذف",
                    callback_data=f"admin_tut_del_{tutorial_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="admin_tutorials"
                )
            ]
        ]
    )


def users_page_keyboard(offset, total, page_size=10):
    rows = []

    if offset > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    "⬅️ قبلی",
                    callback_data=f"admin_users_page_{max(0, offset - page_size)}"
                )
            ]
        )

    if offset + page_size < total:
        rows.append(
            [
                InlineKeyboardButton(
                    "بعدی ➡️",
                    callback_data=f"admin_users_page_{offset + page_size}"
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


def service_detail_keyboard(service_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✏️ ویرایش نام",
                    callback_data=f"svc_edit_name_{service_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "💾 ویرایش حجم",
                    callback_data=f"svc_edit_vol_{service_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "💰 ویرایش قیمت",
                    callback_data=f"svc_edit_price_{service_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 فعال / غیرفعال",
                    callback_data=f"svc_toggle_{service_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 حذف سرویس",
                    callback_data=f"svc_del_{service_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت به لیست",
                    callback_data="admin_services"
                )
            ]
        ]
    )


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



def user_detail_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🧾 سفارش‌ها",
                    callback_data=f"admin_uorders_{user_id}"
                ),
                InlineKeyboardButton(
                    "📦 اشتراک‌ها",
                    callback_data=f"admin_usubs_{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "➕ افزودن اشتراک دستی",
                    callback_data=f"admin_uaddsub_{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✉️ پیام به کاربر",
                    callback_data=f"admin_msg_{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "♻️ ریست اطلاعات",
                    callback_data=f"admin_ureset_{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت به لیست",
                    callback_data="admin_users"
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
                "⚙️ پنل مدیریت\n\n"
                "از دکمه‌های پایین صفحه استفاده کنید.",
                reply_markup=admin_reply_menu()
            )

            raise StopPropagation

        if text == "🏠 منوی کاربر":

            admin_states.pop(user_id, None)

            await message.reply_text(
                "🏠 منوی کاربر",
                reply_markup=main_menu(
                    config,
                    is_admin=True
                )
            )

            raise StopPropagation

        # دکمه‌های ثابت پنل (ReplyKeyboard)
        if text == "🧾 سفارش‌های در انتظار":

            orders = get_pending_orders()

            if not orders:
                await message.reply_text(
                    "🧾 هیچ سفارش در انتظاری وجود ندارد.",
                    reply_markup=admin_reply_menu()
                )
                raise StopPropagation

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

            await message.reply_text(
                "🧾 سفارش‌های در انتظار:",
                reply_markup=InlineKeyboardMarkup(rows)
            )

            raise StopPropagation

        if text == "📦 مدیریت سرویس‌ها":

            services = get_services(False)

            await message.reply_text(
                "📦 مدیریت سرویس‌ها",
                reply_markup=service_admin_keyboard(services)
            )

            raise StopPropagation

        if text == "👥 کاربران":

            count = get_users_count()
            page_size = 10
            users = get_users_page(0, page_size)

            lines = [
                "👥 کاربران\n",
                f"تعداد کل: {count}\n",
                "روی هر کاربر بزنید تا جزئیات باز شود.\n"
            ]

            rows = []

            for u in users:
                uname = u.get("username") or "—"
                name = u.get("first_name") or "—"
                lines.append(
                    f"🆔 <code>{u['id']}</code> | {uname} | {name}"
                )
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"👤 {name} ({u['id']})",
                            callback_data=f"admin_user_{u['id']}"
                        )
                    ]
                )

            if count > page_size:
                rows.append(
                    [
                        InlineKeyboardButton(
                            "بعدی ➡️",
                            callback_data=f"admin_users_page_{page_size}"
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

            await message.reply_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode=enums.ParseMode.HTML
            )

            raise StopPropagation


        if text == "📊 آمار":

            users = get_users_count()
            orders = get_orders_count()
            pending = len(get_pending_orders())

            await message.reply_text(
                "📊 آمار ربات\n\n"
                f"👥 کاربران: {users}\n"
                f"🧾 کل سفارش‌ها: {orders}\n"
                f"⏳ در انتظار: {pending}",
                reply_markup=admin_reply_menu()
            )

            raise StopPropagation

        if text == "🎟️ کد تخفیف":

            admin_states[user_id] = {
                "step": "coupon"
            }

            await message.reply_text(
                "🎟️ کد تخفیف را این‌طور بفرستید:\n\n"
                "کد درصد\n\n"
                "مثال:\nHERMES20 20"
            )

            raise StopPropagation

        if text == "🎁 پاداش‌های دعوت":

            rewards = get_pending_rewards()

            if not rewards:
                await message.reply_text(
                    "🎁 پاداش در انتظاری نیست.",
                    reply_markup=admin_reply_menu()
                )
                raise StopPropagation

            rows = []

            for r in rewards:
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"🎁 {r['user_id']} | {r.get('volume_gb', 10)}GB",
                            callback_data=f"admin_reward_{r['id']}"
                        )
                    ]
                )

            await message.reply_text(
                "🎁 پاداش‌های دعوت در انتظار:",
                reply_markup=InlineKeyboardMarkup(rows)
            )

            raise StopPropagation

        if text == "📢 پیام همگانی":

            admin_states[user_id] = {
                "step": "broadcast"
            }

            await message.reply_text(
                "📢 متن پیام همگانی را ارسال کنید:"
            )

            raise StopPropagation

        if text == "⚙️ تنظیمات دکمه‌ها":

            await message.reply_text(
                "⚙️ تنظیمات دکمه‌های کاربر",
                reply_markup=buttons_keyboard(config)
            )

            raise StopPropagation

        if text == "💳 تنظیمات پرداخت":

            admin_states[user_id] = {
                "step": "payment_card"
            }

            await message.reply_text(
                "💳 شماره کارت جدید را وارد کنید:"
            )

            raise StopPropagation

        if text == "📚 مدیریت آموزش":

            tutorials = get_tutorials(False)

            await message.reply_text(
                "📚 مدیریت آموزش‌ها\n\n"
                "روی هر مورد بزنید تا متن، فایل یا ویدیو را تنظیم کنید.",
                reply_markup=admin_tutorials_keyboard(tutorials)
            )

            raise StopPropagation

        if text == "💾 پشتیبان‌گیری":

            await message.reply_text(
                "در حال ساخت بکاپ..."
            )

            try:
                zip_path = create_backup(config)

                await client.send_document(
                    user_id,
                    zip_path,
                    caption=(
                        "💾 بکاپ کامل کافه هرمس\n\n"
                        "حتماً در Saved Messages ذخیره کنید."
                    )
                )

                await message.reply_text(
                    "✅ بکاپ ارسال شد.",
                    reply_markup=admin_reply_menu()
                )

            except Exception as e:

                await message.reply_text(
                    f"❌ خطا در ساخت بکاپ:\n{e}",
                    reply_markup=admin_reply_menu()
                )

            raise StopPropagation

        if text == "♻️ بازگردانی بکاپ":

            admin_states[user_id] = {
                "step": "restore_backup"
            }

            await message.reply_text(
                "♻️ فایل zip بکاپ را همینجا ارسال کنید."
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
                    f"👤 نام کاربری: <code>{order['username']}</code>\n\n"
                    "⚙️ کانفیگ شما:\n\n"
                    f"<code>{config_text}</code>\n\n"
                    "✅ اشتراک شما فعال شد.",
                    parse_mode=enums.ParseMode.HTML
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
        # پیام به کاربر
        # =====================================================

        if step == "message_user":

            target_id = state.get("target_id")

            admin_states.pop(user_id, None)

            try:
                await client.send_message(
                    target_id,
                    f"📩 پیام از مدیریت:\n\n{text}"
                )
                await message.reply_text(
                    f"✅ پیام برای <code>{target_id}</code> ارسال شد.",
                    reply_markup=admin_reply_menu(),
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                await message.reply_text(
                    f"❌ ارسال ناموفق:\n{e}",
                    reply_markup=admin_reply_menu()
                )

            raise StopPropagation

        # =====================================================
        # افزودن اشتراک دستی - نام سرویس
        # =====================================================

        if step == "edit_sub_config":

            sub_id = state.get("sub_id")
            update_subscription_fields(sub_id, config_text=text)
            admin_states.pop(user_id, None)
            sub = get_subscription(sub_id)
            await message.reply_text(
                f"✅ کانفیگ اشتراک #{sub_id} به‌روز شد.",
                reply_markup=admin_reply_menu()
            )
            raise StopPropagation

        if step == "edit_sub_username":

            from bot.helpers import normalize_username, valid_username
            username = normalize_username(text)
            if not valid_username(username):
                await message.reply_text("❌ نام کاربری نامعتبر است. دوباره بفرستید:")
                raise StopPropagation

            sub_id = state.get("sub_id")
            update_subscription_fields(sub_id, username=username)
            admin_states.pop(user_id, None)
            await message.reply_text(
                f"✅ نام کاربری اشتراک #{sub_id} به <code>{username}</code> تغییر کرد.",
                reply_markup=admin_reply_menu(),
                parse_mode=enums.ParseMode.HTML
            )
            raise StopPropagation

        if step == "edit_sub_service":

            sub_id = state.get("sub_id")
            update_subscription_fields(sub_id, service_name=text)
            admin_states.pop(user_id, None)
            await message.reply_text(
                f"✅ نام سرویس اشتراک #{sub_id} به {text} تغییر کرد.",
                reply_markup=admin_reply_menu()
            )
            raise StopPropagation

        if step == "manual_sub_service":

            state["service_name"] = text
            state["step"] = "manual_sub_username"

            await message.reply_text(
                "👤 نام کاربری اشتراک را بفرستید (بدون @):"
            )
            raise StopPropagation

        if step == "manual_sub_username":

            from bot.helpers import normalize_username, valid_username

            username = normalize_username(text)

            if not valid_username(username):
                await message.reply_text(
                    "❌ نام کاربری نامعتبر است. دوباره بفرستید:"
                )
                raise StopPropagation

            state["username"] = username
            state["step"] = "manual_sub_config"

            await message.reply_text(
                "⚙️ کانفیگ یا لینک اشتراک را بفرستید:"
            )
            raise StopPropagation

        if step == "manual_sub_config":

            target_id = state.get("target_id")
            service_name = state.get("service_name")
            username = state.get("username")
            config_text = text

            save_subscription(
                user_id=target_id,
                order_id=None,
                service_name=service_name,
                username=username,
                subscription_url=None,
                config_text=config_text
            )

            admin_states.pop(user_id, None)

            try:
                await client.send_message(
                    target_id,
                    "🎉 یک اشتراک برای شما ثبت شد.\n\n"
                    f"📦 سرویس: {service_name}\n"
                    f"👤 نام کاربری: <code>{username}</code>\n\n"
                    f"⚙️ کانفیگ:\n<code>{config_text}</code>",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                print(f"Manual sub notify error: {e}")

            await message.reply_text(
                f"✅ اشتراک دستی برای <code>{target_id}</code> ثبت شد.",
                reply_markup=admin_reply_menu(),
                parse_mode=enums.ParseMode.HTML
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

        # 
        if step == "svc_edit_name":

            name = text.strip()

            if len(name) < 2:

                await message.reply_text(
                    "❌ نام خیلی کوتاه است."
                )

                raise StopPropagation

            update_service(
                state["service_id"],
                name=name
            )

            admin_states.pop(user_id, None)

            await message.reply_text(
                f"✅ نام سرویس به «{name}» تغییر کرد.",
                reply_markup=admin_reply_menu()
            )

            raise StopPropagation

        if step == "svc_edit_vol":

            try:
                volume = int(text.strip())
            except ValueError:

                await message.reply_text(
                    "❌ یک عدد معتبر بفرست."
                )

                raise StopPropagation

            if volume <= 0:

                await message.reply_text(
                    "❌ حجم باید بزرگ‌تر از صفر باشد."
                )

                raise StopPropagation

            update_service(
                state["service_id"],
                volume_gb=volume
            )

            admin_states.pop(user_id, None)

            await message.reply_text(
                f"✅ حجم سرویس به {volume}GB تغییر کرد.",
                reply_markup=admin_reply_menu()
            )

            raise StopPropagation

        if step == "svc_edit_price":

            try:
                price = int(
                    text.strip()
                    .replace(",", "")
                    .replace("،", "")
                )
            except ValueError:

                await message.reply_text(
                    "❌ یک عدد معتبر بفرست."
                )

                raise StopPropagation

            if price < 0:

                await message.reply_text(
                    "❌ قیمت نامعتبر است."
                )

                raise StopPropagation

            update_service(
                state["service_id"],
                price=price
            )

            admin_states.pop(user_id, None)

            await message.reply_text(
                f"✅ قیمت به {format_price(price)} تومان تغییر کرد.",
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
            "⚙️ پنل مدیریت — از دکمه‌های پایین استفاده کنید."
        )

        await query.message.reply_text(
            "منوی مدیریت فعال است.",
            reply_markup=admin_reply_menu()
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
            f"👤 نام کاربری: <code>{order['username']}</code>\n"
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
            reply_markup=order_keyboard(order_id),
            parse_mode=enums.ParseMode.HTML
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
    async def admin_service_detail(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        service_id = int(
            query.data.split("_")[-1]
        )

        service = get_service(service_id)

        if not service:

            await query.answer(
                "❌ سرویس پیدا نشد.",
                show_alert=True
            )
            return

        status = (
            "🟢 فعال"
            if service["active"]
            else "🔴 غیرفعال"
        )

        await query.message.edit_text(
            f"📦 {service['name']}\n\n"
            f"💾 حجم: {service['volume_gb']}GB\n"
            f"💰 قیمت: {format_price(service['price'])} تومان\n"
            f"وضعیت: {status}\n\n"
            "چه کاری می‌خواهید انجام دهید؟",
            reply_markup=service_detail_keyboard(
                service_id
            )
        )

        await query.answer()

    # =========================================================
    # فعال/غیرفعال سرویس
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^svc_toggle_\d+$")
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

        new_state = toggle_service(service_id)
        service = get_service(service_id)

        status = (
            "🟢 فعال"
            if service["active"]
            else "🔴 غیرفعال"
        )

        await query.message.edit_text(
            f"📦 {service['name']}\n\n"
            f"💾 حجم: {service['volume_gb']}GB\n"
            f"💰 قیمت: {format_price(service['price'])} تومان\n"
            f"وضعیت: {status}",
            reply_markup=service_detail_keyboard(
                service_id
            )
        )

        await query.answer(
            "🟢 سرویس فعال شد."
            if new_state
            else "🔴 سرویس غیرفعال شد."
        )

    # =========================================================
    # ویرایش نام
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^svc_edit_name_\d+$")
    )
    async def svc_edit_name(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        service_id = int(
            query.data.split("_")[-1]
        )

        admin_states[query.from_user.id] = {
            "step": "svc_edit_name",
            "service_id": service_id
        }

        await query.message.reply_text(
            "✏️ نام جدید سرویس را بفرست:"
        )

        await query.answer()

    # =========================================================
    # ویرایش حجم
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^svc_edit_vol_\d+$")
    )
    async def svc_edit_vol(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        service_id = int(
            query.data.split("_")[-1]
        )

        admin_states[query.from_user.id] = {
            "step": "svc_edit_vol",
            "service_id": service_id
        }

        await query.message.reply_text(
            "💾 حجم جدید را به GB (عدد) بفرست:"
        )

        await query.answer()

    # =========================================================
    # ویرایش قیمت
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^svc_edit_price_\d+$")
    )
    async def svc_edit_price(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        service_id = int(
            query.data.split("_")[-1]
        )

        admin_states[query.from_user.id] = {
            "step": "svc_edit_price",
            "service_id": service_id
        }

        await query.message.reply_text(
            "💰 قیمت جدید را به تومان (عدد) بفرست:"
        )

        await query.answer()

    # =========================================================
    # حذف سرویس
    # =========================================================

    @app.on_callback_query(
        filters.regex(r"^svc_del_\d+$")
    )
    async def svc_del(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        service_id = int(
            query.data.split("_")[-1]
        )

        delete_service(service_id)

        services = get_services(False)

        await query.message.edit_text(
            "📦 مدیریت سرویس‌ها\n\n"
            "✅ سرویس حذف شد.",
            reply_markup=service_admin_keyboard(
                services
            )
        )

        await query.answer("حذف شد.")



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
        page_size = 10
        users = get_users_page(0, page_size)

        lines = [
            "👥 کاربران\n",
            f"تعداد کل: {count}\n",
            "روی هر کاربر بزنید تا جزئیات باز شود.\n"
        ]

        rows = []

        for u in users:
            uname = u.get("username") or "—"
            name = u.get("first_name") or "—"
            lines.append(
                f"🆔 <code>{u['id']}</code> | {uname} | {name}"
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        f"👤 {name} ({u['id']})",
                        callback_data=f"admin_user_{u['id']}"
                    )
                ]
            )

        if count > page_size:
            rows.append(
                [
                    InlineKeyboardButton(
                        "بعدی ➡️",
                        callback_data=f"admin_users_page_{page_size}"
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
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=enums.ParseMode.HTML
        )

        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_users_page_\d+$")
    )
    async def admin_users_page(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        offset = int(query.data.split("_")[-1])
        page_size = 10
        count = get_users_count()
        users = get_users_page(offset, page_size)

        lines = [
            "👥 کاربران\n",
            f"تعداد کل: {count}\n",
            f"از ردیف {offset + 1}\n",
            "روی هر کاربر بزنید تا جزئیات باز شود.\n"
        ]

        rows = []

        for u in users:
            uname = u.get("username") or "—"
            name = u.get("first_name") or "—"
            lines.append(
                f"🆔 <code>{u['id']}</code> | {uname} | {name}"
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        f"👤 {name} ({u['id']})",
                        callback_data=f"admin_user_{u['id']}"
                    )
                ]
            )

        nav = []

        if offset > 0:
            nav.append(
                InlineKeyboardButton(
                    "⬅️ قبلی",
                    callback_data=f"admin_users_page_{max(0, offset - page_size)}"
                )
            )

        if offset + page_size < count:
            nav.append(
                InlineKeyboardButton(
                    "بعدی ➡️",
                    callback_data=f"admin_users_page_{offset + page_size}"
                )
            )

        if nav:
            rows.append(nav)

        rows.append(
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="admin_home"
                )
            ]
        )

        await query.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=enums.ParseMode.HTML
        )

        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_user_\d+$")
    )
    async def admin_user_detail(client, query):

        if not admin(query.from_user.id, config):
            return

        target_id = int(query.data.split("_")[-1])
        user = get_user(target_id)

        if not user:
            await query.answer("❌ کاربر پیدا نشد.", show_alert=True)
            return

        orders = get_user_orders(target_id)
        subs = get_user_subscriptions(target_id)
        ref_count = get_referral_count(target_id)

        uname = user.get("username") or "—"
        name = user.get("first_name") or "—"

        text = (
            "👤 جزئیات کاربر\n\n"
            f"🆔 شناسه: <code>{target_id}</code>\n"
            f"📛 نام: {name}\n"
            f"🔗 یوزرنیم تلگرام: {uname}\n"
            f"📅 عضویت: {user.get('joined_at') or '—'}\n"
            f"👥 دعوت موفق: {ref_count}\n"
            f"🧾 تعداد سفارش: {len(orders)}\n"
            f"📦 تعداد اشتراک: {len(subs)}"
        )

        await query.message.edit_text(
            text,
            reply_markup=user_detail_keyboard(target_id),
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_uorders_\d+$")
    )
    async def admin_user_orders(client, query):

        if not admin(query.from_user.id, config):
            return

        target_id = int(query.data.split("_")[-1])
        orders = get_user_orders(target_id)

        if not orders:
            await query.message.edit_text(
                f"🧾 سفارشی برای کاربر <code>{target_id}</code> نیست.",
                reply_markup=user_detail_keyboard(target_id),
                parse_mode=enums.ParseMode.HTML
            )
            await query.answer()
            return

        lines = [
            f"🧾 سفارش‌های کاربر <code>{target_id}</code>\n",
            "روی هر سفارش بزنید تا مدیریت شود.\n"
        ]
        rows = []

        for o in orders[:25]:
            lines.append(
                f"#{o['id']} | {o['service_name']} | "
                f"<code>{o['username']}</code> | "
                f"{format_price(o['final_price'])} | {o['status']}"
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        f"#{o['id']} | {o['status']}",
                        callback_data=f"admin_o_{o['id']}"
                    )
                ]
            )

        rows.append(
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data=f"admin_user_{target_id}"
                )
            ]
        )

        await query.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_o_\d+$")
    )
    async def admin_order_manage(client, query):

        if not admin(query.from_user.id, config):
            return

        order_id = int(query.data.split("_")[-1])
        order = get_order(order_id)

        if not order:
            await query.answer("❌ سفارش پیدا نشد.", show_alert=True)
            return

        uid = order["user_id"]
        text = (
            f"🧾 مدیریت سفارش #{order_id}\n\n"
            f"👤 کاربر: <code>{uid}</code>\n"
            f"📦 سرویس: {order['service_name']}\n"
            f"👤 نام کاربری: <code>{order['username']}</code>\n"
            f"💰 مبلغ: {format_price(order['final_price'])} تومان\n"
            f"🎟️ تخفیف: {order['discount_percent']}%\n"
            f"🔵 وضعیت: {order['status']}\n"
            f"📅 تاریخ: {order['created_at']}"
        )

        rows = [
            [
                InlineKeyboardButton(
                    "✅ approved",
                    callback_data=f"admin_ost_approved_{order_id}"
                ),
                InlineKeyboardButton(
                    "⏳ pending",
                    callback_data=f"admin_ost_pending_{order_id}"
                ),
                InlineKeyboardButton(
                    "❌ rejected",
                    callback_data=f"admin_ost_rejected_{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 حذف سفارش",
                    callback_data=f"admin_odel_{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت به سفارش‌ها",
                    callback_data=f"admin_uorders_{uid}"
                )
            ]
        ]

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_ost_(approved|pending|rejected)_\d+$")
    )
    async def admin_order_set_status(client, query):

        if not admin(query.from_user.id, config):
            return

        parts = query.data.split("_")
        # admin_ost_STATUS_ID
        status = parts[2]
        order_id = int(parts[3])
        order = get_order(order_id)

        if not order:
            await query.answer("❌ سفارش پیدا نشد.", show_alert=True)
            return

        update_order_status(order_id, status)
        order = get_order(order_id)
        uid = order["user_id"]

        await query.answer(f"وضعیت → {status}")
        # refresh detail
        query.data = f"admin_o_{order_id}"
        await admin_order_manage(client, query)


    @app.on_callback_query(
        filters.regex(r"^admin_odel_\d+$")
    )
    async def admin_order_delete(client, query):

        if not admin(query.from_user.id, config):
            return

        order_id = int(query.data.split("_")[-1])
        order = get_order(order_id)

        if not order:
            await query.answer("❌ سفارش پیدا نشد.", show_alert=True)
            return

        uid = order["user_id"]

        await query.message.edit_text(
            f"🗑 حذف سفارش #{order_id}؟\n\nاین عمل قابل برگشت نیست.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ بله حذف کن",
                            callback_data=f"admin_odelok_{order_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ انصراف",
                            callback_data=f"admin_o_{order_id}"
                        )
                    ]
                ]
            )
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_odelok_\d+$")
    )
    async def admin_order_delete_ok(client, query):

        if not admin(query.from_user.id, config):
            return

        order_id = int(query.data.split("_")[-1])
        order = get_order(order_id)
        uid = order["user_id"] if order else 0

        if order:
            delete_order(order_id)

        await query.answer("حذف شد.")
        # back to orders list
        if uid:
            query.data = f"admin_uorders_{uid}"
            await admin_user_orders(client, query)
        else:
            await query.message.edit_text(
                "✅ سفارش حذف شد.",
                reply_markup=back_admin_keyboard()
            )


    @app.on_callback_query(
        filters.regex(r"^admin_usubs_\d+$")
    )
    async def admin_user_subs(client, query):

        if not admin(query.from_user.id, config):
            return

        target_id = int(query.data.split("_")[-1])
        subs = get_user_subscriptions(target_id)

        if not subs:
            await query.message.edit_text(
                f"📦 اشتراکی برای کاربر <code>{target_id}</code> نیست.",
                reply_markup=user_detail_keyboard(target_id),
                parse_mode=enums.ParseMode.HTML
            )
            await query.answer()
            return

        lines = [
            f"📦 اشتراک‌های کاربر <code>{target_id}</code>\n",
            "روی هر اشتراک بزنید تا مدیریت شود.\n"
        ]
        rows = []

        for s in subs[:25]:
            lines.append(
                f"#{s['id']} | {s['service_name']} | "
                f"<code>{s['username']}</code> | {s['status']}"
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        f"#{s['id']} | {s['service_name'][:20]}",
                        callback_data=f"admin_s_{s['id']}"
                    )
                ]
            )

        rows.append(
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data=f"admin_user_{target_id}"
                )
            ]
        )

        await query.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_s_\d+$")
    )
    async def admin_sub_manage(client, query):

        if not admin(query.from_user.id, config):
            return

        sub_id = int(query.data.split("_")[-1])
        sub = get_subscription(sub_id)

        if not sub:
            await query.answer("❌ اشتراک پیدا نشد.", show_alert=True)
            return

        uid = sub["user_id"]
        cfg = (sub.get("config_text") or "—")
        if len(cfg) > 200:
            cfg = cfg[:200] + "..."

        text = (
            f"📦 مدیریت اشتراک #{sub_id}\n\n"
            f"👤 کاربر: <code>{uid}</code>\n"
            f"📦 سرویس: {sub['service_name']}\n"
            f"👤 نام کاربری: <code>{sub['username']}</code>\n"
            f"🔵 وضعیت: {sub['status']}\n"
            f"📅 ایجاد: {sub.get('created_at') or '—'}\n\n"
            f"⚙️ کانفیگ:\n<code>{cfg}</code>\n"
        )
        if sub.get("subscription_url"):
            text += f"\n🔗 لینک:\n{sub['subscription_url']}"

        rows = [
            [
                InlineKeyboardButton(
                    "🟢 active",
                    callback_data=f"admin_sst_active_{sub_id}"
                ),
                InlineKeyboardButton(
                    "🔴 inactive",
                    callback_data=f"admin_sst_inactive_{sub_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ ویرایش کانفیگ",
                    callback_data=f"admin_seditcfg_{sub_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ ویرایش نام کاربری",
                    callback_data=f"admin_sedituser_{sub_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ ویرایش نام سرویس",
                    callback_data=f"admin_seditname_{sub_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 حذف اشتراک",
                    callback_data=f"admin_sdel_{sub_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت به اشتراک‌ها",
                    callback_data=f"admin_usubs_{uid}"
                )
            ]
        ]

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_sst_(active|inactive)_\d+$")
    )
    async def admin_sub_set_status(client, query):

        if not admin(query.from_user.id, config):
            return

        parts = query.data.split("_")
        status = parts[2]
        sub_id = int(parts[3])

        update_subscription_status(sub_id, status)
        await query.answer(f"وضعیت → {status}")
        query.data = f"admin_s_{sub_id}"
        await admin_sub_manage(client, query)


    @app.on_callback_query(
        filters.regex(r"^admin_seditcfg_\d+$")
    )
    async def admin_sub_edit_cfg(client, query):

        if not admin(query.from_user.id, config):
            return

        sub_id = int(query.data.split("_")[-1])
        admin_states[query.from_user.id] = {
            "step": "edit_sub_config",
            "sub_id": sub_id
        }
        await query.message.reply_text(
            f"⚙️ کانفیگ جدید برای اشتراک #{sub_id} را بفرستید:"
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_sedituser_\d+$")
    )
    async def admin_sub_edit_user(client, query):

        if not admin(query.from_user.id, config):
            return

        sub_id = int(query.data.split("_")[-1])
        admin_states[query.from_user.id] = {
            "step": "edit_sub_username",
            "sub_id": sub_id
        }
        await query.message.reply_text(
            f"👤 نام کاربری جدید برای اشتراک #{sub_id} را بفرستید (بدون @):"
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_seditname_\d+$")
    )
    async def admin_sub_edit_name(client, query):

        if not admin(query.from_user.id, config):
            return

        sub_id = int(query.data.split("_")[-1])
        admin_states[query.from_user.id] = {
            "step": "edit_sub_service",
            "sub_id": sub_id
        }
        await query.message.reply_text(
            f"📦 نام سرویس جدید برای اشتراک #{sub_id} را بفرستید:"
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_sdel_\d+$")
    )
    async def admin_sub_delete(client, query):

        if not admin(query.from_user.id, config):
            return

        sub_id = int(query.data.split("_")[-1])
        sub = get_subscription(sub_id)

        if not sub:
            await query.answer("❌ اشتراک پیدا نشد.", show_alert=True)
            return

        await query.message.edit_text(
            f"🗑 حذف اشتراک #{sub_id}؟\n\nاین عمل قابل برگشت نیست.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ بله حذف کن",
                            callback_data=f"admin_sdelok_{sub_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ انصراف",
                            callback_data=f"admin_s_{sub_id}"
                        )
                    ]
                ]
            )
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_sdelok_\d+$")
    )
    async def admin_sub_delete_ok(client, query):

        if not admin(query.from_user.id, config):
            return

        sub_id = int(query.data.split("_")[-1])
        sub = get_subscription(sub_id)
        uid = sub["user_id"] if sub else 0

        if sub:
            delete_subscription(sub_id)

        await query.answer("حذف شد.")
        if uid:
            query.data = f"admin_usubs_{uid}"
            await admin_user_subs(client, query)
        else:
            await query.message.edit_text(
                "✅ اشتراک حذف شد.",
                reply_markup=back_admin_keyboard()
            )


    @app.on_callback_query(
        filters.regex(r"^admin_ureset_\d+$")
    )
    async def admin_user_reset(client, query):

        if not admin(query.from_user.id, config):
            return

        target_id = int(query.data.split("_")[-1])

        await query.message.edit_text(
            f"♻️ ریست اطلاعات کاربر <code>{target_id}</code>\n\n"
            "این کار اشتراک‌ها و شمارنده‌های دعوت را پاک می‌کند.\n"
            "سفارش‌ها برای تاریخچه نگه داشته می‌شوند.\n\n"
            "مطمئن هستید؟",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ بله، ریست کن",
                            callback_data=f"admin_uresetok_{target_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ انصراف",
                            callback_data=f"admin_user_{target_id}"
                        )
                    ]
                ]
            ),
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_uresetok_\d+$")
    )
    async def admin_user_reset_ok(client, query):

        if not admin(query.from_user.id, config):
            return

        target_id = int(query.data.split("_")[-1])
        reset_user_info(target_id)

        await query.message.edit_text(
            f"✅ اطلاعات کاربر <code>{target_id}</code> ریست شد.",
            reply_markup=user_detail_keyboard(target_id),
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer("ریست شد.")


    @app.on_callback_query(
        filters.regex(r"^admin_uaddsub_\d+$")
    )
    async def admin_user_addsub(client, query):

        if not admin(query.from_user.id, config):
            return

        target_id = int(query.data.split("_")[-1])

        admin_states[query.from_user.id] = {
            "step": "manual_sub_service",
            "target_id": target_id
        }

        await query.message.reply_text(
            f"➕ افزودن اشتراک دستی برای <code>{target_id}</code>\n\n"
            "📦 نام سرویس را بفرستید:",
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_msg_\d+$")
    )
    async def admin_msg_user(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        target_id = int(query.data.split("_")[-1])

        admin_states[query.from_user.id] = {
            "step": "message_user",
            "target_id": target_id
        }

        await query.message.reply_text(
            f"✉️ پیام خود را برای کاربر <code>{target_id}</code> بنویسید:",
            parse_mode=enums.ParseMode.HTML
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
    # مدیریت آموزش‌ها
    # =========================================================

    @app.on_callback_query(
        filters.regex("^admin_tutorials$")
    )
    async def admin_tutorials(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        tutorials = get_tutorials(False)

        await query.message.edit_text(
            "📚 مدیریت آموزش‌ها\n\n"
            "روی هر مورد بزنید تا متن، فایل نصب یا ویدیو را تنظیم کنید.\n"
            "با «➕ افزودن دکمه آموزش» می‌توانید دکمه جدید بسازید.",
            reply_markup=admin_tutorials_keyboard(tutorials)
        )

        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_tut_\d+$")
    )
    async def admin_tut_item(client, query):

        if not admin(
            query.from_user.id,
            config
        ):
            return

        tutorial_id = int(query.data.split("_")[-1])
        item = get_tutorial(tutorial_id)

        if not item:
            await query.answer("❌ پیدا نشد.", show_alert=True)
            return

        status = "فعال" if item["active"] else "غیرفعال"
        has_file = "دارد" if item.get("file_id") else "ندارد"
        has_video = "دارد" if item.get("video_file_id") else "ندارد"
        body_preview = (item.get("body_text") or "")[:120]

        await query.message.edit_text(
            f"📚 {item['title']}\n\n"
            f"وضعیت: {status}\n"
            f"فایل نصب: {has_file}\n"
            f"ویدیو: {has_video}\n\n"
            f"متن:\n{body_preview}",
            reply_markup=admin_tutorial_item_keyboard(tutorial_id)
        )

        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_tut_text_\d+$")
    )
    async def admin_tut_text(client, query):

        if not admin(query.from_user.id, config):
            return

        tutorial_id = int(query.data.split("_")[-1])

        admin_states[query.from_user.id] = {
            "step": "tut_text",
            "tutorial_id": tutorial_id
        }

        await query.message.reply_text(
            "✏️ متن کامل این آموزش را ارسال کنید:\n\n"
            "همین متن وقتی کاربر روی دکمه بزند نمایش داده می‌شود."
        )

        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_tut_file_\d+$")
    )
    async def admin_tut_file(client, query):

        if not admin(query.from_user.id, config):
            return

        tutorial_id = int(query.data.split("_")[-1])

        admin_states[query.from_user.id] = {
            "step": "tut_file",
            "tutorial_id": tutorial_id
        }

        await query.message.reply_text(
            "📎 فایل نصب (APK یا هر فایل دیگر) را همینجا ارسال کنید.\n"
            "برای پاک کردن فایل، کلمه clear را بفرستید."
        )

        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_tut_video_\d+$")
    )
    async def admin_tut_video(client, query):

        if not admin(query.from_user.id, config):
            return

        tutorial_id = int(query.data.split("_")[-1])

        admin_states[query.from_user.id] = {
            "step": "tut_video",
            "tutorial_id": tutorial_id
        }

        await query.message.reply_text(
            "🎬 ویدیو آموزشی را همینجا ارسال کنید.\n"
            "برای پاک کردن، کلمه clear را بفرستید."
        )

        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^admin_tut_toggle_\d+$")
    )
    async def admin_tut_toggle(client, query):

        if not admin(query.from_user.id, config):
            return

        tutorial_id = int(query.data.split("_")[-1])
        new_state = toggle_tutorial(tutorial_id)

        tutorials = get_tutorials(False)

        await query.message.edit_text(
            "📚 مدیریت آموزش‌ها",
            reply_markup=admin_tutorials_keyboard(tutorials)
        )

        await query.answer(
            "🟢 فعال شد." if new_state else "🔴 غیرفعال شد."
        )


    @app.on_callback_query(
        filters.regex(r"^admin_tut_del_\d+$")
    )
    async def admin_tut_del(client, query):

        if not admin(query.from_user.id, config):
            return

        tutorial_id = int(query.data.split("_")[-1])
        delete_tutorial(tutorial_id)

        tutorials = get_tutorials(False)

        await query.message.edit_text(
            "📚 مدیریت آموزش‌ها\n\nآیتم حذف شد.",
            reply_markup=admin_tutorials_keyboard(tutorials)
        )

        await query.answer("حذف شد.")


    @app.on_callback_query(
        filters.regex("^admin_tut_add$")
    )
    async def admin_tut_add(client, query):

        if not admin(query.from_user.id, config):
            return

        admin_states[query.from_user.id] = {
            "step": "tut_add_title"
        }

        await query.message.reply_text(
            "➕ عنوان دکمه آموزش جدید را بنویسید:\n\n"
            "مثال: آموزش اتصال در مک"
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

    @app.on_message(
        filters.private & (
            filters.document | filters.video | filters.animation
        ),
        group=-2
    )
    async def admin_media(client, message):

        user_id = message.from_user.id

        if not admin(user_id, config):
            return

        state = admin_states.get(user_id)

        if not state:
            return

        step = state.get("step")

        if step not in ("tut_file", "tut_video", "restore_backup"):
            return

        if step == "restore_backup":
            # leave to restore handler if document zip
            if message.document and (message.document.file_name or "").lower().endswith(".zip"):
                return
            return

        tutorial_id = state["tutorial_id"]

        file_id = None

        if message.document:
            file_id = message.document.file_id
        elif message.video:
            file_id = message.video.file_id
        elif message.animation:
            file_id = message.animation.file_id

        if not file_id:

            await message.reply_text("❌ فایل معتبر نیست.")
            raise StopPropagation

        # Keep a durable copy inside the dedicated Telegram files channel.
        stored = await store_media_message(message)

        if stored and stored.get("file_id"):
            file_id = stored["file_id"]

        field = "file_id" if step == "tut_file" else "video_file_id"

        update_tutorial_field(
            tutorial_id,
            field,
            file_id
        )

        admin_states.pop(user_id, None)

        label = "فایل نصب" if step == "tut_file" else "ویدیو"

        await message.reply_text(
            f"✅ {label} ذخیره شد.\n"
            "وقتی کاربر این آموزش را بزند، این فایل برایش ارسال می‌شود.",
            reply_markup=admin_reply_menu()
        )

        raise StopPropagation


