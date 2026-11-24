"""Защита базы: копии уходят в Telegram, а если хостинг стёр файл - бот сам восстанавливает последнюю копию."""
import asyncio
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone, timedelta
from urllib.request import pathname2url

from aiogram.types import FSInputFile

MSK = timezone(timedelta(hours=3))
BACKUP_PREFIX = "shop_backup_"
REF_LANG = "eo"            # служебный язык: описание на нём обычные пользователи не видят
REF_PREFIX = "dbref1|"
CHECK_EVERY = 300          # проверяем базу раз в 5 минут
QUICK_GAP = 900            # после новых заказов/отзывов копия не чаще раза в 15 минут
FULL_GAP = 6 * 3600        # всем админам - не реже раза в 6 часов, если что-то менялось


_LAST = {}   # последняя отправленная копия: chat, msg, n


def _run(fn, *args):
    return asyncio.get_running_loop().run_in_executor(None, fn, *args)


def _open_ro(path):
    return sqlite3.connect("file:" + pathname2url(os.path.abspath(path)) + "?mode=ro", uri=True)


def counts(path):
    """Счётчики из файла базы или None, если файла или таблиц нет."""
    if not path or not os.path.exists(path):
        return None
    try:
        con = _open_ro(path)
    except Exception:
        return None
    try:
        def one(q):
            return con.execute(q).fetchone()[0]
        return {
            "users": one("SELECT COUNT(*) FROM users"),
            "orders": one("SELECT COUNT(*) FROM orders"),
            "completed": one("SELECT COUNT(*) FROM orders WHERE status = 'completed'"),
            "confirmed": one("SELECT COUNT(*) FROM orders WHERE status = 'confirmed'"),
            "reviews": one("SELECT COUNT(*) FROM reviews"),
            "products": one("SELECT COUNT(*) FROM products"),
        }
    except Exception:
        return None
    finally:
        con.close()


def is_empty(path):
    c = counts(path)
    return c is None or (c["users"] == 0 and c["orders"] == 0)


def signature(path):
    c = counts(path)
    if not c:
        return None
    return (c["users"], c["orders"], c["completed"], c["confirmed"], c["reviews"], c["products"])


def make_copy(src_path, dst_path):
    src = sqlite3.connect(src_path)
    out = sqlite3.connect(dst_path)
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()


def check_backup(path):
    """Файл - целая база магазина? Возвращает счётчики или None."""
    c = counts(path)
    if not c:
        return None
    try:
        con = _open_ro(path)
        try:
            ok = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            con.close()
    except Exception:
        return None
    return c if ok else None


def adopt_legacy_db(db_path, legacy="shop.db"):
    """База переехала на постоянный диск, а старый shop.db лежит рядом с ботом - переносим его."""
    try:
        if os.path.abspath(db_path) == os.path.abspath(legacy):
            return False
        if os.path.exists(db_path) or not os.path.exists(legacy):
            return False
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        make_copy(legacy, db_path)
        logging.info("старая база %s перенесена в %s", legacy, db_path)
        return True
    except Exception:
        logging.exception("не получилось перенести старую базу")
        return False


# ---------- ссылка на последнюю копию (хранится в Telegram, переживает стирание файлов) ----------

async def save_ref(bot, chat_id, message_id, file_id):
    ref = f"{REF_PREFIX}{chat_id}|{message_id}|{int(time.time())}|{file_id}"
    try:
        await bot.set_my_description(description=ref, language_code=REF_LANG)
        return True
    except Exception:
        logging.exception("не удалось запомнить ссылку на копию базы в описании бота")
    try:
        await bot.pin_chat_message(chat_id, message_id, disable_notification=True)
        return True
    except Exception:
        logging.exception("не удалось закрепить копию базы")
    return False


def _parse_ref(text):
    if not text or not text.startswith(REF_PREFIX):
        return None
    parts = text[len(REF_PREFIX):].split("|", 3)
    if len(parts) != 4:
        return None
    try:
        return {"chat_id": int(parts[0]), "message_id": int(parts[1]), "ts": int(parts[2]), "file_id": parts[3]}
    except ValueError:
        return None


async def load_refs(bot, admin_ids):
    """Где может лежать ссылка на копию: описание бота и закреплённые сообщения у админов. Новые первыми."""
    refs = []
    try:
        d = await bot.get_my_description(language_code=REF_LANG)
        r = _parse_ref(getattr(d, "description", None))
        if r:
            refs.append(r)
    except Exception:
        logging.exception("не удалось прочитать описание бота")
    for admin_id in admin_ids:
        try:
            chat = await bot.get_chat(admin_id)
            pm = getattr(chat, "pinned_message", None)
            doc = getattr(pm, "document", None) if pm else None
            if doc and (doc.file_name or "").startswith(BACKUP_PREFIX):
                ts = int(pm.date.timestamp()) if getattr(pm, "date", None) else 0
                refs.append({"chat_id": admin_id, "message_id": pm.message_id, "ts": ts, "file_id": doc.file_id})
        except Exception:
            pass
    refs.sort(key=lambda r: r["ts"], reverse=True)
    return refs


