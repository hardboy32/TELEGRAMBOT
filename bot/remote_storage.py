import os
import json
import asyncio
import sqlite3
from datetime import datetime


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"

STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")


_storage_app = None
_storage_started = False

_sync_lock = asyncio.Lock()
_sync_task = None
_watcher_task = None

_dirty = False
_last_db_mtime = None
_last_config_mtime = None


def storage_enabled():
    return bool(STORAGE_CHAT_ID)


def configure_storage(app):
    global _storage_app
    _storage_app = app


async def start_storage(app):
    global _storage_app
    global _storage_started

    _storage_app = app

    if _storage_started:
        return True

    if not storage_enabled():
        print(
            "Remote Storage: STORAGE_CHAT_ID is not configured."
        )
        return False

    try:
        chat = await _storage_app.get_chat(
            int(STORAGE_CHAT_ID)
        )

        print(
            "Remote Storage channel connected:"
            f" {chat.title or chat.id}"
        )

        _storage_started = True

        return True

    except Exception as e:
        print(
            f"Remote Storage connection error: {e}"
        )

        _storage_started = False

        return False


async def stop_storage():
    global _storage_started
    global _storage_app
    global _sync_task
    global _watcher_task

    if _watcher_task:

        try:
            _watcher_task.cancel()
            await _watcher_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    if _sync_task:

        try:
            _sync_task.cancel()
            await _sync_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    _watcher_task = None
    _sync_task = None

    _storage_started = False
    _storage_app = None


def _get_file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _create_db_snapshot():
    if not os.path.exists(DB_PATH):
        return None

    os.makedirs(
        "data",
        exist_ok=True
    )

    snapshot_path = (
        "data/.remote_database_snapshot.db"
    )

    source = None
    destination = None

    try:
        source = sqlite3.connect(DB_PATH)
        destination = sqlite3.connect(
            snapshot_path
        )

        source.backup(destination)

        return snapshot_path

    except Exception as e:

        print(
            f"Database snapshot error: {e}"
        )

        return None

    finally:

        if destination:
            try:
                destination.close()
            except Exception:
                pass

        if source:
            try:
                source.close()
            except Exception:
                pass


