from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.database import (
    add_or_update_user,
    get_user,
    get_services,
    get_service,
    create_order,
    get_order,
    set_receipt,
    get_user_orders,
    get_user_subscriptions,
    get_subscription,
    get_referrer,
    get_referral_count,
    get_referral_reward_count,
    get_coupon,
    use_coupon,
    reset_low_volume_warning,
    get_tutorials,
    get_tutorial
)

from bot.helpers import (
    admin,
    calc,
    referral_link,
    normalize_username,
    valid_username,
    format_price
)

from bot.keyboards import (
    main_menu,
    join_keyboard,
    services_reply_keyboard,
    confirm_reply_keyboard,
    payment_reply_keyboard,
    subscriptions_reply_keyboard,
    tutorials_reply_keyboard,
    order_admin_keyboard
)

from bot.messages import (
    welcome,
    join_required,
    payment,
    order_text,
    order_created,
    receipt_received,
    no_services
)


user_states = {}


def _menu(config, user_id):
    return main_menu(
        config,
        is_admin=admin(user_id, config)
    )


def register(app, config):

    async def is_joined(client, user_id):
        if not config.get("join_required_enabled", True):
            return True

        channel = config.get("channel_username", "")

        if not channel or "YOUR_CHANNEL" in channel:
            return True

        try:
            member = await client.get_chat_member(
                channel,
                user_id
            )

            return member.status not in (
                "left",
                "kicked"
            )

        except Exception:
            return False

    async def show_home(message):
        await message.reply_text(
            welcome(
                message.from_user.first_name or "دوست من"
            ),
            reply_markup=main_menu(
                config,
                is_admin=admin(message.from_user.id, config)
            )
        )

    @app.on_message(
        filters.private & filters.command("start")
    )
    async def start_handler(client, message):

        user_id = message.from_user.id

        referral_by = None

        if message.command and len(message.command) > 1:
            arg = message.command[1]

            if arg.startswith("ref_"):
                try:
                    ref_id = int(arg.replace("ref_", ""))

                    if ref_id != user_id:
                        referral_by = ref_id

                except ValueError:
                    pass

        old_user = get_user(user_id)

        if old_user:
            referral_by = old_user.get("referral_by")

        add_or_update_user(
            user_id,
            message.from_user.username,
            message.from_user.first_name,
            referral_by
        )

        if not await is_joined(client, user_id):

            await message.reply_text(
                join_required(
                    config.get(
                        "channel_username",
                        "@YOUR_CHANNEL"
                    )
                ),
                reply_markup=join_keyboard(
                    config.get(
                        "channel_username",
                        "@YOUR_CHANNEL"
                    )
                )
            )

            return

        await show_home(message)

    @app.on_callback_query(
        filters.regex("^check_join$")
    )
    async def check_join(client, query):

        if await is_joined(
            client,
            query.from_user.id
        ):
            await query.message.edit_text(
                "✅ عضویت شما تأیید شد.\n\n"
                "حالا می‌توانید از منوی اصلی استفاده کنید."
            )

            await query.message.reply_text(
                "🏠 منوی اصلی",
                reply_markup=_menu(config, query.from_user.id)
            )

        else:
            await query.answer(
                "❌ هنوز عضو کانال نشده‌اید.",
                show_alert=True
            )

    @app.on_message(
        filters.private & filters.text
    )
    async def user_text(client, message):

        user_id = message.from_user.id

        add_or_update_user(
            user_id,
            message.from_user.username,
            message.from_user.first_name
        )

        text = message.text.strip()

        state = user_states.get(user_id)

        if text == "🛒 خرید سرویس":

            services = get_services(True)

            if not services:
                await message.reply_text(
                    no_services(),
                    reply_markup=_menu(config, user_id)
                )
                return

            services_map = {}

            for s in services:
                label = (
                    f"📦 {s['name']} | {s['volume_gb']}GB"
                )
                services_map[label] = s["id"]

            prev = user_states.get(user_id) or {}

            user_states[user_id] = {
                "step": "pick_service",
                "services_map": services_map,
                "order_type": "buy"
            }

            if prev.get("coupon"):
                user_states[user_id]["coupon"] = prev["coupon"]
                user_states[user_id]["discount"] = prev.get(
                    "discount",
                    0
                )

            await message.reply_text(
                "🛒 سرویس موردنظر را انتخاب کنید:",
                reply_markup=services_reply_keyboard(services)
            )

            return

        if text == "🔄 تمدید":

            subscriptions = get_user_subscriptions(user_id)

            if not subscriptions:
                await message.reply_text(
                    "❌ هنوز اشتراک فعالی ندارید.",
                    reply_markup=_menu(config, user_id)
                )
                return

            sub_map = {}

            for sub in subscriptions:
                label = (
                    f"🔄 {sub['service_name']} | "
                    f"@{sub['username']}"
                )
                sub_map[label] = sub["id"]

            user_states[user_id] = {
                "step": "pick_renew",
                "sub_map": sub_map
            }

            await message.reply_text(
                "🔄 اشتراکی که می‌خواهید تمدید کنید را انتخاب کنید:",
                reply_markup=subscriptions_reply_keyboard(
                    subscriptions,
                    "🔄"
                )
            )

            return

        if text == "📦 اشتراک‌های من":

            subscriptions = get_user_subscriptions(user_id)

            if not subscriptions:
                await message.reply_text(
                    "📦 هنوز اشتراکی برای شما ثبت نشده.",
                    reply_markup=_menu(config, user_id)
                )
                return

            sub_map = {}

            for sub in subscriptions:
                label = (
                    f"📦 {sub['service_name']} | "
                    f"@{sub['username']}"
                )
                sub_map[label] = sub["id"]

            user_states[user_id] = {
                "step": "pick_sub",
                "sub_map": sub_map
            }

            await message.reply_text(
                "📦 اشتراک‌های شما — یکی را انتخاب کنید:",
                reply_markup=subscriptions_reply_keyboard(
                    subscriptions,
                    "📦"
                )
            )

            return

        if text == "📊 وضعیت اشتراک":

            subscriptions = get_user_subscriptions(user_id)

            if not subscriptions:
                await message.reply_text(
                    "📊 اشتراک فعالی ندارید."
                )
                return

            lines = ["📊 وضعیت اشتراک‌ها:\n"]

            for sub in subscriptions:
                lines.append(
                    f"📦 {sub['service_name']}\n"
                    f"👤 @{sub['username']}\n"
                    f"🔵 وضعیت: {sub['status']}\n"
                )

            await message.reply_text(
                "\n".join(lines)
            )

            return

        if text == "👥 دعوت دوستان":

            count = get_referral_count(user_id)
            rewards = get_referral_reward_count(user_id)

            username = (await client.get_me()).username

            link = referral_link(
                username,
                user_id
            )

            await message.reply_text(
                "👥 دعوت دوستان\n\n"
                f"👤 دعوت‌های موفق: {count}\n"
                f"🎁 پاداش‌های ثبت‌شده: {rewards}\n\n"
                "به ازای هر ۵ خرید موفق از طریق لینک شما، "
                "۱۰GB هدیه برای شما ثبت می‌شود.\n\n"
                f"🔗 لینک دعوت شما:\n{link}"
            )

            return

        if text == "🎟️ کد تخفیف":

            user_states[user_id] = {
                "step": "coupon"
            }

            await message.reply_text(
                "🎟️ کد تخفیف را ارسال کنید:"
            )

            return

        if text == "📜 تاریخچه سفارش‌ها":

            orders = get_user_orders(user_id)

            if not orders:
                await message.reply_text(
                    "📜 هنوز سفارشی ندارید."
                )
                return

            lines = ["📜 تاریخچه سفارش‌ها:\n"]

            for order in orders[:20]:
                lines.append(
                    f"🧾 #{order['id']}\n"
                    f"📦 {order['service_name']}\n"
                    f"💰 {format_price(order['final_price'])} تومان\n"
                    f"🔵 {order['status']}\n"
                    f"📅 {order['created_at']}\n"
                )

            await message.reply_text(
                "\n".join(lines)
            )

            return

        if text == "👤 حساب من":

            user = get_user(user_id)

            await message.reply_text(
                "👤 حساب شما\n\n"
                f"🆔 شناسه: {user_id}\n"
                f"👤 نام کاربری: "
                f"@{user.get('username') or 'ندارد'}\n"
                f"📅 عضویت: {user.get('joined_at')}"
            )

            return

        if text == "☎️ پشتیبانی":

            support = config.get(
                "support_username",
                "@hermes_vpn1"
            )

            support = str(support).strip()

            if not support.startswith("@"):
                support = f"@{support}"

            username = support.replace("@", "")

            await message.reply_text(
                "☎️ پشتیبانی\n\n"
                "برای ارتباط مستقیم با پشتیبانی "
                "روی دکمه زیر بزنید:\n"
                f"👤 {support}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "💬 چت با پشتیبانی",
                                url=f"https://t.me/{username}"
                            )
                        ]
                    ]
                )
            )

            return

        if text == "📚 آموزش":

            tutorials = get_tutorials(True)

            if not tutorials:
                await message.reply_text(
                    "📚 هنوز آموزشی ثبت نشده است.",
                    reply_markup=_menu(config, user_id)
                )
                return

            tut_map = {
                t["title"]: t["id"]
                for t in tutorials
            }

            user_states[user_id] = {
                "step": "pick_tutorial",
                "tut_map": tut_map
            }

            await message.reply_text(
                "📚 آموزش اتصال و استفاده\n\n"
                "پلتفرم موردنظر خود را انتخاب کنید:",
                reply_markup=tutorials_reply_keyboard(tutorials)
            )

            return

        if text == "🎁 تست رایگان":

            await message.reply_text(
                "🎁 تست رایگان در حال حاضر فعال نیست."
            )

            return

        if text == "🎉 جشنواره":

            await message.reply_text(
                "🎉 در حال حاضر جشنواره فعالی وجود ندارد."
            )

            return

        # بازگشت / منوی اصلی / لغو
        if text in ("⬅️ بازگشت", "🏠 منوی اصلی", "❌ لغو سفارش"):

            user_states.pop(user_id, None)

            await message.reply_text(
                "🏠 منوی اصلی",
                reply_markup=_menu(config, user_id)
            )

            return

        # انتخاب سرویس از کیبورد پایین
        if state and state.get("step") == "pick_service":

            services_map = state.get("services_map") or {}

            if text not in services_map:

                await message.reply_text(
                    "لطفاً یکی از سرویس‌های لیست را انتخاب کنید."
                )

                return

            service_id = services_map[text]
            service = get_service(service_id)

            if not service:

                await message.reply_text(
                    "❌ سرویس پیدا نشد.",
                    reply_markup=_menu(config, user_id)
                )

                user_states.pop(user_id, None)
                return

            discount = 0
            coupon = None

            saved = user_states.get(user_id) or {}

            if saved.get("step") == "coupon_saved" or saved.get("coupon"):
                # preserve coupon if was set before buy - actually pick_service overwrites state
                pass

            # اگر قبلاً کد تخفیف ذخیره شده بود از بین می‌رود چون state عوض شد؛
            # کاربر باید اول خرید بعد کد بزند یا برعکس. برای حفظ:
            # (اختیاری) — ساده نگه می‌داریم

            new_state = {
                "step": "username",
                "service_id": service_id,
                "order_type": "buy"
            }

            if state.get("coupon"):
                new_state["coupon"] = state["coupon"]
                new_state["discount"] = state.get("discount", 0)

            user_states[user_id] = new_state

            await message.reply_text(
                f"📦 سرویس: {service['name']}\n"
                f"💾 حجم: {service['volume_gb']}GB\n"
                f"💰 قیمت: {format_price(service['price'])} تومان\n\n"
                "👤 حالا نام کاربری دلخواه خود را ارسال کنید:\n"
                "(یا «❌ لغو سفارش»)",
                reply_markup=payment_reply_keyboard(
                    admin(user_id, config)
                )
            )

            return

        # انتخاب اشتراک برای مشاهده
        if state and state.get("step") == "pick_sub":

            sub_map = state.get("sub_map") or {}

            if text not in sub_map:

                await message.reply_text(
                    "یکی از اشتراک‌های لیست را انتخاب کنید."
                )

                return

            sub = get_subscription(sub_map[text])

            user_states.pop(user_id, None)

            if not sub:

                await message.reply_text(
                    "❌ اشتراک پیدا نشد.",
                    reply_markup=_menu(config, user_id)
                )

                return

            text_out = (
                f"📦 {sub['service_name']}\n"
                f"👤 @{sub['username']}\n"
                f"🔵 وضعیت: {sub['status']}\n"
            )

            if sub.get("subscription_url"):
                text_out += f"\n🔗 لینک:\n{sub['subscription_url']}\n"

            if sub.get("config_text"):
                text_out += f"\n📄 کانفیگ:\n<code>{sub['config_text']}</code>"

            await message.reply_text(
                text_out,
                reply_markup=_menu(config, user_id),
                parse_mode=enums.ParseMode.HTML
            )

            return

        # انتخاب تمدید
        if state and state.get("step") == "pick_renew":

            sub_map = state.get("sub_map") or {}

            if text not in sub_map:

                await message.reply_text(
                    "یکی از موارد لیست را انتخاب کنید."
                )

                return

            sub = get_subscription(sub_map[text])

            if not sub:

                await message.reply_text(
                    "❌ اشتراک پیدا نشد.",
                    reply_markup=_menu(config, user_id)
                )

                user_states.pop(user_id, None)
                return

            # پیدا کردن سرویس هم‌نام برای تمدید
            services = get_services(True)
            service = None

            for s in services:
                if s["name"] == sub["service_name"]:
                    service = s
                    break

            if not service:
                service = services[0] if services else None

            if not service:

                await message.reply_text(
                    "❌ سرویسی برای تمدید فعال نیست.",
                    reply_markup=_menu(config, user_id)
                )

                user_states.pop(user_id, None)
                return

            user_states[user_id] = {
                "step": "confirm",
                "service_id": service["id"],
                "username": sub["username"],
                "order_type": "renew",
                "discount": 0
            }

            _, final_price = calc(service["price"], 0)

            await message.reply_text(
                order_text(
                    service,
                    sub["username"],
                    0,
                    final_price
                ),
                reply_markup=confirm_reply_keyboard()
            )

            return

        # انتخاب آموزش
        if state and state.get("step") == "pick_tutorial":

            tut_map = state.get("tut_map") or {}

            if text not in tut_map:

                await message.reply_text(
                    "یکی از آموزش‌های لیست را انتخاب کنید."
                )

                return

            item = get_tutorial(tut_map[text])
            user_states.pop(user_id, None)

            if not item or not item.get("active"):

                await message.reply_text(
                    "❌ این آموزش فعال نیست.",
                    reply_markup=_menu(config, user_id)
                )

                return

            body = (item.get("body_text") or "").strip()

            if body:
                await message.reply_text(
                    f"{item['title']}\n\n{body}",
                    reply_markup=_menu(config, user_id)
                )
            else:
                await message.reply_text(
                    item["title"],
                    reply_markup=_menu(config, user_id)
                )

            if item.get("file_id"):
                try:
                    await client.send_document(
                        user_id,
                        item["file_id"],
                        caption="📎 فایل نصب / برنامه"
                    )
                except Exception as e:
                    print(f"Tutorial file error: {e}")

            if item.get("video_file_id"):
                try:
                    await client.send_video(
                        user_id,
                        item["video_file_id"],
                        caption="🎬 ویدیو آموزشی"
                    )
                except Exception:
                    try:
                        await client.send_document(
                            user_id,
                            item["video_file_id"],
                            caption="🎬 ویدیو آموزشی"
                        )
                    except Exception as e:
                        print(f"Tutorial video error: {e}")

            return

        # تأیید سفارش از کیبورد پایین
        if state and state.get("step") == "confirm":

            if text == "✅ تأیید سفارش":

                service = get_service(state["service_id"])

                if not service:

                    await message.reply_text(
                        "❌ سرویس پیدا نشد.",
                        reply_markup=_menu(config, user_id)
                    )

                    user_states.pop(user_id, None)
                    return

                discount = state.get("discount", 0)
                coupon = state.get("coupon")

                _, final_price = calc(
                    service["price"],
                    discount
                )

                order_id = create_order(
                    user_id=user_id,
                    service_id=service["id"],
                    service_name=service["name"],
                    order_type=state.get("order_type", "buy"),
                    username=state["username"],
                    original_price=service["price"],
                    discount_percent=discount,
                    final_price=final_price,
                    coupon=coupon
                )

                user_states[user_id] = {
                    "step": "waiting_receipt",
                    "order_id": order_id
                }

                await message.reply_text(
                    order_created(order_id)
                )

                await message.reply_text(
                    payment(
                        config.get("payment_card", "YOUR_CARD"),
                        config.get("payment_name", "CARD_OWNER")
                    ),
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=payment_reply_keyboard(
                        admin(user_id, config)
                    )
                )

                return

            await message.reply_text(
                "برای ادامه «✅ تأیید سفارش» یا «❌ لغو سفارش» را بزنید."
            )

            return

        if state and state.get("step") == "coupon":

            code = text.upper()

            coupon = get_coupon(code)

            if not coupon:
                await message.reply_text(
                    "❌ کد تخفیف معتبر نیست."
                )
                return

            if (
                coupon["max_uses"] > 0
                and coupon["used_count"] >= coupon["max_uses"]
            ):
                await message.reply_text(
                    "❌ ظرفیت استفاده از این کد تمام شده."
                )
                return

            user_states[user_id] = {
                "step": "coupon_saved",
                "coupon": code,
                "discount": coupon["percent"]
            }

            await message.reply_text(
                f"✅ کد تخفیف ثبت شد.\n\n"
                f"🎟️ تخفیف: {coupon['percent']}%\n\n"
                "حالا از «🛒 خرید سرویس» استفاده کنید."
            )

            return

        if state and state.get("step") == "username":

            username = normalize_username(text)

            if not valid_username(username):

                await message.reply_text(
                    "❌ نام کاربری نامعتبر است.\n\n"
                    "فقط حروف انگلیسی، عدد و _ مجاز است.\n"
                    "حداقل ۳ و حداکثر ۳۲ کاراکتر."
                )

                return

            state["username"] = username
            state["step"] = "confirm"

            service = get_service(
                state["service_id"]
            )

            discount = state.get(
                "discount",
                0
            )

            _, final_price = calc(
                service["price"],
                discount
            )

            await message.reply_text(
                order_text(
                    service,
                    username,
                    discount,
                    final_price
                ),
                reply_markup=confirm_reply_keyboard()
            )

            return

        await message.reply_text(
            "لطفاً از دکمه‌های منوی پایین استفاده کنید.",
            reply_markup=_menu(config, user_id)
        )

    @app.on_callback_query(
        filters.regex(r"^service_\d+$")
    )
    async def service_selected(client, query):

        user_id = query.from_user.id

        service_id = int(
            query.data.split("_")[1]
        )

        service = get_service(service_id)

        if not service or not service["active"]:
            await query.answer(
                "❌ این سرویس فعال نیست.",
                show_alert=True
            )
            return

        user_states[user_id] = {
            "step": "username",
            "service_id": service_id,
            "discount": 0
        }

        await query.message.reply_text(
            f"📦 سرویس انتخاب شد: {service['name']}\n"
            f"💾 حجم: {service['volume_gb']}GB\n"
            f"💰 قیمت: {format_price(service['price'])} تومان\n\n"
            "👤 حالا نام کاربری دلخواه خود را ارسال کنید:"
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^confirm_order$")
    )
    async def confirm_order(client, query):

        user_id = query.from_user.id

        state = user_states.get(user_id)

        if not state or state.get("step") != "confirm":
            await query.answer(
                "❌ سفارش منقضی شده.",
                show_alert=True
            )
            return

        service = get_service(
            state["service_id"]
        )

        if not service:
            await query.answer(
                "❌ سرویس پیدا نشد.",
                show_alert=True
            )
            return

        discount = state.get(
            "discount",
            0
        )

        coupon = state.get("coupon")

        _, final_price = calc(
            service["price"],
            discount
        )

        if coupon:
            coupon_obj = get_coupon(coupon)

            if not coupon_obj:
                discount = 0
                coupon = None

            else:
                discount = coupon_obj["percent"]

                _, final_price = calc(
                    service["price"],
                    discount
                )

        order_id = create_order(
            user_id=user_id,
            service_id=service["id"],
            service_name=service["name"],
            order_type="buy",
            username=state["username"],
            original_price=service["price"],
            discount_percent=discount,
            final_price=final_price,
            coupon=coupon
        )

        user_states[user_id] = {
            "step": "waiting_receipt",
            "order_id": order_id
        }

        await query.message.edit_text(
            order_created(order_id)
        )

        await query.message.reply_text(
            payment(
                config.get("payment_card", "YOUR_CARD"),
                config.get("payment_name", "CARD_OWNER")
            ),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=payment_reply_keyboard(
                admin(user_id, config)
            )
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^payment_info$")
    )
    async def payment_info(client, query):

        await query.message.reply_text(
            payment(
                config.get("payment_card", "YOUR_CARD"),
                config.get("payment_name", "CARD_OWNER")
            )
        )

        await query.answer()

    @app.on_message(
        filters.private & filters.photo
    )
    async def receipt_handler(client, message):

        user_id = message.from_user.id

        state = user_states.get(user_id)

        order_id = None

        if state:
            order_id = state.get("order_id")

        if not order_id:
            orders = get_user_orders(user_id)

            for order in orders:
                if order["status"] == "pending":
                    order_id = order["id"]
                    break

        if not order_id:

            await message.reply_text(
                "❌ سفارش در انتظاری برای این رسید پیدا نشد."
            )

            return

        order = get_order(order_id)

        if not order or order["status"] != "pending":

            await message.reply_text(
                "❌ این سفارش دیگر در انتظار بررسی نیست."
            )

            return

        set_receipt(
            order_id,
            message.photo.file_id
        )

        user_states.pop(
            user_id,
            None
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
                        "🧾 رسید پرداخت جدید\n\n"
                        f"شماره سفارش: #{order['id']}\n"
                        f"👤 کاربر: {user_id}\n"
                        f"📦 سرویس: {order['service_name']}\n"
                        f"👤 نام کاربری: @{order['username']}\n"
                        f"💰 مبلغ: "
                        f"{format_price(order['final_price'])} تومان"
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🔎 بررسی سفارش",
                                    callback_data=f"admin_order_{order['id']}"
                                )
                            ]
                        ]
                    )
                )

            except Exception as e:
                print(
                    f"Admin receipt error: {e}"
                )

        await message.reply_text(
            receipt_received(),
            reply_markup=_menu(config, user_id)
        )

    @app.on_callback_query(
        filters.regex(r"^sub_\d+$")
    )
    async def subscription_selected(client, query):

        sub_id = int(
            query.data.split("_")[1]
        )

        sub = get_subscription(sub_id)

        if not sub or sub["user_id"] != query.from_user.id:
            await query.answer(
                "❌ این اشتراک متعلق به شما نیست.",
                show_alert=True
            )
            return

        text = (
            "📦 اطلاعات اشتراک\n\n"
            f"📦 سرویس: {sub['service_name']}\n"
            f"👤 نام کاربری: @{sub['username']}\n"
            f"🔵 وضعیت: {sub['status']}\n"
        )

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

        await query.message.reply_text(
            text,
            reply_markup=_menu(config, query.from_user.id)
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex(r"^renew_\d+$")
    )
    async def renew_selected(client, query):

        sub_id = int(
            query.data.split("_")[1]
        )

        sub = get_subscription(sub_id)

        if not sub or sub["user_id"] != query.from_user.id:
            await query.answer(
                "❌ اشتراک پیدا نشد.",
                show_alert=True
            )
            return

        service_name = sub["service_name"]

        services = get_services(True)

        service = next(
            (
                x for x in services
                if x["name"] == service_name
            ),
            None
        )

        if not service:
            await query.answer(
                "❌ سرویس مربوطه دیگر فعال نیست.",
                show_alert=True
            )
            return

        user_states[query.from_user.id] = {
            "step": "renew_confirm",
            "subscription_id": sub_id,
            "service_id": service["id"],
            "username": sub["username"],
            "discount": 0
        }

        await query.message.reply_text(
            "🔄 تمدید اشتراک\n\n"
            f"📦 سرویس: {service['name']}\n"
            f"💾 حجم: {service['volume_gb']}GB\n"
            f"👤 نام کاربری: @{sub['username']}\n"
            f"💰 مبلغ: {format_price(service['price'])} تومان\n\n"
            "برای ادامه تأیید کنید:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ تأیید تمدید",
                            callback_data="confirm_renew"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ لغو",
                            callback_data="user_home"
                        )
                    ]
                ]
            )
        )

        await query.answer()

    @app.on_callback_query(
        filters.regex("^confirm_renew$")
    )
    async def confirm_renew(client, query):

        user_id = query.from_user.id

        state = user_states.get(user_id)

        if not state or state.get("step") != "renew_confirm":
            await query.answer(
                "❌ درخواست منقضی شده.",
                show_alert=True
            )
            return

        service = get_service(
            state["service_id"]
        )

        if not service:
            await query.answer(
                "❌ سرویس پیدا نشد.",
                show_alert=True
            )
            return

        order_id = create_order(
            user_id=user_id,
            service_id=service["id"],
            service_name=service["name"],
            order_type="renew",
            username=state["username"],
            original_price=service["price"],
            discount_percent=0,
            final_price=service["price"],
            coupon=None
        )

        user_states[user_id] = {
            "step": "waiting_receipt",
            "order_id": order_id
        }

        await query.message.reply_text(
            order_created(order_id)
        )

        await query.message.reply_text(
            payment(
                config.get("payment_card", "YOUR_CARD"),
                config.get("payment_name", "CARD_OWNER")
            )
        )

        await query.answer()


    @app.on_callback_query(
        filters.regex(r"^tutorial_\d+$")
    )
    async def tutorial_selected(client, query):

        tutorial_id = int(
            query.data.split("_")[1]
        )

        item = get_tutorial(tutorial_id)

        if not item or not item.get("active"):
            await query.answer(
                "❌ این آموزش فعال نیست.",
                show_alert=True
            )
            return

        body = (item.get("body_text") or "").strip()

        if body:
            await query.message.reply_text(
                f"{item['title']}\n\n{body}"
            )
        else:
            await query.message.reply_text(
                f"{item['title']}"
            )

        if item.get("file_id"):
            try:
                await client.send_document(
                    query.from_user.id,
                    item["file_id"],
                    caption="📎 فایل نصب / برنامه"
                )
            except Exception as e:
                print(f"Tutorial file error: {e}")

        if item.get("video_file_id"):
            try:
                await client.send_video(
                    query.from_user.id,
                    item["video_file_id"],
                    caption="🎬 ویدیو آموزشی"
                )
            except Exception:
                try:
                    await client.send_document(
                        query.from_user.id,
                        item["video_file_id"],
                        caption="🎬 ویدیو آموزشی"
                    )
                except Exception as e:
                    print(f"Tutorial video error: {e}")

        await query.answer()


    @app.on_callback_query(
        filters.regex("^user_home$")
    )
    async def user_home(client, query):

        user_states.pop(
            query.from_user.id,
            None
        )

        await query.message.reply_text(
            "🏠 منوی اصلی",
            reply_markup=_menu(config, query.from_user.id)
        )

        await query.answer()
