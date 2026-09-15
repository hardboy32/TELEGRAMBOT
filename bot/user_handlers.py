from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from bot.database import (
    add_user,
    get_user,
    get_services,
    get_service,
    create_order,
    get_order,
    set_receipt,
    get_user_orders,
    get_user_subscriptions,
    get_subscription,
    get_coupon,
    use_coupon,
)
from bot.helpers import (
    calculate_discount,
    make_referral_link,
    replace_payment_info,
)
from bot.keyboards import (
    main_menu,
    services_keyboard,
    order_payment_button,
    back_button,
)
from bot.messages import (
    welcome_message,
    services_text,
    order_text,
    payment_received,
    referral_text,
    history_empty,
    account_text,
    no_subscription,
    support_text,
    tutorial_text,
    coupon_invalid,
    coupon_applied,
)
from bot.hermes import get_subscription_info


user_states = {}


def get_settings(config):
    return {
        "buy": config.get("buy", True),
        "renew": config.get("renew", True),
        "subscriptions": config.get("subscriptions", True),
        "status": config.get("status", True),
        "referral": config.get("referral_enabled", True),
        "coupon": config.get("coupon_enabled", True),
        "history": config.get("order_history_enabled", True),
        "account": True,
        "support": config.get("support_enabled", True),
        "tutorial": config.get("tutorial_enabled", True),
        "free_test": config.get("free_test_enabled", False),
        "festival": config.get("festival_enabled", False),
    }


def register_user(message, referral_by=None):
    user = message.from_user

    add_user(
        user.id,
        user.username,
        user.first_name,
        referral_by
    )


