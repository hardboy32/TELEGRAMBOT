import asyncio
import json
from datetime import datetime

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
)


# =========================================================
# ابزارهای کمکی
# =========================================================

def is_admin(user_id, config):
    return user_id in config.get("admin_ids", [])


def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧾 سفارش‌های در انتظار", callback_data="admin_pending"),
        ],
        [
            InlineKeyboardButton("📦 مدیریت سرویس‌ها", callback_data="admin_services"),
            InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="admin_coupons"),
        ],
        [
            InlineKeyboardButton("👥 کاربران", callback_data="admin_users"),
            InlineKeyboardButton("📊 آمار", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("🎛️ مدیریت دکمه‌ها", callback_data="admin_buttons"),
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات پرداخت", callback_data="admin_payment"),
        ],
        [
            InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast"),
        ],
    ])


def back_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")]
    ])


# =========================================================
# ثبت Handler ها
# =========================================================

def register(app, config):

    # -----------------------------------------------------
    # /admin
    # -----------------------------------------------------

    @app.on_message(
        filters.private
        & filters.command("admin")
    )
    async def admin_start(client, message):

        if not is_admin(message.from_user.id, config):
            await message.reply_text("⛔️ شما دسترسی مدیریت ندارید.")
            return

        await message.reply_text(
            "👨‍💻 پنل مدیریت کافه هرمس\n\n"
            "یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=admin_menu()
        )

    # -----------------------------------------------------
    # callback ها
    # -----------------------------------------------------

    @app.on_callback_query()
    async def admin_callbacks(client, query):

        user_id = query.from_user.id

        if not is_admin(user_id, config):
            await query.answer(
                "⛔️ دسترسی ندارید.",
                show_alert=True
            )
            return

        data = query.data

        # ================================
        # منوی اصلی
        # ================================

        if data == "admin_menu":

            await query.message.edit_text(
                "👨‍💻 پنل مدیریت کافه هرمس\n\n"
                "یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=admin_menu()
            )

            await query.answer()
            return

        # ================================
        # سفارش‌های در انتظار
        # ================================

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
                    f"💵 مبلغ: {order['final_price']:,} تومان\n\n"
                )

                buttons.append([
                    InlineKeyboardButton(
                        f"🧾 سفارش #{order['id']}",
                        callback_data=f"admin_order_{order['id']}"
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

        # ================================
        # نمایش سفارش
        # ================================

        if data.startswith("admin_order_"):

            order_id = int(data.split("_")[-1])

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
                f"👤 نام کاربری سرویس: {order['username']}\n"
                f"📦 سرویس: {order['service_name']}\n\n"
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

            # اگر رسید عکس داشته باشد
            if order.get("receipt_file_id"):

                try:
                    await client.send_photo(
                        chat_id=user_id,
                        photo=order["receipt_file_id"],
                        caption=f"🧾 رسید سفارش #{order_id}"
                    )
                except Exception:
                    pass

            await query.answer()
            return

        # ================================
        # تأیید سفارش
        # ================================

        if data.startswith("approve_"):

            order_id = int(data.split("_")[-1])

            order = get_order(order_id)

            if not order:
                await query.answer(
                    "سفارش پیدا نشد.",
                    show_alert=True
                )
                return

            if order["status"] != "pending":
                await query.answer(
                    "این سفارش قبلاً بررسی شده.",
                    show_alert=True
                )
                return

            approve_order(order_id)

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

            await query.message.edit_text(
                f"✅ سفارش #{order_id} تأیید شد.\n\n"
                "اکنون کانفیگ این سفارش را ثبت کنید.",
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

            await query.answer("پرداخت تأیید شد.")
            return

        # ================================
        # رد سفارش
        # ================================

        if data.startswith("reject_"):

            order_id = int(data.split("_")[-1])

            order = get_order(order_id)

            if not order:
                await query.answer(
                    "سفارش پیدا نشد.",
                    show_alert=True
                )
                return

            if order["status"] != "pending":
                await query.answer(
                    "این سفارش قبلاً بررسی شده.",
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

            await query.answer("سفارش رد شد.")
            return

        # ================================
        # ثبت کانفیگ
        # ================================

        if data.startswith("config_"):

            order_id = int(data.split("_")[-1])

            app.admin
