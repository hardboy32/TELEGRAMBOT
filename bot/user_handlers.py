from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .database import (
    add_or_update_user,
    get_user,
    get_services,
    get_service,
    create_order,
    set_receipt,
    get_order,
    get_user_orders,
    get_user_subscriptions,
    get_subscription,
    get_referral_count,
    get_referral_reward_count,
    get_coupon,
    use_coupon,
    get_referrer,
    record_successful_referral,
    reset_low_volume_warning,
)

from .messages import welcome, join_required, payment, order_text


# =========================================================
# ابزارهای کمکی
# =========================================================

def is_enabled(config, key):
    return config.get(key, True)


def main_menu(config):
    buttons = []

    if is_enabled(config, "buy_enabled"):
        buttons.append([
            InlineKeyboardButton(
                "🛒 خرید سرویس",
                callback_data="user_buy"
            )
        ])

    row = []

    if is_enabled(config, "renew_enabled"):
        row.append(
            InlineKeyboardButton(
                "🔄 تمدید",
                callback_data="user_renew"
            )
        )

    if is_enabled(config, "subscriptions_enabled"):
        row.append(
            InlineKeyboardButton(
                "📦 اشتراک‌های من",
                callback_data="user_subscriptions"
            )
        )

    if row:
        buttons.append(row)

    row = []

    if is_enabled(config, "status_enabled"):
        row.append(
            InlineKeyboardButton(
                "📊 وضعیت",
                callback_data="user_status"
            )
        )

    if is_enabled(config, "order_history_enabled"):
        row.append(
            InlineKeyboardButton(
                "📜 تاریخچه سفارش‌ها",
                callback_data="user_orders"
            )
        )

    if row:
        buttons.append(row)

    row = []

    if is_enabled(config, "referral_enabled"):
        row.append(
            InlineKeyboardButton(
                "👥 دعوت دوستان",
                callback_data="user_referral"
            )
        )

    if is_enabled(config, "account_enabled"):
        row.append(
            InlineKeyboardButton(
                "👤 حساب من",
                callback_data="user_account"
            )
        )

    if row:
        buttons.append(row)

    row = []

    if is_enabled(config, "support_enabled"):
        row.append(
            InlineKeyboardButton(
                "☎️ پشتیبانی",
                callback_data="user_support"
            )
        )

    if is_enabled(config, "tutorial_enabled"):
        row.append(
            InlineKeyboardButton(
                "📚 آموزش",
                callback_data="user_tutorial"
            )
        )

    if row:
        buttons.append(row)

    if is_enabled(config, "coupon_enabled"):
        buttons.append([
            InlineKeyboardButton(
                "🎟️ کد تخفیف",
                callback_data="user_coupon"
            )
        ])

    return InlineKeyboardMarkup(buttons)


def back_home():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 منوی اصلی",
                callback_data="user_home"
            )
        ]
    ])


def services_keyboard():
    services = get_services(active_only=True)

    buttons = []

    for service in services:
        buttons.append([
            InlineKeyboardButton(
                f"📦 {service['name']} - "
                f"{service['volume_gb']}GB | "
                f"{service['price']:,} تومان",
                callback_data=f"service_{service['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="user_home"
        )
    ])

    return InlineKeyboardMarkup(buttons)


def order_keyboard(service_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ ادامه سفارش",
                callback_data=f"buy_service_{service_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 سرویس‌ها",
                callback_data="user_buy"
            )
        ]
    ])


def payment_keyboard(order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📤 ارسال رسید پرداخت",
                callback_data=f"send_receipt_{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 منوی اصلی",
                callback_data="user_home"
            )
        ]
    ])


# =========================================================
# ثبت Handler ها
# =========================================================

