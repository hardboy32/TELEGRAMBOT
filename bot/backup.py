import os
import zipfile
import sqlite3
import shutil
import tempfile
from datetime import datetime

from bot.helpers import save_config, apply_restored_config
from bot.database import init_db


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"
BACKUP_DIR = "data/backups"

ALLOWED_NAMES = {
    "cafe_hermes.db",
    "config.json",
    "data/cafe_hermes.db"
}

MAX_UNCOMPRESSED = 40 * 1024 * 1024


def _ensure_dirs():
    os.makedirs("data", exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_backup(config=None):
    _ensure_dirs()

    if config is not None:
        save_config(config, CONFIG_PATH)

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    zip_path = os.path.join(
        BACKUP_DIR,
        f"cafe_hermes_backup_{stamp}.zip"
    )

    snap_path = os.path.join(
        BACKUP_DIR,
        f"_snap_{stamp}.db"
    )

    if os.path.exists(DB_PATH):
        source = sqlite3.connect(DB_PATH)
        snapshot = sqlite3.connect(snap_path)
        source.backup(snapshot)
        snapshot.close()
        source.close()

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zf:

        if os.path.exists(snap_path):
            zf.write(
                snap_path,
                "cafe_hermes.db"
            )

        if os.path.exists(CONFIG_PATH):
            zf.write(
                CONFIG_PATH,
                "config.json"
            )

    if os.path.exists(snap_path):
        os.remove(snap_path)

    return zip_path


def _extract_member(zf, names, dest_dir, target):
    for name in names:
        base = os.path.basename(name)

        if base == target or name == target:
            zf.extract(name, dest_dir)

            extracted = os.path.join(dest_dir, name)

            final_path = os.path.join(dest_dir, target)

            if extracted != final_path:
                os.makedirs(
                    os.path.dirname(final_path),
                    exist_ok=True
                )
                shutil.move(extracted, final_path)

            return final_path

    return None


def inspect_backup(zip_path):
    if not zip_path or not os.path.exists(zip_path):
        return {
            "ok": False,
            "message": "فایل بکاپ پیدا نشد."
        }

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:

            names = zf.namelist()

            total = 0

            for info in zf.infolist():
                name = info.filename.replace("\\", "/")

                if name.endswith("/"):
                    continue

                base = os.path.basename(name)

                if (
                    name not in ALLOWED_NAMES
                    and base not in ALLOWED_NAMES
                ):
                    return {
                        "ok": False,
                        "message": "این فایل بکاپ معتبر نیست."
                    }

                total += info.file_size

                if total > MAX_UNCOMPRESSED:
                    return {
                        "ok": False,
                        "message": "حجم بکاپ بیش از حد مجاز است."
                    }

            has_db = any(
                os.path.basename(n) == "cafe_hermes.db"
                or n == "data/cafe_hermes.db"
                for n in names
            )

            if not has_db:
                return {
                    "ok": False,
                    "message": "دیتابیس داخل بکاپ نیست."
                }

            tmp = tempfile.mkdtemp(dir=BACKUP_DIR)

            try:
                db_file = _extract_member(
                    zf,
                    names,
                    tmp,
                    "cafe_hermes.db"
                )

                conn = sqlite3.connect(db_file)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                tables = [
                    row["name"]
                    for row in cur.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table'"
                    ).fetchall()
                ]

                if "users" not in tables:
                    conn.close()
                    return {
                        "ok": False,
                        "message": "ساختار دیتابیس بکاپ نامعتبر است."
                    }

                def count(table):
                    if table not in tables:
                        return 0

                    row = cur.execute(
                        f"SELECT COUNT(*) AS c FROM {table}"
                    ).fetchone()

                    return row["c"]

                info = {
                    "ok": True,
                    "users": count("users"),
                    "orders": count("orders"),
                    "services": count("services"),
                    "subscriptions": count("subscriptions"),
                    "has_config": any(
                        os.path.basename(n) == "config.json"
                        for n in names
                    )
                }

                conn.close()

                return info

            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    except zipfile.BadZipFile:
        return {
            "ok": False,
            "message": "فایل زیپ خراب است."
        }

    except Exception as e:
        return {
            "ok": False,
            "message": f"خطا در بررسی بکاپ: {e}"
        }


def restore_backup(zip_path, config):
    info = inspect_backup(zip_path)

    if not info.get("ok"):
        return info

    _ensure_dirs()

    tmp = tempfile.mkdtemp(dir=BACKUP_DIR)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            db_file = _extract_member(
                zf,
                names,
                tmp,
                "cafe_hermes.db"
            )

            config_file = _extract_member(
                zf,
                names,
                tmp,
                "config.json"
            )

        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        if os.path.exists(DB_PATH):
            shutil.copy2(
                DB_PATH,
                os.path.join(
                    "data",
                    f"cafe_hermes.db.before_restore_{stamp}"
                )
            )

        shutil.copy2(db_file, DB_PATH)

        if config_file and os.path.exists(config_file):
            if os.path.exists(CONFIG_PATH):
                shutil.copy2(
                    CONFIG_PATH,
                    f"config.json.before_restore_{stamp}"
                )

            shutil.copy2(config_file, CONFIG_PATH)
            apply_restored_config(config, CONFIG_PATH)

        init_db()

        info["ok"] = True
        info["message"] = "بکاپ با موفقیت بازگردانی شد."

        return info

    except Exception as e:
        return {
            "ok": False,
            "message": f"خطا در بازگردانی: {e}"
        }

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
