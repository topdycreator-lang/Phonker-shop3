"""Веб-API магазина: сайт/мини-приложение оформляет заказ и платит СБП прямо на сайте.

Секреты Platega остаются на сервере. Пользователь определяется по подписи Telegram (initData мини-приложения)
либо по токену, который выдаётся после входа через бота (для обычного браузера).
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import time
from urllib.parse import parse_qsl

from aiohttp import web
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import config
import database as db
import platega
import admin_api

SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
MAX_QTY = 10
INIT_DATA_TTL = 3 * 24 * 3600
SESSION_TTL = 30 * 24 * 3600
LOGIN_TTL = 600

GAME_TO_SITE = {"bs": "bs", "clash": "cr", "coc": "coc"}
_EMOJI_LEAD = re.compile(r"^[^\w(]+", re.UNICODE)

_ctx = {}
_logins = {}      # login-токен -> {"uid": int|None, "exp": float}
_rate = {}        # user_id -> [время создания платежей]
_SESS_KEY = hashlib.sha256(("phonker-web:" + config.BOT_TOKEN).encode()).digest()


def clean_name(s):
    """Убираем эмодзи в начале названия: на сайте свои значки."""
    return _EMOJI_LEAD.sub("", s or "").strip() or (s or "")


# ---------- авторизация ----------
def check_init_data(init_data):
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        got = pairs.pop("hash", None)
        if not got:
            return None
        dcs = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        key = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(key, dcs.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got):
            return None
        if time.time() - int(pairs.get("auth_date", "0")) > INIT_DATA_TTL:
            return None
        user = json.loads(pairs.get("user", "{}"))
        return user if user.get("id") else None
    except Exception:
        return None


def make_session(uid):
    body = f"{uid}:{int(time.time()) + SESSION_TTL}"
    sig = hmac.new(_SESS_KEY, body.encode(), hashlib.sha256).hexdigest()[:40]
    return base64.urlsafe_b64encode(f"{body}:{sig}".encode()).decode()


def check_session(tok):
    try:
        uid, exp, sig = base64.urlsafe_b64decode(tok.encode()).decode().split(":")
        calc = hmac.new(_SESS_KEY, f"{uid}:{exp}".encode(), hashlib.sha256).hexdigest()[:40]
        if hmac.compare_digest(calc, sig) and int(exp) > time.time():
            return int(uid)
    except Exception:
        pass
    return None


def auth_user(request):
    """Возвращает (user_id, user_dict|None) или None."""
    h = request.headers.get("Authorization", "")
    if h.startswith("tma "):
        u = check_init_data(h[4:])
        if u:
            return u["id"], u
    elif h.startswith("Bearer "):
        uid = check_session(h[7:])
        if uid:
            return uid, None
    return None


def bad(msg, status=400, **extra):
    return web.json_response({"ok": False, "error": msg, **extra}, status=status)


async def user_card(uid, u=None):
    if u is None:
        try:
            chat = await _ctx["bot"].get_chat(uid)
            u = {"id": uid, "first_name": chat.first_name or "", "last_name": chat.last_name or "",
                 "username": chat.username}
        except Exception:
            u = {"id": uid, "first_name": "Пользователь"}
    return {"id": uid, "first_name": u.get("first_name", ""), "last_name": u.get("last_name", ""),
            "username": u.get("username"), "photo_url": u.get("photo_url")}


# ---------- middleware ----------
@web.middleware
async def cors(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            resp = e
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- каталог и настройки ----------
async def h_config(request):
    me = await _ctx["bot"].get_me()
    methods = [{"id": mid, "label": re.sub(r"^[^\w]+", "", label).strip() or label}
               for mid, label in platega.method_list()] if platega.enabled() else []
    if _ctx.get("invoice_link") and (await db.get_setting("pay_stars_on", "1")) == "1":
        methods.append({"id": "stars", "label": "Telegram Stars"})  # работает в любой стране
    return web.json_response({
        "ok": True,
        "bot": f"https://t.me/{me.username}",
        "bot_username": me.username,
        "methods": methods,
        "open": _ctx["is_open"](),
        "notice": {
            "on": (await db.get_setting("post_pay_on", "1")) == "1",
            "text": (await db.get_setting("post_pay_text")) or config.POST_PAY_DEFAULT,
            "url": (await db.get_setting("post_pay_url")) or config.CHANNEL_URL or config.REVIEWS_URL,
        },
    })


async def h_catalog(request):
    cats = await db.list_categories(active_only=True)
    out = {}
    for key, game, name, _so, _act in cats:
        site_game = GAME_TO_SITE.get(game)
        if not site_game:
            continue
        prods = await db.list_products(active_only=True, category=key)
        items = [[clean_name(p[1]), p[2] or "", p[3], p[0]] for p in prods if p[4] != 0]
        if items:
            out.setdefault(site_game, {})[clean_name(name)] = items
    return web.json_response({"ok": True, "catalog": out})


# ---------- профиль ----------
async def h_me(request):
    a = auth_user(request)
    if not a:
        return bad("auth", 401)
    uid, u = a
    acc = await db.account_get(uid)
    return web.json_response({"ok": True, "user": await user_card(uid, u), "is_admin": bool(_ctx["is_admin"](uid)),
                              "registered": bool(acc), "login": acc[1] if acc else None})


# ---------- аккаунт: логин, почта, пароль (привязываются к Telegram) ----------
LOGIN_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s.]{2,24}$")
_arate = {}   # ключ -> [время попыток]
_DUMMY = "s1$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def _hash_pw(pw, salt=None):
    salt = salt or os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "s1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def _check_pw(pw, stored):
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:
        return False


def _throttle(key, limit, window=300):
    now = time.time()
    hist = [t for t in _arate.get(key, []) if now - t < window]
    if len(_arate) > 5000:
        _arate.clear()
    if len(hist) >= limit:
        _arate[key] = hist
        return False
    hist.append(now)
    _arate[key] = hist
    return True


def _ip(request):
    return request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote or "?"


async def h_register(request):
    """Первый вход: логин + почта + пароль, аккаунт привязывается к Telegram-профилю."""
    a = auth_user(request)
    if not a:
        return bad("auth", 401)
    uid, _u = a
    if not _throttle(("reg", uid), 8):
        return bad("Слишком много попыток, подожди несколько минут", 429)
    try:
        body = await request.json()
    except Exception:
        return bad("bad json")
    login = str(body.get("login") or "").strip()
    email = str(body.get("email") or "").strip()
    pw = str(body.get("password") or "")
    if not LOGIN_RE.match(login):
        return bad("Логин: 3-24 символа, латиница, цифры, точка, _ и -")
    if not EMAIL_RE.match(email) or len(email) > 254:
        return bad("Проверь почту, похоже на опечатку")
    if len(pw) < 8:
        return bad("Пароль не меньше 8 символов")
    if len(pw) > 128:
        return bad("Пароль слишком длинный")
    if pw.lower() == login.lower():
        return bad("Пароль не должен совпадать с логином")
    pw_hash = await asyncio.get_running_loop().run_in_executor(None, _hash_pw, pw)
    taken = await db.account_create(uid, login, email, pw_hash)
    if taken == "user":
        return bad("К этому Telegram уже привязан аккаунт")
    if taken == "login":
        return bad("Этот логин занят, придумай другой")
    if taken == "email":
        return bad("Эта почта уже используется")
    await db.get_or_create_user(uid, (_u or {}).get("username"))
    return web.json_response({"ok": True, "login": login})


async def h_login_pw(request):
    """Вход по логину и паролю (для обычного браузера): отдаёт сессию привязанного Telegram-профиля."""
    try:
        body = await request.json()
    except Exception:
        return bad("bad json")
    login = str(body.get("login") or "").strip()
    pw = str(body.get("password") or "")
    if not _throttle(("lip", _ip(request)), 20) or not _throttle(("lil", login.lower()), 8):
        return bad("Слишком много попыток, подожди несколько минут", 429)
    acc = await db.account_by_login(login) if login and len(pw) <= 128 else None
    ok = await asyncio.get_running_loop().run_in_executor(None, _check_pw, pw, acc[3] if acc else _DUMMY)
    if not acc or not ok:
        return bad("Неверный логин или пароль", 401)
    return web.json_response({"ok": True, "session": make_session(acc[0]), "user": await user_card(acc[0])})


# ---------- вход через бота (для обычного браузера) ----------
async def h_login_start(request):
    now = time.time()
    for k in [k for k, v in _logins.items() if v["exp"] < now]:
        _logins.pop(k, None)
    if len(_logins) > 5000:
        return bad("busy", 429)
    tok = secrets.token_urlsafe(12)
    _logins[tok] = {"uid": None, "exp": now + LOGIN_TTL}
    me = await _ctx["bot"].get_me()
    return web.json_response({"ok": True, "token": tok, "url": f"https://t.me/{me.username}?start=login_{tok}"})


async def h_login_check(request):
    tok = request.query.get("t", "")
    v = _logins.get(tok)
    if not v or v["exp"] < time.time():
        return bad("expired", 410)
    if v["uid"] is None:
        return web.json_response({"ok": True, "done": False})
    _logins.pop(tok, None)
    return web.json_response({"ok": True, "done": True, "session": make_session(v["uid"]),
                              "user": await user_card(v["uid"])})


# ---------- вход по коду из бота ----------
# Человек вводит свой @username, бот сам присылает ему код в Telegram. Код делает только сервер:
# 6 цифр из secrets, живёт 5 минут, одноразовый, 5 попыток. Придумать или подобрать код нельзя.
CODE_TTL = 300
CODE_TRIES = 5
USERNAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$")
_codes = {}       # id запроса -> {"uid", "h", "exp", "tries"}
_code_last = {}   # username -> время последней отправки


def _code_hash(rid, code):
    return hmac.new(_SESS_KEY, (rid + ":" + code).encode(), hashlib.sha256).hexdigest()


async def h_code_request(request):
    try:
        body = await request.json()
    except Exception:
        return bad("bad json")
    uname = str(body.get("username") or "").strip()
    if not USERNAME_RE.match(uname):
        return bad("Username: 5-32 символа, латиница, цифры и _, начинается с буквы")
    uname = uname.lstrip("@")
    now = time.time()
    if not _throttle(("cri", _ip(request)), 6, 600):
        return bad("Слишком много попыток, подожди несколько минут", 429)
    if now - _code_last.get(uname.lower(), 0) < 60:
        return bad("Код уже отправлен. Новый можно запросить через минуту", 429)
    me = await _ctx["bot"].get_me()
    start_url = f"https://t.me/{me.username}"
    row = await db.find_user(uname)
    generic = ("Не получилось отправить код. Нажми Start в боте @" + me.username +
               " с этого Telegram-аккаунта и попробуй снова")
    if not row or not row[1] or row[1].lower() != uname.lower():
        _code_last[uname.lower()] = now
        return web.json_response({"ok": False, "error": generic, "bot_url": start_url})
    uid = row[0]
    code = "%06d" % secrets.randbelow(1000000)
    rid = secrets.token_urlsafe(12)
    try:
        await _ctx["bot"].send_message(
            uid,
            "🔐 Код для входа на сайт Phonker Shop: " + code + "\n\n"
            "Он действует 5 минут. Никому его не говори, даже поддержке: мы код не спрашиваем. "
            "Если это не ты, просто проигнорируй сообщение.")
    except Exception:
        logging.exception("web: code send failed")
        _code_last[uname.lower()] = now
        return web.json_response({"ok": False, "error": generic, "bot_url": start_url})
    for k in [k for k, v in _codes.items() if v["exp"] < now]:
        _codes.pop(k, None)
    if len(_codes) > 5000:
        _codes.clear()
    _codes[rid] = {"uid": uid, "h": _code_hash(rid, code), "exp": now + CODE_TTL, "tries": 0}
    _code_last[uname.lower()] = now
    return web.json_response({"ok": True, "rid": rid, "ttl": CODE_TTL})


async def h_code_verify(request):
    try:
        body = await request.json()
    except Exception:
        return bad("bad json")
    rid = str(body.get("rid") or "")
    code = str(body.get("code") or "").strip()
    if not _throttle(("cvi", _ip(request)), 30, 600):
        return bad("Слишком много попыток, подожди несколько минут", 429)
    v = _codes.get(rid)
    if not v or v["exp"] < time.time():
        _codes.pop(rid, None)
        return bad("Код истёк. Запроси новый")
    if not re.fullmatch(r"\d{6}", code):
        return bad("Код состоит из 6 цифр")
    v["tries"] += 1
    if not hmac.compare_digest(_code_hash(rid, code), v["h"]):
        if v["tries"] >= CODE_TRIES:
            _codes.pop(rid, None)
            return bad("Слишком много неверных попыток. Запроси новый код")
        return bad("Неверный код. Осталось попыток: %d" % (CODE_TRIES - v["tries"]))
    _codes.pop(rid, None)
    return web.json_response({"ok": True, "session": make_session(v["uid"]), "user": await user_card(v["uid"])})


# ---------- заказы и чат с продавцом ----------
def _site_btn(order_id, text):
    site = (getattr(config, "SITE_URL", "") or "").rstrip("/")
    if not site:
        return None
    url = f"{site}/?order={order_id}"
    btn = InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url)) if site.startswith("https://") \
        else InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


async def _chat_access(request, oid):
    """Возвращает (uid, order, role) или ответ-ошибку. role: buyer | seller."""
    a = auth_user(request)
    if not a:
        return None, bad("auth", 401)
    uid = a[0]
    order = await db.get_order(oid)
    if not order:
        return None, bad("Заказ не найден", 404)
    if order[1] == uid:
        return (uid, order, "buyer"), None
    if _ctx["is_admin"](uid):
        return (uid, order, "seller"), None
    return None, bad("Нет доступа", 403)


async def h_orders(request):
    a = auth_user(request)
    if not a:
        return bad("auth", 401)
    rows = await db.user_orders_ext(a[0], 30)
    return web.json_response({"ok": True, "orders": [
        {"id": r[0], "name": r[1], "price": r[2], "at": r[3], "status": r[4], "delivered": bool(r[5]),
         "reviewed": bool(r[6])} for r in rows]})


async def h_chat_get(request):
    try:
        oid = int(request.match_info["oid"])
        after = int(request.query.get("after") or 0)
    except ValueError:
        return bad("bad id")
    acc, err = await _chat_access(request, oid)
    if err:
        return err
    uid, order, role = acc
    rows = await db.chat_list(oid, after)
    return web.json_response({"ok": True, "role": role,
        "order": {"id": order[0], "name": order[3], "price": order[4], "status": order[5],
                  "delivered": bool(await db.order_is_delivered(oid))},
        "messages": [{"id": r[0], "from": r[1], "text": r[2], "at": r[3]} for r in rows]})


async def h_chat_post(request):
    try:
        oid = int(request.match_info["oid"])
        body = await request.json()
    except Exception:
        return bad("bad request")
    acc, err = await _chat_access(request, oid)
    if err:
        return err
    uid, order, role = acc
    text = str(body.get("text") or "").strip()
    if not text:
        return bad("Пустое сообщение")
    if len(text) > 1000:
        return bad("Слишком длинное сообщение (до 1000 символов)")
    if not _throttle(("chat", uid), 20, 60):
        return bad("Слишком часто, подожди минуту", 429)
    mid = await db.chat_add(oid, role, text)
    name = order[3]
    if role == "buyer":
        try:
            chat = await _ctx["bot"].get_chat(uid)
            who = ("@" + chat.username) if chat.username else (chat.first_name or str(uid))
        except Exception:
            who = str(uid)
        for admin_id in _ctx["admin_ids"]():
            try:
                await _ctx["bot"].send_message(
                    admin_id, f"💬 Заказ №{oid} «{name}», {who}:\n{text[:500]}",
                    reply_markup=_site_btn(oid, "Ответить на сайте"))
            except Exception:
                pass
    else:
        try:
            await _ctx["bot"].send_message(
                order[1], f"💬 Продавец по заказу №{oid} «{name}»:\n{text[:500]}",
                reply_markup=_site_btn(oid, "Открыть чат"))
        except Exception:
            logging.warning("чат: не удалось уведомить покупателя %s", order[1])
    return web.json_response({"ok": True, "id": mid})


async def h_order_done(request):
    """Покупатель подтверждает получение (то же, что кнопка в боте)."""
    a = auth_user(request)
    if not a:
        return bad("auth", 401)
    try:
        oid = int(request.match_info["oid"])
    except ValueError:
        return bad("bad id")
    order = await db.get_order(oid)
    if not order or order[1] != a[0]:
        return bad("Это не твой заказ", 403)
    if order[5] == "completed":
        return web.json_response({"ok": True})
    if order[5] != "confirmed":
        return bad("Заказ ещё не в статусе для закрытия")
    if not await db.order_is_delivered(oid):
        return bad("Продавец ещё не выдал товар")
    await db.set_order_status(oid, "completed")
    return web.json_response({"ok": True})


async def h_order_review(request):
    a = auth_user(request)
    if not a:
        return bad("auth", 401)
    try:
        oid = int(request.match_info["oid"])
        body = await request.json()
    except Exception:
        return bad("bad request")
    order = await db.get_order(oid)
    if not order or order[1] != a[0]:
        return bad("Это не твой заказ", 403)
    if order[5] != "completed":
        return bad("Сначала подтверди получение заказа")
    if await db.has_review(oid):
        return bad("Отзыв по этому заказу уже есть")
    text = str(body.get("text") or "").strip()
    if len(text) < 5:
        return bad("Напиши хотя бы пару слов")
    if len(text) > 800:
        return bad("Слишком длинный отзыв (до 800 символов)")
    if not _throttle(("rev", a[0]), 5, 600):
        return bad("Слишком часто, подожди", 429)
    try:
        chat = await _ctx["bot"].get_chat(a[0])
        username = chat.username or chat.first_name or str(a[0])
    except Exception:
        username = str(a[0])
    await db.add_review(oid, a[0], username, order[3], order[4], text, None)
    posted = False
    if _ctx.get("publish_review"):
        posted = await _ctx["publish_review"](oid, username, order[3], order[4], text)
    return web.json_response({"ok": True, "posted": posted})


def _mask(name):
    name = (name or "").lstrip("@")
    return (name[:2] + "***") if len(name) > 2 else "покупатель"


async def h_reviews(request):
    try:
        off = max(0, int(request.query.get("offset") or 0))
    except ValueError:
        off = 0
    rows = await db.reviews_list(off, 20)
    return web.json_response({"ok": True, "reviews": [
        {"id": r[0], "user": _mask(r[1]), "product": r[2], "text": r[3], "photo": bool(r[4]), "at": str(r[5])[:10]}
        for r in rows]})


async def h_review_photo(request):
    try:
        rid = int(request.match_info["rid"])
    except ValueError:
        return web.Response(status=404)
    fid = await db.review_photo(rid)
    if not fid:
        return web.Response(status=404)
    try:
        import io
        buf = io.BytesIO()
        await _ctx["bot"].download(fid, destination=buf)
        return web.Response(body=buf.getvalue(), content_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        return web.Response(status=404)


def bind_login(tok, uid):
    """Вызывается ботом, когда пользователь нажал Start по ссылке входа."""
    v = _logins.get(tok)
    if not v or v["exp"] < time.time():
        return False
    v["uid"] = uid
    return True


# ---------- промокоды ----------
def apply_discount(price, promo):
    _, discount_type, value, _a = promo
    if discount_type == "percent":
        return max(round(price * (100 - value) / 100), 0)
    return max(price - value, 0)


async def h_promo(request):
    a = auth_user(request)
    if not a:
        return bad("auth", 401)
    uid = a[0]
    now = time.time()
    hist = [t for t in _rate.get(("promo", uid), []) if now - t < 60]
    if len(hist) >= 10:
        return bad("Слишком часто, подожди минуту", 429)
    hist.append(now)
    _rate[("promo", uid)] = hist
    promo = await db.get_promocode(str(request.query.get("code", "")).strip())
    if not promo or not promo[3]:
        return bad("Промокод не найден или не действует")
    return web.json_response({"ok": True, "code": promo[0], "type": promo[1], "value": promo[2]})


# ---------- оплата ----------
async def h_pay(request):
    a = auth_user(request)
    if not a:
        return bad("auth", 401)
    uid, u = a
    if not await db.account_get(uid):
        return bad("Сначала заверши регистрацию", 403, need_register=True)
    try:
        body = await request.json()
    except Exception:
        return bad("bad json")
    use_stars = str(body.get("method")) == "stars"
    if use_stars:
        if not _ctx.get("invoice_link") or (await db.get_setting("pay_stars_on", "1")) != "1":
            return bad("Оплата звёздами сейчас недоступна")
    elif not platega.enabled():
        return bad("Оплата временно недоступна")
    if not _ctx["is_admin"](uid) and not _ctx["is_open"]():
        return bad(f"Магазин сейчас закрыт, работаем с {config.WORK_HOURS_START}:00 до {config.WORK_HOURS_END}:00 по МСК")

    method_id = None
    if not use_stars:
        allowed = dict(platega.method_list())
        try:
            method_id = int(body.get("method"))
        except (TypeError, ValueError):
            method_id = next(iter(allowed), None)
        if method_id not in allowed:
            return bad("Способ оплаты недоступен")

    now = time.time()
    hist = [t for t in _rate.get(uid, []) if now - t < 60]
    if len(hist) >= 5:
        return bad("Слишком часто, подожди минуту", 429)

    raw = body.get("items") or []
    if not isinstance(raw, list) or not raw or len(raw) > 30:
        return bad("Корзина пуста")
    merged = {}
    for it in raw:
        try:
            pid, qty = int(it["id"]), int(it["qty"])
        except (KeyError, TypeError, ValueError):
            return bad("Неверный товар")
        if qty < 1:
            continue
        merged[pid] = min(MAX_QTY, merged.get(pid, 0) + qty)
    lines, total = [], 0
    for pid, qty in merged.items():
        p = await db.get_product(pid)  # product_id, name, desc, price, stock, active, photo, category
        if not p or not p[5] or p[4] == 0:
            return bad("Один из товаров уже недоступен, обнови страницу")
        if p[4] > 0 and qty > p[4]:
            return bad(f"«{p[1]}» осталось только {p[4]} шт.")
        lines.append((pid, p[1], p[3], qty))
        total += p[3] * qty
    if not lines or total <= 0:
        return bad("Корзина пуста")

    promo_code = None
    promo_raw = str(body.get("promo") or "").strip()
    if promo_raw:
        promo = await db.get_promocode(promo_raw)
        if not promo or not promo[3]:
            return bad("Промокод не найден или уже не действует")
        total = apply_discount(total, promo)
        if total <= 0:
            return bad("Сумма после скидки должна быть больше нуля")
        promo_code = promo[0]

    tag = re.sub(r"\s+", " ", str(body.get("tag") or "")).strip()[:40]
    name = "🛒 " + ", ".join(f"{n} ×{q}" if q > 1 else n for _p, n, _pr, q in lines)
    if tag:
        name += f" | тег: {tag}"
    if promo_code:
        name += f" | промо: {promo_code}"
    name = name if len(name) <= 180 else name[:179] + "…"

    await db.get_or_create_user(uid, (u or {}).get("username"))
    snap_id = await db.snap_create(uid, name, total, lines)
    if use_stars:
        # Telegram Stars: счёт создаёт бот, оплату и заказ оформляет тот же обработчик, что и при оплате в боте
        stars = max(math.ceil(total / config.STARS_TO_RUB), 1)
        try:
            link = await _ctx["invoice_link"](name, f"Заказ: {total}{config.CURRENCY} = {stars} ⭐",
                                              f"order:{-snap_id}:{total}:{promo_code or '-'}", stars)
        except Exception:
            logging.exception("web: stars invoice failed")
            return bad("Не удалось создать счёт, попробуй ещё раз или напиши в поддержку", 502)
        hist.append(now)
        _rate[uid] = hist
        return web.json_response({"ok": True, "invoice": link, "stars": stars, "total": total})
    site = os.getenv("SITE_URL") or getattr(config, "SITE_URL", "") or await _ctx["bot_link"]()
    try:
        tx_id, url = await platega.create_payment(total, method_id, f"Заказ: {name}"[:200], f"{uid}:{-snap_id}", site)
    except platega.PlategaLimit as e:
        return bad(str(e))
    except Exception as e:
        logging.exception("web: platega create failed")
        for admin_id in _ctx["admin_ids"]():
            try:
                await _ctx["bot"].send_message(admin_id, f"⚠️ Platega (сайт): не удалось создать платёж.\n{str(e)[:400]}")
            except Exception:
                pass
        return bad("Не удалось создать платёж, попробуй ещё раз или напиши в поддержку", 502)
    await db.pg_add(tx_id, uid, -snap_id, total, promo_code or "-")
    hist.append(now)
    _rate[uid] = hist
    return web.json_response({"ok": True, "tx": tx_id, "url": url, "total": total})


async def h_pay_status(request):
    a = auth_user(request)
    if not a:
        return bad("auth", 401)
    uid, _u = a
    tx_id = request.match_info["tx"]
    tx = await db.pg_get(tx_id)  # tx_id, user_id, product_id, price, promo, status, order_id
    if not tx or tx[1] != uid:
        return bad("Платёж не найден", 404)
    status = tx[5]
    if status == "pending":
        try:
            st = await platega.get_status(tx_id)
            if st in ("CONFIRMED", "CANCELED"):
                await _ctx["apply_status"](tx_id, st)
                tx = await db.pg_get(tx_id)
                status = tx[5]
        except Exception:
            logging.exception("web: status check failed")
    drops = []
    if status == "paid" and tx[6]:
        try:
            order = await db.get_order(tx[6])
            m = re.search(r"выпало: (.+)$", (order[3] if order else "") or "")
            if m:
                drops = [d.strip() for d in m.group(1).split(",") if d.strip()]
        except Exception:
            logging.exception("web: drops read failed")
    return web.json_response({"ok": True, "status": status, "order_id": tx[6], "total": tx[3], "drops": drops})


# ---------- сайт ----------
async def h_index(request):
    path = os.path.join(SITE_DIR, "index.html")
    if not os.path.exists(path):
        return web.Response(status=404, text="site/index.html not found")
    return web.FileResponse(path)


STATIC_RE = re.compile(r"^[\w-]+\.(css|js|png|jpg|jpeg|webp)$")


async def h_static(request):
    """Файлы сайта (style.css, app.js, images.js) из папки site. Только .css/.js, без выхода из папки."""
    name = request.match_info["name"]
    path = os.path.join(SITE_DIR, name)
    if not STATIC_RE.match(name) or not os.path.isfile(path):
        return web.Response(status=404, text="not found")
    resp = web.FileResponse(path)
    resp.headers["Cache-Control"] = "no-cache"  # после обновления бота Telegram не держит старый код
    return resp


def build_app():
    app = web.Application(middlewares=[cors])
    app.router.add_get("/", h_index)
    app.router.add_get("/static/{name}", h_static)
    app.router.add_get("/{name:[A-Za-z0-9_.-]+\\.(?:css|js|png|jpg)}", h_static)  # те же файлы с корня, чтобы работали относительные пути
    app.router.add_get("/api/config", h_config)
    app.router.add_get("/api/catalog", h_catalog)
    app.router.add_get("/api/me", h_me)
    app.router.add_post("/api/register", h_register)
    app.router.add_post("/api/login/pw", h_login_pw)
    app.router.add_post("/api/login/start", h_login_start)
    app.router.add_get("/api/login/check", h_login_check)
    app.router.add_post("/api/login/code/request", h_code_request)
    app.router.add_post("/api/login/code/verify", h_code_verify)
    app.router.add_get("/api/promo", h_promo)
    app.router.add_get("/api/orders", h_orders)
    app.router.add_post("/api/orders/{oid}/done", h_order_done)
    app.router.add_post("/api/orders/{oid}/review", h_order_review)
    app.router.add_get("/api/reviews", h_reviews)
    app.router.add_get("/api/review_photo/{rid}", h_review_photo)
    app.router.add_get("/api/chat/{oid}", h_chat_get)
    app.router.add_post("/api/chat/{oid}", h_chat_post)
    app.router.add_post("/api/pay", h_pay)
    app.router.add_get("/api/pay/{tx}", h_pay_status)
    admin_api.setup(app, auth_user, _ctx)
    app.router.add_route("OPTIONS", "/{tail:.*}", lambda r: web.Response(status=204))
    return app


async def start(**ctx):
    """ctx: bot, is_open, is_admin, admin_ids, bot_link, apply_status, deliver_order"""
    _ctx.update(ctx)
    port = int(os.getenv("PORT") or os.getenv("WEB_PORT") or getattr(config, "WEB_PORT", 8080))
    runner = web.AppRunner(build_app())
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info("Веб-сайт и API запущены на порту %s", port)
    return runner
