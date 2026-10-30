import asyncio
import os
import re
from datetime import datetime

from bot import remote_storage


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"
READY_MARKER = "data/.remote_state_ready"
CHECK_INTERVAL = 300
MIN_REMOTE_ADVANTAGE_SECONDS = 30

_monitor_task = None


def mark_remote_state_ready():
    try:
        os.makedirs("data", exist_ok=True)
        with open(READY_MARKER, "w", encoding="utf-8") as f:
            f.write("ok")
    except Exception as e:
        print(
            f"Remote State Monitor marker error: {e}"
        )


def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _remote_updated_at(message):
    # remote_storage._get_state_message returns the raw Bot API dictionary,
    # not a Pyrogram Message object.
    if isinstance(message, dict):
        caption = message.get("caption") or message.get("text") or ""
    else:
        caption = getattr(message, "caption", None) or getattr(message, "text", None) or ""

    match = re.search(
        r"(?:Backup time|Updated):\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
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
        db_message = await remote_storage._get_state_message(
            remote_storage._data_chat_id(),
            remote_storage.DB_STATE_MARKER
        )
        config_message = await remote_storage._get_state_message(
            remote_storage._config_chat_id(),
            remote_storage.CONFIG_STATE_MARKER
        )

        if not db_message and not config_message:
            return

        # On a fresh/ephemeral instance, restore both remote state components.
        if not os.path.exists(READY_MARKER):
            print(
                "Remote State Monitor: local readiness marker is missing; "
                "trying remote restore."
            )
            restored = await remote_storage.restore_from_remote()
            if restored:
                mark_remote_state_ready()
            return

        local_db_time = _file_mtime(DB_PATH)
        local_config_time = _file_mtime(CONFIG_PATH)
        remote_db_time = _remote_updated_at(db_message) if db_message else None
        remote_config_time = _remote_updated_at(config_message) if config_message else None

        # Compare each remote artifact with its matching local file. Comparing
        # the DB timestamp to max(DB, config) could hide a newer config backup.
        db_is_newer = bool(
            db_message and (
                local_db_time is None
                or (remote_db_time is not None
                    and remote_db_time > local_db_time + MIN_REMOTE_ADVANTAGE_SECONDS)
            )
        )
        config_is_newer = bool(
            config_message and (
                local_config_time is None
                or (remote_config_time is not None
                    and remote_config_time > local_config_time + MIN_REMOTE_ADVANTAGE_SECONDS)
            )
        )

        if db_is_newer or config_is_newer:
            newer_parts = []
            if db_is_newer:
                newer_parts.append("database")
            if config_is_newer:
                newer_parts.append("configuration")
            print(
                "Remote State Monitor: remote "
                + " and ".join(newer_parts)
                + " state is newer; restoring remote state."
            )
            restored = await remote_storage.restore_from_remote()
            if restored:
                mark_remote_state_ready()

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