def register(app, config):

    app.user_state = {}

    # =====================================================
    # /start
    # =====================================================

    @app.on_message(
        filters.private
        & filters.command("start")
    )
    async def start(client, message):

        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name or ""

        referral_by = None

        if len(message.command) > 1:

            payload = message.command[1]

            if payload.startswith("ref_"):

                try:
                    referral_by = int(
                        payload.replace("ref_", "", 1)
                    )
                except Exception:
                    referral_by = None

        add_or_update_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            referral_by=referral_by
        )

        if not is_enabled(
            config,
            "join_required_enabled"
        ):
            await message.reply_text(
                welcome(first_name),
                reply_markup=main_menu(config)
            )
            return

        channel = config.get("channel_username")

        if not channel or channel == "@YOUR_CHANNEL":

            await message.reply_text(
                welcome(first_name),
                reply_markup=main_menu(config)
            )
            return

        try:

            member = await client.get_chat_member(
                channel,
                user_id
            )

            if member.status in [
                "member",
                "administrator",
                "owner"
            ]:

                await message.reply_text(
                    welcome(first_name),
                    reply_markup=main_menu(config)
                )

            else:

                await message.reply_text(
                    join_required(),
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "📢 عضویت در کانال",
                                url=(
                                    f"https://t.me/"
                                    f"{channel.lstrip('@')}"
                                )
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "✅ بررسی عضویت",
                                callback_data="check_join"
                            )
                        ]
                    ])
                )

        except Exception:

            await message.reply_text(
                welcome(first_name),
                reply_markup=main_menu(config)
            )

    # =====================================================
    # Callback های کاربر
    # =====================================================

    @app.on_callback_query(
        filters.regex(r"^(user_|check_join|service_|buy_service_|"
                      r"renew_|sub_|send_receipt_)")
    )
    async def user_callbacks(client, query):

        user_id = query.from_user.id
        data = query.data

        # -------------------------------------------------
        # بررسی عضویت
        # -------------------------------------------------

        if data == "check_join":

            channel = config.get("channel_username")

            try:

                member = await client.get_chat_member(
                    channel,
                    user_id
                )

                if member.status in [
                    "member",
                    "administrator",
                    "owner"
                ]:

                    user = get_user(user_id)

                    first_name = (
                        user["first_name"]
                        if user
                        else query.from_user.first_name or ""
                    )

                    await query.message.edit_text(
                        welcome(first_name),
                        reply_markup=main_menu(config)
                    )

                    await query.answer(
                        "عضویت شما تأیید شد."
                    )

                else:

                    await query.answer(
                        "❌ هنوز عضو کانال نشده‌اید.",
                        show_alert=True
                    )

            except Exception:

                await query.answer(
                    "❌ امکان بررسی عضویت وجود ندارد.",
                    show_alert=True
                )

            return

        # -------------------------------------------------
        # منوی اصلی
        # -------------------------------------------------

        if data == "user_home":

            user = get_user(user_id)

            first_name = (
                user["first_name"]
                if user
                else query.from_user.first_name or ""
            )

            await query.message.edit_text(
                welcome(first_name),
                reply_markup=main_menu(config)
            )

            await query.answer()
            return

        # -------------------------------------------------
        # خرید
        # -------------------------------------------------

        if data == "user_buy":

            if not is_enabled(config, "buy_enabled"):

                await query.answer(
                    "این بخش در حال حاضر غیرفعال است.",
                    show_alert=True
                )
                return

            services = get_services(active_only=True)

            if not services:

                await query.message.edit_text(
                    "❌ در حال حاضر هیچ سرویسی برای فروش وجود ندارد.",
                    reply_markup=back_home()
                )

                await query.answer()
                return

            await query.message.edit_text(
                "🛒 خرید سرویس\n\n"
                "لطفاً سرویس موردنظر خود را انتخاب کنید:",
                reply_markup=services_keyboard()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # انتخاب سرویس
        # -------------------------------------------------

        if data.startswith("service_"):

            try:

                service_id = int(
                    data.replace(
                        "service_",
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

            service = get_service(service_id)

            if not service or not service["active"]:

                await query.answer(
                    "این سرویس در دسترس نیست.",
                    show_alert=True
                )
                return

            await query.message.edit_text(
                "📦 مشخصات سرویس\n\n"
                f"📌 نام: {service['name']}\n"
                f"💾 حجم: {service['volume_gb']}GB\n"
                f"💰 قیمت: {service['price']:,} تومان\n\n"
                "برای ادامه سفارش دکمه زیر را بزنید.",
                reply_markup=order_keyboard(service_id)
            )

            await query.answer()
            return

        # -------------------------------------------------
        # ادامه خرید
        # -------------------------------------------------

        if data.startswith("buy_service_"):

            try:

                service_id = int(
                    data.replace(
                        "buy_service_",
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

            service = get_service(service_id)

            if not service or not service["active"]:

                await query.answer(
                    "این سرویس دیگر فعال نیست.",
                    show_alert=True
                )
                return

            app.user_state[user_id] = {
                "action": "service_username",
                "service_id": service_id,
                "service_name": service["name"],
                "price": service["price"]
            }

            await query.message.edit_text(
                "👤 نام کاربری سرویس\n\n"
                "لطفاً نام کاربری دلخواه خود را ارسال کنید.\n\n"
                "مثال:\n"
                "`myvpn123`",
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # تمدید
        # -------------------------------------------------

        if data == "user_renew":

            if not is_enabled(config, "renew_enabled"):

                await query.answer(
                    "این بخش در حال حاضر غیرفعال است.",
                    show_alert=True
                )
                return

            subscriptions = get_user_subscriptions(user_id)

            if not subscriptions:

                await query.message.edit_text(
                    "📦 شما هنوز اشتراک فعالی ندارید.",
                    reply_markup=back_home()
                )

                await query.answer()
                return

            buttons = []

            for sub in subscriptions:

                buttons.append([
                    InlineKeyboardButton(
                        f"🔄 {sub['service_name']}",
                        callback_data=f"renew_{sub['id']}"
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="user_home"
                )
            ])

            await query.message.edit_text(
                "🔄 تمدید اشتراک\n\n"
                "اشتراکی که می‌خواهید تمدید کنید را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            await query.answer()
            return

        # -------------------------------------------------
        # انتخاب اشتراک برای تمدید
        # -------------------------------------------------

        if data.startswith("renew_"):

            try:

                subscription_id = int(
                    data.replace(
                        "renew_",
                        "",
                        1
                    )
                )

            except Exception:

                await query.answer(
                    "اشتراک نامعتبر است.",
                    show_alert=True
                )
                return

            sub = get_subscription(subscription_id)

            if not sub or sub["user_id"] != user_id:

                await query.answer(
                    "اشتراک پیدا نشد.",
                    show_alert=True
                )
                return

            services = get_services(active_only=True)

            buttons = []

            for service in services:

                buttons.append([
                    InlineKeyboardButton(
                        f"📦 {service['name']} - "
                        f"{service['price']:,} تومان",
                        callback_data=(
                            f"renew_service_"
                            f"{service['id']}_"
                            f"{subscription_id}"
                        )
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="user_renew"
                )
            ])

            await query.message.edit_text(
                "🔄 انتخاب سرویس برای تمدید\n\n"
                "سرویس موردنظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            await query.answer()
            return

        # -------------------------------------------------
        # انتخاب سرویس تمدید
        # -------------------------------------------------

        if data.startswith("renew_service_"):

            parts = data.split("_")

            try:

                service_id = int(parts[2])
                subscription_id = int(parts[3])

            except Exception:

                await query.answer(
                    "اطلاعات تمدید نامعتبر است.",
                    show_alert=True
                )
                return

            service = get_service(service_id)
            sub = get_subscription(subscription_id)

            if not service or not sub:

                await query.answer(
                    "اطلاعات پیدا نشد.",
                    show_alert=True
                )
                return

            if sub["user_id"] != user_id:

                await query.answer(
                    "دسترسی غیرمجاز.",
                    show_alert=True
                )
                return

            app.user_state[user_id] = {
                "action": "renew_username",
                "service_id": service_id,
                "service_name": service["name"],
                "price": service["price"],
                "subscription_id": subscription_id,
                "username": sub["username"]
            }

            await query.message.edit_text(
                "👤 نام کاربری تمدید\n\n"
                f"نام کاربری فعلی:\n`{sub['username']}`\n\n"
                "نام کاربری را ارسال کنید.",
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # اشتراک‌های من
        # -------------------------------------------------

        if data == "user_subscriptions":

            if not is_enabled(
                config,
                "subscriptions_enabled"
            ):

                await query.answer(
                    "این بخش در حال حاضر غیرفعال است.",
                    show_alert=True
                )
                return

            subscriptions = get_user_subscriptions(user_id)

            if not subscriptions:

                await query.message.edit_text(
                    "📦 شما هنوز اشتراک فعالی ندارید.",
                    reply_markup=back_home()
                )

                await query.answer()
                return

            buttons = []

            for sub in subscriptions:

                buttons.append([
                    InlineKeyboardButton(
                        f"📦 {sub['service_name']} - "
                        f"{sub['username']}",
                        callback_data=f"sub_{sub['id']}"
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="user_home"
                )
            ])

            await query.message.edit_text(
                "📦 اشتراک‌های من\n\n"
                "برای مشاهده جزئیات، اشتراک را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            await query.answer()
            return

        # -------------------------------------------------
        # جزئیات اشتراک
        # -------------------------------------------------

        if data.startswith("sub_"):

            try:

                subscription_id = int(
                    data.replace(
                        "sub_",
                        "",
                        1
                    )
                )

            except Exception:

                await query.answer(
                    "اشتراک نامعتبر است.",
                    show_alert=True
                )
                return

            sub = get_subscription(subscription_id)

            if not sub or sub["user_id"] != user_id:

                await query.answer(
                    "اشتراک پیدا نشد.",
                    show_alert=True
                )
                return

            text = (
                "📦 اشتراک شما\n\n"
                f"📌 سرویس: {sub['service_name']}\n"
                f"👤 نام کاربری: {sub['username']}\n"
                f"📊 وضعیت: {sub['status']}\n\n"
            )

            if sub.get("subscription_url"):

                text += (
                    "🔗 لینک اشتراک / کانفیگ:\n"
                    f"{sub['subscription_url']}\n"
                )

            await query.message.edit_text(
                text,
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # وضعیت
        # -------------------------------------------------

        if data == "user_status":

            if not is_enabled(
                config,
                "status_enabled"
            ):

                await query.answer(
                    "این بخش در حال حاضر غیرفعال است.",
                    show_alert=True
                )
                return

            subscriptions = get_user_subscriptions(user_id)

            if not subscriptions:

                await query.message.edit_text(
                    "📊 وضعیت اشتراک\n\n"
                    "شما اشتراک فعالی ندارید.",
                    reply_markup=back_home()
                )

                await query.answer()
                return

            text = "📊 وضعیت اشتراک‌های شما\n\n"

            for sub in subscriptions:

                text += (
                    f"📦 {sub['service_name']}\n"
                    f"👤 {sub['username']}\n"
                    f"🟢 وضعیت: {sub['status']}\n\n"
                )

            await query.message.edit_text(
                text,
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # تاریخچه سفارش‌ها
        # -------------------------------------------------

        if data == "user_orders":

            if not is_enabled(
                config,
                "order_history_enabled"
            ):

                await query.answer(
                    "این بخش در حال حاضر غیرفعال است.",
                    show_alert=True
                )
                return

            orders = get_user_orders(user_id)

            if not orders:

                await query.message.edit_text(
                    "📜 هنوز سفارشی ثبت نکرده‌اید.",
                    reply_markup=back_home()
                )

                await query.answer()
                return

            text = "📜 تاریخچه سفارش‌ها\n\n"

            for order in orders[:20]:

                text += (
                    f"🧾 #{order['id']}\n"
                    f"📦 {order['service_name']}\n"
                    f"💵 {order['final_price']:,} تومان\n"
                    f"📌 وضعیت: {order['status']}\n\n"
                )

            await query.message.edit_text(
                text,
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # دعوت دوستان
        # -------------------------------------------------

        if data == "user_referral":

            if not is_enabled(
                config,
                "referral_enabled"
            ):

                await query.answer(
                    "این بخش در حال حاضر غیرفعال است.",
                    show_alert=True
                )
                return

            count = get_referral_count(user_id)
            rewards = get_referral_reward_count(user_id)

            bot_info = await client.get_me()

            link = (
                f"https://t.me/{bot_info.username}"
                f"?start=ref_{user_id}"
            )

            await query.message.edit_text(
                "👥 دعوت دوستان\n\n"
                "لینک دعوت اختصاصی شما:\n\n"
                f"{link}\n\n"
                f"👥 دعوت‌های موفق فعلی: {count}\n"
                f"🎁 پاداش‌های ۱۰GB ثبت‌شده: {rewards}\n\n"
                "هر ۵ خرید موفق توسط دوستان شما، "
                "یک پاداش ۱۰GB برایتان ثبت می‌کند.",
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # حساب
        # -------------------------------------------------

        if data == "user_account":

            if not is_enabled(
                config,
                "account_enabled"
            ):

                await query.answer(
                    "این بخش در حال حاضر غیرفعال است.",
                    show_alert=True
                )
                return

            user = get_user(user_id)

            username = "-"

            if user and user["username"]:
                username = f"@{user['username']}"

            first_name = "-"

            if user:
                first_name = user["first_name"] or "-"

            await query.message.edit_text(
                "👤 حساب من\n\n"
                f"🆔 شناسه: `{user_id}`\n"
                f"👤 نام: {first_name}\n"
                f"🔗 username: {username}",
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # پشتیبانی
        # -------------------------------------------------

        if data == "user_support":

            await query.message.edit_text(
                "☎️ پشتیبانی\n\n"
                "برای دریافت پشتیبانی، پیام خود را برای "
                "ادمین ارسال کنید.",
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # آموزش
        # -------------------------------------------------

        if data == "user_tutorial":

            await query.message.edit_text(
                "📚 آموزش\n\n"
                "بعد از خرید سرویس، لینک اشتراک یا کانفیگ "
                "از طریق همین ربات برای شما ارسال می‌شود.\n\n"
                "می‌توانید از بخش «اشتراک‌های من» "
                "دوباره به اطلاعات سرویس دسترسی داشته باشید.",
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # کد تخفیف عمومی
        # -------------------------------------------------

        if data == "user_coupon":

            if not is_enabled(
                config,
                "coupon_enabled"
            ):

                await query.answer(
                    "این بخش در حال حاضر غیرفعال است.",
                    show_alert=True
                )
                return

            app.user_state[user_id] = {
                "action": "coupon"
            }

            await query.message.edit_text(
                "🎟️ کد تخفیف\n\n"
                "کد تخفیف خود را ارسال کنید.",
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # کد تخفیف هنگام سفارش
        # -------------------------------------------------

        if data == "order_coupon":

            state = app.user_state.get(user_id)

            if not state:

                await query.answer(
                    "سفارش فعال وجود ندارد.",
                    show_alert=True
                )
                return

            state["action"] = "order_coupon"

            await query.message.edit_text(
                "🎟️ کد تخفیف\n\n"
                "کد تخفیف خود را ارسال کنید.",
                reply_markup=back_home()
            )

            await query.answer()
            return

        # -------------------------------------------------
        # تأیید سفارش
        # -------------------------------------------------

        if data == "confirm_order":

            state = app.user_state.get(user_id)

            if not state:

                await query.answer(
                    "سفارش منقضی شده است.",
                    show_alert=True
                )
                return

            if state.get("action") != "confirm_order":

                await query.answer(
                    "سفارش آماده تأیید نیست.",
                    show_alert=True
                )
                return

            order_id = create_order(
                user_id=user_id,
                service_id=state["service_id"],
                service_name=state["service_name"],
                order_type="buy",
                username=state["username"],
                original_price=state["original_price"],
                discount_percent=state["discount_percent"],
                final_price=state["final_price"],
                coupon=state["coupon"]
            )

            coupon = state.get("coupon")

            if coupon:
                use_coupon(coupon)

            app.user_state.pop(user_id, None)

            await query.message.edit_text(
                payment(
                    config.get("payment_card", ""),
                    config.get("payment_name", "")
                )
                + "\n\n"
                + f"💵 مبلغ قابل پرداخت: "
                f"{state['final_price']:,} تومان\n\n"
                + "بعد از پرداخت، عکس رسید را ارسال کنید.",
                reply_markup=payment_keyboard(order_id)
            )

            await query.answer()
            return

        # -------------------------------------------------
        # تأیید تمدید
        # -------------------------------------------------

        if data == "confirm_renew":

            state = app.user_state.get(user_id)

            if not state:

                await query.answer(
                    "سفارش تمدید منقضی شده است.",
                    show_alert=True
                )
                return

            order_id = create_order(
                user_id=user_id,
                service_id=state["service_id"],
                service_name=state["service_name"],
                order_type="renew",
                username=state["username"],
                original_price=state["price"],
                discount_percent=0,
                final_price=state["price"],
                coupon=None
            )

            app.user_state.pop(user_id, None)

            await query.message.edit_text(
                payment(
                    config.get("payment_card", ""),
                    config.get("payment_name", "")
                )
                + "\n\n"
                + f"💵 مبلغ تمدید: "
                f"{state['price']:,} تومان\n\n"
                + "بعد از پرداخت، عکس رسید را ارسال کنید.",
                reply_markup=payment_keyboard(order_id)
            )

            await query.answer()
            return

        # -------------------------------------------------
        # ارسال رسید
        # -------------------------------------------------

        if data.startswith("send_receipt_"):

            try:

                order_id = int(
                    data.replace(
                        "send_receipt_",
                        "",
                        1
                    )
                )

            except Exception:

                await query.answer(
                    "سفارش نامعتبر است.",
                    show_alert=True
                )
                return

            order = get_order(order_id)

            if not order or order["user_id"] != user_id:

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

            app.user_state[user_id] = {
                "action": "receipt",
                "order_id": order_id
            }

            await query.message.edit_text(
                "📤 ارسال رسید پرداخت\n\n"
                "لطفاً عکس رسید پرداخت را همینجا ارسال کنید.",
                reply_markup=back_home()
            )

            await query.answer()
            return

    # =====================================================
    # پیام‌های متنی کاربر
    # =====================================================

    @app.on_message(
        filters.private
        & filters.text
    )
    async def user_text(client, message):

        user_id = message.from_user.id

        state = app.user_state.get(user_id)

        if not state:
            return

        action = state.get("action")

        # -------------------------------------------------
        # نام کاربری خرید
        # -------------------------------------------------

        if action == "service_username":

            username = message.text.strip()

            if len(username) < 3:

                await message.reply_text(
                    "❌ نام کاربری باید حداقل ۳ کاراکتر باشد."
                )
                return

            service = get_service(
                state["service_id"]
            )

            if not service or not service["active"]:

                await message.reply_text(
                    "❌ این سرویس دیگر در دسترس نیست."
                )

                app.user_state.pop(user_id, None)
                return

            original_price = service["price"]

            app.user_state[user_id] = {
                "action": "confirm_order",
                "service_id": service["id"],
                "service_name": service["name"],
                "username": username,
                "original_price": original_price,
                "discount_percent": 0,
                "final_price": original_price,
                "coupon": None
            }

            await message.reply_text(
                order_text(
                    service,
                    username,
                    0,
                    original_price
                ),
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🎟️ وارد کردن کد تخفیف",
                            callback_data="order_coupon"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "✅ تأیید سفارش",
                            callback_data="confirm_order"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 لغو",
                            callback_data="user_home"
                        )
                    ]
                ])
            )

            return

        # -------------------------------------------------
        # نام کاربری تمدید
        # -------------------------------------------------

        if action == "renew_username":

            username = message.text.strip()

            if len(username) < 3:

                await message.reply_text(
                    "❌ نام کاربری نامعتبر است."
                )
                return

            state["username"] = username
            state["action"] = "confirm_renew"

            await message.reply_text(
                "🔄 تمدید سرویس\n\n"
                f"📦 سرویس: {state['service_name']}\n"
                f"👤 نام کاربری: {username}\n"
                f"💰 مبلغ: {state['price']:,} تومان\n\n"
                "آیا سفارش تمدید را تأیید می‌کنید؟",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✅ تأیید",
                            callback_data="confirm_renew"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 لغو",
                            callback_data="user_home"
                        )
                    ]
                ])
            )

            return

        # -------------------------------------------------
        # کد تخفیف در سفارش
        # -------------------------------------------------

        if action == "order_coupon":

            code = message.text.strip().upper()

            coupon = get_coupon(code)

            if not coupon:

                await message.reply_text(
                    "❌ کد تخفیف پیدا نشد."
                )
                return

            if not coupon["active"]:

                await message.reply_text(
                    "❌ این کد تخفیف غیرفعال است."
                )
                return

            if (
                coupon["max_uses"] > 0
                and coupon["used_count"] >= coupon["max_uses"]
            ):

                await message.reply_text(
                    "❌ ظرفیت استفاده از این کد تمام شده است."
                )
                return

            discount_percent = coupon["percent"]

            original_price = state["original_price"]

            discount_amount = int(
                original_price * discount_percent / 100
            )

            final_price = (
                original_price - discount_amount
            )

            state["discount_percent"] = discount_percent
            state["final_price"] = final_price
            state["coupon"] = code
            state["action"] = "confirm_order"

            service = get_service(
                state["service_id"]
            )

            await message.reply_text(
                order_text(
                    service,
                    state["username"],
                    discount_percent,
                    final_price
                ),
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✅ تأیید سفارش",
                            callback_data="confirm_order"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎟️ تغییر کد تخفیف",
                            callback_data="order_coupon"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 لغو",
                            callback_data="user_home"
                        )
                    ]
                ])
            )

            return

        # -------------------------------------------------
        # کد تخفیف عمومی
        # -------------------------------------------------

        if action == "coupon":

            code = message.text.strip().upper()

            coupon = get_coupon(code)

            if not coupon:

                await message.reply_text(
                    "❌ کد تخفیف پیدا نشد."
                )
                return

            if not coupon["active"]:

                await message.reply_text(
                    "❌ این کد تخفیف غیرفعال است."
                )
                return

            if (
                coupon["max_uses"] > 0
                and coupon["used_count"] >= coupon["max_uses"]
            ):

                await message.reply_text(
                    "❌ ظرفیت استفاده از این کد تمام شده است."
                )
                return

            await message.reply_text(
                f"✅ کد تخفیف `{code}` معتبر است.\n\n"
                f"📉 میزان تخفیف: {coupon['percent']}%\n\n"
                "در هنگام خرید می‌توانید از این کد استفاده کنید.",
                reply_markup=back_home()
            )

            app.user_state.pop(user_id, None)
            return

    # =====================================================
    # دریافت عکس رسید
    # =====================================================

    @app.on_message(
        filters.private
        & filters.photo
    )
    async def receipt_handler(client, message):

        user_id = message.from_user.id

        state = app.user_state.get(user_id)

        if not state:
            return

        if state.get("action") != "receipt":
            return

        order_id = state["order_id"]

        order = get_order(order_id)

        if not order or order["user_id"] != user_id:

            await message.reply_text(
                "❌ سفارش پیدا نشد."
            )

            app.user_state.pop(user_id, None)
            return

        if order["status"] != "pending":

            await message.reply_text(
                "❌ این سفارش قبلاً بررسی شده است."
            )

            app.user_state.pop(user_id, None)
            return

        photo_id = message.photo.file_id

        set_receipt(
            order_id,
            photo_id
        )

        app.user_state.pop(user_id, None)

        await message.reply_text(
            "✅ رسید شما دریافت شد.\n\n"
            f"🧾 شماره سفارش: #{order_id}\n\n"
            "⏳ رسید توسط مدیریت بررسی می‌شود."
        )

        # ارسال رسید برای ادمین‌ها
        for admin_id in config.get("admin_ids", []):

            try:

                await client.send_photo(
                    admin_id,
                    photo_id,
                    caption=(
                        "🧾 رسید پرداخت جدید\n\n"
                        f"🆔 سفارش: #{order_id}\n"
                        f"👤 کاربر: {user_id}\n"
                        f"📦 سرویس: {order['service_name']}\n"
                        f"💵 مبلغ: "
                        f"{order['final_price']:,} تومان"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "🧾 مشاهده سفارش",
                                callback_data=(
                                    f"admin_order_{order_id}"
                                )
                            )
                        ]
                    ])
                )

            except Exception:
                pass