def register_user_handlers(app: Client, config):

    @app.on_message(
        filters.command("start") & filters.private
    )
    async def start_handler(client, message: Message):

        referral_by = None

        if len(message.command) > 1:
            argument = message.command[1]

            if argument.startswith("ref_"):
                try:
                    referral_by = int(
                        argument.replace("ref_", "")
                    )
                except ValueError:
                    referral_by = None

        register_user(
            message,
            referral_by
        )

        settings = get_settings(config)

        text = welcome_message(
            message.from_user.first_name
        )

        await message.reply_text(
            text,
            reply_markup=main_menu(settings)
        )

    @app.on_callback_query(
        filters.regex("^main_menu$")
    )
    async def main_menu_handler(client, query: CallbackQuery):

        settings = get_settings(config)

        await query.message.edit_text(
            welcome_message(
                query.from_user.first_name
            ),
            reply_markup=main_menu(settings)
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^buy$")
    )
    async def buy_handler(client, query: CallbackQuery):

        services = get_services()

        if not services:
            await query.answer(
                "در حال حاضر سرویسی موجود نیست.",
                show_alert=True
            )
            return

        await query.message.edit_text(
            services_text(),
            reply_markup=services_keyboard(
                services,
                "buy_service"
            )
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex(r"^buy_service:\d+$")
    )
    async def select_buy_service(client, query: CallbackQuery):

        service_id = int(
            query.data.split(":")[1]
        )

        service = get_service(service_id)

        if not service:
            await query.answer(
                "سرویس پیدا نشد.",
                show_alert=True
            )
            return

        user_states[query.from_user.id] = {
            "action": "buy",
            "service_id": service_id
        }

        await query.message.edit_text(
            f"""
📦 سرویس انتخاب شد:

{service['name']}
💰 قیمت: {service['price']:,} تومان

👤 لطفاً نام کاربری موردنظر خود برای سرویس را ارسال کنید.

مثال:
ali123
""",
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^renew$")
    )
    async def renew_handler(client, query: CallbackQuery):

        subscriptions = get_user_subscriptions(
            query.from_user.id
        )

        if not subscriptions:
            await query.answer(
                "شما اشتراک فعالی ندارید.",
                show_alert=True
            )
            return

        buttons = []

        for sub in subscriptions:
            buttons.append([
                __import__(
                    "pyrogram.types",
                    fromlist=["InlineKeyboardButton"]
                ).InlineKeyboardButton(
                    f"🔄 {sub['service_name']} - {sub['username']}",
                    callback_data=f"renew_sub:{sub['id']}"
                )
            ])

        buttons.append([
            __import__(
                "pyrogram.types",
                fromlist=["InlineKeyboardButton"]
            ).InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="main_menu"
            )
        ])

        from pyrogram.types import InlineKeyboardMarkup

        await query.message.edit_text(
            "🔄 اشتراکی که می‌خواهید تمدید کنید را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex(r"^renew_sub:\d+$")
    )
    async def renew_subscription(client, query: CallbackQuery):

        subscription_id = int(
            query.data.split(":")[1]
        )

        subscription = get_subscription(
            subscription_id
        )

        if not subscription:
            await query.answer(
                "اشتراک پیدا نشد.",
                show_alert=True
            )
            return

        user_states[query.from_user.id] = {
            "action": "renew",
            "subscription_id": subscription_id
        }

        services = get_services()

        await query.message.edit_text(
            "📦 حجم تمدید را انتخاب کنید:",
            reply_markup=services_keyboard(
                services,
                "renew_service"
            )
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex(r"^renew_service:\d+$")
    )
    async def select_renew_service(client, query: CallbackQuery):

        service_id = int(
            query.data.split(":")[1]
        )

        service = get_service(service_id)

        state = user_states.get(
            query.from_user.id
        )

        if not state:
            await query.answer(
                "اطلاعات سفارش منقضی شده است.",
                show_alert=True
            )
            return

        state["service_id"] = service_id

        user_states[
            query.from_user.id
        ] = state

        await query.message.edit_text(
            f"""
🔄 تمدید سرویس

📦 {service['name']}
💰 مبلغ: {service['price']:,} تومان

اگر کد تخفیف دارید، می‌توانید قبل از پرداخت آن را وارد کنید.

برای ادامه، نام کاربری سرویس خود را ارسال کنید.
""",
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_message(
        filters.private & filters.text
    )
    async def text_handler(client, message: Message):

        user_id = message.from_user.id

        state = user_states.get(user_id)

        if not state:
            return

        if state.get("action") in ("buy", "renew"):

            username = message.text.strip()

            if len(username) < 3:
                await message.reply_text(
                    "❌ نام کاربری باید حداقل ۳ کاراکتر باشد."
                )
                return

            state["username"] = username

            service = get_service(
                state["service_id"]
            )

            state["price"] = service["price"]
            state["discount"] = 0
            state["final_price"] = service["price"]

            user_states[user_id] = state

            await message.reply_text(
                f"""
👤 نام کاربری:
{username}

📦 سرویس:
{service['name']}

💰 مبلغ:
{service['price']:,} تومان

اگر کد تخفیف دارید، همین حالا ارسال کنید.

اگر کد تخفیف ندارید، عبارت «ندارم» را ارسال کنید.
"""
            )

            state["action"] = (
                "buy_coupon"
                if state["action"] == "buy"
                else "renew_coupon"
            )

            user_states[user_id] = state

            return

        if state.get("action") in (
            "buy_coupon",
            "renew_coupon"
        ):

            service = get_service(
                state["service_id"]
            )

            if message.text.strip().lower() == "ندارم":

                discount_percent = 0

            else:

                coupon = get_coupon(
                    message.text.strip()
                )

                if not coupon:
                    await message.reply_text(
                        coupon_invalid()
                    )
                    return

                if coupon["max_uses"] > 0:
                    if coupon["used_count"] >= coupon["max_uses"]:
                        await message.reply_text(
                            coupon_invalid()
                        )
                        return

                discount_percent = coupon["percent"]
                state["coupon"] = coupon["code"]

                await message.reply_text(
                    coupon_applied(
                        discount_percent
                    )
                )

            discount, final_price = calculate_discount(
                service["price"],
                discount_percent
            )

            state["discount"] = discount_percent
            state["final_price"] = final_price

            state["action"] = (
                "confirm_buy"
                if state["action"] == "buy_coupon"
                else "confirm_renew"
            )

            user_states[user_id] = state

            text = order_text(
                service,
                state["username"],
                service["price"],
                discount_percent,
                final_price
            )

            text = replace_payment_info(
                text,
                config
            )

            order_id = create_order(
                user_id=user_id,
                service_id=service["id"],
                order_type=(
                    "purchase"
                    if state["action"] == "confirm_buy"
                    else "renew"
                ),
                username=state["username"],
                original_price=service["price"],
                discount_percent=discount_percent,
                final_price=final_price,
                coupon=state.get("coupon")
            )

            state["order_id"] = order_id

            user_states[user_id] = state

            await message.reply_text(
                text,
                reply_markup=order_payment_button(
                    order_id
                )
            )

            return

    @app.on_callback_query(
        filters.regex(r"^receipt:\d+$")
    )
    async def receipt_request(client, query: CallbackQuery):

        order_id = int(
            query.data.split(":")[1]
        )

        order = get_order(order_id)

        if not order:
            await query.answer(
                "سفارش پیدا نشد.",
                show_alert=True
            )
            return

        user_states[
            query.from_user.id
        ] = {
            "action": "receipt",
            "order_id": order_id
        }

        await query.message.reply_text(
            "📸 لطفاً عکس رسید پرداخت را ارسال کنید."
        )

        await query.answer()

    @app.on_message(
        filters.private & filters.photo
    )
    async def photo_handler(client, message: Message):

        user_id = message.from_user.id

        state = user_states.get(user_id)

        if not state:
            return

        if state.get("action") != "receipt":
            return

        order_id = state["order_id"]

        file_id = message.photo.file_id

        set_receipt(
            order_id,
            file_id
        )

        user_states.pop(
            user_id,
            None
        )

        await message.reply_text(
            payment_received(),
            reply_markup=back_button()
        )

    @app.on_callback_query(
        filters.regex("^referral$")
    )
    async def referral_handler(client, query):

        user = get_user(
            query.from_user.id
        )

        me = await client.get_me()

        link = make_referral_link(
            me.username,
            query.from_user.id
        )

        text = referral_text(
            user["referral_success"]
        )

        text += f"""

🔗 لینک دعوت شما:

{link}

این لینک را برای دوستانتان ارسال کنید.
"""

        await query.message.edit_text(
            text,
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^history$")
    )
    async def history_handler(client, query):

        orders = get_user_orders(
            query.from_user.id
        )

        if not orders:
            await query.message.edit_text(
                history_empty(),
                reply_markup=back_button()
            )
            await query.answer()
            return

        text = "📜 تاریخچه سفارش‌ها\n\n"

        for order in orders[:20]:

            status = {
                "pending": "⏳ در انتظار رسید",
                "waiting_admin": "🔍 در انتظار بررسی",
                "approved": "✅ تأیید شده",
                "rejected": "❌ رد شده"
            }.get(
                order["status"],
                order["status"]
            )

            text += f"""
🧾 سفارش #{order['id']}
📦 {order['service_name'] or 'نامشخص'}
💰 {order['final_price']:,} تومان
📅 {order['created_at']}
📌 {status}

"""

        await query.message.edit_text(
            text,
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^account$")
    )
    async def account_handler(client, query):

        user = get_user(
            query.from_user.id
        )

        await query.message.edit_text(
            account_text(user),
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^my_subscriptions$")
    )
    async def subscriptions_handler(client, query):

        subscriptions = get_user_subscriptions(
            query.from_user.id
        )

        if not subscriptions:
            await query.message.edit_text(
                no_subscription(),
                reply_markup=back_button()
            )

            await query.answer()
            return

        text = "📦 اشتراک‌های شما\n\n"

        for sub in subscriptions:

            text += f"""
━━━━━━━━━━━━━━
📦 سرویس: {sub['service_name']}
👤 نام کاربری: {sub['username']}
📌 وضعیت: {sub['status']}
"""

            if sub["subscription_url"]:
                text += (
                    f"\n🔗 لینک اشتراک:\n"
                    f"{sub['subscription_url']}\n"
                )

            if sub["config_text"]:
                text += (
                    f"\n⚙️ کانفیگ:\n"
                    f"{sub['config_text']}\n"
                )

        await query.message.edit_text(
            text,
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^status$")
    )
    async def status_handler(client, query):

        subscriptions = get_user_subscriptions(
            query.from_user.id
        )

        if not subscriptions:
            await query.message.edit_text(
                no_subscription(),
                reply_markup=back_button()
            )

            await query.answer()
            return

        text = "📊 وضعیت اشتراک\n\n"

        for sub in subscriptions:

            text += f"""
📦 {sub['service_name']}
👤 {sub['username']}
"""

            if sub["subscription_url"]:

                info = await get_subscription_info(
                    sub["subscription_url"]
                )

                if info["success"]:

                    text += f"""
📊 مصرف کل: {info['total_usage']}
📦 حجم کل: {info['total_volume']}
📉 باقی‌مانده: {info['remaining']}
🕐 آخرین اتصال: {info['last_connection']}
"""

                else:

                    text += (
                        "\n⚠️ اطلاعات مصرف در حال حاضر قابل دریافت نیست.\n"
                    )

        await query.message.edit_text(
            text,
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^support$")
    )
    async def support_handler(client, query):

        await query.message.edit_text(
            support_text(),
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^tutorial$")
    )
    async def tutorial_handler(client, query):

        await query.message.edit_text(
            tutorial_text(),
            reply_markup=back_button()
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex(r"^cancel_order:\d+$")
    )
    async def cancel_order_handler(client, query):

        order_id = int(
            query.data.split(":")[1]
        )

        order = get_order(order_id)

        if not order:
            await query.answer(
                "سفارش پیدا نشد.",
                show_alert=True
            )
            return

        if order["user_id"] != query.from_user.id:
            await query.answer(
                "این سفارش متعلق به شما نیست.",
                show_alert=True
            )
            return

        from bot.database import set_order_status

        set_order_status(
            order_id,
            "cancelled"
        )

        user_states.pop(
            query.from_user.id,
            None
        )

        await query.message.edit_text(
            "❌ سفارش شما لغو شد.",
            reply_markup=back_button()
        )

        await query.answer()
