import asyncio
import html
import logging
import random
import os
import re
import math
import time
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (
    Message, CallbackQuery, ChatMemberUpdated, FSInputFile, InputMediaPhoto, BufferedInputFile,
    LabeledPrice, PreCheckoutQuery, LinkPreviewOptions,
    BotCommand, BotCommandScopeChat, MenuButtonCommands, MenuButtonWebApp, WebAppInfo, MessageEntity,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION

import config
import database as db
import platega
import web_api
import tunnel
import premium
import dbsafe
from fsm_storage import SQLiteStorage
from keyboards import (
    main_menu_kb, catalog_kb, product_kb, admin_menu_kb, admins_kb, bcast_confirm_kb,
    buy_donate_kb, format_review_post, review_preview_kb, _site_chat_button,
    user_found_kb, giveaway_kb, order_admin_kb, order_confirm_kb,
    admin_orders_kb, admin_order_view_kb, order_wait_kb, order_paid_admin_kb, order_chat_kb, review_offer_kb, my_orders_kb,
    cancel_kb, game_menu_kb, sections_kb, clash_placeholder_kb, category_pick_kb,
    reviews_kb, product_settings_kb, admin_categories_kb, admin_users_kb,
    category_game_pick_kb, category_settings_kb, promo_admin_kb, promo_settings_kb,
    purchase_promo_kb, pay_notice_kb, pay_methods_kb, pay_done_kb, pay_auto_kb, PAY_METHODS,
    docs_kb, doc_back_kb, DOC_TITLES, admin_payments_kb, admin_pay_method_kb,
    admin_docs_kb, admin_doc_edit_kb,
    cart_kb, profile_kb, queue_kb, GAME_LABELS, GAME_NAMES,
)

logging.basicConfig(level=logging.INFO)

if not config.BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Создай .env по примеру .env.example и укажи токен бота.")

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=SQLiteStorage())
router = Router()
dp.include_router(router)

MSK = timezone(timedelta(hours=3))


def is_shop_open():
    now = datetime.now(MSK)
    return config.WORK_HOURS_START <= now.hour < config.WORK_HOURS_END


def slugify_category(name):
    table = str.maketrans({
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
        "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    })
    slug = name.lower().translate(table)
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug or "cat"


ADMIN_CACHE = set()


def admin_ids():
    ids = list(config.ADMIN_IDS)
    ids.extend(i for i in ADMIN_CACHE if i not in ids)
    return ids


def is_admin(user_id):
    return user_id in config.ADMIN_IDS or user_id in ADMIN_CACHE


def state_for(user_id):
    return FSMContext(
        storage=dp.storage,
        key=StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id),
    )


def game_photo():
    return FSInputFile("assets/choose_game.jpg") if os.path.exists("assets/choose_game.jpg") else None


def welcome_photo():
    return FSInputFile(WELCOME_IMAGE) if os.path.exists(WELCOME_IMAGE) else None


CAPTION_LIMIT = 1024
REVIEW_MAX = 700
PHOTO_IDS = {}


def banner(name):
    """Картинка раздела assets/<name>.jpg. После первой отправки берём готовый file_id из Telegram."""
    path = f"assets/{name}.jpg"
    if path in PHOTO_IDS:
        return PHOTO_IDS[path]
    return FSInputFile(path) if os.path.exists(path) else None


def _remember_photo(photo, msg):
    try:
        if isinstance(photo, FSInputFile) and msg is not None and getattr(msg, "photo", None):
            PHOTO_IDS[str(photo.path)] = msg.photo[-1].file_id
    except Exception:
        pass


SCREEN_LOCKS: dict[int, asyncio.Lock] = {}


def _screen_lock(user_id):
    lock = SCREEN_LOCKS.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        SCREEN_LOCKS[user_id] = lock
    return lock


PREMIUM = {"buttons": False, "text": False}
PREMIUM_MAP = getattr(config, "PREMIUM_EMOJI", {"🎮": "5938413566624272793"})
ICON_FIELD = "icon_custom_emoji_id" in InlineKeyboardButton.model_fields


def premium_entities(text):
    if not PREMIUM["text"] or not text:
        return None
    spans = premium.find_spans(text, PREMIUM_MAP)
    if not spans:
        return None
    return [MessageEntity(type="custom_emoji", offset=o, length=l, custom_emoji_id=i) for o, l, i in spans]


def premium_markup(markup):
    if not PREMIUM["buttons"] or not ICON_FIELD or markup is None:
        return markup
    rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            found = premium.split_button_text(btn.text, PREMIUM_MAP)
            if found:
                btn = btn.model_copy(update={"text": found[0], "icon_custom_emoji_id": found[1]})
            new_row.append(btn)
        rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def probe_premium():
    if not PREMIUM_MAP or not admin_ids():
        return
    char, emoji_id = next(iter(PREMIUM_MAP.items()))
    target = admin_ids()[0]
    if ICON_FIELD:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="ok", callback_data="noop", icon_custom_emoji_id=emoji_id)]])
            msg = await bot.send_message(target, ".", reply_markup=kb, disable_notification=True)
            shown = msg.reply_markup.inline_keyboard[0][0]
            PREMIUM["buttons"] = getattr(shown, "icon_custom_emoji_id", None) == emoji_id
            await bot.delete_message(target, msg.message_id)
        except Exception:
            logging.info("premium icons on buttons are not available")
    try:
        length = len(char.encode("utf-16-le")) // 2
        ent = MessageEntity(type="custom_emoji", offset=0, length=length, custom_emoji_id=emoji_id)
        msg = await bot.send_message(target, char, entities=[ent], disable_notification=True)
        PREMIUM["text"] = any(e.type == "custom_emoji" for e in (msg.entities or []))
        await bot.delete_message(target, msg.message_id)
    except Exception:
        logging.info("premium emoji in text are not available")
    logging.info("premium emoji: %s", PREMIUM)


async def show(user_id, text, reply_markup=None, photo=None, parse_mode=None, no_preview=False):
    async with _screen_lock(user_id):
        reply_markup = premium_markup(reply_markup)
        ents = premium_entities(text) if parse_mode is None else None
        if photo is not None and len(text) > CAPTION_LIMIT:
            photo = None  # подпись к картинке не длиннее 1024 символов, тогда показываем просто текст
        preview = LinkPreviewOptions(is_disabled=True) if no_preview else None
        msg_id = await db.get_screen(user_id)
        if msg_id:
            try:
                if photo is not None:
                    media = InputMediaPhoto(media=photo, caption=text, parse_mode=parse_mode, caption_entities=ents)
                    edited = await bot.edit_message_media(
                        media=media, chat_id=user_id, message_id=msg_id, reply_markup=reply_markup
                    )
                    _remember_photo(photo, edited)
                else:
                    await bot.edit_message_text(
                        text, chat_id=user_id, message_id=msg_id,
                        reply_markup=reply_markup, parse_mode=parse_mode, entities=ents,
                        link_preview_options=preview,
                    )
                return
            except Exception as e:
                if "message is not modified" in str(e):
                    return
                try:
                    await bot.delete_message(chat_id=user_id, message_id=msg_id)
                except Exception:
                    pass
                await db.clear_screen(user_id)

        try:
            if photo is not None:
                m = await bot.send_photo(
                    user_id, photo, caption=text, reply_markup=reply_markup, parse_mode=parse_mode,
                    caption_entities=ents,
                )
                _remember_photo(photo, m)
            else:
                m = await bot.send_message(
                    user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, entities=ents,
                    link_preview_options=preview,
                )
            await db.set_screen(user_id, m.message_id)
        except Exception:
            logging.exception("show(): failed to send screen to user_id=%s", user_id)
            if photo is not None:
                try:
                    m = await bot.send_message(
                        user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, entities=ents,
                        link_preview_options=preview,
                    )
                    await db.set_screen(user_id, m.message_id)
                except Exception:
                    logging.exception("show(): text fallback failed for user_id=%s", user_id)


class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    stock = State()
    category = State()
    photo = State()


class DelProduct(StatesGroup):
    product_id = State()


class EditProduct(StatesGroup):
    product_id = State()
    field = State()
    value = State()
    photo = State()


class Broadcast(StatesGroup):
    text = State()
    confirm = State()
    button = State()


class AdminAdd(StatesGroup):
    who = State()


class EmojiId(StatesGroup):
    wait = State()


class FindUser(StatesGroup):
    query = State()


class AdminChat(StatesGroup):
    text = State()


class BuyerChat(StatesGroup):
    active = State()


class LeaveReview(StatesGroup):
    text = State()
    photo = State()
    confirm = State()


class Purchase(StatesGroup):
    notice = State()
    promocode = State()
    method = State()


class SetPayLink(StatesGroup):
    value = State()


class SetDoc(StatesGroup):
    value = State()


class AddCategory(StatesGroup):
    game = State()
    name = State()


class RenameCategory(StatesGroup):
    name = State()


class AddPromo(StatesGroup):
    code = State()
    discount = State()


KEEP_STATES = {Broadcast.text.state, Broadcast.confirm.state, AdminChat.text.state, BuyerChat.active.state, LeaveReview.text.state,
               LeaveReview.photo.state, LeaveReview.confirm.state}


async def cleanup_user_messages(handler, event, data):
    result = await handler(event, data)
    try:
        if event.chat.type != "private" or not event.from_user or event.from_user.is_bot:
            return result
        state = data.get("state")
        current = await state.get_state() if state else None
        is_command = bool(event.text and event.text.startswith("/"))
        if event.text == "/endchat" or event.successful_payment:
            return result
        if is_command or (current and current not in KEEP_STATES):
            await event.delete()
    except Exception:
        pass
    return result


router.message.outer_middleware(cleanup_user_messages)


LAST_ACTION = {}
NOTIFY_PREFIXES = ("order_ok:", "order_no:", "order_chat:", "order_deliv:", "chat_admin")


def _is_repeat(user_id, key, window):
    now = time.monotonic()
    last = LAST_ACTION.get(user_id)
    LAST_ACTION[user_id] = (key, now)
    return bool(last and last[0] == key and now - last[1] < window)


async def track_user_message(handler, event, data):
    u = event.from_user
    if u and not u.is_bot and event.chat.type == "private":
        try:
            await db.touch_user(u.id, u.username, u.first_name)
        except Exception:
            logging.exception("touch_user failed")
        parts = event.text.split() if event.text else []
        if parts and parts[0] == "/start" and _is_repeat(u.id, "msg:/start", 1.5):
            return
    return await handler(event, data)


async def track_user_callback(handler, event, data):
    u = event.from_user
    if u and not u.is_bot:
        try:
            await db.touch_user(u.id, u.username, u.first_name)
        except Exception:
            logging.exception("touch_user failed")
        if _is_repeat(u.id, "cb:" + str(event.data), 1.0):
            try:
                await event.answer()
            except Exception:
                pass
            return
        msg = event.message
        if msg is not None and event.data and not event.data.startswith(NOTIFY_PREFIXES):
            async with _screen_lock(u.id):
                await db.set_screen(u.id, msg.message_id)
    return await handler(event, data)


router.message.outer_middleware(track_user_message)
router.callback_query.outer_middleware(track_user_callback)


WELCOME_IMAGE = "assets/welcome.jpg"
GAME_IMAGE = "assets/choose_game.jpg"
WELCOME_TEXT = (
    "Привет! 👋 Рад видеть тебя в магазине.\n"
    "Тут можно глянуть каталог и купить то, что нужно - быстро и без гемора.\n\n"
    "Что делаем?"
)

@router.message(CommandStart(deep_link=True))
async def cmd_start_link(message, command):
    arg = command.args or ""
    if arg.startswith("login_"):
        await db.get_or_create_user(message.from_user.id, message.from_user.username)
        ok = web_api.bind_login(arg[6:], message.from_user.id)
        await message.answer("✅ Готово! Вернись на сайт - ты вошёл в свой профиль." if ok
                             else "Ссылка для входа устарела. Вернись на сайт и нажми «Войти» ещё раз.")
        return
    await cmd_start(message)


@router.message(CommandStart())
async def cmd_start(message):
    await db.get_or_create_user(message.from_user.id, message.from_user.username)
    admin = is_admin(message.from_user.id)
    async with _screen_lock(message.from_user.id):
        old_id = await db.get_screen(message.from_user.id)
        await db.clear_screen(message.from_user.id)
        if old_id:
            try:
                await bot.delete_message(chat_id=message.from_user.id, message_id=old_id)
            except Exception:
                pass
        try:
            m = await message.answer_photo(
                FSInputFile(WELCOME_IMAGE), caption=WELCOME_TEXT,
                reply_markup=premium_markup(main_menu_kb(admin)),
                caption_entities=premium_entities(WELCOME_TEXT),
            )
        except Exception:
            m = await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb(admin))
        await db.set_screen(message.from_user.id, m.message_id)


@router.callback_query(F.data == "miniapp_wait")
async def miniapp_wait(call: CallbackQuery):
    await call.answer("Мини-приложение запускается, попробуй открыть меню через минуту: /start", show_alert=True)


@router.callback_query(F.data == "menu")
async def cb_menu(call):
    admin = is_admin(call.from_user.id)
    await show(call.from_user.id, WELCOME_TEXT, reply_markup=main_menu_kb(admin), photo=welcome_photo())
    await call.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(call, state):
    await state.clear()
    admin = is_admin(call.from_user.id)
    await show(call.from_user.id, WELCOME_TEXT, reply_markup=main_menu_kb(admin), photo=welcome_photo())
    await call.answer("Отменено")


