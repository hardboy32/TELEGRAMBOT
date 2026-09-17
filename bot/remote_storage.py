import os
import json
import asyncio
import sqlite3
from datetime import datetime

from pyrogram import Client


STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")

STORAGE_API_ID = os.getenv("STORAGE_API_ID")
STORAGE_API_HASH = os.getenv("STORAGE_API_HASH")
STORAGE_SESSION_STRING = os.getenv("STORAGE_SESSION_STRING")


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"


_storage_client = None
_storage_started = False
_sync_lock = asyncio.Lock()


def storage_enabled():
    return all([
        STORAGE_CHAT_ID,
        STORAGE_API_ID,
        STORAGE_API_HASH,
        STORAGE_SESSION_STRING
    ])


async def start_storage():
    global _storage_client
    global _storage_started

    if _storage_started:
        return

    if not storage_enabled():
        print(
            "Remote Storage: environment variables are not configured."
        )
        return

    try:

        _storage_client = Client(
            "cafe_hermes_storage",
            api_id=int(STORAGE_API_ID),
            api_hash=STORAGE_API_HASH,
            session_string=STORAGE_SESSION_STRING
        )

        await _storage_client.start()

        _storage_started = True

        print(
            "Remote Storage account connected successfully."
        )

    except Exception as e:

        print(
            f"Remote Storage start error: {e}"
        )

        _storage_client = None
        _storage_started = False


async def stop_storage():

    global _storage_client
    global _storage_started

    if _storage_client:

        try:
            await _storage_client.stop()

        except Exception:
            pass

    _storage_client = None
    _storage_started = False


def _get_db_snapshot():

    if not os.path.exists(DB_PATH):
        return None

    os.makedirs(
        "data",
        exist_ok=True
    )

    snapshot_path = (
        "data/.remote_snapshot.db"
    )

    source = sqlite3.connect(
        DB_PATH
    )

    destination = sqlite3.connect(
        snapshot_path
    )

    try:

        source.backup(destination)

    finally:

        destination.close()
        source.close()

    return snapshot_path


async def upload_database():

    if not _storage_started:
        return False

    snapshot_path = _get_db_snapshot()

    if not snapshot_path:
        return False

    try:

        await _storage_client.send_document(
            STORAGE_CHAT_ID,
            snapshot_path,
            caption=(
                "🗄 Cafe Hermes Database\n"
                f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        return True

    except Exception as e:

        print(
            f"Remote database upload error: {e}"
        )

        return False

    finally:

        try:
            os.remove(snapshot_path)

        except Exception:
            pass


async def upload_config():

    if not _storage_started:
        return False

    if not os.path.exists(CONFIG_PATH):
        return False

    try:

        await _storage_client.send_document(
            STORAGE_CHAT_ID,
            CONFIG_PATH,
            caption=(
                "⚙️ Cafe Hermes Config\n"
                f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        return True

    except Exception as e:

        print(
            f"Remote config upload error: {e}"
        )

        return False


async def sync_all():

    if not _storage_started:
        return False

    async with _sync_lock:

        db_ok = await upload_database()
        config_ok = await upload_config()

        return db_ok and config_ok


def schedule_sync():

    try:

        loop = asyncio.get_running_loop()

    except RuntimeError:

        return

    loop.create_task(
        sync_all()
    )
