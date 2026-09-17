import os
import json
import asyncio
import sqlite3
from datetime import datetime

from pyrogram import Client


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"

STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")
STORAGE_API_ID = os.getenv("STORAGE_API_ID")
STORAGE_API_HASH = os.getenv("STORAGE_API_HASH")
STORAGE_SESSION_STRING = os.getenv("STORAGE_SESSION_STRING")


_storage_client = None
_storage_started = False

_sync_lock = asyncio.Lock()
_sync_task = None


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
        return True

    if not storage_enabled():
        print("Remote Storage: environment variables are not configured.")
        return False

    try:
        _storage_client = Client(
            "cafe_hermes_storage",
            api_id=int(STORAGE_API_ID),
            api_hash=STORAGE_API_HASH,
            session_string=STORAGE_SESSION_STRING
        )

        await _storage_client.start()

        _storage_started = True

        print("Remote Storage account connected successfully.")

        return True

    except Exception as e:
        print(f"Remote Storage start error: {e}")

        _storage_client = None
        _storage_started = False

        return False


async def stop_storage():
    global _storage_client
    global _storage_started

    if _storage_client:

        try:
            await _storage_client.stop()

        except Exception as e:
            print(f"Remote Storage stop error: {e}")

    _storage_client = None
    _storage_started = False


def _create_db_snapshot():
    if not os.path.exists(DB_PATH):
        return None

    os.makedirs("data", exist_ok=True)

    snapshot_path = "data/.remote_database.db"

    source = None
    destination = None

    try:
        source = sqlite3.connect(DB_PATH)
        destination = sqlite3.connect(snapshot_path)

        source.backup(destination)

        return snapshot_path

    except Exception as e:
        print(f"Database snapshot error: {e}")
        return None

    finally:

        if destination:
            destination.close()

        if source:
            source.close()


async def _find_latest_message(marker):
    if not _storage_started:
        return None

    latest = None

    try:

        async for message in _storage_client.get_chat_history(
            int(STORAGE_CHAT_ID)
        ):

            text = ""

            if message.caption:
                text = message.caption

            elif message.text:
                text = message.text

            if text.startswith(marker):

                latest = message
                break

    except Exception as e:
        print(f"Remote search error: {e}")

    return latest


async def _delete_old_message(marker):
    old_message = await _find_latest_message(marker)

    if old_message:

        try:
            await _storage_client.delete_messages(
                int(STORAGE_CHAT_ID),
                old_message.id
            )

        except Exception as e:
            print(f"Remote old message delete error: {e}")