@router.callback_query(F.data == "support")
async def cb_support(call):
    await show(
        call.from_user.id,
        "Пиши прямо сюда, что случилось - сообщение сразу улетит мне, отвечу как только увижу 🙌",
        reply_markup=main_menu_kb(is_admin(call.from_user.id)),
        photo=banner("support"),
    )
    await call.answer()


def order_status_label(status, delivered):
    if status == "confirmed":
        return "📬 выдан, подтверди получение" if delivered else "📦 оплачен, жди товар"
    return {
        "pending": "⏳ ждёт подтверждения оплаты",
        "completed": "✅ завершён",
        "rejected": "❌ отклонён",
    }.get(status, status)


@router.callback_query(F.data == "my_orders")
async def cb_my_orders(call):
    user_id = call.from_user.id
    admin = is_admin(user_id)
    orders = await db.user_orders_ext(user_id, limit=20)
    photo = banner("my_orders")
    if not orders:
        await show(user_id, "Пока пусто - ты ещё ничего не покупал(а) 🙂", reply_markup=main_menu_kb(admin), photo=photo)
        await call.answer()
        return
    text = "🧾 Твои покупки:\n"
    shown = 0
    confirm_actions = []
    review_actions = []
    for order_id, name, price, _created, status, delivered, reviewed in orders:
        line = f"№{order_id} - {name} ({price}{config.CURRENCY}) - {order_status_label(status, delivered)}"
        if len(text) + len(line) + 1 > CAPTION_LIMIT - 40:
            break
        text += "\n" + line
        shown += 1
        if status == "confirmed" and delivered:
            confirm_actions.append((f"✅ Получил заказ №{order_id}", f"order_done:{order_id}"))
        elif status == "completed" and not reviewed:
            review_actions.append((f"⭐ Отзыв по заказу №{order_id}", f"review_start:{order_id}"))
    if shown < len(orders):
        text += f"\n... и ещё {len(orders) - shown}"
    actions = (confirm_actions + review_actions[:3])[:5]
    await show(user_id, text, reply_markup=my_orders_kb(actions, admin), photo=photo)
    await call.answer()


def reviews_channel():
    return (config.REVIEWS_CHANNEL or "").strip()


async def render_reviews(user_id, offset=0):
    url = (await db.get_setting("reviews_url", None)) or config.REVIEWS_URL or ""
    uname = (await db.get_setting("reviews_username", None)) or config.REVIEWS_USERNAME or ""
    reviews_line = ""
    if url.startswith("http"):
        reviews_line = f'\n\nВсе отзывы: <a href="{url}">{html.escape(uname or "здесь")}</a>'
    header = (
        "<b>Почему стоит выбирать именно нас?</b>\n\n"
        "• Огромный опыт работы.\n"
        "• Низкие цены.\n"
        "• Быстрая выдача товаров."
    )
    text = header + reviews_line
    parts = []
    for r in await db.list_reviews(limit=3):
        # review_id, order_id, username, product_name, price, text, created_at
        parts.append(f"• <b>{html.escape(str(r[2] or 'Покупатель'))}</b> - {html.escape(str(r[3]))}: {html.escape(str(r[5])[:120])}")
        candidate = header + "\n\n<b>Последние отзывы:</b>\n" + "\n".join(parts) + reviews_line
        if len(candidate) > CAPTION_LIMIT - 40:
            parts.pop()
            break
        text = candidate
    await show(user_id, text, reply_markup=reviews_kb(), parse_mode="HTML", no_preview=True, photo=banner("reviews"))


@router.callback_query(F.data == "reviews")
async def cb_reviews(call):
    await render_reviews(call.from_user.id)
    await call.answer()


@router.callback_query(F.data.startswith("reviews:"))
async def cb_reviews_page(call):
    await render_reviews(call.from_user.id)
    await call.answer()


@router.callback_query(F.data == "admin_open")
async def cb_admin_open(call):
    if not is_admin(call.from_user.id):
        await call.answer("Это не для тебя 😉", show_alert=True)
        return
    await show(call.from_user.id, "Админка. Погнали:", reply_markup=admin_menu_kb())
    await call.answer()


@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def forward_support_message(message, state):
    if is_admin(message.from_user.id):
        return
    for admin_id in admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"✉️ Новое сообщение от @{message.from_user.username or message.from_user.id} "
                f"(id {message.from_user.id}):\n\n{message.text}",
            )
        except Exception:
            pass
    await message.answer("Принял, передал 👌 Скоро отвечу.")



async def resolve_product(product_id):
    """Обычный товар или снимок корзины (product_id < 0). Формат как у db.get_product."""
    if product_id >= 0:
        return await db.get_product(product_id)
    snap = await db.snap_get(-product_id)
    if not snap:
        return None
    return (product_id, snap["name"], "", snap["price"], -1, 1, None, None)


async def answer_text(message, text, reply_markup=None):
    await message.answer(
        text, reply_markup=premium_markup(reply_markup), entities=premium_entities(text),
    )


# ---------------- Корзина ----------------
def cart_text(items):
    if not items:
        return "🛒 Корзина пуста.\n\nДобавь товары из каталога кнопкой «🛒 В корзину»."
    lines = ["🛒 Твоя корзина:", ""]
    total = 0
    for n, (_pid, name, price, qty, _stock, active) in enumerate(items, 1):
        mark = "" if active else " (недоступен)"
        lines.append(f"{n}. {name} × {qty} - {price * qty}{config.CURRENCY}{mark}")
        total += price * qty
    lines += ["", f"Итого: {total}{config.CURRENCY}"]
    return "\n".join(lines)


async def show_cart(user_id):
    items = await db.cart_items(user_id)
    await show(user_id, cart_text(items), reply_markup=cart_kb(items))


@router.callback_query(F.data == "noop")
async def cb_noop(call):
    await call.answer()


@router.callback_query(F.data == "cart")
async def cb_cart(call):
    await show_cart(call.from_user.id)
    await call.answer()


@router.message(Command("cart"))
async def cmd_cart(message):
    await show_cart(message.from_user.id)


@router.callback_query(F.data.startswith("cart_add:"))
async def cb_cart_add(call):
    product_id = int(call.data.split(":")[1])
    p = await db.get_product(product_id)
    if not p or not p[5] or p[4] == 0:
        await call.answer("Товар недоступен", show_alert=True)
        return
    res = await db.cart_add(call.from_user.id, product_id)
    if res == "max_qty":
        await call.answer(f"Максимум {db.CART_MAX_QTY} шт. одного товара", show_alert=True)
    elif res == "max_lines":
        await call.answer(f"В корзине максимум {db.CART_MAX_LINES} разных товаров", show_alert=True)
    else:
        await call.answer("🛒 Добавлено в корзину")


@router.callback_query(F.data.startswith("cart_inc:"))
async def cb_cart_inc(call):
    product_id = int(call.data.split(":")[1])
    p = await db.get_product(product_id)
    in_cart = {row[0]: row[3] for row in await db.cart_items(call.from_user.id)}
    if p and p[4] >= 0 and in_cart.get(product_id, 0) >= p[4]:
        await call.answer("Больше нет в наличии", show_alert=True)
        return
    await db.cart_change(call.from_user.id, product_id, +1)
    await show_cart(call.from_user.id)
    await call.answer()


@router.callback_query(F.data.startswith("cart_dec:"))
async def cb_cart_dec(call):
    await db.cart_change(call.from_user.id, int(call.data.split(":")[1]), -1)
    await show_cart(call.from_user.id)
    await call.answer()


@router.callback_query(F.data == "cart_clear")
async def cb_cart_clear(call):
    await db.cart_clear(call.from_user.id)
    await show_cart(call.from_user.id)
    await call.answer("Корзина очищена")


@router.callback_query(F.data == "cart_checkout")
async def cb_cart_checkout(call, state):
    user_id = call.from_user.id
    items = await db.cart_items(user_id)
    if not items:
        await show_cart(user_id)
        await call.answer("Корзина пуста", show_alert=True)
        return
    if not is_admin(user_id) and not is_shop_open():
        await call.answer(
            f"Магазин сейчас закрыт, работаем с {config.WORK_HOURS_START}:00 до "
            f"{config.WORK_HOURS_END}:00 по МСК. Загляни в это время 🙂",
            show_alert=True,
        )
        return
    bad = [n for _pid, n, _pr, qty, stock, active in items if not active or stock == 0 or (stock > 0 and qty > stock)]
    if bad:
        for pid, _n, _pr, qty, stock, active in items:
            if not active or stock == 0:
                await db.cart_remove(user_id, pid)
            elif stock > 0 and qty > stock:
                await db.cart_change(user_id, pid, stock - qty)
        await show_cart(user_id)
        await call.answer("Часть товаров закончилась или недоступна - я поправил корзину, проверь и оформи ещё раз", show_alert=True)
        return
    total = sum(price * qty for _pid, _n, price, qty, _s, _a in items)
    name = "🛒 " + ", ".join(f"{n} ×{qty}" if qty > 1 else n for _pid, n, _pr, qty, _s, _a in items)
    name = name if len(name) <= 180 else name[:179] + "…"
    snap_id = await db.snap_create(
        user_id, name, total, [(pid, n, price, qty) for pid, n, price, qty, _s, _a in items],
    )
    await state.clear()
    await state.update_data(product_id=-snap_id)
    await state.set_state(Purchase.notice)
    await show_pay_notice(user_id, name, total)
    await call.answer()


# ---------------- Профиль и очередь ----------------
def queue_text(total, mine, pending=None):
    lines = [f"🕒 Всего в очереди заказов: {total}"]
    for order_id, name, pos in mine:
        if pos == 1:
            lines.append(f"\n№{order_id} «{name}»: ты первый, выдаём прямо сейчас 🚀")
        else:
            lines.append(f"\n№{order_id} «{name}»: ты {pos}-й, перед тобой {pos - 1}")
    for order_id, name in (pending or []):
        lines.append(f"\n№{order_id} «{name}»: ждёт подтверждения оплаты ⏳")
    if not mine and not pending:
        lines.append("\nУ тебя сейчас нет заказов в очереди.")
    return "\n".join(lines)


async def build_queue_text(user_id, with_pending=False):
    pending = await db.user_pending_orders(user_id) if with_pending else None
    return queue_text(await db.queue_total(), await db.user_queue(user_id), pending)


async def build_profile_text(user_id):
    count, spent = await db.user_profile_stats(user_id)
    mine = await db.user_queue(user_id)
    text = (
        "👤 Твой профиль:\n\n"
        f"• Количество заказов: {count}\n"
        f"• Потрачено: {spent}{config.CURRENCY}\n"
        f"• Заказов в очереди: {len(mine)}"
    )
    if mine:
        text += f" (ближайший - {mine[0][2]}-й)"
    return text


@router.callback_query(F.data == "profile")
async def cb_profile(call):
    await show(call.from_user.id, await build_profile_text(call.from_user.id),
               reply_markup=profile_kb(), photo=banner("profile"))
    await call.answer()


@router.message(Command("profile"))
async def cmd_profile(message):
    await show(message.from_user.id, await build_profile_text(message.from_user.id),
               reply_markup=profile_kb(), photo=banner("profile"))


@router.callback_query(F.data == "queue")
async def cb_queue(call):
    await show(call.from_user.id, await build_queue_text(call.from_user.id, with_pending=True),
               reply_markup=queue_kb())
    await call.answer("Обновлено")


@router.message(Command("queue"))
async def cmd_queue(message):
    await answer_text(message, await build_queue_text(message.from_user.id))


@router.message(Command("orders"))
async def cmd_orders(message):
    user_id = message.from_user.id
    orders = await db.user_orders_ext(user_id, limit=5)
    if not orders:
        await answer_text(message, "Пока пусто - ты ещё ничего не покупал(а) 🙂")
        return
    queue = {oid: pos for oid, _n, pos in await db.user_queue(user_id)}
    lines = ["🧾 Твои последние заказы:", ""]
    for order_id, name, price, _created, status, delivered, _reviewed in orders:
        label = order_status_label(status, delivered)
        if order_id in queue:
            label += f", в очереди {queue[order_id]}-й"
        lines.append(f"№{order_id} - {name} ({price}{config.CURRENCY}) - {label}")
    await answer_text(message, "\n".join(lines))


@router.callback_query(F.data == "catalog")
async def cb_catalog(call):
    await show(call.from_user.id, "🛍 Каталог - выбери игру:", reply_markup=game_menu_kb(), photo=game_photo())
    await call.answer()


@router.callback_query(F.data.startswith("game:"))
async def cb_game(call):
    game = call.data.split(":", 1)[1]
    categories = await db.list_categories(game=game, active_only=True)
    game_label = GAME_LABELS.get(game, game)
    if not categories:
        await show(
            call.from_user.id,
            f"{game_label}\n\nРаздел пока пустой, скоро подвезём товары 👀",
            reply_markup=clash_placeholder_kb(),
        )
        await call.answer()
        return
    await show(call.from_user.id, f"{game_label} - выбери раздел:", reply_markup=sections_kb(categories, game))
    await call.answer()


@router.callback_query(F.data.startswith("section:"))
async def cb_section(call):
    category = call.data.split(":", 1)[1]
    cat = await db.get_category(category)
    game = cat[1] if cat else "bs"
    label = cat[2] if cat else "Раздел"
    products = await db.list_products(category=category)
    categories = await db.list_categories(game=game, active_only=True)
    if not products:
        await show(
            call.from_user.id, f"{label} - пока пусто, скоро подвезём 🙁",
            reply_markup=sections_kb(categories, game),
        )
        await call.answer()
        return
    short = [(p[0], p[1], p[3]) for p in products]
    await show(call.from_user.id, f"{label}:", reply_markup=catalog_kb(short, back_cb=f"game:{game}"))
    await call.answer()


