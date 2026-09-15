import aiohttp
from bs4 import BeautifulSoup


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


def remaining_less_than_one_gb(remaining):
    if not remaining:
        return False

    text = remaining.lower().replace(",", "")

    try:
        if "gb" in text:
            number = float(
                text.replace("gb", "").strip()
            )
            return number < 1

        if "mb" in text:
            number = float(
                text.replace("mb", "").strip()
            )
            return number < 1024

    except ValueError:
        pass

    return False
