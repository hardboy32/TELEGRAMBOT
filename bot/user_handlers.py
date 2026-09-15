from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
)

from .database import (
    add_or_update_user,
    get_user,
    get_services,
    get_service,
    create_order,
    set_receipt,
    get_user_orders,
    get_user_subscriptions,
    get_subscription,
    get_referrer,
    get_referral_count,
    get_referral_reward_count,
    get_coupon,
    use_coupon,
    reset_low_volume_warning
)

from .helpers import calc, referral_link
from .messages import welcome, join_required, payment, order_text
from .keyboards import main_menu


def register(app, config):

    # =====================================================
    # ابزارها
    # =====================================================

    async def is_joined(client, user_id):

        if not config.get(
            "join_required_enabled",
            True
        ):
            return True

        channel = config.get(
            "channel_username"
        )

        if not channel or channel == "@YOUR_CHANNEL":
            return True

        try:

            member = await client.get_chat_member(
                channel,
                user_id
            )

            return member.status in [
                "member",
                "administrator",
                "owner"
            ]

        except Exception:

            return False

    async def send_main_menu(client, chat_id, text=None):

        if text is None:
            text = "👇 از منوی زیر انتخاب کنید:"

        await client.send_message(
            chat_id,
            text,
            reply_markup=main_menu(config)
        )

    # =====================================================
    # /start
    # =====================================================

    @app.on_message(
        filters.private
        & filters.command("start")
    )
    async def start(client, message):

        user = message.from_user

        referral_by = None

        if len(message.command) > 1:

            start_param = message.command[1]

            if start_param.startswith("ref_"):

                try:
                    referral_by = int(
                        start_param.replace(
                            "ref_",
                            "",
                            1
                        )
                    )
                except Exception:
                    referral_by = None

        add_or_update_user(
            user.id,
            user.username,
            user.first_name,
            referral_by
        )

        if not await is_joined(
            client,
            user.id
        ):

            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📢 عضویت در کانال",
                        url=(
                            "https://t.me/"
                            + config["channel_username"].replace(
                                "@",
                                ""
                            )
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

            await message.reply_text(
                join_required(),
                reply_markup=buttons
            )

            return

        await message.reply_text(
            welcome(
                user.first_name or "دوست عزیز"
            ),
            reply_markup=main_menu(config)
        )

    # =====================================================
    # بررسی عضویت
    # =====================================================

    @app.on_callback_query(
        filters.regex("^check_join$")
    )
    async def check_join(client, query):

        if await is_joined(
            client,
            query.from_user.id
        ):

            await query.message.delete()

            await send_main_menu(
                client,
                query.from_user.id,
                "✅ عضویت شما تأیید شد.\n\n"
                "👇 از منوی زیر انتخاب کنید:"
            )

            await query.answer(
                "عضویت تأیید شد."
            )

        else:

            await query.answer(
                "❌ هنوز عضو کانال نشده‌اید.",
                show_alert=True
            )

    # =====================================================
    # خرید سرویس
    # =====================================================

    async def show_services(client, message):

        services = get_services(
            active_only=True
        )

        if not services:

            await message.reply_text(
                "❌ در حال حاضر سرویسی برای فروش وجود ندارد.",
                reply_markup=main_menu(config)
            )

            return

        buttons = []

        for service in services:

            buttons.append([
                InlineKeyboardButton(
                    (
                        f"📦 {service['name']} | "
                        f"{service['volume_gb']}GB | "
                        f"{service['price']:,} تومان"
                    ),
                    callback_data=(
                        f"service_{service['id']}"
                    )
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="user_home"
            )
        ])

        await message.reply_text(
            "📦 سرویس موردنظر خود را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    @app.on_message(
        filters.private
        & filters.regex("^🛒 خرید سرویس$")
    )
    async def buy_service_button(client, message):

        if not await is_joined(
            client,
            message.from_user.id
        ):
            await message.reply_text(
                join_required()
            )
            return

        await show_services(
            client,
            message
        )

    # =====================================================
    # انتخاب سرویس
    # =====================================================

    @app.on_callback_query(
        filters.regex("^service_")
    )
    async def service_selected(client, query):

        try:

            service_id = int(
                query.data.replace(
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

        service = get_service(
            service_id
        )

        if not service:

            await query.answer(
                "سرویس پیدا نشد.",
                show_alert=True
            )
            return

        await query.message.edit_text(
            f"📦 {service['name']}\n\n"
            f"💾 حجم: {service['volume_gb']}GB\n"
            f"💰 قیمت: {service['price']:,} تومان\n\n"
            "👤 لطفاً نام کاربری دلخواه خود را ارسال کنید.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت",
                        callback_data="user_home"
                    )
                ]
            ])
        )

        app.user_state = getattr(
            app,
            "user_state",
            {}
        )

        app.user_state[
            query.from_user.id
        ] = {
            "action": "username",
            "service_id": service_id,
            "order_type": "new"
        }

        await query.answer()

    # =====================================================
    # متن کاربر
    # =====================================================

    @app.on_message(
        filters.private
        & filters.text
    )
    async def user_text(client, message):

        user_id = message.from_user.id
        text = message.text.strip()

        # دکمه‌های اصلی
        if text == "🛒 خرید سرویس":
            await show_services(
                client,
                message
            )
            return

        if text == "🔄 تمدید":
            await renew_menu(
                client,
                message
            )
            return

        if text == "📦 اشتراک‌های من":
            await subscriptions_menu(
                client,
                message
            )
            return

        if text == "📊 وضعیت اشتراک":
            await status_menu(
                client,
                message
            )
            return

        if text == "👥 دعوت دوستان":
            await referral_menu(
                client,
                message
            )
            return

        if text == "🎟️ کد تخفیف":
            await message.reply_text(
                "🎟️ کد تخفیف خود را ارسال کنید."
            )

            app.user_state = getattr(
                app,
                "user_state",
                {}
            )

            app.user_state[user_id] = {
                "action": "coupon"
            }

            return

        if text == "📜 تاریخچه سفارش‌ها":
            await history_menu(
                client,
                message
            )
            return

        if text == "👤 حساب من":
            await account_menu(
                client,
                message
            )
            return

        if text == "☎️ پشتیبانی":
            await message.reply_text(
                "☎️ برای پشتیبانی با ادمین تماس بگیرید.",
                reply_markup=main_menu(config)
            )
            return

        if text == "📚 آموزش":
            await message.reply_text(
                "📚 آموزش استفاده از سرویس\n\n"
                "بعد از خرید و تأیید پرداخت، "
                "لینک اشتراک یا کانفیگ برای شما ارسال می‌شود.",
                reply_markup=main_menu(config)
            )
            return

        state = getattr(
            app,
            "user_state",
            {}
        ).get(user_id)

        if not state:
            return

        # =================================================
        # نام کاربری
        # =================================================

        if state["action"] == "username":

            username = text

            if len(username) < 3:
                await message.reply_text(
                    "❌ نام کاربری باید حداقل ۳ کاراکتر باشد."
                )
                return

            service = get_service(
                state["service_id"]
            )

            if not service:
                await message.reply_text(
                    "❌ سرویس پیدا نشد."
                )
                return

            app.user_state[user_id] = {
                "action": "confirm_order",
                "service_id": service["id"],
                "order_type": state["order_type"],
                "username": username,
                "discount": 0,
                "coupon": None
            }

            await message.reply_text(
                order_text(
                    service,
                    username,
                    0,
                    service["price"]
                ),
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🎟️ کد تخفیف",
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
                            "❌ لغو",
                            callback_data="user_home"
                        )
                    ]
                ])
            )

            return

        # =================================================
        # کد تخفیف
        # =================================================

        if state["action"] == "coupon":

            coupon = get_coupon(
                text.upper()
            )

            if not coupon:

                await message.reply_text(
                    "❌ کد تخفیف معتبر نیست."
                )
                return

            percent = coupon["percent"]

            await message.reply_text(
                f"✅ کد تخفیف معتبر است.\n"
                f"📉 میزان تخفیف: {percent}%\n\n"
                "کد تخفیف هنگام سفارش اعمال خواهد شد.",
                reply_markup=main_menu(config)
            )

            app.user_state.pop(
                user_id,
                None
            )

            return

        # =================================================
        # ارسال کانفیگ در صورت نیاز
        # =================================================

        return

    # =====================================================
    # تأیید سفارش
    # =====================================================

    @app.on_callback_query(
        filters.regex("^confirm_order$")
    )
    async def confirm_order(client, query):

        user_id = query.from_user.id

        state = getattr(
            app,
            "user_state",
            {}
        ).get(user_id)

        if not state:

            await query.answer(
                "سفارش پیدا نشد.",
                show_alert=True
            )
            return

        service = get_service(
            state["service_id"]
        )

        if not service:

            await query.answer(
                "سرویس پیدا نشد.",
                show_alert=True
            )
            return

        discount = state.get(
            "discount",
            0
        )

        discount_amount, final_price = calc(
            service["price"],
            100 - discount
        )

        order_id = create_order(
            user_id=user_id,
            service_id=service["id"],
            service_name=service["name"],
            order_type=state["order_type"],
            username=state["username"],
            original_price=service["price"],
            discount_percent=discount,
            final_price=final_price,
            coupon=state.get("coupon")
        )

        app.user_state.pop(
            user_id,
            None
        )

        await query.message.edit_text(
            f"🧾 سفارش #{order_id} ثبت شد.\n\n"
            f"📦 سرویس: {service['name']}\n"
            f"👤 نام کاربری: {state['username']}\n"
            f"💵 مبلغ: {final_price:,} تومان\n\n"
            f"{payment(config['payment_card'], config['payment_name'])}\n\n"
            "بعد از پرداخت، عکس رسید را همینجا ارسال کنید."
        )

        await query.answer(
            "سفارش ثبت شد."
        )

    # =====================================================
    # رسید پرداخت
    # =====================================================

    @app.on_message(
        filters.private
        & filters.photo
    )
    async def receipt_photo(client, message):

        user_id = message.from_user.id

        orders = get_user_orders(
            user_id
        )

        pending = None

        for order in orders:

            if order["status"] == "pending":

                pending = order
                break

        if not pending:

            return

        set_receipt(
            pending["id"],
            message.photo.file_id
        )

        for admin_id in config.get(
            "admin_ids",
            []
        ):

            try:

                await client.send_photo(
                    admin_id,
                    message.photo.file_id,
                    caption=(
                        f"🧾 رسید سفارش #{pending['id']}\n\n"
                        f"👤 User ID: {user_id}\n"
                        f"📦 سرویس: {pending['service_name']}\n"
                        f"💵 مبلغ: "
                        f"{pending['final_price']:,} تومان"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "🔎 بررسی سفارش",
                                callback_data=(
                                    f"admin_order_{pending['id']}"
                                )
                            )
                        ]
                    ])
                )

            except Exception:
                pass

        await message.reply_text(
            "✅ رسید شما دریافت شد.\n\n"
            "⏳ پس از بررسی ادمین، نتیجه برای شما ارسال می‌شود.",
            reply_markup=main_menu(config)
        )

    # =====================================================
    # منوی تمدید
    # =====================================================

    async def renew_menu(client, message):

        subscriptions = get_user_subscriptions(
            message.from_user.id
        )

        if not subscriptions:

            await message.reply_text(
                "❌ هنوز اشتراکی ندارید.",
                reply_markup=main_menu(config)
            )
            return

        buttons = []

        for sub in subscriptions:

            buttons.append([
                InlineKeyboardButton(
                    f"🔄 {sub['service_name']} - {sub['username']}",
                    callback_data=f"renew_{sub['id']}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="user_home"
            )
        ])

        await message.reply_text(
            "🔄 اشتراکی که می‌خواهید تمدید کنید را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # =====================================================
    # انتخاب تمدید
    # =====================================================

    @app.on_callback_query(
        filters.regex("^renew_")
    )
    async def renew_selected(client, query):

        try:

            sub_id = int(
                query.data.replace(
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

        sub = get_subscription(
            sub_id
        )

        if not sub:

            await query.answer(
                "اشتراک پیدا نشد.",
                show_alert=True
            )
            return

        service = None

        for item in get_services(
            active_only=True
        ):

            if item["name"] == sub["service_name"]:
                service = item
                break

        if not service:

            await query.answer(
                "سرویس مربوط به این اشتراک موجود نیست.",
                show_alert=True
            )
            return

        app.user_state = getattr(
            app,
            "user_state",
            {}
        )

        app.user_state[
            query.from_user.id
        ] = {
            "action": "username",
            "service_id": service["id"],
            "order_type": "renew",
            "subscription_id": sub_id
        }

        await query.message.edit_text(
            f"🔄 تمدید {service['name']}\n\n"
            f"👤 نام کاربری فعلی: {sub['username']}\n"
            f"💰 قیمت: {service['price']:,} تومان\n\n"
            "برای ادامه، تأیید سفارش را بزنید.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ ادامه تمدید",
                        callback_data="confirm_renew"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ لغو",
                        callback_data="user_home"
                    )
                ]
            ])
        )

        await query.answer()

    # =====================================================
    # تأیید تمدید
    # =====================================================

    @app.on_callback_query(
        filters.regex("^confirm_renew$")
    )
    async def confirm_renew(client, query):

        user_id = query.from_user.id

        state = getattr(
            app,
            "user_state",
            {}
        ).get(user_id)

        if not state:

            await query.answer(
                "اطلاعات تمدید پیدا نشد.",
                show_alert=True
            )
            return

        service = get_service(
            state["service_id"]
        )

        if not service:

            await query.answer(
                "سرویس پیدا نشد.",
                show_alert=True
            )
            return

        order_id = create_order(
            user_id=user_id,
            service_id=service["id"],
            service_name=service["name"],
            order_type="renew",
            username=state.get(
                "username",
                ""
            ),
            original_price=service["price"],
            discount_percent=0,
            final_price=service["price"],
            coupon=None
        )

        app.user_state.pop(
            user_id,
            None
        )

        await query.message.edit_text(
            f"🔄 سفارش تمدید #{order_id} ثبت شد.\n\n"
            f"📦 سرویس: {service['name']}\n"
            f"💵 مبلغ: {service['price']:,} تومان\n\n"
            f"{payment(config['payment_card'], config['payment_name'])}\n\n"
            "بعد از پرداخت، عکس رسید را ارسال کنید."
        )

        await query.answer(
            "سفارش تمدید ثبت شد."
        )

    # =====================================================
    # اشتراک‌های من
    # =====================================================

    async def subscriptions_menu(client, message):

        subscriptions = get_user_subscriptions(
            message.from_user.id
        )

        if not subscriptions:

            await message.reply_text(
                "📦 شما هنوز اشتراکی ندارید.",
                reply_markup=main_menu(config)
            )
            return

        text = "📦 اشتراک‌های من\n\n"

        for sub in subscriptions:

            text += (
                f"🆔 #{sub['id']}\n"
                f"📦 {sub['service_name']}\n"
                f"👤 {sub['username']}\n"
                f"📌 وضعیت: {sub['status']}\n\n"
            )

        await message.reply_text(
            text,
            reply_markup=main_menu(config)
        )

    # =====================================================
    # وضعیت اشتراک
    # =====================================================

    async def status_menu(client, message):

        subscriptions = get_user_subscriptions(
            message.from_user.id
        )

        if not subscriptions:

            await message.reply_text(
                "📊 اشتراک فعالی ندارید.",
                reply_markup=main_menu(config)
            )
            return

        buttons = []

        for sub in subscriptions:

            buttons.append([
                InlineKeyboardButton(
                    f"📊 {sub['username']}",
                    callback_data=f"sub_{sub['id']}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="user_home"
            )
        ])

        await message.reply_text(
            "📊 اشتراک موردنظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # =====================================================
    # جزئیات اشتراک
    # =====================================================

    @app.on_callback_query(
        filters.regex("^sub_")
    )
    async def subscription_details(client, query):

        try:

            sub_id = int(
                query.data.replace(
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

        sub = get_subscription(
            sub_id
        )

        if not sub or sub["user_id"] != query.from_user.id:

            await query.answer(
                "اشتراک پیدا نشد.",
                show_alert=True
            )
            return

        text = (
            "📊 وضعیت اشتراک\n\n"
            f"📦 سرویس: {sub['service_name']}\n"
            f"👤 نام کاربری: {sub['username']}\n"
            f"📌 وضعیت: {sub['status']}\n"
        )

        if sub.get("subscription_url"):
            text += (
                f"\n🔗 لینک اشتراک:\n"
                f"{sub['subscription_url']}"
            )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت",
                        callback_data="user_home"
                    )
                ]
            ])
        )

        await query.answer()

    # =====================================================
    # تاریخچه سفارش‌ها
    # =====================================================

    async def history_menu(client, message):

        orders = get_user_orders(
            message.from_user.id
        )

        if not orders:

            await message.reply_text(
                "📜 هنوز سفارشی ثبت نکرده‌اید.",
                reply_markup=main_menu(config)
            )
            return

        text = "📜 تاریخچه سفارش‌ها\n\n"

        for order in orders[:20]:

            text += (
                f"🧾 #{order['id']}\n"
                f"📦 {order['service_name']}\n"
                f"💵 {order['final_price']:,} تومان\n"
                f"📌 {order['status']}\n\n"
            )

        await message.reply_text(
            text,
            reply_markup=main_menu(config)
        )

    # =====================================================
    # دعوت دوستان
    # =====================================================

    async def referral_menu(client, message):

        user_id = message.from_user.id

        count = get_referral_count(
            user_id
        )

        rewards = get_referral_reward_count(
            user_id
        )

        bot_info = await client.get_me()

        link = referral_link(
            bot_info.username,
            user_id
        )

        await message.reply_text(
            "👥 دعوت دوستان\n\n"
            f"🔗 لینک دعوت شما:\n{link}\n\n"
            f"✅ دعوت‌های موفق: {count}\n"
            f"🎁 پاداش‌های دریافت‌شده: {rewards}\n\n"
            "هر ۵ دعوت موفق = ۱۰GB هدیه.",
            reply_markup=main_menu(config)
        )

    # =====================================================
    # حساب
    # =====================================================

    async def account_menu(client, message):

        user = get_user(
            message.from_user.id
        )

        if not user:
            await message.reply_text(
                "❌ اطلاعات حساب پیدا نشد.",
                reply_markup=main_menu(config)
            )
            return

        await message.reply_text(
            "👤 حساب من\n\n"
            f"🆔 شناسه: {user['id']}\n"
            f"👤 نام: {user['first_name'] or '-'}\n"
            f"🔹 Username: "
            f"@{user['username']}"
            if user["username"]
            else
            "👤 حساب من\n\n"
            f"🆔 شناسه: {user['id']}\n"
            f"👤 نام: {user['first_name'] or '-'}",
            reply_markup=main_menu(config)
        )

    # =====================================================
    # بازگشت به منوی اصلی
    # =====================================================

    @app.on_callback_query(
        filters.regex("^user_home$")
    )
    async def user_home(client, query):

        await query.message.delete()

        await send_main_menu(
            client,
            query.from_user.id
        )

        await query.answer()