@router.callback_query(F.data.startswith("product:"))
async def cb_product(call):
    product_id = int(call.data.split(":")[1])
    p = await db.get_product(product_id)
    if not p or not p[5]:
        await call.answer("Товар недоступен", show_alert=True)
        return
    _, name, desc, price, stock, _, photo, category = p
    stock_text = "неограничено" if stock < 0 else f"{stock} шт."
    text = f"<b>{name}</b>\n{desc or ''}\n\nЦена: {price}{config.CURRENCY}\nОстаток: {stock_text}"
    display_photo = photo if photo else welcome_photo()
    back_cb = f"section:{category}" if category else "catalog"
    admin = is_admin(call.from_user.id)
    await show(
        call.from_user.id, text,
        reply_markup=product_kb(product_id, back_cb=back_cb, show_settings=admin),
        photo=display_photo, parse_mode="HTML",
    )
    await call.answer()


async def pay_urls():
    urls = {}
    for key in ("account_check", "terms", "privacy", "support"):
        val = await db.get_setting(f"doc_{key}")
        if val and val.strip().lower().startswith("http"):
            urls[key] = val.strip()
    return urls


def build_pay_notice_text(urls):
    def link(key, label):
        u = urls.get(key)
        return f'<a href="{html.escape(u, quote=True)}">{label}</a>' if u else label

    return (
        "❗️ <b>Перед покупкой обязательно проверьте</b> ❗️:\n"
        f"• Можно ли донатить на ваш аккаунт - {link('account_check', 'проверка аккаунта')}.\n\n"
        "По желанию можете ознакомиться:\n"
        f"• {link('terms', 'Пользовательское соглашение')}.\n"
        f"• {link('privacy', 'Политика конфиденциальности')}.\n\n"
        "⚠️ Шанс на откат доната составляет 15%."
    )


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(call, state):
    product_id = int(call.data.split(":")[1])
    p = await db.get_product(product_id)
    if not p or not p[5]:
        await call.answer("Товар недоступен", show_alert=True)
        return
    _, name, desc, price, stock, _, photo, category = p
    if stock == 0:
        await call.answer("Товара нет в наличии", show_alert=True)
        return
    if not is_admin(call.from_user.id) and not is_shop_open():
        await call.answer(
            f"Магазин сейчас закрыт, работаем с {config.WORK_HOURS_START}:00 до "
            f"{config.WORK_HOURS_END}:00 по МСК. Загляни в это время 🙂",
            show_alert=True,
        )
        return

    await state.clear()
    await state.update_data(product_id=product_id)
    await state.set_state(Purchase.notice)
    await show_pay_notice(call.from_user.id, name, price)
    await call.answer()


async def show_pay_notice(user_id, name, price):
    urls = await pay_urls()
    await show(
        user_id,
        f"🧾 «{html.escape(name)}» - {price}{config.CURRENCY}\n\n{build_pay_notice_text(urls)}",
        reply_markup=pay_notice_kb(urls),
        parse_mode="HTML",
        no_preview=True,
    )


@router.callback_query(F.data == "pay_notice_back", StateFilter(Purchase.notice))
async def cb_pay_notice_back(call, state):
    data = await state.get_data()
    p = await resolve_product(data["product_id"])
    if not p:
        await call.answer("Товар недоступен", show_alert=True)
        return
    await show_pay_notice(call.from_user.id, p[1], p[3])
    await call.answer()


@router.callback_query(F.data == "pay_continue", StateFilter(Purchase.notice))
async def cb_pay_continue(call, state):
    data = await state.get_data()
    p = await resolve_product(data["product_id"])
    if not p or not p[5]:
        await call.answer("Товар недоступен", show_alert=True)
        return
    await state.set_state(Purchase.promocode)
    await show(
        call.from_user.id,
        f"Есть промокод на скидку? Введи его текстом, или жми «Без промокода».",
        reply_markup=purchase_promo_kb(),
    )
    await call.answer()


def apply_discount(price, promo):
    _, discount_type, value, _ = promo
    if discount_type == "percent":
        return max(round(price * (100 - value) / 100), 0)
    return max(price - value, 0)


def stars_for_price(rub):
    return max(math.ceil(rub / config.STARS_TO_RUB), 1)


async def available_pay_methods():
    methods = []
    if (await db.get_setting("pay_stars_on", "1")) == "1":
        methods.append(("stars", PAY_METHODS["stars"]))
    if await db.get_setting("pay_crypto_url"):
        methods.append(("crypto", PAY_METHODS["crypto"]))
    if await db.get_setting("pay_sbp_url"):
        methods.append(("sbp", PAY_METHODS["sbp"]))
    methods.extend(platega.methods())
    return methods


async def go_to_methods(user_id, state, promo=None):
    data = await state.get_data()
    p = await resolve_product(data["product_id"])
    if not p or not p[5]:
        await state.clear()
        await show(user_id, "Этот товар уже недоступен 🙁", reply_markup=main_menu_kb(is_admin(user_id)))
        return
    _, name, desc, price, stock, _, photo, category = p
    if stock == 0:
        await state.clear()
        await show(user_id, "Товара нет в наличии 🙁", reply_markup=main_menu_kb(is_admin(user_id)))
        return
    final_price = price
    promo_line = ""
    promo_code = None
    if promo:
        final_price = apply_discount(price, promo)
        promo_code = promo[0]
        promo_line = f"\nПромокод {promo_code}: было {price}{config.CURRENCY}"
    await state.update_data(final_price=final_price, promo_code=promo_code)

    methods = await available_pay_methods()
    if not methods:
        await state.clear()
        await show(
            user_id,
            "Способы оплаты пока не настроены 🙁 Напиши в поддержку - подскажем, как оплатить.",
            reply_markup=main_menu_kb(is_admin(user_id)),
        )
        return
    await state.set_state(Purchase.method)
    await show(
        user_id,
        f"«{name}»\nК оплате: {final_price}{config.CURRENCY}{promo_line}\n\nВыбери способ оплаты:",
        reply_markup=pay_methods_kb(methods),
    )


@router.callback_query(F.data == "promo_skip", StateFilter(Purchase.promocode))
async def cb_promo_skip(call, state):
    await go_to_methods(call.from_user.id, state)
    await call.answer()


@router.message(Purchase.promocode)
async def handle_promo_text(message, state):
    code = message.text.strip()
    promo = await db.get_promocode(code)
    if not promo or not promo[3]:
        await show(
            message.from_user.id,
            "Такой промокод не найден или уже не действует. Попробуй другой, "
            "или жми «Без промокода».",
            reply_markup=purchase_promo_kb(),
        )
        return
    await go_to_methods(message.from_user.id, state, promo=promo)


@router.callback_query(F.data == "pay_continue_methods", StateFilter(Purchase.method))
async def cb_pay_back_to_methods(call, state):
    data = await state.get_data()
    p = await resolve_product(data["product_id"])
    methods = await available_pay_methods()
    await show(
        call.from_user.id,
        f"«{p[1]}»\nК оплате: {data['final_price']}{config.CURRENCY}\n\nВыбери способ оплаты:",
        reply_markup=pay_methods_kb(methods),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pay:"), StateFilter(Purchase.method))
async def cb_pay_method(call, state):
    method = call.data.split(":", 1)[1]
    data = await state.get_data()
    product_id = data["product_id"]
    final_price = data["final_price"]
    promo_code = data.get("promo_code")
    p = await resolve_product(product_id)
    if not p or not p[5] or p[4] == 0:
        await state.clear()
        await show(call.from_user.id, "Этот товар уже недоступен 🙁", reply_markup=main_menu_kb(is_admin(call.from_user.id)))
        await call.answer()
        return
    name = p[1]
    await state.update_data(method=method)

    if method == "stars":
        stars = stars_for_price(final_price)
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=name[:32],
            description=f"Оплата заказа «{name}»: {final_price}{config.CURRENCY} = {stars} ⭐"[:255],
            payload=f"order:{product_id}:{final_price}:{promo_code or '-'}",
            currency="XTR",
            prices=[LabeledPrice(label=name[:32], amount=stars)],
        )
        await call.answer("Счёт на оплату звёздами отправлен ниже 👇")
        return

    if method.startswith("pg"):
        await start_platega_payment(call, method, p, final_price, promo_code)
        return

    if method in ("crypto", "sbp"):
        url = await db.get_setting(f"pay_{method}_url")
        if not url:
            await call.answer("Этот способ сейчас недоступен", show_alert=True)
            return
        await show(
            call.from_user.id,
            f"{PAY_METHODS[method]}\nСумма: {final_price}{config.CURRENCY}\n\n"
            f"Оплати по ссылке и вернись сюда - нажми «Я оплатил», админ проверит и выдаст товар.",
            reply_markup=pay_done_kb(url),
        )
        await call.answer()
        return


BOT_LINK = {}


async def bot_link():
    if "url" not in BOT_LINK:
        me = await bot.get_me()
        BOT_LINK["url"] = f"https://t.me/{me.username}"
    return BOT_LINK["url"]


async def start_platega_payment(call, method, p, final_price, promo_code):
    user_id = call.from_user.id
    name = p[1]
    method_id = int(method[2:])
    label = dict(platega.method_list()).get(method_id, "оплата")
    try:
        tx_id, url = await platega.create_payment(
            final_price, method_id, f"Заказ: {name}"[:200], f"{user_id}:{p[0]}", await bot_link(),
        )
    except platega.PlategaLimit as e:
        await call.answer(str(e), show_alert=True)
        return
    except Exception as e:
        logging.exception("platega create failed")
        for admin_id in admin_ids():
            try:
                await bot.send_message(admin_id, f"⚠️ Platega: не удалось создать платёж.\n{str(e)[:400]}")
            except Exception:
                pass
        await call.answer("Не удалось создать платёж, попробуй другой способ или напиши в поддержку", show_alert=True)
        return
    await db.pg_add(tx_id, user_id, p[0], final_price, promo_code or "-")
    await show(
        user_id,
        f"{label}\nСумма: {final_price}{config.CURRENCY}\n\n"
        f"Нажми «Перейти к оплате», оплати и вернись сюда. Бот сам увидит оплату "
        f"(обычно в течение минуты) и оформит заказ. Если не сработало - нажми «Проверить оплату».",
        reply_markup=pay_auto_kb(url, tx_id),
    )
    await call.answer()


DEFAULT_POST_PAY = config.POST_PAY_DEFAULT

# ---- рассылка из админки мини-аппа (текст + необязательная кнопка-ссылка) ----
BCAST = {"running": False, "total": 0, "sent": 0, "failed": 0}
_BCAST_TASKS = set()


async def broadcast_run(audience, text, btn_text, btn_url, admin_id):
    try:
        if audience == "me":
            ids = [admin_id]
        elif audience == "reg":
            ids = await db.account_user_ids()
        else:
            ids = await db.all_user_ids()
        BCAST["total"] = len(ids)
        kb = None
        if btn_url:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=btn_text or "Открыть", url=btn_url)]])
        for uid in ids:
            for attempt in (1, 2):
                try:
                    await bot.send_message(uid, text, reply_markup=kb,
                                           link_preview_options=LinkPreviewOptions(is_disabled=True))
                    BCAST["sent"] += 1
                    break
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
                    if attempt == 2:
                        BCAST["failed"] += 1
                except Exception:
                    BCAST["failed"] += 1  # бот заблокирован, чат удалён и т.п.
                    break
            await asyncio.sleep(0.05)
    except Exception:
        logging.exception("broadcast failed")
    finally:
        BCAST["running"] = False


def broadcast_start(audience, text, btn_text, btn_url, admin_id):
    if BCAST["running"]:
        return False
    BCAST.update(running=True, total=0, sent=0, failed=0)  # сразу, до старта задачи: защита от двойного запуска
    task = asyncio.create_task(broadcast_run(audience, text, btn_text, btn_url, admin_id))
    _BCAST_TASKS.add(task)
    task.add_done_callback(_BCAST_TASKS.discard)
    return True


async def send_post_pay_notice(user_id):
    """Объявление покупателю в бот сразу после оплаты: текст и ссылка задаются в админке мини-аппа."""
    if (await db.get_setting("post_pay_on", "1")) != "1":
        return
    text = (await db.get_setting("post_pay_text")) or DEFAULT_POST_PAY
    url = (await db.get_setting("post_pay_url")) or config.CHANNEL_URL or config.REVIEWS_URL
    kb = None
    if url:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Наш канал", url=url)]])
    try:
        await bot.send_message(user_id, text, reply_markup=kb,
                               link_preview_options=LinkPreviewOptions(is_disabled=True))
    except Exception:
        logging.warning("не удалось отправить объявление после оплаты %s", user_id)


async def make_invoice_link(title, description, payload, stars):
    """Ссылка на счёт в Telegram Stars (для мини-аппа). Оплату обрабатывает process_successful_payment."""
    return await bot.create_invoice_link(
        title=title[:32], description=description[:255], payload=payload, currency="XTR",
        prices=[LabeledPrice(label=title[:32], amount=stars)],
    )


CASE_DROPS = ("Brawl Pass", "Brawl Pass Plus", "Pro Pass")


def roll_case_name(name):
    """Pass Case: каждый выпавший пасс выбирается на сервере, шансы равные (по 1/3). Результат дописывается в название заказа."""
    import random
    import re as _re
    if "Pass Case" not in (name or "") or "выпало:" in name:
        return name
    m = _re.search(r"Pass Case ×(\d+)", name)
    qty = int(m.group(1)) if m else 1
    rng = random.SystemRandom()
    drops = [rng.choice(CASE_DROPS) for _ in range(max(1, min(qty, 30)))]
    return f"{name} - выпало: {', '.join(drops)}"


