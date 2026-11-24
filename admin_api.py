"""Админ-API мини-приложения. Работает с той же базой, что и бот, поэтому всё, что админ меняет
в мини-аппе (товары, разделы, промокоды, выдача заказов), сразу видно в боте и наоборот.
Доступ только у админов: проверка по подписи Telegram (initData), а не по скрытой кнопке на сайте."""
import logging
import re
import secrets

import aiosqlite
from aiohttp import web

import config
import database as db

_ctx = {}
_auth = None

PROMO_RE = re.compile(r"^[A-Z0-9_-]{2,20}$")
BASE_CATS = {c[0] for c in config.BASE_CATEGORIES}
GAMES = {"bs": "Brawl Stars", "clash": "Clash Royale", "coc": "Clash of Clans"}


def _bad(msg, status=400):
    return web.json_response({"ok": False, "error": msg}, status=status)


def _int(v, name, lo=None, hi=None):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"Поле «{name}»: нужно целое число")
    if lo is not None and n < lo or hi is not None and n > hi:
        raise ValueError(f"Поле «{name}»: допустимо от {lo} до {hi}")
    return n


def _text(v, name, maxlen, required=True):
    s = re.sub(r"\s+", " ", str(v or "")).strip()
    if required and not s:
        raise ValueError(f"Заполни поле «{name}»")
    if len(s) > maxlen:
        raise ValueError(f"Поле «{name}»: максимум {maxlen} символов")
    return s


# ---------- обзор ----------
async def a_overview(b, uid):
    st = await db.user_stats()
    return {"revenue": await db.total_revenue(), "orders": await db.order_count(),
            "queue": await db.queue_total(), "users": st}


# ---------- каталог ----------
async def a_catalog(b, uid):
    cats = await db.list_categories()
    async with aiosqlite.connect(db.DB_PATH) as c:
        cur = await c.execute(
            "SELECT product_id, name, description, price, stock, active, category FROM products "
            "ORDER BY sort_order ASC, product_id ASC")
        prods = await cur.fetchall()
    return {
        "games": [{"id": k, "name": v} for k, v in GAMES.items()],
        "cats": [{"key": k, "game": g, "name": n, "active": bool(a), "base": k in BASE_CATS}
                 for k, g, n, _so, a in cats],
        "prods": [{"id": p[0], "name": p[1], "desc": p[2] or "", "price": p[3], "stock": p[4],
                   "active": bool(p[5]), "cat": p[6]} for p in prods],
    }


async def a_product_save(b, uid):
    name = _text(b.get("name"), "Название", 60)
    desc = _text(b.get("desc"), "Описание", 200, required=False)
    price = _int(b.get("price"), "Цена", 1, 1_000_000)
    stock = _int(b.get("stock", -1), "Остаток", -1, 1_000_000)
    cat = b.get("cat")
    if not cat or not await db.category_exists(cat):
        raise ValueError("Выбери раздел")
    pid = b.get("id")
    if pid:
        pid = _int(pid, "id", 1)
        if not await db.get_product(pid):
            raise ValueError("Товар не найден")
        for field, val in (("name", name), ("description", desc), ("price", price),
                           ("stock", stock), ("category", cat)):
            await db.update_product_field(pid, field, val)
    else:
        pid = await db.add_product(name, desc, price, stock=stock, category=cat)
    return {"id": pid}


async def a_product_toggle(b, uid):
    pid = _int(b.get("id"), "id", 1)
    p = await db.get_product(pid)
    if not p:
        raise ValueError("Товар не найден")
    await db.set_product_active(pid, not p[5])
    return {"active": not p[5]}


async def a_product_move(b, uid):
    d = "up" if b.get("dir") == "up" else "down"
    await db.move_product(_int(b.get("id"), "id", 1), d)
    return {}


async def a_category_save(b, uid):
    name = _text(b.get("name"), "Название раздела", 40)
    key = b.get("key")
    if key:
        if not await db.category_exists(key):
            raise ValueError("Раздел не найден")
        await db.rename_category(key, name)
        return {"key": key}
    game = b.get("game")
    if game not in GAMES:
        raise ValueError("Выбери игру")
    key = f"{game}_{secrets.token_hex(3)}"
    await db.add_category(key, game, name)
    return {"key": key}


async def a_category_toggle(b, uid):
    key = b.get("key")
    if not await db.category_exists(key):
        raise ValueError("Раздел не найден")
    await db.toggle_category(key)
    return {}


async def a_category_move(b, uid):
    await db.move_category(b.get("key"), "up" if b.get("dir") == "up" else "down")
    return {}


async def a_category_delete(b, uid):
    key = b.get("key")
    if key in BASE_CATS:
        raise ValueError("Базовый раздел нельзя удалить, его можно скрыть")
    if not await db.category_exists(key):
        raise ValueError("Раздел не найден")
    n = await db.delete_category(key)
    return {"detached": n}


# ---------- промокоды ----------
async def a_promo_list(b, uid):
    return {"promos": [{"code": c, "type": t, "value": v, "active": bool(a)}
                       for c, t, v, a in await db.list_promocodes()]}


async def a_promo_save(b, uid):
    code = str(b.get("code") or "").strip().upper()
    if not PROMO_RE.match(code):
        raise ValueError("Код: 2-20 символов, латиница, цифры, - и _")
    t = b.get("type")
    if t not in ("percent", "amount"):
        raise ValueError("Выбери тип скидки")
    v = _int(b.get("value"), "Размер скидки", 1, 100 if t == "percent" else 100000)
    await db.add_promocode(code, t, v)
    return {}


