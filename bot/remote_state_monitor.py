import asyncio
import os
import re
from datetime import datetime

from bot import remote_storage


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"
CHECK_INTERVAL = 300
MIN_REMOTE_ADVANTAGE_SECONDS = 30

_monitor_task = None


def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _remote_updated_at(message):
    caption = ""

    try:
        caption = message.caption or message.text or ""
    except Exception:
        return None

    match = re.search(
        r"Updated:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
        caption
    )

    if not match:
        return None

    try:
        return datetime.strptime(
            match.group(1),
            "%Y-%m-%d %H:%M:%S"
        ).timestamp()
    except ValueError:
        return None


async def _check_remote_state():
    if not remote_storage._storage_started:
        return

    try:
        message = await remote_storage._get_state_message()

        if not message:
            return

        remote_time = _remote_updated_at(message)

        if remote_time is None:
            return

        local_times = [
            value
            for value in (
                _file_mtime(DB_PATH),
                _file_mtime(CONFIG_PATH)
            )
            if value is not None
        ]

        if not local_times:
            print(
                "Remote State Monitor: local state is missing; restoring remote state."
            )
            await remote_storage.restore_from_remote()
            return

        local_time = max(local_times)

        if remote_time > local_time + MIN_REMOTE_ADVANTAGE_SECONDS:
            print(
                "Remote State Monitor: remote state is newer; restoring it."
            )
            await remote_storage.restore_from_remote()

    except Exception as e:
        print(
            f"Remote State Monitor error: {e}"
        )


async def _monitor_loop():
    try:
        while remote_storage._storage_started:
            await asyncio.sleep(CHECK_INTERVAL)

            if not remote_storage._storage_started:
                break

            await _check_remote_state()

    except asyncio.CancelledError:
        raise

    except Exception as e:
        print(
            f"Remote State Monitor loop error: {e}"
        )

    finally:
        global _monitor_task
        _monitor_task = None


def start_remote_state_monitor():
    global _monitor_task

    if not remote_storage._storage_started:
        return

    if (
        _monitor_task
        and not _monitor_task.done()
    ):
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    _monitor_task = loop.create_task(
        _monitor_loop()
    )

    print(
        "Remote State Monitor started. Interval: 5 minutes."
    )


async def stop_remote_state_monitor():
    global _monitor_task

    if _monitor_task:
        _monitor_task.cancel()

        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    _monitor_task = None