async def finalize_platega(tx_id):
    if not await db.pg_claim(tx_id, "paid"):
        return
    tx = await db.pg_get(tx_id)
    _, user_id, product_id, price, promo, _, _ = tx
    p = await resolve_product(product_id)
    name = roll_case_name(p[1] if p else "товар")
    order_id = await db.create_order(user_id, product_id, name, price, status="confirmed")
    await db.decrement_stock(product_id)
    if product_id < 0:
        await db.cart_clear(user_id)
    await db.pg_set_order(tx_id, order_id)
    try:
        await state_for(user_id).clear()
    except Exception:
        pass
    await show(
        user_id,
        f"✅ Оплата прошла! Заказ №{order_id} «{name}» оформлен.\n"
        f"Жди товар - админ пришлёт детали прямо здесь.\n\n"
        f"Когда товар будет выдан, сюда придёт кнопка, чтобы подтвердить получение и оставить отзыв.",
        reply_markup=order_wait_kb(order_id),
    )
    await send_post_pay_notice(user_id)
    try:
        chat = await bot.get_chat(user_id)
        username = chat.username or chat.first_name
    except Exception:
        username = str(user_id)
    promo_note = f" (промокод {promo})" if promo and promo != "-" else ""
    for admin_id in admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"💳 Оплачено через Platega - заказ №{order_id}\n"
                f"От: @{username} (id {user_id})\n"
                f"Товар: {name}\n"
                f"Сумма: {price}{config.CURRENCY}{promo_note}\n"
                f"Оплата уже прошла - осталось выдать товар.",
                reply_markup=order_paid_admin_kb(order_id),
            )
        except Exception:
            pass


async def cancel_platega(tx_id):
    if not await db.pg_claim(tx_id, "canceled"):
        return
    tx = await db.pg_get(tx_id)
    user_id = tx[1]
    try:
        await state_for(user_id).clear()
    except Exception:
        pass
    await show(
        user_id,
        "Платёж не прошёл или истёк срок оплаты 🙁 Попробуй оформить заказ ещё раз.",
        reply_markup=main_menu_kb(is_admin(user_id)),
    )


async def publish_review(order_id, username, product_name, price, text):
    """Публикация отзыва в канал (для отзывов, оставленных на сайте). Возвращает True, если ушло в канал."""
    channel = reviews_channel()
    if not channel:
        return False
    try:
        await bot.send_message(channel, format_review_post(order_id, username, product_name, price, text),
                               reply_markup=buy_donate_kb())
        return True
    except Exception:
        logging.exception("Не удалось опубликовать отзыв в канал %s", channel)
        return False


@router.callback_query(F.data == "admin:chats")
async def cb_admin_chats(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    rows = await db.chat_recent(15)
    b = InlineKeyboardBuilder()
    if not rows:
        text = "💬 Чатов с покупателями пока нет."
    else:
        text = "💬 Чаты с покупателями (последние). 🟢 покупатель ждёт ответа, ↩️ ты ответил последним:"
        for oid, sender, msg, _at, name, _status, username, uid in rows:
            who = ("@" + username) if username else str(uid)
            mark = "🟢" if sender == "buyer" else "↩️"
            _site_chat_button(b, oid, f"{mark} №{oid} {who}: {msg[:24]}")
    b.button(text="Назад", callback_data="admin_open")
    b.adjust(1)
    await show(call.from_user.id, text, reply_markup=b.as_markup())
    await call.answer()


async def apply_platega_status(tx_id, status):
    if status == "CONFIRMED":
        await finalize_platega(tx_id)
    elif status == "CANCELED":
        await cancel_platega(tx_id)


@router.callback_query(F.data.startswith("pgcheck:"))
async def cb_platega_check(call):
    tx_id = call.data.split(":", 1)[1]
    tx = await db.pg_get(tx_id)
    if not tx or tx[1] != call.from_user.id:
        await call.answer("Платёж не найден", show_alert=True)
        return
    if tx[5] == "paid":
        await call.answer("Оплата уже принята, заказ оформлен ✅", show_alert=True)
        return
    try:
        status = await platega.get_status(tx_id)
    except Exception:
        logging.exception("platega status failed")
        await call.answer("Не получилось проверить, попробуй через минуту", show_alert=True)
        return
    if status in ("CONFIRMED", "CANCELED"):
        await apply_platega_status(tx_id, status)
        await call.answer()
        return
    await call.answer("Оплата пока не поступила. Если уже оплатил, подожди минуту и нажми снова", show_alert=True)


async def platega_poller():
    while True:
        await asyncio.sleep(10)
        try:
            for tx_id in await db.pg_pending():
                try:
                    status = await platega.get_status(tx_id)
                except Exception:
                    logging.exception("platega poll failed")
                    continue
                await apply_platega_status(tx_id, status)
        except Exception:
            logging.exception("platega poller crashed iteration")


@router.callback_query(F.data == "pay_paid", StateFilter(Purchase.method))
async def cb_pay_paid(call, state):
    data = await state.get_data()
    method = data.get("method", "?")
    p = await resolve_product(data["product_id"])
    await state.clear()
    if not p or not p[5]:
        await show(call.from_user.id, "Этот товар уже недоступен 🙁", reply_markup=main_menu_kb(is_admin(call.from_user.id)))
        await call.answer()
        return
    name = p[1]
    final_price = data["final_price"]
    promo_code = data.get("promo_code")
    promo_note = f" (промокод {promo_code})" if promo_code else ""
    user_id = call.from_user.id
    username = call.from_user.username or call.from_user.first_name

    order_id = await db.create_order(user_id, data["product_id"], name, final_price, status="pending")
    if data["product_id"] < 0:
        await db.cart_clear(user_id)
    await show(
        user_id,
        f"Заявка №{order_id} на «{name}» отправлена продавцу 📨\n"
        f"Как только он проверит оплату - подтвердит заказ прямо здесь, в боте.",
        reply_markup=main_menu_kb(is_admin(user_id)),
    )
    for admin_id in admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"🛒 Новый заказ №{order_id} (нужно проверить оплату вручную)\n"
                f"От: @{username} (id {user_id})\n"
                f"Товар: {name}\n"
                f"Цена: {final_price}{config.CURRENCY}{promo_note}\n"
                f"Способ оплаты: {PAY_METHODS.get(method, method)}",
                reply_markup=order_admin_kb(order_id),
            )
        except Exception:
            pass
    await call.answer()


