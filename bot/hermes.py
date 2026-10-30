import asyncio

import aiohttp
from bs4 import BeautifulSoup

from bot.database import (
    get_active_subscriptions,
    get_low_volume_warned,
    set_low_volume_warned,
    reset_low_volume_warning,
)


_monitor_task = None
CHECK_INTERVAL_SECONDS = 3600


async def get_subscription_info(url):
    if not url:
        return {
            "success": False,
            "message": "لینک اشتراک ثبت نشده است."
        }

    try:
        timeout = aiohttp.ClientTimeout(total=20)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            )
        }

        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers
        ) as session:

            async with session.get(url) as response:
                if response.status != 200:
                    return {
                        "success": False,
                        "message": f"خطای سایت: {response.status}"
                    }

                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")

        text = soup.get_text(
            "\n",
            strip=True
        )

        result = {
            "success": True,
            "username": find_value(text, [
                "نام کاربری",
                "Username",
                "username"
            ]),
            "last_connection": find_value(text, [
                "آخرین اتصال",
                "Last Connection"
            ]),
            "total_usage": find_value(text, [
                "مصرف کل",
                "Total Usage"
            ]),
            "period_usage": find_value(text, [
                "مصرف دوره",
                "Period Usage"
            ]),
            "total_volume": find_value(text, [
                "حجم کل",
                "Total Volume"
            ]),
            "remaining": find_value(text, [
                "باقیمانده",
                "Remaining"
            ])
        }

        return result

    except Exception as e:
        return {
            "success": False,
            "message": f"خطا در بررسی اشتراک: {e}"
        }


def find_value(text, labels):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for index, line in enumerate(lines):
        for label in labels:
            if label.lower() in line.lower():

                if ":" in line:
                    value = line.split(":", 1)[1].strip()

                    if value:
                        return value

                if index + 1 < len(lines):
                    return lines[index + 1]

    return "نامشخص"


def remaining_less_than_one_gb(remaining, threshold_gb=1):
    if not remaining:
        return False

    text = remaining.lower().replace(",", "").strip()

    try:
        if "gb" in text:
            number = float(text.replace("gb", "").strip())
            return number < float(threshold_gb)

        if "mb" in text:
            number = float(text.replace("mb", "").strip())
            return number < float(threshold_gb) * 1024

    except (TypeError, ValueError):
        pass

    return False


async def check_low_volume_once(client, config):
    if not config.get("hermes_check_enabled", False):
        return

    subscriptions = get_active_subscriptions()
    low_users = {}
    failed_users = set()

    for subscription in subscriptions:
        result = await get_subscription_info(subscription.get("subscription_url"))
        if not result.get("success"):
            failed_users.add(subscription["user_id"])
            continue

        remaining = result.get("remaining")
        if remaining_less_than_one_gb(remaining, config.get("low_volume_gb", 1)):
            low_users.setdefault(subscription["user_id"], []).append({
                "username": subscription.get("username") or "نامشخص",
                "service_name": subscription.get("service_name") or "اشتراک",
                "remaining": remaining or "نامشخص",
            })

    user_ids = {item["user_id"] for item in subscriptions}
    for user_id in user_ids:
        low_items = low_users.get(user_id, [])
        if not low_items:
            if user_id not in failed_users:
                reset_low_volume_warning(user_id)
            continue

        if (not config.get("low_volume_notification_enabled", False)
                or get_low_volume_warned(user_id)):
            continue

        details = "\n".join(
            f"• {item['service_name']} ({item['username']}): {item['remaining']}"
            for item in low_items
        )
        try:
            await client.send_message(
                user_id,
                "⚠️ هشدار کاهش حجم اشتراک\n\n"
                + details
                + "\n\nحجم باقی‌مانده یکی از اشتراک‌های شما کمتر از ۱ گیگابایت است."
            )
            set_low_volume_warned(user_id)
        except Exception as e:
            print(f"Hermes low-volume notification failed for {user_id}: {e}")


async def _monitor_loop(client, config):
    try:
        while True:
            try:
                await check_low_volume_once(client, config)
            except Exception as e:
                print(f"Hermes monitor check failed: {e}")
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        raise
    finally:
        global _monitor_task
        _monitor_task = None


def start_hermes_monitor(client, config):
    global _monitor_task
    if not config.get("hermes_check_enabled", False):
        print("Hermes monitor is disabled by configuration.")
        return
    if _monitor_task and not _monitor_task.done():
        return
    _monitor_task = asyncio.create_task(_monitor_loop(client, config))
    print("Hermes subscription monitor started (hourly checks).")


async def stop_hermes_monitor():
    global _monitor_task
    if _monitor_task:
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
    _monitor_task = None