SEED_FILE = "seed_shop.db"


def restore_from_seed(db_path, seed=SEED_FILE):
    """Если рядом с ботом лежит seed_shop.db и база пустая - берём данные из него (непустую базу не трогаем)."""
    try:
        if not os.path.exists(seed):
            return None
        c = check_backup(seed)
        if not c or (c["users"] == 0 and c["orders"] == 0):
            return None
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        part = db_path + ".restoring"
        shutil.copyfile(seed, part)
        os.replace(part, db_path)
        logging.info("база восстановлена из %s: %s", seed, c)
        return {**c, "ts": int(os.path.getmtime(seed))}
    except Exception:
        logging.exception("не получилось взять базу из %s", seed)
        return None


async def restore_if_empty(bot, db_path, admin_ids):
    """Если база пустая (хостинг стёр файл), достаём последнюю копию из Telegram.
    Непустую базу не трогаем никогда. Возвращает счётчики восстановленной базы или None."""
    if os.getenv("NO_DB_RESTORE") == "1":
        return None
    if not await _run(is_empty, db_path):
        return None
    seed = await _run(restore_from_seed, db_path)
    if seed:
        return seed
    refs = await load_refs(bot, admin_ids)
    if not refs:
        logging.info("копии базы в Telegram пока нет, восстанавливать нечего")
        return None
    for ref in refs:
        tmp = os.path.join(tempfile.gettempdir(), f"restore_{int(time.time())}.db")
        try:
            await bot.download(ref["file_id"], destination=tmp)
            c = await _run(check_backup, tmp)
            if not c or (c["users"] == 0 and c["orders"] == 0):
                continue
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            part = db_path + ".restoring"
            shutil.copyfile(tmp, part)
            os.replace(part, db_path)
            logging.info("база восстановлена из копии Telegram: %s", c)
            return {**c, "ts": ref["ts"]}
        except Exception:
            logging.exception("не получилось восстановить базу из копии")
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
    return None


# ---------- отправка копий ----------

async def send_backup(bot, db_path, admin_ids, reason, *, everyone=True, silent=True,
                      set_ref=True, allow_empty=False):
    """Шлёт копию базы админам. True, если хоть кому-то ушло.
    Пустую базу не сохраняем, чтобы не затереть хорошую копию."""
    c = await _run(counts, db_path)
    if not allow_empty and (not c or (c["users"] == 0 and c["orders"] == 0)):
        return False
    stamp = datetime.now(MSK).strftime("%Y-%m-%d_%H-%M")
    tmp = os.path.join(tempfile.gettempdir(), f"{BACKUP_PREFIX}{stamp}.db")
    await _run(make_copy, db_path, tmp)
    users = c["users"] if c else 0
    orders = c["orders"] if c else 0
    caption = (f"💾 {reason}\nПользователей: {users}, заказов: {orders}\n"
               "Сохрани этот файл - это копия всей базы.")
    file_id = None
    sent_any = False
    try:
        for admin_id in admin_ids:
            try:
                doc = file_id or FSInputFile(tmp, filename=os.path.basename(tmp))
                msg = await bot.send_document(admin_id, doc, caption=caption, disable_notification=silent)
            except Exception:
                logging.exception("копия базы не ушла админу %s", admin_id)
                continue
            if file_id is None:
                file_id = msg.document.file_id
                if set_ref:
                    await save_ref(bot, admin_id, msg.message_id, file_id)
                    prev = _LAST.get("prev")
                    now_n = users + orders
                    # старую копию удаляем, чтобы чат не засорялся (только если новая не меньше по данным)
                    if prev and prev[0] == admin_id and now_n >= prev[2]:
                        try:
                            await bot.delete_message(chat_id=prev[0], message_id=prev[1])
                        except Exception:
                            pass
                    _LAST["prev"] = (admin_id, msg.message_id, now_n)
            sent_any = True
            if not everyone:
                break
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return sent_any


async def backup_loop(bot, db_path, admin_ids):
    """Первая копия сразу после запуска, потом после новых заказов/отзывов и раз в 6 часов."""
    await asyncio.sleep(90)
    last_sig = None
    last_time = 0.0
    while True:
        try:
            sig = await _run(signature, db_path)
            if sig and (sig[0] + sig[1]) > 0:
                now = time.time()
                mode = None
                if last_sig is None:
                    mode, reason = "first", "Копия базы после запуска бота"
                elif sig[1:] != last_sig[1:] and now - last_time >= QUICK_GAP:
                    mode, reason = "first", "Копия базы"
                elif sig != last_sig and now - last_time >= FULL_GAP:
                    mode, reason = "first", "Автокопия базы"
                if mode:
                    ok = await send_backup(bot, db_path, admin_ids, reason, everyone=False)
                    if ok:
                        last_sig, last_time = sig, now
        except Exception:
            logging.exception("auto backup failed")
        await asyncio.sleep(CHECK_EVERY)