@router.callback_query(F.data.startswith("order_ok:"))
async def cb_order_ok(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order[5] != "pending":
        await call.answer("Заказ уже обработан", show_alert=True)
        return
    _, buyer_id, product_id, product_name, price, _ = order

    await db.decrement_stock(product_id)
    await db.set_order_status(order_id, "confirmed")

    await call.message.edit_text(call.message.text + "\n\n✅ Принято", reply_markup=order_paid_admin_kb(order_id))
    try:
        await bot.send_message(
            buyer_id,
            f"✅ Продавец подтвердил оплату заказа №{order_id} «{product_name}»!\n"
            f"Жди товар - детали пришлют здесь же.\n\n"
            f"Когда товар будет выдан, сюда придёт кнопка, чтобы подтвердить получение и оставить отзыв.",
            reply_markup=order_wait_kb(order_id),
        )
    except Exception:
        pass
    await send_post_pay_notice(buyer_id)
    await call.answer("Заказ принят")


@router.callback_query(F.data.startswith("order_no:"))
async def cb_order_no(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order[5] != "pending":
        await call.answer("Заказ уже обработан", show_alert=True)
        return
    _, buyer_id, product_id, product_name, price, _ = order
    await db.set_order_status(order_id, "rejected")
    await call.message.edit_text(call.message.text + "\n\n❌ Отклонено")
    try:
        await bot.send_message(
            buyer_id,
            f"❌ По заказу №{order_id} «{product_name}» продавец отказал.\n"
            f"Можешь написать ему прямо тут, если есть вопросы.",
        )
    except Exception:
        pass
    await call.answer("Заказ отклонён")


async def deliver_order(order_id):
    """Отметить заказ выданным и отправить покупателю кнопку подтверждения (то же, что кнопка в боте)."""
    order = await db.get_order(order_id)
    if not order:
        return False, "Заказ не найден"
    _, buyer_id, _pid, product_name, _price, status = order
    if status == "completed" or await db.order_is_delivered(order_id):
        return False, "Этот заказ уже выдан"
    if status != "confirmed" or not await db.set_order_delivered(order_id):
        return False, "Заказ ещё не оплачен или уже обработан"
    try:
        await bot.send_message(
            buyer_id,
            f"📦 Заказ №{order_id} «{product_name}» выдан!\n\n"
            f"Всё получил? Нажми кнопку ниже, чтобы закрыть заказ. После этого можно оставить отзыв.",
            reply_markup=order_confirm_kb(order_id),
        )
        return True, "Отмечено, покупателю отправил кнопку"
    except Exception:
        return True, "Отметил, но покупатель не получил сообщение (мог заблокировать бота)"


@router.callback_query(F.data.startswith("order_deliv:"))
async def cb_order_delivered(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    _, buyer_id, product_id, product_name, price, status = order
    if status == "completed" or await db.order_is_delivered(order_id):
        await call.answer("Этот заказ уже отмечен как выданный", show_alert=True)
        return
    if status != "confirmed" or not await db.set_order_delivered(order_id):
        await call.answer("Заказ ещё не оплачен или уже обработан", show_alert=True)
        return
    try:
        await call.message.edit_text(
            (call.message.text or f"Заказ №{order_id}") + "\n\n📦 Выдано, покупателю отправил кнопку подтверждения",
            reply_markup=order_chat_kb(order_id),
        )
    except Exception:
        pass
    try:
        await bot.send_message(
            buyer_id,
            f"📦 Заказ №{order_id} «{product_name}» выдан!\n\n"
            f"Всё получил? Нажми кнопку ниже, чтобы закрыть заказ. После этого можно оставить отзыв.",
            reply_markup=order_confirm_kb(order_id),
        )
        await call.answer("Отмечено, покупателю отправил кнопку")
    except Exception:
        await call.answer("Отметил, но покупатель не получил сообщение (мог заблокировать бота)", show_alert=True)


@router.callback_query(F.data.startswith("order_done:"))
async def cb_order_done(call):
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order[1] != call.from_user.id:
        await call.answer("Это не твой заказ", show_alert=True)
        return
    if order[5] == "completed":
        await call.answer("Этот заказ уже закрыт ✅", show_alert=True)
        return
    if order[5] != "confirmed":
        await call.answer("Заказ ещё не в статусе для закрытия", show_alert=True)
        return
    if not await db.order_is_delivered(order_id):
        await call.answer(
            "Продавец ещё не выдал товар. Кнопка подтверждения придёт сюда, когда заказ будет выдан 🙏",
            show_alert=True,
        )
        return
    await db.set_order_status(order_id, "completed")
    await show(
        call.from_user.id,
        "Отлично, заказ закрыт ✅ Спасибо за покупку!\n"
        "Оставишь пару слов отзыва? Это очень помогает магазину.",
        reply_markup=review_offer_kb(order_id),
    )
    await call.answer()

    for admin_id in admin_ids():
        try:
            await bot.send_message(admin_id, f"👍 Покупатель подтвердил получение по заказу №{order_id}")
        except Exception:
            pass


@router.callback_query(F.data.startswith("review_start:"))
async def cb_review_start(call, state):
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order[1] != call.from_user.id:
        await call.answer("Это не твой заказ", show_alert=True)
        return
    if order[5] != "completed":
        await call.answer("Сначала подтверди получение заказа", show_alert=True)
        return
    if await db.has_review(order_id):
        await call.answer("Отзыв по этому заказу уже есть, спасибо 🙏", show_alert=True)
        return
    _, buyer_id, product_id, product_name, price, _ = order
    await state.set_data({"order_id": order_id, "product_name": product_name, "price": price})
    await state.set_state(LeaveReview.text)
    await show(
        call.from_user.id,
        f"Напиши пару слов об отзыве обычным сообщением сюда в чат (до {REVIEW_MAX} символов, "
        "отвечать на это сообщение не нужно).\n"
        "Если передумал, нажми «Отмена» или отправь /skip.",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(Command("skip"), StateFilter(LeaveReview.text))
async def skip_review(message, state):
    await state.clear()
    await message.answer("Ладно, без отзыва так без отзыва 👌", reply_markup=main_menu_kb(is_admin(message.from_user.id)))


@router.message(LeaveReview.text)
async def handle_review_text(message, state):
    text = (message.text or "").strip()
    if not text:
        await show(message.from_user.id, "Напиши отзыв текстом или нажми «Отмена».", reply_markup=cancel_kb())
        return
    if len(text) > REVIEW_MAX:
        await show(
            message.from_user.id,
            f"Получилось длинно ({len(text)} символов). Сократи до {REVIEW_MAX} и отправь ещё раз.",
            reply_markup=cancel_kb(),
        )
        return
    data = await state.get_data()
    await state.update_data(text=text)
    if "photo" in data:
        await show_review_preview(message.from_user.id, state)
        return
    await show(
        message.from_user.id,
        "Добавишь фото к отзыву? Пришли картинку, или /skip если без фото.",
        reply_markup=cancel_kb(),
    )
    await state.set_state(LeaveReview.photo)


@router.message(Command("skip"), StateFilter(LeaveReview.photo))
async def skip_review_photo(message, state):
    await state.update_data(photo=None)
    await show_review_preview(message.from_user.id, state)


@router.message(LeaveReview.photo, F.photo)
async def handle_review_photo(message, state):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await show_review_preview(message.from_user.id, state)


@router.message(LeaveReview.photo)
async def handle_review_photo_wrong_type(message, state):
    await show(
        message.from_user.id,
        "Пришли именно картинку (фото), или /skip если без фото.",
        reply_markup=cancel_kb(),
    )


async def show_review_preview(user_id, state):
    data = await state.get_data()
    order_id = data["order_id"]
    product_name = data["product_name"]
    price = data["price"]
    text = data["text"]
    photo = data.get("photo")

    post_text = format_review_post(order_id, "ты", product_name, price, text)
    caption = (
        "Вот так будет выглядеть отзыв - всё верно?\n\n"
        f"{post_text}" + ("" if photo else "\n\n(без фото)")
    )
    await state.set_state(LeaveReview.confirm)
    await show(user_id, caption, reply_markup=review_preview_kb(), photo=photo)


@router.callback_query(F.data == "review_edit_text", StateFilter(LeaveReview.confirm))
async def cb_review_edit_text(call, state):
    await show(call.from_user.id, "Напиши новый текст отзыва:", reply_markup=cancel_kb())
    await state.set_state(LeaveReview.text)
    await call.answer()


@router.callback_query(F.data == "review_edit_photo", StateFilter(LeaveReview.confirm))
async def cb_review_edit_photo(call, state):
    await show(
        call.from_user.id,
        "Пришли новое фото, или /skip чтобы убрать фото из отзыва.",
        reply_markup=cancel_kb(),
    )
    await state.set_state(LeaveReview.photo)
    await call.answer()


@router.callback_query(F.data == "review_drop", StateFilter(LeaveReview.confirm))
async def cb_review_drop(call, state):
    await state.clear()
    await show(
        call.from_user.id,
        "Ладно, без отзыва так без отзыва 👌",
        reply_markup=main_menu_kb(is_admin(call.from_user.id)),
    )
    await call.answer()


@router.callback_query(F.data == "review_pub", StateFilter(LeaveReview.confirm))
async def cb_review_publish(call, state):
    data = await state.get_data()
    order_id = data["order_id"]
    product_name = data["product_name"]
    price = data["price"]
    text = data["text"]
    photo = data.get("photo")
    username = call.from_user.username or call.from_user.first_name

    if await db.has_review(order_id):
        await state.clear()
        await show(call.from_user.id, "Отзыв по этому заказу уже есть, спасибо 🙏",
                   reply_markup=main_menu_kb(is_admin(call.from_user.id)))
        await call.answer()
        return
    post_text = format_review_post(order_id, username, product_name, price, text)
    await db.add_review(order_id, call.from_user.id, username, product_name, price, text, photo)
    channel = reviews_channel()
    posted = False
    if channel:
        try:
            if photo:
                await bot.send_photo(channel, photo, caption=post_text, reply_markup=buy_donate_kb())
            else:
                await bot.send_message(channel, post_text, reply_markup=buy_donate_kb())
            posted = True
        except Exception:
            logging.exception("Не удалось опубликовать отзыв в канал %s", channel)
    if posted:
        msg = "Спасибо большое за отзыв, реально помогает! Уже выложил в канал 🙏"
    else:
        msg = "Спасибо большое за отзыв, реально помогает! 🙏 Он сохранён и виден в разделе «Отзывы»."
        for admin_id in admin_ids():
            try:
                await bot.send_message(
                    admin_id,
                    "⚠️ Отзыв сохранён, но в канал не ушёл. "
                    + ("REVIEWS_CHANNEL не задан в config.py / переменных окружения."
                       if not channel else
                       f"Проверь, что бот админ канала {channel} с правом постить.")
                )
            except Exception:
                pass
    await show(call.from_user.id, msg, reply_markup=main_menu_kb(is_admin(call.from_user.id)))
    await state.clear()
    await call.answer()


@router.callback_query(F.data.startswith("order_chat:"))
async def cb_order_chat(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    buyer_id = order[1]
    await start_admin_chat(call.message, state, call.from_user.id, buyer_id)
    await call.answer()


@router.callback_query(F.data.startswith("chat:"))
async def cb_chat_user(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    buyer_id = int(call.data.split(":")[1])
    await start_admin_chat(call.message, state, call.from_user.id, buyer_id)
    await call.answer()


async def start_admin_chat(message, state, admin_id, buyer_id):
    await state.update_data(target_id=buyer_id)
    await state.set_state(AdminChat.text)
    await message.answer(
        f"Пишешь покупателю (id {buyer_id}). Всё, что напишешь дальше - уходит ему от лица продавца.\n"
        f"Когда закончишь - отправь /endchat."
    )
    try:
        buyer_state = state_for(buyer_id)
        await buyer_state.update_data(admin_id=admin_id)
        await buyer_state.set_state(BuyerChat.active)
        await bot.send_message(
            buyer_id,
            "💬 С тобой сейчас свяжется продавец прямо здесь. Просто пиши ответы в бот."
        )
    except Exception:
        pass


@router.callback_query(F.data == "chat_admin")
async def cb_chat_admin(call, state):
    admin_id = admin_ids()[0] if admin_ids() else None
    await state.update_data(admin_id=admin_id)
    await state.set_state(BuyerChat.active)
    await call.message.answer("Пиши сообщение - оно уйдёт продавцу. Когда закончишь - /endchat.")
    await call.answer()


@router.message(Command("endchat"))
async def cmd_endchat(message, state):
    current = await state.get_state()
    if current == AdminChat.text.state:
        data = await state.get_data()
        target_id = data.get("target_id")
        await state.clear()
        if target_id:
            try:
                await state_for(target_id).clear()
                await bot.send_message(target_id, "Диалог с продавцом завершён.")
            except Exception:
                pass
        await message.answer("Диалог закрыт.", reply_markup=admin_menu_kb())
    elif current == BuyerChat.active.state:
        data = await state.get_data()
        admin_id = data.get("admin_id")
        await state.clear()
        if admin_id:
            try:
                await bot.send_message(admin_id, f"Покупатель (id {message.from_user.id}) завершил диалог.")
            except Exception:
                pass
        await message.answer("Диалог закрыт.", reply_markup=main_menu_kb(is_admin(message.from_user.id)))


@router.message(AdminChat.text)
async def handle_admin_chat(message, state):
    data = await state.get_data()
    target_id = data.get("target_id")
    try:
        await bot.send_message(target_id, f"💬 Продавец:\n{db.clean_text(message.text)}")
        await message.answer("Отправлено 👌 (напиши ещё или /endchat, чтобы закрыть диалог)")
    except Exception:
        await message.answer("Не получилось отправить - покупатель мог заблокировать бота.")


@router.message(BuyerChat.active)
async def handle_buyer_chat(message, state):
    data = await state.get_data()
    admin_id = data.get("admin_id")
    username = message.from_user.username or message.from_user.first_name
    try:
        await bot.send_message(admin_id, f"💬 Покупатель @{username} (id {message.from_user.id}):\n{message.text}")
        await message.answer("Отправлено продавцу 👌")
    except Exception:
        await message.answer("Не получилось отправить, попробуй позже.")


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    if not payload.startswith("order:"):
        return
    _, product_id, price, promo = payload.split(":")
    product_id = int(product_id)
    price = int(price)
    p = await resolve_product(product_id)
    name = roll_case_name(p[1] if p else "товар")
    stars = payment.total_amount

    order_id = await db.create_order(user_id, product_id, name, price, status="confirmed")
    await db.decrement_stock(product_id)
    if product_id < 0:
        await db.cart_clear(user_id)
    promo_note = f" (промокод {promo})" if promo != "-" else ""
    await show(
        user_id,
        f"✅ Оплата {stars}⭐ прошла! Заказ №{order_id} «{name}» оформлен.\n"
        f"Жди товар - админ пришлёт детали прямо здесь.\n\n"
        f"Когда товар будет выдан, сюда придёт кнопка, чтобы подтвердить получение и оставить отзыв.",
        reply_markup=order_wait_kb(order_id),
    )
    await send_post_pay_notice(user_id)
    for admin_id in admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"⭐ Оплачено Stars - заказ №{order_id}\n"
                f"От: @{username} (id {user_id})\n"
                f"Товар: {name}\n"
                f"Сумма: {price}{config.CURRENCY}{promo_note} = {stars}⭐\n"
                f"Оплата уже прошла - осталось выдать товар.",
                reply_markup=order_paid_admin_kb(order_id),
            )
        except Exception:
            pass


DOCS_DATE = "28.09.2026"

DEFAULT_DOCS = {
    "account_check": (
        "🔍 Проверка аккаунта перед покупкой\n\n"
        "Перед оплатой обязательно проверьте, можно ли донатить на ваш аккаунт:\n"
        "1. Войдите в store.supercell.com через свой Supercell ID.\n"
        "2. Добавьте в корзину любой товар (покупать его не нужно - только для проверки).\n"
        "3. Перейдите к оплате.\n"
        "   ☑ Если открылось обычное окно оплаты картой - аккаунт подходит, можно оформлять заказ у нас.\n"
        "   ❌ Если появилась ошибка - на этот аккаунт покупку выполнить нельзя, не оплачивайте заказ.\n\n"
        "Если основной аккаунт не подходит, можно проверить дополнительный аккаунт и после получения "
        "передать товар на основной способом, доступным в игре.\n\n"
        "⚠️ Если вы оплатили заказ, не проверив аккаунт заранее, и он оказался неподходящим - "
        "возврат средств невозможен."
    ),
    "terms": (
        "📜 Пользовательское соглашение\n"
        f"Редакция от {DOCS_DATE}\n\n"
        "1. Общие положения. Этот бот (далее - «Магазин») оформляет заказы на цифровые товары "
        "для мобильных игр (внутриигровая валюта, пропуски и др.). Оформляя заказ, пользователь "
        "принимает условия этого соглашения.\n\n"
        "2. Цены. Актуальные цены указаны в каталоге и в разделе «Цены и тарифы». Сумма, которую "
        "пользователь видит перед оплатой, окончательная - комиссия платёжной системы уже включена.\n\n"
        "3. Аккаунт. Перед покупкой пользователь сам проверяет, что на его аккаунт можно совершать "
        "донат, и указывает верные данные для выдачи товара.\n\n"
        "4. Выдача. После подтверждения оплаты товар выдаётся в чате с ботом. Пользователь подтверждает "
        "получение кнопкой в боте.\n\n"
        "5. Риски. Издатель игры может отменить (откатить) донат - вероятность оценивается примерно в 15%. "
        "Магазин не отвечает за решения издателя игры; по такому случаю нужно написать в поддержку.\n\n"
        "6. Возврат. Если товар не был выдан по вине Магазина, пользователь может обратиться в поддержку "
        "- вопрос решается индивидуально.\n\n"
        "7. Контакты. Способы связи - в разделе «Контакты поддержки»."
    ),
    "privacy": (
        "🔒 Политика конфиденциальности\n"
        f"Редакция от {DOCS_DATE}\n\n"
        "1. Какие данные собираем: Telegram ID, имя пользователя (username), историю заказов, "
        "текст обращений в поддержку и отзывов.\n\n"
        "2. Зачем: чтобы оформить и выдать заказ, связаться с пользователем, вести учёт покупок "
        "и отвечать на обращения.\n\n"
        "3. Передача третьим лицам: данные не продаются и не передаются, кроме случаев, когда это "
        "нужно для проведения платежа (платёжные системы) или требуется по закону.\n\n"
        "4. Хранение: данные хранятся, пока это нужно для работы Магазина и учёта заказов.\n\n"
        "5. Права пользователя: можно запросить удаление своих данных, написав в поддержку.\n\n"
        "6. Контакты - в разделе «Контакты поддержки»."
    ),
    "support": (
        "📞 Контакты поддержки\n\n"
        "Telegram: @Phonker_sup\n"
        f"Время работы: {config.WORK_HOURS_START}:00-{config.WORK_HOURS_END}:00 по МСК."
    ),
}


async def get_doc_text(key):
    if key == "prices":
        return await build_prices_text()
    value = await db.get_setting(f"doc_{key}")
    return value if value else DEFAULT_DOCS[key]


async def build_prices_text():
    lines = ["💰 Цены и тарифы", "Актуальные цены на товары (комиссия платёжных систем уже включена):", ""]
    any_products = False
    for cat in await db.list_categories(active_only=True):
        products = await db.list_products(category=cat[0])
        if not products:
            continue
        any_products = True
        game = GAME_NAMES.get(cat[1], cat[1])
        lines.append(f"{game} · {cat[2]}")
        for p in products:
            lines.append(f"  • {p[1]} - {p[3]}{config.CURRENCY}")
        lines.append("")
    if not any_products:
        lines.append("Каталог пока пуст.")
    lines.append(
        f"Оплата Telegram Stars: цена в ⭐ = цена в {config.CURRENCY} / {config.STARS_TO_RUB}, "
        "с округлением вверх."
    )
    return "\n".join(lines)


@router.callback_query(F.data == "docs")
async def cb_docs(call):
    await show(
        call.from_user.id,
        "📄 Документы магазина:",
        reply_markup=docs_kb(await pay_urls()),
        photo=banner("docs"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("doc:"))
async def cb_doc_view(call):
    _, key, origin = call.data.split(":")
    if key not in DOC_TITLES:
        await call.answer()
        return
    text = await get_doc_text(key)
    back_cb = "pay_notice_back" if origin == "notice" else "docs"
    await show(call.from_user.id, text[:4000], reply_markup=doc_back_kb(back_cb))
    await call.answer()



async def send_db_backup(chat_id, reason="Копия базы"):
    ok = await dbsafe.send_backup(
        bot, config.DB_PATH, [chat_id], reason,
        everyone=False, silent=False, set_ref=False, allow_empty=True,
    )
    if not ok:
        raise RuntimeError("backup was not sent")


@router.message(Command("admin"))
async def cmd_admin(message):
    if not is_admin(message.from_user.id):
        return
    await show(message.from_user.id, "Админка. Погнали:", reply_markup=admin_menu_kb())


ORDER_STATUS_ADMIN = {
    "pending": "⏳ ждёт проверки оплаты",
    "completed": "✅ завершён",
    "rejected": "❌ отклонён",
}


async def render_admin_orders(call, todo):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    rows = await db.admin_orders(todo=todo, limit=20)
    title = "📦 Ждут действия (принять или выдать):" if todo else "📋 Последние заказы:"
    if not rows:
        title += "\n\nПока пусто."
    else:
        title += "\nНажми на заказ - увидишь детали и кнопки."
    await show(call.from_user.id, title, reply_markup=admin_orders_kb(rows, todo))
    await call.answer()


@router.callback_query(F.data == "admin:orders")
async def cb_admin_orders(call):
    await render_admin_orders(call, False)


@router.callback_query(F.data == "admin:orders_todo")
async def cb_admin_orders_todo(call):
    await render_admin_orders(call, True)


@router.callback_query(F.data.startswith("aorder:"))
async def cb_admin_order_view(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    row = await db.admin_order(int(call.data.split(":")[1]))
    if not row:
        await call.answer("Заказ не найден", show_alert=True)
        return
    order_id, name, price, status, delivered, uid, username, created = row
    if status == "confirmed":
        label = "📬 выдан, ждём подтверждения покупателя" if delivered else "📦 оплачен, нужно выдать товар"
    else:
        label = ORDER_STATUS_ADMIN.get(status, status)
    text = (
        f"Заказ №{order_id}\n"
        f"Покупатель: @{username or '-'} (id {uid})\n"
        f"Товар: {name}\n"
        f"Сумма: {price}{config.CURRENCY}\n"
        f"Статус: {label}\n"
        f"Создан: {created} (UTC)"
    )
    await show(call.from_user.id, text, reply_markup=admin_order_view_kb(order_id, status, delivered))
    await call.answer()


@router.callback_query(F.data == "admin:files")
async def cb_admin_files(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    try:
        await send_db_backup(call.from_user.id, "Копия базы по кнопке")
        await call.answer("Файл отправлен")
    except Exception as e:
        logging.exception("send db file failed")
        await call.answer("Не получилось отправить файл", show_alert=True)


@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    count = await db.user_count()
    products = await db.list_products(active_only=False)
    orders = await db.order_count()
    revenue = await db.total_revenue()
    await show(
        call.from_user.id,
        f"📊 Статистика:\n"
        f"Пользователей: {count}\n"
        f"Товаров в базе: {len(products)}\n"
        f"Заказов: {orders}\n"
        f"Продано на: {revenue}{config.CURRENCY}",
        reply_markup=admin_menu_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:users")
async def cb_admin_users(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    st = await db.user_stats()
    await show(
        call.from_user.id,
        "👥 Пользователи бота:\n\n"
        f"Всего: {st['total']}\n"
        f"Новых за 24 часа: {st['new_24h']}\n"
        f"Новых за 7 дней: {st['new_7d']}\n"
        f"Были в боте за 24 часа: {st['active_24h']}\n"
        f"Были в боте за 7 дней: {st['active_7d']}",
        reply_markup=admin_users_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:users_export")
async def cb_admin_users_export(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    import csv
    import io
    rows = await db.list_users_full()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "username", "имя", "первый вход (UTC)", "последняя активность (UTC)"])
    for r in rows:
        w.writerow(r)
    data = ("\ufeff" + buf.getvalue()).encode("utf-8")
    await bot.send_document(
        call.from_user.id,
        BufferedInputFile(data, filename="users_1.csv"),
        caption=f"👥 Пользователей: {len(rows)}",
    )
    await call.answer()


async def payments_status():
    return {
        "stars": (await db.get_setting("pay_stars_on", "1")) == "1",
        "crypto": bool(await db.get_setting("pay_crypto_url")),
        "sbp": bool(await db.get_setting("pay_sbp_url")),
    }


@router.callback_query(F.data == "admin:payments")
async def cb_admin_payments(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await show(
        call.from_user.id,
        "💳 Способы оплаты. ✅ - покупатель видит этот способ, 🚫 - скрыт.\n"
        "Крипта и СБП появляются, когда задана ссылка.",
        reply_markup=admin_payments_kb(await payments_status()),
    )
    await call.answer()


@router.callback_query(F.data.startswith("payset:"))
async def cb_admin_pay_method(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    status = await payments_status()
    if code in ("crypto", "sbp"):
        url = await db.get_setting(f"pay_{code}_url")
        info = f"Ссылка: {url}" if url else "Ссылка не задана - способ скрыт от покупателей."
    else:
        info = "Оплата звёздами работает автоматически."
    await show(
        call.from_user.id,
        f"{PAY_METHODS[code]}\n\n{info}",
        reply_markup=admin_pay_method_kb(code, status[code]),
    )
    await call.answer()


@router.callback_query(F.data == "paytoggle:stars")
async def cb_admin_toggle_stars(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    on = (await db.get_setting("pay_stars_on", "1")) == "1"
    await db.set_setting("pay_stars_on", "0" if on else "1")
    await show(
        call.from_user.id,
        "💳 Способы оплаты:",
        reply_markup=admin_payments_kb(await payments_status()),
    )
    await call.answer("Готово")


@router.callback_query(F.data.startswith("paylink:"))
async def cb_admin_pay_link(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    await state.update_data(pay_code=code)
    await show(
        call.from_user.id,
        f"Пришли ссылку на оплату ({PAY_METHODS[code]}), начиная с https://",
        reply_markup=cancel_kb(),
    )
    await state.set_state(SetPayLink.value)
    await call.answer()


@router.message(SetPayLink.value)
async def handle_pay_link(message, state):
    url = message.text.strip()
    if not url.lower().startswith("http"):
        await show(message.from_user.id, "Ссылка должна начинаться с https://", reply_markup=cancel_kb())
        return
    data = await state.get_data()
    await db.set_setting(f"pay_{data['pay_code']}_url", url)
    await state.clear()
    await show(
        message.from_user.id,
        "✅ Ссылка сохранена.",
        reply_markup=admin_payments_kb(await payments_status()),
    )


@router.callback_query(F.data.startswith("paylinkdel:"))
async def cb_admin_pay_link_del(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    await db.delete_setting(f"pay_{code}_url")
    await show(
        call.from_user.id,
        "🗑 Ссылку убрал, способ скрыт от покупателей.",
        reply_markup=admin_payments_kb(await payments_status()),
    )
    await call.answer()


@router.callback_query(F.data == "admin:docs")
async def cb_admin_docs(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await show(
        call.from_user.id,
        "📄 Документы. Можно задать свой текст или ссылку (например на telegra.ph). "
        "«Цены и тарифы» собираются из каталога автоматически.",
        reply_markup=admin_docs_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("docedit:"))
async def cb_admin_doc_edit(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    key = call.data.split(":", 1)[1]
    current = await db.get_setting(f"doc_{key}")
    note = "Сейчас: свой текст/ссылка." if current else "Сейчас: стандартный текст."
    await show(
        call.from_user.id,
        f"{DOC_TITLES[key]}\n{note}\n\n{(current or DEFAULT_DOCS[key])[:3000]}",
        reply_markup=admin_doc_edit_kb(key),
    )
    await call.answer()


@router.callback_query(F.data.startswith("docset:"))
async def cb_admin_doc_set(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    key = call.data.split(":", 1)[1]
    await state.update_data(doc_key=key)
    await show(
        call.from_user.id,
        "Пришли текст документа одним сообщением, либо ссылку (https://...) - "
        "тогда кнопка в боте будет открывать её.",
        reply_markup=cancel_kb(),
    )
    await state.set_state(SetDoc.value)
    await call.answer()


@router.message(SetDoc.value)
async def handle_doc_value(message, state):
    data = await state.get_data()
    await db.set_setting(f"doc_{data['doc_key']}", message.text.strip())
    await state.clear()
    await show(message.from_user.id, "✅ Документ обновил.", reply_markup=admin_docs_kb())


@router.callback_query(F.data.startswith("docreset:"))
async def cb_admin_doc_reset(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await db.delete_setting(f"doc_{call.data.split(':', 1)[1]}")
    await show(call.from_user.id, "♻️ Вернул стандартный текст.", reply_markup=admin_docs_kb())
    await call.answer()


@router.callback_query(F.data == "admin:find_user")
async def cb_admin_find_user(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await show(call.from_user.id, "Пришли ID пользователя или его @юзернейм:", reply_markup=cancel_kb())
    await state.set_state(FindUser.query)
    await call.answer()


@router.message(FindUser.query)
async def handle_find_user(message, state):
    await state.clear()
    user = await db.find_user(message.text)
    if not user:
        await show(
            message.from_user.id,
            "Не нашёл такого - либо опечатка, либо он ещё не писал боту.",
            reply_markup=admin_menu_kb(),
        )
        return
    user_id, username = user
    orders = await db.user_orders(user_id)
    spent = sum(o[2] for o in orders)
    await show(
        message.from_user.id,
        f"👤 Юзер найден:\n"
        f"ID: <code>{user_id}</code>\n"
        f"Юзернейм: @{username or '-'}\n"
        f"Заказов: {len(orders)}\n"
        f"Всего потратил: {spent}{config.CURRENCY}",
        reply_markup=user_found_kb(user_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:giveaway")
async def cb_admin_giveaway(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    winner = await db.random_user()
    if not winner:
        await show(call.from_user.id, "Пока нет ни одного пользователя, некого разыгрывать 🙁", reply_markup=admin_menu_kb())
        await call.answer()
        return
    user_id, username = winner
    await show(
        call.from_user.id,
        f"🎉 Рандомный победитель:\n@{username or 'без юзернейма'} (id {user_id})",
        reply_markup=giveaway_kb(user_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("giveaway_announce:"))
async def cb_giveaway_announce(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db.find_user(str(user_id))
    username = user[1] if user else None
    text = f"🎉 Розыгрыш подвели! Победитель - @{username or user_id} 🔥\nПоздравляем!"

    users = await db.all_user_ids()
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            pass
    chats = await db.all_broadcast_chats()
    for chat_id in chats:
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            pass
    try:
        await bot.send_message(user_id, "🎉 Поздравляем, ты выиграл(а) розыгрыш! С тобой скоро свяжутся.")
    except Exception:
        pass
    await show(call.from_user.id, f"Объявил победителя {sent} пользователям и во все привязанные чаты ✅", reply_markup=admin_menu_kb())
    await call.answer()


async def category_label(key):
    if not key:
        return "не задан"
    cat = await db.get_category(key)
    return cat[2] if cat else key


async def show_product_settings(user_id, product_id):
    p = await db.get_product(product_id)
    if not p:
        await show(user_id, "Товар не найден.", reply_markup=admin_menu_kb())
        return
    _, name, desc, price, stock, active, photo, category = p
    stock_text = "неограничено" if stock < 0 else f"{stock} шт."
    cat_text = await category_label(category)
    status = "🟢 включен" if active else "🔴 выключен"
    await show(
        user_id,
        f"⚙️ Настройка товара\n\n<b>{name}</b>\n{desc or ''}\n\n"
        f"Цена: {price}{config.CURRENCY}\nОстаток: {stock_text}\n"
        f"Фото: {'есть' if photo else 'нет'}\nРаздел: {cat_text}\nСтатус: {status}",
        reply_markup=product_settings_kb(product_id, bool(active), category),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("pset:"))
async def cb_product_settings(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    product_id = int(call.data.split(":")[1])
    await show_product_settings(call.from_user.id, product_id)
    await call.answer()


@router.callback_query(F.data.startswith("pmove:"))
async def cb_product_move(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    _, product_id, direction = call.data.split(":")
    moved = await db.move_product(int(product_id), direction)
    await show_product_settings(call.from_user.id, int(product_id))
    await call.answer("Переставил" if moved else "Уже крайний в разделе")


@router.callback_query(F.data.startswith("ptoggle:"))
async def cb_product_toggle(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    product_id = int(call.data.split(":")[1])
    p = await db.get_product(product_id)
    if not p:
        await call.answer("Товар не найден", show_alert=True)
        return
    await db.set_product_active(product_id, not p[5])
    await show_product_settings(call.from_user.id, product_id)
    await call.answer("Готово")


@router.callback_query(F.data.startswith("pdel:"))
async def cb_product_delete(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    product_id = int(call.data.split(":")[1])
    await db.remove_product(product_id)
    await show(call.from_user.id, "🗑 Товар удалён (скрыт из каталога).", reply_markup=admin_menu_kb())
    await call.answer()


@router.callback_query(F.data == "admin:add_product")
async def cb_admin_add_product(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await show(call.from_user.id, "Введи название товара:", reply_markup=cancel_kb())
    await state.set_state(AddProduct.name)
    await call.answer()


@router.message(AddProduct.name)
async def add_product_name(message, state):
    await state.update_data(name=message.text)
    await show(message.from_user.id, "Введи описание товара:", reply_markup=cancel_kb())
    await state.set_state(AddProduct.description)


@router.message(AddProduct.description)
async def add_product_desc(message, state):
    await state.update_data(description=message.text)
    await show(message.from_user.id, "Введи цену (число, ₽):", reply_markup=cancel_kb())
    await state.set_state(AddProduct.price)


@router.message(AddProduct.price)
async def add_product_price(message, state):
    if not message.text.isdigit():
        await show(message.from_user.id, "Введи число, например: 149", reply_markup=cancel_kb())
        return
    await state.update_data(price=int(message.text))
    await show(message.from_user.id, "Введи количество на складе (или -1 если без ограничений):", reply_markup=cancel_kb())
    await state.set_state(AddProduct.stock)


@router.message(AddProduct.stock)
async def add_product_stock(message, state):
    try:
        stock = int(message.text)
    except ValueError:
        await show(message.from_user.id, "Введи целое число, например 10 или -1", reply_markup=cancel_kb())
        return
    await state.update_data(stock=stock)
    categories = await db.list_categories(active_only=True)
    await show(message.from_user.id, "В какой раздел добавить товар?", reply_markup=category_pick_kb(categories))
    await state.set_state(AddProduct.category)


@router.callback_query(AddProduct.category, F.data.startswith("setcat:"))
async def add_product_category(call, state):
    category = call.data.split(":", 1)[1]
    if category == "_none":
        category = None
    await state.update_data(category=category)
    await show(call.from_user.id, "Пришли фото товара (или /skip, если добавишь позже):", reply_markup=cancel_kb())
    await state.set_state(AddProduct.photo)
    await call.answer()


async def finish_add_product(message, state, photo):
    data = await state.get_data()
    await db.add_product(
        data["name"], data["description"], data["price"], data["stock"],
        photo, data.get("category"),
    )
    await state.clear()
    await show(message.from_user.id, f"✅ Товар «{data['name']}» добавлен!", reply_markup=admin_menu_kb())

    chats = await db.all_broadcast_chats()
    caption = (
        f"🆕 Новый товар в магазине!\n\n<b>{data['name']}</b>\n"
        f"{data['description']}\nЦена: {data['price']}{config.CURRENCY}"
    )
    for chat_id in chats:
        try:
            if photo:
                await bot.send_photo(chat_id, photo, caption=caption, parse_mode="HTML")
            else:
                await bot.send_message(chat_id, caption, parse_mode="HTML")
        except Exception:
            pass


@router.message(AddProduct.photo, F.photo)
async def add_product_photo(message, state):
    file_id = message.photo[-1].file_id
    await finish_add_product(message, state, file_id)


@router.message(AddProduct.photo, Command("skip"))
async def add_product_skip_photo(message, state):
    await finish_add_product(message, state, None)


@router.callback_query(F.data == "admin:edit_product")
async def cb_admin_edit_product(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    products = await db.list_products(active_only=False)
    if not products:
        await show(call.from_user.id, "Товаров пока нет.", reply_markup=admin_menu_kb())
        await call.answer()
        return
    lines = [f"{p[0]} - {p[1]} ({p[3]}{config.CURRENCY})" for p in products]
    await show(call.from_user.id, "Введи ID товара, который редактируем:\n\n" + "\n".join(lines), reply_markup=cancel_kb())
    await state.set_state(EditProduct.product_id)
    await call.answer()


@router.message(EditProduct.product_id)
async def edit_product_choose(message, state):
    if not message.text.isdigit():
        await show(message.from_user.id, "Введи числовой ID", reply_markup=cancel_kb())
        return
    product_id = int(message.text)
    p = await db.get_product(product_id)
    if not p:
        await show(message.from_user.id, "Нет такого товара, попробуй ещё раз", reply_markup=cancel_kb())
        return
    await state.clear()
    await show_product_settings(message.from_user.id, product_id)


@router.callback_query(F.data.startswith("editfield:"))
async def cb_edit_field(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    _, product_id, field = call.data.split(":")
    product_id = int(product_id)
    await state.update_data(product_id=product_id, field=field)
    if field == "category":
        categories = await db.list_categories(active_only=True)
        await show(call.from_user.id, "Выбери новый раздел:", reply_markup=category_pick_kb(categories))
        await state.set_state(EditProduct.value)
        await call.answer()
        return
    prompts = {
        "name": "Пришли новое название:",
        "description": "Пришли новое описание:",
        "price": "Пришли новую цену (число):",
        "stock": "Пришли новый остаток (число, -1 = без ограничений):",
        "photo": "Пришли новое фото товара:",
    }
    await show(call.from_user.id, prompts[field], reply_markup=cancel_kb())
    if field == "photo":
        await state.set_state(EditProduct.photo)
    else:
        await state.set_state(EditProduct.value)
    await call.answer()


@router.callback_query(EditProduct.value, F.data.startswith("setcat:"))
async def edit_product_category(call, state):
    category = call.data.split(":", 1)[1]
    if category == "_none":
        category = None
    data = await state.get_data()
    await db.update_product_field(data["product_id"], "category", category)
    await state.clear()
    label = await category_label(category)
    await show(call.from_user.id, f"✅ Раздел обновил: {label}", reply_markup=admin_menu_kb())
    await call.answer()


@router.message(EditProduct.photo, F.photo)
async def edit_product_photo(message, state):
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    await db.update_product_field(data["product_id"], "photo", file_id)
    await state.clear()
    await show(message.from_user.id, "✅ Фото обновил.", reply_markup=admin_menu_kb())


@router.message(EditProduct.value)
async def edit_product_value(message, state):
    data = await state.get_data()
    field = data["field"]
    if field == "category":
        categories = await db.list_categories(active_only=True)
        await show(message.from_user.id, "Выбери раздел кнопкой ниже 👇", reply_markup=category_pick_kb(categories))
        return
    value = message.text
    if field in ("price", "stock"):
        try:
            value = int(value)
        except ValueError:
            await show(message.from_user.id, "Нужно число, попробуй ещё раз", reply_markup=cancel_kb())
            return
    await db.update_product_field(data["product_id"], field, value)
    await state.clear()
    await show(message.from_user.id, "✅ Обновил.", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:del_product")
async def cb_admin_del_product(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    products = await db.list_products()
    if not products:
        await show(call.from_user.id, "Товаров нет.", reply_markup=admin_menu_kb())
        await call.answer()
        return
    lines = [f"{p[0]} - {p[1]} ({p[3]}{config.CURRENCY})" for p in products]
    await show(call.from_user.id, "Введи ID товара для удаления:\n\n" + "\n".join(lines), reply_markup=cancel_kb())
    await state.set_state(DelProduct.product_id)
    await call.answer()


@router.message(DelProduct.product_id)
async def del_product_id(message, state):
    if not message.text.isdigit():
        await show(message.from_user.id, "Введи числовой ID", reply_markup=cancel_kb())
        return
    await db.remove_product(int(message.text))
    await state.clear()
    await show(message.from_user.id, "✅ Товар удалён (скрыт из каталога).", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:categories")
async def cb_admin_categories(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    categories = await db.list_categories()
    await show(
        call.from_user.id,
        "📂 Категории каталога:" if categories else "Категорий пока нет.",
        reply_markup=admin_categories_kb(categories),
    )
    await call.answer()


@router.callback_query(F.data == "admin:add_category")
async def cb_admin_add_category(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await show(call.from_user.id, "Для какой игры категория?", reply_markup=category_game_pick_kb())
    await state.set_state(AddCategory.game)
    await call.answer()


@router.callback_query(AddCategory.game, F.data.startswith("catgame:"))
async def cb_add_category_game(call, state):
    game = call.data.split(":", 1)[1]
    await state.update_data(game=game)
    await show(call.from_user.id, "Введи название категории (например «💎 Гемы»):", reply_markup=cancel_kb())
    await state.set_state(AddCategory.name)
    await call.answer()


@router.message(AddCategory.name)
async def add_category_name(message, state):
    data = await state.get_data()
    name = message.text.strip()
    base_key = f"{data['game']}_{slugify_category(name)}"
    key = base_key
    n = 2
    while await db.category_exists(key):
        key = f"{base_key}_{n}"
        n += 1
    await db.add_category(key, data["game"], name)
    await state.clear()
    await show(message.from_user.id, f"✅ Категория «{name}» добавлена.", reply_markup=admin_menu_kb())


@router.callback_query(F.data.startswith("catset:"))
async def cb_category_settings(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    key = call.data.split(":", 1)[1]
    cat = await db.get_category(key)
    if not cat:
        await call.answer("Категория не найдена", show_alert=True)
        return
    _, game, name, order, active = cat
    status = "✅ включена" if active else "🚫 выключена"
    await show(
        call.from_user.id,
        f"📂 {name}\nИгра: {GAME_NAMES.get(game, game)}\nСтатус: {status}",
        reply_markup=category_settings_kb(key, bool(active)),
    )
    await call.answer()


@router.callback_query(F.data.startswith("catmove:"))
async def cb_category_move(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    _, key, direction = call.data.split(":")
    moved = await db.move_category(key, direction)
    await cb_category_settings_render(call, key)
    await call.answer("Переставил" if moved else "Уже крайняя")


@router.callback_query(F.data.startswith("cattoggle:"))
async def cb_category_toggle(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    key = call.data.split(":", 1)[1]
    await db.toggle_category(key)
    await cb_category_settings_render(call, key)
    await call.answer("Готово")


async def cb_category_settings_render(call, key):
    cat = await db.get_category(key)
    if not cat:
        await show(call.from_user.id, "Категория удалена.", reply_markup=admin_menu_kb())
        return
    _, game, name, order, active = cat
    status = "✅ включена" if active else "🚫 выключена"
    await show(
        call.from_user.id,
        f"📂 {name}\nИгра: {GAME_NAMES.get(game, game)}\nСтатус: {status}",
        reply_markup=category_settings_kb(key, bool(active)),
    )


@router.callback_query(F.data.startswith("catrename:"))
async def cb_category_rename(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    key = call.data.split(":", 1)[1]
    await state.update_data(key=key)
    await show(call.from_user.id, "Введи новое название категории:", reply_markup=cancel_kb())
    await state.set_state(RenameCategory.name)
    await call.answer()


@router.message(RenameCategory.name)
async def category_rename_value(message, state):
    data = await state.get_data()
    await db.rename_category(data["key"], message.text.strip())
    await state.clear()
    await show(message.from_user.id, "✅ Название обновил.", reply_markup=admin_menu_kb())


@router.callback_query(F.data.startswith("catdel:"))
async def cb_category_delete(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    key = call.data.split(":", 1)[1]
    affected = await db.delete_category(key)
    note = f" ({affected} товар(ов) стали «без раздела»)" if affected else ""
    await show(call.from_user.id, f"🗑 Категория удалена{note}.", reply_markup=admin_menu_kb())
    await call.answer()


@router.callback_query(F.data == "admin:promocodes")
async def cb_admin_promocodes(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    promos = await db.list_promocodes()
    await show(
        call.from_user.id,
        "🎟️ Промокоды:" if promos else "Промокодов пока нет.",
        reply_markup=promo_admin_kb(promos),
    )
    await call.answer()


@router.callback_query(F.data == "admin:add_promo")
async def cb_admin_add_promo(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await show(call.from_user.id, "Введи текст промокода (например SALE20):", reply_markup=cancel_kb())
    await state.set_state(AddPromo.code)
    await call.answer()


@router.message(AddPromo.code)
async def add_promo_code(message, state):
    code = message.text.strip().upper()
    if not code or " " in code:
        await show(message.from_user.id, "Промокод без пробелов, например SALE20:", reply_markup=cancel_kb())
        return
    await state.update_data(code=code)
    await show(
        message.from_user.id,
        "Какая скидка? Введи в процентах (например 20%) или фиксированной суммой в ₽ (например 100):",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AddPromo.discount)


@router.message(AddPromo.discount)
async def add_promo_discount(message, state):
    text = message.text.strip().replace(",", ".")
    if text.endswith("%"):
        discount_type = "percent"
        raw = text[:-1]
    else:
        discount_type = "amount"
        raw = text
    try:
        value = int(float(raw))
    except ValueError:
        await show(
            message.from_user.id,
            "Не понял число. Введи, например, 20% или 100:",
            reply_markup=cancel_kb(),
        )
        return
    if discount_type == "percent" and not (0 < value <= 100):
        await show(message.from_user.id, "Процент должен быть от 1 до 100. Попробуй ещё раз:", reply_markup=cancel_kb())
        return
    data = await state.get_data()
    await db.add_promocode(data["code"], discount_type, value)
    await state.clear()
    suffix = "%" if discount_type == "percent" else config.CURRENCY
    await show(
        message.from_user.id,
        f"✅ Промокод {data['code']} создан: скидка {value}{suffix}.",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data.startswith("promoset:"))
async def cb_promo_settings(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    promo = await db.get_promocode(code)
    if not promo:
        await call.answer("Промокод не найден", show_alert=True)
        return
    _, discount_type, value, active = promo
    suffix = "%" if discount_type == "percent" else config.CURRENCY
    status = "✅ активен" if active else "🚫 выключен"
    await show(
        call.from_user.id,
        f"🎟️ Промокод {code}\nСкидка: {value}{suffix}\nСтатус: {status}",
        reply_markup=promo_settings_kb(code, bool(active)),
    )
    await call.answer()


@router.callback_query(F.data.startswith("promotoggle:"))
async def cb_promo_toggle(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    await db.toggle_promocode(code)
    promo = await db.get_promocode(code)
    _, discount_type, value, active = promo
    suffix = "%" if discount_type == "percent" else config.CURRENCY
    status = "✅ активен" if active else "🚫 выключен"
    await show(
        call.from_user.id,
        f"🎟️ Промокод {code}\nСкидка: {value}{suffix}\nСтатус: {status}",
        reply_markup=promo_settings_kb(code, bool(active)),
    )
    await call.answer("Готово")


@router.callback_query(F.data.startswith("promodel:"))
async def cb_promo_delete(call):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    await db.delete_promocode(code)
    await show(call.from_user.id, f"🗑 Промокод {code} удалён.", reply_markup=admin_menu_kb())
    await call.answer()


@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await show(
        call.from_user.id,
        "📣 Пришли сообщение для рассылки. Я разошлю его как есть: текст, фото, видео, стикер, "
        "оформление и эмодзи сохранятся. Альбомы из нескольких фото не поддерживаются, шли по одному.",
        reply_markup=cancel_kb(),
    )
    await state.set_state(Broadcast.text)
    await call.answer()


@router.message(Broadcast.text)
async def do_broadcast(message, state):
    if not is_admin(message.from_user.id):
        return
    ents = message.entities if message.text is not None else message.caption_entities
    await state.update_data(
        src_chat=message.chat.id,
        src_msg=message.message_id,
        text=message.text,
        caption=message.caption,
        ents=[e.model_dump(mode="json", exclude_none=True) for e in (ents or [])],
        markup=message.reply_markup.model_dump(mode="json", exclude_none=True) if message.reply_markup else None,
    )
    await state.set_state(Broadcast.confirm)
    users = await db.all_user_ids()
    await show(
        message.from_user.id,
        f"Отправить это сообщение всем пользователям бота? Получателей: {len(users)}",
        reply_markup=bcast_confirm_kb(),
    )


BTN_RE = re.compile(r"^(.+?)\s+[-|]\s+((?:https?|tg)://\S+)$")


def parse_buttons(text):
    rows = []
    for line in (text or "").splitlines():
        line = db.clean_text(line.strip())
        if not line:
            continue
        found = BTN_RE.match(line)
        if not found:
            return None
        rows.append([{"text": found.group(1).strip(), "url": found.group(2)}])
    return {"inline_keyboard": rows} if rows else None


async def send_copy(uid, d):
    ents = [MessageEntity(**e) for e in d["ents"]]
    markup = InlineKeyboardMarkup.model_validate(d["markup"]) if d.get("markup") else None
    text, caption = d["text"], d["caption"]
    body = text if text is not None else caption
    rewrite = body is not None and db.clean_text(body) != body
    for attempt in range(2):
        try:
            if text is not None and rewrite:
                await bot.send_message(uid, db.clean_text(text), entities=ents or None, reply_markup=markup)
            elif caption is not None and rewrite:
                await bot.copy_message(
                    uid, d["src_chat"], d["src_msg"],
                    caption=db.clean_text(caption), caption_entities=ents or None, reply_markup=markup,
                )
            else:
                await bot.copy_message(uid, d["src_chat"], d["src_msg"], reply_markup=markup)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except Exception:
            if attempt == 0 and any(x.type == "custom_emoji" for x in ents):
                ents = [x for x in ents if x.type != "custom_emoji"]
                rewrite = True
                continue
            return False
    return False


@router.callback_query(F.data == "bcast:button", StateFilter(Broadcast.confirm))
async def cb_bcast_button(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await state.set_state(Broadcast.button)
    await show(
        call.from_user.id,
        "Пришли кнопки под постом, каждая с новой строки в формате:\n\nТекст кнопки - https://ссылка\n\n"
        "Например:\nКупить донат - https://t.me/твой_бот",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(Broadcast.button)
async def do_bcast_buttons(message, state):
    if not is_admin(message.from_user.id):
        return
    markup = parse_buttons(message.text)
    if not markup:
        await show(
            message.from_user.id,
            "Не разобрал. Каждая кнопка с новой строки: Текст - https://ссылка. Пришли ещё раз.",
            reply_markup=cancel_kb(),
        )
        return
    await state.update_data(markup=markup)
    await state.set_state(Broadcast.confirm)
    data = await state.get_data()
    try:
        await message.delete()
    except Exception:
        pass
    try:
        await bot.copy_message(
            message.chat.id, data["src_chat"], data["src_msg"],
            reply_markup=InlineKeyboardMarkup.model_validate(markup),
        )
    except Exception:
        pass
    users = await db.all_user_ids()
    await show(
        message.from_user.id,
        f"Кнопки добавил (предпросмотр выше). Отправить всем? Получателей: {len(users)}",
        reply_markup=bcast_confirm_kb(),
    )


@router.callback_query(F.data == "bcast:send", StateFilter(Broadcast.confirm))
async def cb_bcast_send(call, state):
    if not is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    await call.answer("Рассылка пошла")
    users = await db.all_user_ids()
    await show(call.from_user.id, f"📣 Рассылка идёт, получателей: {len(users)}...")
    sent = 0
    for uid in users:
        if await send_copy(uid, data):
            sent += 1
        await asyncio.sleep(0.05)
    try:
        await bot.delete_message(data["src_chat"], data["src_msg"])
    except Exception:
        pass
    await show(
        call.from_user.id,
        f"📣 Рассылка отправлена {sent}/{len(users)} пользователям.",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "admin:admins")
async def cb_admin_admins(call):
    if call.from_user.id not in config.ADMIN_IDS:
        await call.answer("Только для главного админа", show_alert=True)
        return
    rows = await db.admin_list()
    lines = ["👮 Админы бота:", ""]
    lines.append("Главные: " + ", ".join(str(i) for i in config.ADMIN_IDS))
    lines.append("Добавленные: " + (", ".join(f"@{u}" if u else str(i) for i, u in rows) if rows else "нет"))
    await show(call.from_user.id, "\n".join(lines), reply_markup=admins_kb(rows))
    await call.answer()


@router.callback_query(F.data == "adm:add")
async def cb_admin_add(call, state):
    if call.from_user.id not in config.ADMIN_IDS:
        await call.answer("Только для главного админа", show_alert=True)
        return
    await state.set_state(AdminAdd.who)
    await show(
        call.from_user.id,
        "Пришли @username или числовой ID человека. Если он ещё не открывал бота, "
        "пусть сначала нажмёт /start.",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AdminAdd.who)
async def do_admin_add(message, state):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    query = (message.text or "").strip()
    await state.clear()
    row = await db.find_user(query)
    if not row and query.lstrip("@").isdigit():
        row = (int(query.lstrip("@")), None)
    if not row:
        await show(
            message.from_user.id,
            "Такого пользователя в боте нет. Пусть он откроет бота, нажмёт /start, и добавь его снова.",
            reply_markup=admins_kb(await db.admin_list()),
        )
        return
    uid, uname = row
    await db.admin_add(uid, uname)
    ADMIN_CACHE.add(uid)
    try:
        await bot.set_my_commands(
            [BotCommand(command="start", description="Главное меню"),
             BotCommand(command="cart", description="Корзина"),
             BotCommand(command="profile", description="Профиль"),
             BotCommand(command="orders", description="Статус заказа"),
             BotCommand(command="queue", description="Очередь"),
             BotCommand(command="admin", description="Админка")],
            scope=BotCommandScopeChat(chat_id=uid),
        )
        await bot.send_message(uid, "Тебя назначили админом бота. Нажми /start, чтобы появилась кнопка «Админка».")
    except Exception:
        pass
    rows = await db.admin_list()
    await show(message.from_user.id, f"✅ Добавил админа {'@' + uname if uname else uid}", reply_markup=admins_kb(rows))


@router.callback_query(F.data.startswith("adm:del:"))
async def cb_admin_del(call):
    if call.from_user.id not in config.ADMIN_IDS:
        await call.answer("Только для главного админа", show_alert=True)
        return
    uid = int(call.data.split(":")[2])
    await db.admin_remove(uid)
    ADMIN_CACHE.discard(uid)
    rows = await db.admin_list()
    await show(call.from_user.id, "Удалил из админов.", reply_markup=admins_kb(rows))
    await call.answer()


@router.message(Command("emojiid"))
async def cmd_emojiid(message, state):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(EmojiId.wait)
    await message.answer("Пришли сообщение с премиум-эмодзи, я покажу их ID.")


@router.message(EmojiId.wait)
async def got_emojiid(message, state):
    await state.clear()
    text = message.text or message.caption or ""
    ents = message.entities or message.caption_entities or []
    raw = text.encode("utf-16-le")
    lines, seen = [], set()
    for e in ents:
        if e.type == "custom_emoji" and e.custom_emoji_id not in seen:
            seen.add(e.custom_emoji_id)
            ch = raw[e.offset * 2:(e.offset + e.length) * 2].decode("utf-16-le")
            lines.append(f'    "{ch}": "{e.custom_emoji_id}",')
    if not lines:
        await message.answer("Премиум-эмодзи в сообщении не нашёл. Отправь /emojiid и пришли ещё раз.")
        return
    await message.answer(
        "Вставь эти строки в config.py, в список PREMIUM_EMOJI:\n\n" + "\n".join(lines)
    )


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_bot_added(event):
    chat = event.chat
    await db.register_chat(chat.id, chat.title or chat.username or str(chat.id), chat.type)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
async def on_bot_removed(event):
    await db.unregister_chat(event.chat.id)


async def send_startup_summary(restored=None):
    count = await db.user_count()
    products = await db.list_products(active_only=False)
    orders = await db.order_count()
    revenue = await db.total_revenue()
    text = (
        "🤖 Бот запущен и работает!\n\n"
        f"Пользователей: {count}\n"
        f"Товаров в базе: {len(products)}\n"
        f"Заказов: {orders}\n"
        f"Продано на: {revenue}{config.CURRENCY}\n"
        f"База: {os.path.abspath(config.DB_PATH)}"
    )
    if restored:
        when = ""
        if restored.get("ts"):
            when = " от " + datetime.fromtimestamp(restored["ts"], MSK).strftime("%d.%m %H:%M")
        text = (f"♻️ База была пустая (хостинг стёр файл), поэтому я достал последнюю копию{when} и восстановил её. "
                f"Вернулось: пользователей {restored['users']}, заказов {restored['orders']}.\n\n") + text
    elif count == 0:
        text += ("\n\n⚠️ База пустая, копии в Telegram пока нет. Если раньше были пользователи и заказы - хостинг стёр файл. "
                 "Теперь бот сам шлёт копии и в следующий раз восстановится сам.")
    for admin_id in admin_ids():
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


async def apply_menu_button():
    try:
        if (config.SITE_URL or "").startswith("https://"):
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Магазин", web_app=WebAppInfo(url=config.SITE_URL)))
        else:
            await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception:
        logging.exception("не удалось поставить кнопку меню")


async def on_tunnel_url(url):
    config.SITE_URL = url
    logging.info("Мини-приложение доступно по адресу %s", url)
    await apply_menu_button()
    for admin_id in admin_ids():
        try:
            await bot.send_message(admin_id, f"📱 Мини-приложение запущено: {url}\nАдрес временный и меняется при перезапуске бота.",
                                   disable_notification=True)
        except Exception:
            pass


async def setup_commands():
    try:
        user_commands = [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="cart", description="Корзина"),
            BotCommand(command="profile", description="Профиль"),
            BotCommand(command="orders", description="Статус заказа"),
            BotCommand(command="queue", description="Очередь"),
        ]
        await bot.set_my_commands(user_commands)
        await apply_menu_button()
        for admin_id in admin_ids():
            try:
                await bot.set_my_commands(
                    user_commands + [BotCommand(command="admin", description="Админка")],
                    scope=BotCommandScopeChat(chat_id=admin_id),
                )
            except Exception:
                pass
    except Exception:
        logging.exception("set_my_commands failed")


async def main():
    restored = None
    try:
        dbsafe.adopt_legacy_db(config.DB_PATH)
        restored = await dbsafe.restore_if_empty(bot, config.DB_PATH, config.ADMIN_IDS)
    except Exception:
        logging.exception("проверка копии базы не удалась")
    await db.init_db()
    await db.seed_products_if_empty()
    await db.migrate_catalog_prices_and_clash()
    await db.normalize_saved_texts()
    await db.seed_default_settings()
    await db.sync_catalog(config.BASE_CATEGORIES, config.BASE_PRODUCTS, config.REMOVED_CATEGORIES, config.REMOVED_PRODUCTS)
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    BOT_LINK["url"] = f"https://t.me/{me.username}"
    logging.info("Токен принят. Бот @%s подключён к Telegram, начинаю получать сообщения.", me.username)
    if 123456789 in config.ADMIN_IDS:
        logging.warning("В config.py ADMIN_IDS всё ещё заглушка 123456789 - впиши свой Telegram ID, "
                        "иначе уведомления о заказах и /admin работать не будут.")
    ADMIN_CACHE.update(r[0] for r in await db.admin_list())
    await setup_commands()
    await probe_premium()
    if platega.enabled():
        asyncio.create_task(platega_poller())
    try:
        await web_api.start(bot=bot, is_open=is_shop_open, is_admin=is_admin, admin_ids=admin_ids,
                            bot_link=bot_link, apply_status=apply_platega_status, publish_review=publish_review,
                            deliver_order=deliver_order, send_notice=send_post_pay_notice,
                            broadcast_start=broadcast_start, invoice_link=make_invoice_link, broadcast_status=lambda: dict(BCAST))
    except Exception:
        logging.exception("не удалось запустить веб-сервер")
    cf_token = tunnel.named_token()
    if cf_token:
        host = os.getenv("CF_TUNNEL_HOST", "phonkershop.com").strip().replace("https://", "").strip("/")
        config.SITE_URL = "https://" + host
        await apply_menu_button()
        asyncio.create_task(tunnel.start_named(cf_token))
    elif not config.SITE_URL:
        port = int(os.getenv("PORT") or os.getenv("WEB_PORT") or getattr(config, "WEB_PORT", 8080))
        asyncio.create_task(tunnel.start(port, on_tunnel_url))
    await send_startup_summary(restored)
    asyncio.create_task(dbsafe.backup_loop(bot, config.DB_PATH, config.ADMIN_IDS))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