async def upload_database():
    if not _storage_started:
        return False

    snapshot_path = _create_db_snapshot()

    if not snapshot_path:
        return False

    marker = "CAFE_HERMES_DATABASE"

    try:

        await _delete_old_message(marker)

        await _storage_client.send_document(
            int(STORAGE_CHAT_ID),
            snapshot_path,
            caption=(
                f"{marker}\n"
                f"Updated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        print("Remote database synchronized.")

        return True

    except Exception as e:

        print(f"Remote database upload error: {e}")

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

    marker = "CAFE_HERMES_CONFIG"

    try:

        await _delete_old_message(marker)

        await _storage_client.send_document(
            int(STORAGE_CHAT_ID),
            CONFIG_PATH,
            caption=(
                f"{marker}\n"
                f"Updated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        print("Remote config synchronized.")

        return True

    except Exception as e:

        print(f"Remote config upload error: {e}")

        return False


def _get_all_users():
    if not os.path.exists(DB_PATH):
        return []

    conn = None

    try:

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT * FROM users ORDER BY id ASC"
        ).fetchall()

        return [dict(row) for row in rows]

    except Exception as e:

        print(f"User export error: {e}")

        return []

    finally:

        if conn:
            conn.close()


async def upload_user_file(user):
    if not _storage_started:
        return False

    user_id = user.get("id")

    if not user_id:
        return False

    os.makedirs("data/remote_users", exist_ok=True)

    path = f"data/remote_users/user_{user_id}.json"

    try:

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                user,
                f,
                ensure_ascii=False,
                indent=2
            )

        marker = f"CAFE_HERMES_USER:{user_id}"

        await _delete_old_message(marker)

        await _storage_client.send_document(
            int(STORAGE_CHAT_ID),
            path,
            caption=(
                f"{marker}\n"
                f"Updated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        return True

    except Exception as e:

        print(
            f"Remote user {user_id} upload error: {e}"
        )

        return False

    finally:

        try:
            os.remove(path)

        except Exception:
            pass


async def upload_all_users():
    users = _get_all_users()

    if not users:
        return True

    success = True

    for user in users:

        result = await upload_user_file(user)

        if not result:
            success = False

        await asyncio.sleep(0.2)

    print(
        f"Remote users synchronized: {len(users)}"
    )

    return success


async def sync_all():
    if not _storage_started:
        return False

    async with _sync_lock:

        print("Remote Storage: synchronization started.")

        db_ok = await upload_database()

        config_ok = await upload_config()

        users_ok = await upload_all_users()

        result = (
            db_ok
            and config_ok
            and users_ok
        )

        if result:
            print(
                "Remote Storage: synchronization completed."
            )

        else:
            print(
                "Remote Storage: synchronization completed with errors."
            )

        return result


def schedule_sync():
    global _sync_task

    if not _storage_started:
        return

    try:
        loop = asyncio.get_running_loop()

    except RuntimeError:
        return

    if _sync_task and not _sync_task.done():
        return

    _sync_task = loop.create_task(
        sync_all()
    )


async def restore_database_from_remote():
    if not _storage_started:
        return False

    message = await _find_latest_message(
        "CAFE_HERMES_DATABASE"
    )

    if not message:
        print(
            "Remote Storage: no database snapshot found."
        )
        return False

    os.makedirs("data", exist_ok=True)

    temp_path = "data/.remote_restore.db"

    try:

        await _storage_client.download_media(
            message,
            file_name=temp_path
        )

        if not os.path.exists(temp_path):
            print(
                "Remote database download failed."
            )
            return False

        if os.path.exists(DB_PATH):

            backup_path = (
                "data/cafe_hermes_before_restore.db"
            )

            try:
                os.replace(
                    DB_PATH,
                    backup_path
                )

            except Exception:
                pass

        os.replace(
            temp_path,
            DB_PATH
        )

        print(
            "Remote database restored successfully."
        )

        return True

    except Exception as e:

        print(
            f"Remote database restore error: {e}"
        )

        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        except Exception:
            pass

        return False


async def restore_config_from_remote():
    if not _storage_started:
        return False

    message = await _find_latest_message(
        "CAFE_HERMES_CONFIG"
    )

    if not message:
        print(
            "Remote Storage: no config snapshot found."
        )
        return False

    temp_path = "data/.remote_config.json"

    try:

        os.makedirs("data", exist_ok=True)

        await _storage_client.download_media(
            message,
            file_name=temp_path
        )

        if not os.path.exists(temp_path):
            return False

        with open(
            temp_path,
            "r",
            encoding="utf-8"
        ) as f:

            remote_config = json.load(f)

        with open(
            CONFIG_PATH,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                remote_config,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.remove(temp_path)

        print(
            "Remote config restored successfully."
        )

        return True

    except Exception as e:

        print(
            f"Remote config restore error: {e}"
        )

        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        except Exception:
            pass

        return False


async def restore_from_remote():
    if not _storage_started:
        return False

    print(
        "Remote Storage: checking remote state..."
    )

    db_restored = await restore_database_from_remote()

    config_restored = await restore_config_from_remote()

    if db_restored or config_restored:

        print(
            "Remote Storage: remote state restored."
        )

        return True

    print(
        "Remote Storage: nothing to restore."
    )

    return False
