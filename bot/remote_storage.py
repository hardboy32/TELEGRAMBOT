import os
import json
import asyncio
import sqlite3
import zipfile
import shutil
from datetime import datetime

import aiohttp


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"

# Primary/current storage channel = user data.
STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")

# Dedicated channels:
# - STORAGE_CHAT_ID = database/user/business data
# - STORAGE_CONFIG_CHAT_ID = bot configuration/settings
# - STORAGE_FILES_CHAT_ID = tutorials, installers, videos, receipts and other media
STORAGE_CONFIG_CHAT_ID = os.getenv(
    "STORAGE_CONFIG_CHAT_ID"
)

STORAGE_FILES_CHAT_ID = os.getenv(
    "STORAGE_FILES_CHAT_ID"
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_STATE_MARKER = "CAFE_HERMES_DB_STATE"
CONFIG_STATE_MARKER = "CAFE_HERMES_CONFIG_STATE"
LEGACY_STATE_MARKER = "CAFE_HERMES_STATE"

DB_ARCHIVE = "data/.remote_db_state.zip"
CONFIG_ARCHIVE = "data/.remote_config_state.zip"
LEGACY_ARCHIVE = "data/.remote_state.zip"

_storage_app = None
_storage_started = False

_storage_data_chat_id = None
_storage_config_chat_id = None
_storage_files_chat_id = None

_sync_task = None
_sync_lock = asyncio.Lock()

_dirty = False
_last_db_mtime = None
_last_config_mtime = None
_watcher_task = None

_db_state_message_id = None
_config_state_message_id = None


def storage_enabled():
    return bool(
        STORAGE_CHAT_ID
        and STORAGE_CONFIG_CHAT_ID
        and STORAGE_FILES_CHAT_ID
        and BOT_TOKEN
    )


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


async def _bot_api(method, data=None, multipart=None):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        if multipart is not None:
            request = session.post(url, data=multipart)
        else:
            request = session.post(url, json=data or {})

        async with request as response:
            payload = await response.json(content_type=None)

            if not payload.get("ok"):
                description = payload.get(
                    "description",
                    "Telegram API error"
                )
                raise RuntimeError(description)

            return payload.get("result")


async def _get_chat_info(chat_id):
    try:
        target_id = int(chat_id)
    except (TypeError, ValueError):
        raise RuntimeError(
            "Storage chat id is invalid."
        )

    chat = await _bot_api(
        "getChat",
        {
            "chat_id": target_id
        }
    )

    if not chat or chat.get("id") != target_id:
        raise RuntimeError(
            "Telegram returned a different storage chat."
        )

    return chat


async def start_storage(app):
    global _storage_app
    global _storage_started
    global _storage_data_chat_id
    global _storage_config_chat_id
    global _storage_files_chat_id

    _storage_app = app

    if not BOT_TOKEN:
        print(
            "Remote Storage: BOT_TOKEN is not configured."
        )
        return False

    if not STORAGE_CHAT_ID:
        print(
            "Remote Storage: STORAGE_CHAT_ID is not configured."
        )
        return False

    if not STORAGE_CONFIG_CHAT_ID:
        print(
            "Remote Storage: STORAGE_CONFIG_CHAT_ID is not configured."
        )
        return False

    if not STORAGE_FILES_CHAT_ID:
        print(
            "Remote Storage: STORAGE_FILES_CHAT_ID is not configured."
        )
        return False

    try:
        print(
            "Remote Storage: resolving storage channels automatically..."
        )

        data_chat = await _get_chat_info(
            STORAGE_CHAT_ID
        )

        config_chat = await _get_chat_info(
            STORAGE_CONFIG_CHAT_ID
        )

        files_chat = await _get_chat_info(
            STORAGE_FILES_CHAT_ID
        )

        channel_ids = {
            data_chat["id"],
            config_chat["id"],
            files_chat["id"]
        }

        if len(channel_ids) != 3:
            raise RuntimeError(
                "Storage channels must be three different private channels."
            )

        _storage_data_chat_id = data_chat["id"]
        _storage_config_chat_id = config_chat["id"]
        _storage_files_chat_id = files_chat["id"]

        _storage_started = True

        print(
            "Remote Storage: data channel connected: "
            f"{_storage_data_chat_id}"
        )
        print(
            "Remote Storage: config channel connected: "
            f"{_storage_config_chat_id}"
        )
        print(
            "Remote Storage: files channel connected: "
            f"{_storage_files_chat_id}"
        )

        return True

    except Exception as e:
        _storage_started = False

        print(
            f"Remote Storage connection error: {e}"
        )
        print(
            "Remote Storage: make sure the bot is a member/admin "
            "of all configured storage channels."
        )

        return False


async def stop_storage():
    global _storage_app
    global _storage_started
    global _storage_data_chat_id
    global _storage_config_chat_id
    global _storage_files_chat_id
    global _sync_task
    global _watcher_task
    global _dirty
    global _db_state_message_id
    global _config_state_message_id

    for task_name in (
        "_watcher_task",
        "_sync_task"
    ):
        task = globals().get(task_name)

        if task:
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    _watcher_task = None
    _sync_task = None
    _storage_app = None
    _storage_data_chat_id = None
    _storage_config_chat_id = None
    _storage_files_chat_id = None
    _storage_started = False
    _dirty = False
    _db_state_message_id = None
    _config_state_message_id = None


def _data_chat_id():
    if _storage_data_chat_id is not None:
        return _storage_data_chat_id

    return int(STORAGE_CHAT_ID)


def _config_chat_id():
    if _storage_config_chat_id is not None:
        return _storage_config_chat_id

    return int(STORAGE_CONFIG_CHAT_ID)


def _files_chat_id():
    if _storage_files_chat_id is not None:
        return _storage_files_chat_id

    return int(STORAGE_FILES_CHAT_ID)


def _sanitized_config():
    if not os.path.exists(CONFIG_PATH):
        return None

    try:
        with open(
            CONFIG_PATH,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return None

        for key in (
            "api_id",
            "api_hash",
            "bot_token"
        ):
            data.pop(key, None)

        return data

    except Exception as e:
        print(
            f"Remote config snapshot error: {e}"
        )
        return None


def _create_db_archive():
    if not os.path.exists(DB_PATH):
        return None

    os.makedirs(
        "data",
        exist_ok=True
    )

    snapshot_path = (
        "data/.remote_database_snapshot.db"
    )

    try:
        if os.path.exists(DB_ARCHIVE):
            os.remove(DB_ARCHIVE)

        source = sqlite3.connect(DB_PATH)
        destination = sqlite3.connect(snapshot_path)

        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        with zipfile.ZipFile(
            DB_ARCHIVE,
            "w",
            compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.write(
                snapshot_path,
                arcname="cafe_hermes.db"
            )

        return DB_ARCHIVE

    except Exception as e:
        print(
            f"Remote database archive error: {e}"
        )
        return None

    finally:
        try:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
        except Exception:
            pass


def _create_config_archive():
    config = _sanitized_config()

    if config is None:
        return None

    os.makedirs(
        "data",
        exist_ok=True
    )

    snapshot_path = (
        "data/.remote_config_snapshot.json"
    )

    try:
        if os.path.exists(CONFIG_ARCHIVE):
            os.remove(CONFIG_ARCHIVE)

        with open(
            snapshot_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                config,
                f,
                ensure_ascii=False,
                indent=2
            )

        with zipfile.ZipFile(
            CONFIG_ARCHIVE,
            "w",
            compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.write(
                snapshot_path,
                arcname="config.json"
            )

        return CONFIG_ARCHIVE

    except Exception as e:
        print(
            f"Remote config archive error: {e}"
        )
        return None

    finally:
        try:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
        except Exception:
            pass


def _cleanup_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


async def _get_state_message(
    chat_id,
    marker
):
    try:
        chat = await _get_chat_info(
            chat_id
        )
    except Exception as e:
        print(
            f"Remote Storage: state getChat failed: {e}"
        )
        return None

    pinned = (
        chat.get("pinned_message")
        if isinstance(chat, dict)
        else None
    )

    if not pinned:
        return None

    caption = (
        pinned.get("caption")
        or pinned.get("text")
        or ""
    )

    if not caption.startswith(marker):
        return None

    message_id = (
        pinned.get("message_id")
        or pinned.get("id")
    )

    if not message_id:
        return None

    return pinned


async def _send_document(
    chat_id,
    archive_path,
    caption
):
    form = aiohttp.FormData()

    form.add_field(
        "chat_id",
        str(chat_id)
    )
    form.add_field(
        "caption",
        caption
    )

    with open(
        archive_path,
        "rb"
    ) as document:
        form.add_field(
            "document",
            document,
            filename=os.path.basename(
                archive_path
            ),
            content_type="application/zip"
        )

        return await _bot_api(
            "sendDocument",
            multipart=form
        )


async def _edit_document(
    chat_id,
    message_id,
    archive_path,
    caption
):
    form = aiohttp.FormData()

    form.add_field(
        "chat_id",
        str(chat_id)
    )
    form.add_field(
        "message_id",
        str(message_id)
    )
    form.add_field(
        "media",
        json.dumps(
            {
                "type": "document",
                "media": "attach://statefile",
                "caption": caption
            }
        )
    )

    with open(
        archive_path,
        "rb"
    ) as document:
        form.add_field(
            "statefile",
            document,
            filename=os.path.basename(
                archive_path
            ),
            content_type="application/zip"
        )

        return await _bot_api(
            "editMessageMedia",
            multipart=form
        )


async def _pin_message(
    chat_id,
    message_id
):
    return await _bot_api(
        "pinChatMessage",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "disable_notification": True
        }
    )


async def _create_or_replace_channel_state(
    chat_id,
    marker,
    label,
    archive_path,
    state_message_id=None
):
    existing = await _get_state_message(
        chat_id,
        marker
    )

    caption = (
        f"{marker}\n"
        f"Contains: {label}\n"
        f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    if existing:
        existing_id = (
            existing.get("message_id")
            or existing.get("id")
        )

        try:
            edited = await _edit_document(
                chat_id,
                existing_id,
                archive_path,
                caption
            )

            return (
                edited.get("message_id")
                if isinstance(edited, dict)
                else existing_id
            )

        except Exception as e:
            print(
                f"Remote Storage: state edit failed: {e}"
            )

    sent = await _send_document(
        chat_id,
        archive_path,
        caption
    )

    if not sent:
        raise RuntimeError(
            "Telegram did not return the uploaded state message."
        )

    message_id = (
        sent.get("message_id")
        or sent.get("id")
    )

    try:
        await _pin_message(
            chat_id,
            message_id
        )
    except Exception as e:
        print(
            f"Remote Storage: pin failed: {e}"
        )

    return message_id


async def sync_all(force=False):
    global _dirty
    global _db_state_message_id
    global _config_state_message_id

    if not _storage_started:
        return False

    async with _sync_lock:
        if not force and not _dirty:
            return True

        _dirty = False

        print(
            "Remote Storage: sync started."
        )

        db_archive = _create_db_archive()
        config_archive = _create_config_archive()

        if not db_archive or not config_archive:
            _dirty = True

            print(
                "Remote Storage: sync failed while creating archives."
            )

            return False

        try:
            _db_state_message_id = (
                await _create_or_replace_channel_state(
                    _data_chat_id(),
                    DB_STATE_MARKER,
                    "database / users / orders / subscriptions / services / coupons",
                    db_archive,
                    _db_state_message_id
                )
            )

            _config_state_message_id = (
                await _create_or_replace_channel_state(
                    _config_chat_id(),
                    CONFIG_STATE_MARKER,
                    "bot settings and configuration",
                    config_archive,
                    _config_state_message_id
                )
            )

            print(
                "Remote Storage: sync completed."
            )

            return True

        except Exception as e:
            _dirty = True

            print(
                f"Remote Storage: sync failed: {e}"
            )

            return False

        finally:
            _cleanup_file(db_archive)
            _cleanup_file(config_archive)


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

    if (
        _sync_task
        and not _sync_task.done()
    ):
        return

    _sync_task = loop.create_task(
        _sync_worker()
    )


async def _sync_worker():
    global _sync_task
    global _dirty

    try:
        await asyncio.sleep(1.5)

        while (
            _storage_started
            and _dirty
        ):
            await sync_all(
                force=False
            )

            if _dirty:
                await asyncio.sleep(2)

    except asyncio.CancelledError:
        raise

    except Exception as e:
        print(
            f"Remote sync worker error: {e}"
        )

    finally:
        _sync_task = None


async def _watch_files():
    global _last_db_mtime
    global _last_config_mtime

    _last_db_mtime = _mtime(
        DB_PATH
    )
    _last_config_mtime = _mtime(
        CONFIG_PATH
    )

    while _storage_started:
        try:
            await asyncio.sleep(3)

            db_mtime = _mtime(
                DB_PATH
            )
            config_mtime = _mtime(
                CONFIG_PATH
            )

            if db_mtime != _last_db_mtime:
                _last_db_mtime = db_mtime
                schedule_sync()

            if config_mtime != _last_config_mtime:
                _last_config_mtime = config_mtime
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

    if (
        _watcher_task
        and not _watcher_task.done()
    ):
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    _watcher_task = loop.create_task(
        _watch_files()
    )

    print(
        "Remote Storage watcher started."
    )


async def _download_document(
    message,
    destination
):
    document = (
        message.get("document")
        if isinstance(message, dict)
        else None
    )

    if not document:
        raise RuntimeError(
            "Remote state message has no document."
        )

    file_id = document.get("file_id")

    if not file_id:
        raise RuntimeError(
            "Remote state file_id is missing."
        )

    file_info = await _bot_api(
        "getFile",
        {
            "file_id": file_id
        }
    )

    file_path = (
        file_info.get("file_path")
        if file_info
        else None
    )

    if not file_path:
        raise RuntimeError(
            "Telegram did not return a file path."
        )

    url = (
        f"https://api.telegram.org/file/"
        f"bot{BOT_TOKEN}/{file_path}"
    )

    timeout = aiohttp.ClientTimeout(
        total=180
    )

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:
        async with session.get(
            url
        ) as response:
            if response.status != 200:
                raise RuntimeError(
                    "Telegram file download failed "
                    f"with HTTP {response.status}."
                )

            with open(
                destination,
                "wb"
            ) as output:
                while True:
                    chunk = await response.content.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    output.write(chunk)


async def _restore_archive(
    message,
    expected_name,
    extract_root
):
    temp_archive = os.path.join(
        "data",
        ".remote_restore_tmp.zip"
    )

    _cleanup_file(
        temp_archive
    )

    await _download_document(
        message,
        temp_archive
    )

    if not os.path.exists(
        temp_archive
    ):
        raise RuntimeError(
            "Remote archive download failed."
        )

    try:
        _cleanup_extract_root(
            extract_root
        )

        os.makedirs(
            extract_root,
            exist_ok=True
        )

        with zipfile.ZipFile(
            temp_archive,
            "r"
        ) as archive:
            names = set(
                archive.namelist()
            )

            if expected_name not in names:
                raise RuntimeError(
                    "Remote archive is incomplete."
                )

            archive.extract(
                expected_name,
                extract_root
            )

    finally:
        _cleanup_file(
            temp_archive
        )


def _cleanup_extract_root(
    extract_root
):
    try:
        shutil.rmtree(
            extract_root,
            ignore_errors=True
        )
    except Exception:
        pass


async def _restore_database_from_message(
    message
):
    extract_root = (
        "data/.remote_db_restore"
    )

    await _restore_archive(
        message,
        "cafe_hermes.db",
        extract_root
    )

    extracted_db = os.path.join(
        extract_root,
        "cafe_hermes.db"
    )

    if not os.path.exists(
        extracted_db
    ):
        raise RuntimeError(
            "Restored database is missing."
        )

    if os.path.exists(
        DB_PATH
    ):
        try:
            os.replace(
                DB_PATH,
                "data/cafe_hermes_before_restore.db"
            )
        except Exception:
            pass

    os.replace(
        extracted_db,
        DB_PATH
    )

    _cleanup_extract_root(
        extract_root
    )


async def _restore_config_from_message(
    message
):
    extract_root = (
        "data/.remote_config_restore"
    )

    await _restore_archive(
        message,
        "config.json",
        extract_root
    )

    extracted_config = os.path.join(
        extract_root,
        "config.json"
    )

    if not os.path.exists(
        extracted_config
    ):
        raise RuntimeError(
            "Restored config is missing."
        )

    with open(
        extracted_config,
        "r",
        encoding="utf-8"
    ) as f:
        restored_config = json.load(f)

    if not isinstance(
        restored_config,
        dict
    ):
        raise RuntimeError(
            "Restored config is invalid."
        )

    os.replace(
        extracted_config,
        CONFIG_PATH
    )

    _cleanup_extract_root(
        extract_root
    )


async def _restore_legacy_combined_state():
    legacy_message = await _get_state_message(
        _data_chat_id(),
        LEGACY_STATE_MARKER
    )

    if not legacy_message:
        return False

    extract_root = (
        "data/.remote_legacy_restore"
    )

    await _restore_archive(
        legacy_message,
        "cafe_hermes.db",
        extract_root
    )

    # Re-open the archive once to restore both files from the same legacy zip.
    temp_archive = (
        "data/.remote_legacy_restore.zip"
    )

    await _download_document(
        legacy_message,
        temp_archive
    )

    try:
        with zipfile.ZipFile(
            temp_archive,
            "r"
        ) as archive:
            names = set(
                archive.namelist()
            )

            if {
                "cafe_hermes.db",
                "config.json"
            }.issubset(names):
                legacy_root = (
                    "data/.remote_legacy_restore_full"
                )

                _cleanup_extract_root(
                    legacy_root
                )

                os.makedirs(
                    legacy_root,
                    exist_ok=True
                )

                archive.extract(
                    "cafe_hermes.db",
                    legacy_root
                )
                archive.extract(
                    "config.json",
                    legacy_root
                )

                legacy_db = os.path.join(
                    legacy_root,
                    "cafe_hermes.db"
                )

                legacy_config = os.path.join(
                    legacy_root,
                    "config.json"
                )

                if os.path.exists(
                    DB_PATH
                ):
                    try:
                        os.replace(
                            DB_PATH,
                            "data/cafe_hermes_before_restore.db"
                        )
                    except Exception:
                        pass

                os.replace(
                    legacy_db,
                    DB_PATH
                )

                os.replace(
                    legacy_config,
                    CONFIG_PATH
                )

                _cleanup_extract_root(
                    legacy_root
                )

                return True

    finally:
        _cleanup_file(
            temp_archive
        )
        _cleanup_extract_root(
            extract_root
        )

    return False


async def restore_from_remote():
    if not _storage_started:
        return False

    print(
        "Remote Storage: checking remote state..."
    )

    restored_any = False

    try:
        db_message = await _get_state_message(
            _data_chat_id(),
            DB_STATE_MARKER
        )

        config_message = await _get_state_message(
            _config_chat_id(),
            CONFIG_STATE_MARKER
        )

        if db_message:
            try:
                await _restore_database_from_message(
                    db_message
                )
                restored_any = True
                print(
                    "Remote Storage: database restored."
                )
            except Exception as e:
                print(
                    f"Remote database restore error: {e}"
                )

        if config_message:
            try:
                await _restore_config_from_message(
                    config_message
                )
                restored_any = True
                print(
                    "Remote Storage: configuration restored."
                )
            except Exception as e:
                print(
                    f"Remote config restore error: {e}"
                )

        if restored_any:
            print(
                "Remote state restored successfully."
            )
            return True

        legacy_restored = (
            await _restore_legacy_combined_state()
        )

        if legacy_restored:
            print(
                "Remote state restored successfully "
                "from legacy combined backup."
            )
            return True

        print(
            "Remote Storage: no remote state backup found."
        )
        return False

    except Exception as e:
        print(
            f"Remote state restore error: {e}"
        )
        return False


async def store_media_message(message):
    """Copy a durable media message into the dedicated files channel.

    Returns the file_id of the copied media and the copied message metadata.
    Used for tutorial files/videos and payment receipts.
    """

    if not _storage_started:
        return None

    if not message or not getattr(
        message,
        "chat",
        None
    ):
        return None

    try:
        result = await _bot_api(
            "copyMessage",
            {
                "chat_id": _files_chat_id(),
                "from_chat_id": message.chat.id,
                "message_id": message.id
            }
        )

        if not isinstance(
            result,
            dict
        ):
            return None

        copied_message_id = (
            result.get("message_id")
            or result.get("id")
        )

        document = result.get(
            "document"
        )

        video = result.get(
            "video"
        )

        animation = result.get(
            "animation"
        )

        photo = result.get(
            "photo"
        )

        file_id = None

        if document:
            file_id = document.get(
                "file_id"
            )

        elif video:
            file_id = video.get(
                "file_id"
            )

        elif animation:
            file_id = animation.get(
                "file_id"
            )

        elif photo and isinstance(
            photo,
            list
        ):
            if photo:
                file_id = photo[-1].get(
                    "file_id"
                )

        if not file_id:
            # copyMessage returns the full message object for supported media.
            # Keep message_id so future file recovery can still be traced.
            print(
                "Remote Storage: media copied but no file_id was returned."
            )

        else:
            print(
                "Remote Storage: media copied to files channel."
            )

        return {
            "message_id": copied_message_id,
            "file_id": file_id
        }

    except Exception as e:
        print(
            f"Remote Storage: media copy failed: {e}"
        )
        return None