async def _find_latest_message(marker):
    if not _storage_started:
        return None

    if not _storage_app:
        return None

    latest = None

    try:

        async for message in _storage_app.get_chat_history(
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

        print(
            f"Remote search error: {e}"
        )

    return latest


async def _delete_all_messages_with_marker(marker):
    if not _storage_started:
        return

    if not _storage_app:
        return

    message_ids = []

    try:

        async for message in _storage_app.get_chat_history(
            int(STORAGE_CHAT_ID)
        ):

            text = ""

            if message.caption:
                text = message.caption

            elif message.text:
                text = message.text

            if text.startswith(marker):
                message_ids.append(message.id)

                if len(message_ids) >= 20:
                    break

        if not message_ids:
            return

        await _storage_app.delete_messages(
            int(STORAGE_CHAT_ID),
            message_ids
        )

    except Exception as e:

        print(
            f"Remote old message delete error: {e}"
        )


async def upload_database():
    if not _storage_started:
        return False

    if not _storage_app:
        return False

    snapshot_path = _create_db_snapshot()

    if not snapshot_path:
        return False

    marker = "CAFE_HERMES_DATABASE"

    try:

        await _delete_all_messages_with_marker(
            marker
        )

        await _storage_app.send_document(
            int(STORAGE_CHAT_ID),
            snapshot_path,
            caption=(
                f"{marker}\n"
                f"Updated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        print(
            "Remote database synchronized."
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

    if not _storage_app:
        return False

    if not os.path.exists(CONFIG_PATH):
        return False

    marker = "CAFE_HERMES_CONFIG"

    try:

        await _delete_all_messages_with_marker(
            marker
        )

        await _storage_app.send_document(
            int(STORAGE_CHAT_ID),
            CONFIG_PATH,
            caption=(
                f"{marker}\n"
                f"Updated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        print(
            "Remote config synchronized."
        )

        return True

    except Exception as e:

        print(
            f"Remote config upload error: {e}"
        )

        return False


def _get_user_full_record(user_id):
    conn = None

    try:

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        user_row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user_row:
            return None

        record = {
            "user": dict(user_row),
            "orders": [],
            "subscriptions": [],
            "referral_success": [],
            "referral_rewards": [],
        }

        rows = conn.execute(
            """
            SELECT *
            FROM orders
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        ).fetchall()

        record["orders"] = [
            dict(row)
            for row in rows
        ]

        rows = conn.execute(
            """
            SELECT *
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        ).fetchall()

        record["subscriptions"] = [
            dict(row)
            for row in rows
        ]

        rows = conn.execute(
            """
            SELECT *
            FROM referral_success
            WHERE inviter_id = ?
               OR invited_id = ?
            ORDER BY id DESC
            """,
            (user_id, user_id)
        ).fetchall()

        record["referral_success"] = [
            dict(row)
            for row in rows
        ]

        rows = conn.execute(
            """
            SELECT *
            FROM referral_rewards
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        ).fetchall()

        record["referral_rewards"] = [
            dict(row)
            for row in rows
        ]

        return record

    except Exception as e:

        print(
            f"User export error ({user_id}): {e}"
        )

        return None

    finally:

        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _get_all_user_ids():
    if not os.path.exists(DB_PATH):
        return []

    conn = None

    try:

        conn = sqlite3.connect(DB_PATH)

        rows = conn.execute(
            """
            SELECT id
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()

        return [
            row[0]
            for row in rows
        ]

    except Exception as e:

        print(
            f"User list export error: {e}"
        )

        return []

    finally:

        if conn:
            try:
                conn.close()
            except Exception:
                pass


async def upload_user_record(user_id):
    if not _storage_started:
        return False

    if not _storage_app:
        return False

    record = _get_user_full_record(user_id)

    if not record:
        return False

    os.makedirs(
        "data/.remote_users",
        exist_ok=True
    )

    file_path = (
        f"data/.remote_users/user_{user_id}.json"
    )

    marker = f"CAFE_HERMES_USER:{user_id}"

    try:

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                record,
                f,
                ensure_ascii=False,
                indent=2
            )

        await _delete_all_messages_with_marker(
            marker
        )

        await _storage_app.send_document(
            int(STORAGE_CHAT_ID),
            file_path,
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
            os.remove(file_path)
        except Exception:
            pass


async def upload_all_users():
    user_ids = _get_all_user_ids()

    if not user_ids:
        return True

    success = True

    for user_id in user_ids:

        result = await upload_user_record(
            user_id
        )

        if not result:
            success = False

        await asyncio.sleep(0.15)

    print(
        f"Remote users synchronized: "
        f"{len(user_ids)}"
    )

    return success


async def sync_all(force=False):
    global _dirty

    if not _storage_started:
        return False

    async with _sync_lock:

        if not force and not _dirty:
            return True

        print(
            "Remote Storage: synchronization started."
        )

        _dirty = False

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
                "Remote Storage: "
                "synchronization completed."
            )

        else:

            print(
                "Remote Storage: "
                "synchronization completed with errors."
            )

            _dirty = True

        return result


def schedule_sync():
    global _dirty
    global _sync_task

    if not _storage_started:
        return

    _dirty = True

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if _sync_task and not _sync_task.done():
        return

    _sync_task = loop.create_task(
        _sync_worker()
    )


async def _sync_worker():
    global _sync_task
    global _dirty

    try:

        while _storage_started:

            if not _dirty:
                break

            await asyncio.sleep(2)

            if _dirty:
                await sync_all(force=False)

    except asyncio.CancelledError:
        raise

    except Exception as e:

        print(
            f"Remote sync worker error: {e}"
        )

    finally:

        _sync_task = None


async def _watch_files_loop():
    global _last_db_mtime
    global _last_config_mtime

    _last_db_mtime = _get_file_mtime(DB_PATH)
    _last_config_mtime = _get_file_mtime(
        CONFIG_PATH
    )

    while _storage_started:

        try:

            await asyncio.sleep(2)

            current_db_mtime = _get_file_mtime(
                DB_PATH
            )

            current_config_mtime = _get_file_mtime(
                CONFIG_PATH
            )

            if current_db_mtime != _last_db_mtime:

                _last_db_mtime = current_db_mtime

                schedule_sync()

            if (
                current_config_mtime
                != _last_config_mtime
            ):

                _last_config_mtime = (
                    current_config_mtime
                )

                schedule_sync()

        except asyncio.CancelledError:
            raise

        except Exception as e:

            print(
                f"Remote watcher error: {e}"
            )

            await asyncio.sleep(5)


def start_file_watcher():
    global _watcher_task

    if not _storage_started:
        return

    if _watcher_task and not _watcher_task.done():
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    _watcher_task = loop.create_task(
        _watch_files_loop()
    )

    print(
        "Remote Storage file watcher started."
    )


async def restore_database_from_remote():
    if not _storage_started:
        return False

    if not _storage_app:
        return False

    message = await _find_latest_message(
        "CAFE_HERMES_DATABASE"
    )

    if not message:

        print(
            "Remote Storage: "
            "no database snapshot found."
        )

        return False

    os.makedirs(
        "data",
        exist_ok=True
    )

    temp_path = (
        "data/.remote_restore.db"
    )

    try:

        await _storage_app.download_media(
            message,
            file_name=temp_path
        )

        if not os.path.exists(temp_path):

            print(
                "Remote database download failed."
            )

            return False

        if os.path.exists(DB_PATH):

            local_backup = (
                "data/cafe_hermes_before_restore.db"
            )

            try:

                os.replace(
                    DB_PATH,
                    local_backup
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

    if not _storage_app:
        return False

    message = await _find_latest_message(
        "CAFE_HERMES_CONFIG"
    )

    if not message:

        print(
            "Remote Storage: "
            "no config snapshot found."
        )

        return False

    os.makedirs(
        "data",
        exist_ok=True
    )

    temp_path = (
        "data/.remote_config.json"
    )

    try:

        await _storage_app.download_media(
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

            restored = json.load(f)

        if not isinstance(restored, dict):
            return False

        with open(
            CONFIG_PATH,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                restored,
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

    db_restored = (
        await restore_database_from_remote()
    )

    config_restored = (
        await restore_config_from_remote()
    )

    if db_restored or config_restored:

        print(
            "Remote Storage: "
            "remote state restored."
        )

        return True

    print(
        "Remote Storage: "
        "nothing to restore."
    )

    return False