async def a_promo_toggle(b, uid):
    await db.toggle_promocode(str(b.get("code") or "").upper())
    return {}


async def a_promo_delete(b, uid):
    await db.delete_promocode(str(b.get("code") or "").upper())
    return {}


# ---------- заказы ----------
async def a_orders(b, uid):
    rows = await db.admin_orders(todo=bool(b.get("todo")), limit=40)
    return {"orders": [{"id": r[0], "name": r[1], "price": r[2], "status": r[3], "delivered": bool(r[4]),
                        "user": r[5], "username": r[6], "at": r[7]} for r in rows]}


async def a_deliver(b, uid):
    ok, msg = await _ctx["deliver_order"](_int(b.get("id"), "id", 1))
    if not ok:
        raise ValueError(msg)
    return {"msg": msg}


# ---------- объявление после оплаты ----------
async def a_notice_get(b, uid):
    return {"on": (await db.get_setting("post_pay_on", "1")) == "1",
            "text": await db.get_setting("post_pay_text") or "",
            "url": await db.get_setting("post_pay_url") or "",
            "default_text": config.POST_PAY_DEFAULT,
            "default_url": config.CHANNEL_URL or config.REVIEWS_URL}


async def a_notice_save(b, uid):
    text = _text(b.get("text"), "Текст объявления", 500, required=False)
    url = str(b.get("url") or "").strip()
    if url and (not re.match(r"^https://[^\s]{3,200}$", url)):
        raise ValueError("Ссылка должна начинаться с https://")
    await db.set_setting("post_pay_on", "1" if b.get("on") else "0")
    for key, val in (("post_pay_text", text), ("post_pay_url", url)):
        if val:
            await db.set_setting(key, val)
        else:
            await db.delete_setting(key)
    return {}


async def a_notice_test(b, uid):
    await _ctx["send_notice"](uid)
    return {"msg": "Отправил тебе в бот"}


# ---------- рассылка ----------
async def a_bcast_info(b, uid):
    return {"users": len(await db.all_user_ids()), "accounts": len(await db.account_user_ids()),
            "status": _ctx["broadcast_status"]()}


async def a_bcast_status(b, uid):
    return {"status": _ctx["broadcast_status"]()}


async def a_bcast_send(b, uid):
    text = _text(b.get("text"), "Текст", 3500)
    btn_text = _text(b.get("btn_text"), "Текст кнопки", 40, required=False)
    btn_url = str(b.get("btn_url") or "").strip()
    if btn_url and not re.match(r"^https://[^\s]{3,300}$", btn_url):
        raise ValueError("Ссылка кнопки должна начинаться с https://")
    if btn_url and not btn_text:
        raise ValueError("Укажи текст кнопки")
    audience = b.get("audience")
    if audience not in ("all", "reg", "me"):
        raise ValueError("Выбери, кому отправить")
    if not _ctx["broadcast_start"](audience, text, btn_text, btn_url, uid):
        raise ValueError("Рассылка уже идёт, дождись окончания")
    return {"started": True}


# ---------- чаты, люди, оплата ----------
async def a_chats(b, uid):
    rows = await db.chat_recent(40)
    return {"chats": [{"order": r[0], "from": r[1], "text": r[2][:120], "at": r[3], "name": r[4],
                       "status": r[5], "username": r[6], "user": r[7]} for r in rows]}


async def a_users(b, uid):
    st = await db.user_stats()
    q = str(b.get("q") or "").strip()[:64]
    found = None
    if q:
        r = await db.find_user(q)
        if r:
            found = {"id": r[0], "username": r[1]}
    return {"stats": st, "found": found, "searched": bool(q)}


async def a_pay_get(b, uid):
    return {"stars": (await db.get_setting("pay_stars_on", "1")) == "1"}


async def a_pay_toggle(b, uid):
    on = (await db.get_setting("pay_stars_on", "1")) == "1"
    await db.set_setting("pay_stars_on", "0" if on else "1")
    return {"stars": not on}


ACTIONS = {
    "bcast_info": a_bcast_info, "bcast_status": a_bcast_status, "bcast_send": a_bcast_send,
    "notice_get": a_notice_get, "notice_save": a_notice_save, "notice_test": a_notice_test,
    "overview": a_overview, "catalog": a_catalog,
    "product_save": a_product_save, "product_toggle": a_product_toggle, "product_move": a_product_move,
    "category_save": a_category_save, "category_toggle": a_category_toggle,
    "category_move": a_category_move, "category_delete": a_category_delete,
    "promo_list": a_promo_list, "promo_save": a_promo_save, "promo_toggle": a_promo_toggle,
    "promo_delete": a_promo_delete, "orders": a_orders, "deliver": a_deliver,
    "chats": a_chats, "users": a_users, "pay_get": a_pay_get, "pay_toggle": a_pay_toggle,
}


async def h_admin(request):
    a = _auth(request)
    if not a:
        return _bad("auth", 401)
    uid = a[0]
    if not _ctx["is_admin"](uid):  # проверка на сервере: скрытая кнопка сама по себе ничего не защищает
        return _bad("Только для админов", 403)
    fn = ACTIONS.get(request.match_info["action"])
    if not fn:
        return _bad("unknown action", 404)
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}
    try:
        data = await fn(body, uid)
    except ValueError as e:
        return _bad(str(e))
    except Exception:
        logging.exception("admin api failed: %s", request.match_info["action"])
        return _bad("Ошибка сервера", 500)
    return web.json_response({"ok": True, **data})


def setup(app, auth_user, ctx):
    global _auth
    _auth = auth_user
    _ctx.update(ctx)
    app.router.add_post("/api/admin/{action}", h_admin)
