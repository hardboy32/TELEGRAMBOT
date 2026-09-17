from pyrogram import filters, StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.database import (
    get_services,
    get_service,
    add_service,
    toggle_service,
    update_service,
    delete_service
)
from bot.helpers import admin, format_price


service_states = {}


def _digits(value):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )
    return str(value).translate(table)


def _service_list_keyboard(services):
    rows = []

    for service in services:
        status = "🟢" if service["active"] else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{status} {service['volume_gb']}GB | "
                    f"{format_price(service['price'])} تومان",
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


def _service_detail_keyboard(service_id):
    return InlineKeyboardMarkup(
        [
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


def _service_list_text(services):
    if not services:
        return "📦 مدیریت سرویس‌ها\n\nهنوز سرویسی ثبت نشده است."

    lines = ["📦 مدیریت سرویس‌ها\n"]

    for index, service in enumerate(services, start=1):
        status = "🟢 فعال" if service["active"] else "🔴 غیرفعال"
        lines.append(
            f"{index}. 📦 {service['volume_gb']}GB | "
            f"💰 {format_price(service['price'])} تومان | {status}"
        )

    return "\n".join(lines)


def _service_detail_text(service):
    status = "🟢 فعال" if service["active"] else "🔴 غیرفعال"

    return (
        "📦 جزئیات سرویس\n\n"
        f"💾 حجم: {service['volume_gb']}GB\n"
        f"💰 قیمت: {format_price(service['price'])} تومان\n"
        f"🔘 وضعیت: {status}"
    )


def _show_services(message):
    services = get_services(False)
    return message.reply_text(
        _service_list_text(services),
        reply_markup=_service_list_keyboard(services)
    )


async def _show_services_callback(query):
    services = get_services(False)
    await query.message.edit_text(
        _service_list_text(services),
        reply_markup=_service_list_keyboard(services)
    )


def register(app, config):

    @app.on_message(
        filters.private
        & filters.text
        & filters.regex("^📦 مدیریت سرویس‌ها$"),
        group=-19
    )
    async def service_management_message(client, message):
        if not admin(message.from_user.id, config):
            return

        service_states.pop(message.from_user.id, None)
        await _show_services(message)
        raise StopPropagation

    @app.on_message(
        filters.private & filters.text,
        group=-19
    )
    async def service_management_text(client, message):
        user_id = message.from_user.id

        if not admin(user_id, config):
            return

        state = service_states.get(user_id)

        if not state:
            return

        text = _digits(message.text.strip())
        action = state.get("action")

        if action in ("add_volume", "edit_volume"):
            try:
                volume = int(text)
            except ValueError:
                await message.reply_text("❌ حجم باید یک عدد صحیح باشد. مثال: 100")
                raise StopPropagation

            if volume <= 0:
                await message.reply_text("❌ حجم باید بیشتر از صفر باشد.")
                raise StopPropagation

            if action == "add_volume":
                state["volume_gb"] = volume
                state["action"] = "add_price"
                await message.reply_text("💰 قیمت این پلن را به تومان وارد کنید:")
            else:
                service_id = state["service_id"]
                service = get_service(service_id)

                if not service:
                    service_states.pop(user_id, None)
                    await message.reply_text("❌ سرویس پیدا نشد.")
                    raise StopPropagation

                update_service(
                    service_id,
                    name=f"{volume}GB",
                    volume_gb=volume
                )

                service_states.pop(user_id, None)
                updated = get_service(service_id)
                await message.reply_text(
                    "✅ حجم سرویس تغییر کرد.\n\n" + _service_detail_text(updated),
                    reply_markup=_service_detail_keyboard(service_id)
                )

            raise StopPropagation

        if action in ("add_price", "edit_price"):
            try:
                price = int(text.replace(",", "").replace(" ", ""))
            except ValueError:
                await message.reply_text("❌ قیمت باید یک عدد باشد. مثال: 150000")
                raise StopPropagation

            if price <= 0:
                await message.reply_text("❌ قیمت باید بیشتر از صفر باشد.")
                raise StopPropagation

            if action == "add_price":
                volume = state.get("volume_gb")
                if not volume:
                    service_states.pop(user_id, None)
                    await message.reply_text("❌ اطلاعات سرویس ناقص شد. دوباره تلاش کنید.")
                    raise StopPropagation

                service_id = add_service(
                    f"{volume}GB",
                    volume,
                    price
                )
                service_states.pop(user_id, None)

                created = get_service(service_id)
                await message.reply_text(
                    "✅ سرویس با موفقیت اضافه شد.\n\n" + _service_detail_text(created),
                    reply_markup=_service_detail_keyboard(service_id)
                )

            else:
                service_id = state["service_id"]
                service = get_service(service_id)

                if not service:
                    service_states.pop(user_id, None)
                    await message.reply_text("❌ سرویس پیدا نشد.")
                    raise StopPropagation

                update_service(
                    service_id,
                    price=price
                )

                service_states.pop(user_id, None)
                updated = get_service(service_id)
                await message.reply_text(
                    "✅ قیمت سرویس تغییر کرد.\n\n" + _service_detail_text(updated),
                    reply_markup=_service_detail_keyboard(service_id)
                )

            raise StopPropagation

    @app.on_callback_query(
        filters.regex("^admin_services$"),
        group=-19
    )
    async def service_list_callback(client, query):
        if not admin(query.from_user.id, config):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return

        await query.answer()
        service_states.pop(query.from_user.id, None)
        await _show_services_callback(query)

    @app.on_callback_query(
        filters.regex("^admin_add_service$"),
        group=-19
    )
    async def service_add_callback(client, query):
        if not admin(query.from_user.id, config):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return

        await query.answer()
        service_states[query.from_user.id] = {
            "action": "add_volume"
        }

        await query.message.edit_text(
            "➕ افزودن سرویس جدید\n\n"
            "💾 حجم پلن را به گیگابایت وارد کنید:\n"
            "مثال: 50 یا 100 یا 200"
        )

    @app.on_callback_query(
        filters.regex(r"^admin_service_\d+$"),
        group=-19
    )
    async def service_detail_callback(client, query):
        if not admin(query.from_user.id, config):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return

        await query.answer()

        try:
            service_id = int(query.data.rsplit("_", 1)[1])
        except (TypeError, ValueError):
            await query.message.edit_text("❌ شناسه سرویس نامعتبر است.")
            return

        service = get_service(service_id)

        if not service:
            await query.message.edit_text(
                "❌ سرویس پیدا نشد.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_services")]]
                )
            )
            return

        service_states.pop(query.from_user.id, None)
        await query.message.edit_text(
            _service_detail_text(service),
            reply_markup=_service_detail_keyboard(service_id)
        )

    @app.on_callback_query(
        filters.regex(r"^svc_edit_vol_\d+$"),
        group=-19
    )
    async def service_edit_volume_callback(client, query):
        if not admin(query.from_user.id, config):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return

        await query.answer()
        service_id = int(query.data.rsplit("_", 1)[1])
        service = get_service(service_id)

        if not service:
            await query.message.edit_text("❌ سرویس پیدا نشد.")
            return

        service_states[query.from_user.id] = {
            "action": "edit_volume",
            "service_id": service_id
        }

        await query.message.edit_text(
            "💾 حجم جدید را به گیگابایت وارد کنید:\n"
            f"حجم فعلی: {service['volume_gb']}GB"
        )

    @app.on_callback_query(
        filters.regex(r"^svc_edit_price_\d+$"),
        group=-19
    )
    async def service_edit_price_callback(client, query):
        if not admin(query.from_user.id, config):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return

        await query.answer()
        service_id = int(query.data.rsplit("_", 1)[1])
        service = get_service(service_id)

        if not service:
            await query.message.edit_text("❌ سرویس پیدا نشد.")
            return

        service_states[query.from_user.id] = {
            "action": "edit_price",
            "service_id": service_id
        }

        await query.message.edit_text(
            "💰 قیمت جدید را به تومان وارد کنید:\n"
            f"قیمت فعلی: {format_price(service['price'])} تومان"
        )

    @app.on_callback_query(
        filters.regex(r"^svc_toggle_\d+$"),
        group=-19
    )
    async def service_toggle_callback(client, query):
        if not admin(query.from_user.id, config):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return

        await query.answer()
        service_id = int(query.data.rsplit("_", 1)[1])
        service = get_service(service_id)

        if not service:
            await query.message.edit_text("❌ سرویس پیدا نشد.")
            return

        toggle_service(service_id)
        service = get_service(service_id)

        await query.message.edit_text(
            _service_detail_text(service),
            reply_markup=_service_detail_keyboard(service_id)
        )

    @app.on_callback_query(
        filters.regex(r"^svc_del_\d+$"),
        group=-19
    )
    async def service_delete_callback(client, query):
        if not admin(query.from_user.id, config):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return

        await query.answer()
        service_id = int(query.data.rsplit("_", 1)[1])
        service = get_service(service_id)

        if not service:
            await query.message.edit_text("❌ سرویس پیدا نشد.")
            return

        delete_service(service_id)
        service_states.pop(query.from_user.id, None)
        await _show_services_callback(query)
