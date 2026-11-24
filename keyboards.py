from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config

SHOP_BOT_USERNAME = "PhonkerShopBOT"


def main_menu_kb(is_admin=False):
    b = InlineKeyboardBuilder()
    site = (getattr(config, "SITE_URL", "") or "")
    if site.startswith("https://"):
        b.button(text="Phonker App", web_app=WebAppInfo(url=site))
    else:
        b.button(text="Phonker App", callback_data="miniapp_wait")
    b.button(text="Каталог", callback_data="catalog")
    b.button(text="Корзина", callback_data="cart")
    b.button(text="Мои покупки", callback_data="my_orders")
    b.button(text="Профиль", callback_data="profile")
    b.button(text="Отзывы", callback_data="reviews")
    b.button(text="Документы", callback_data="docs")
    b.button(text="Поддержка", callback_data="support")
    sizes = [2, 2, 2, 1]
    sizes = [1] + sizes
    if (config.CHANNEL_URL or "").startswith("http"):
        b.button(text="Наш канал", url=config.CHANNEL_URL)
        sizes.append(1)
    if is_admin:
        b.button(text="Админка", callback_data="admin_open")
        sizes.append(1)
    b.adjust(*sizes)
    return b.as_markup()


SECTION_LABELS = {
    "bs_pass": "🎟 Пассы",
    "bs_gems": "💎 Гемы",
    "bs_pin": "📌 Пины",
}

GAME_NAMES = {"bs": "Brawl Stars", "clash": "Clash Royale", "coc": "Clash of Clans"}

GAME_LABELS = {
    "bs": "🟡 Brawl Stars",
    "clash": "🔵 Clash Royale",
    "coc": "⚔️ Clash of Clans",
}


def game_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Brawl Stars", callback_data="game:bs")
    b.button(text="Clash Royale", callback_data="game:clash")
    b.button(text="Clash of Clans", callback_data="game:coc")
    b.button(text="Корзина", callback_data="cart")
    b.button(text="Назад", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def sections_kb(categories, game):
    b = InlineKeyboardBuilder()
    for key, _game, name, _order, active in categories:
        b.button(text=name, callback_data=f"section:{key}")
    b.button(text="Назад", callback_data="catalog")
    b.adjust(1)
    return b.as_markup()


def clash_placeholder_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Назад", callback_data="catalog")
    b.adjust(1)
    return b.as_markup()


def catalog_kb(products, back_cb="menu"):
    b = InlineKeyboardBuilder()
    for pid, name, price in products:
        b.button(text=f"{name} - {price}₽", callback_data=f"product:{pid}")
    b.button(text="Назад", callback_data=back_cb)
    b.adjust(1)
    return b.as_markup()


def product_kb(product_id, back_cb="catalog", show_settings=False):
    b = InlineKeyboardBuilder()
    b.button(text="Оплатить", callback_data=f"buy:{product_id}")
    b.button(text="В корзину", callback_data=f"cart_add:{product_id}")
    if show_settings:
        b.button(text="Настроить", callback_data=f"pset:{product_id}")
    b.button(text="К каталогу", callback_data=back_cb)
    b.adjust(1)
    return b.as_markup()


def category_pick_kb(categories):
    b = InlineKeyboardBuilder()
    for key, game, name, _order, active in categories:
        b.button(text=f"{GAME_NAMES.get(game, game)} · {name}", callback_data=f"setcat:{key}")
    b.button(text="Без раздела", callback_data="setcat:_none")
    b.button(text="Отмена", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def reviews_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Назад", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def admin_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Заказы", callback_data="admin:orders")
    b.button(text="Чаты с покупателями", callback_data="admin:chats")
    b.button(text="Добавить товар", callback_data="admin:add_product")
    b.button(text="Редактировать товар", callback_data="admin:edit_product")
    b.button(text="Удалить товар", callback_data="admin:del_product")
    b.button(text="Категории", callback_data="admin:categories")
    b.button(text="Промокоды", callback_data="admin:promocodes")
    b.button(text="Статистика", callback_data="admin:stats")
    b.button(text="Пользователи", callback_data="admin:users")
    b.button(text="Рассылка", callback_data="admin:broadcast")
    b.button(text="Админы", callback_data="admin:admins")
    b.button(text="Способы оплаты", callback_data="admin:payments")
    b.button(text="Документы", callback_data="admin:docs")
    b.button(text="Найти юзера", callback_data="admin:find_user")
    b.button(text="Розыгрыш", callback_data="admin:giveaway")
    b.button(text="Файлы (база)", callback_data="admin:files")
    b.adjust(1)
    return b.as_markup()


def product_settings_kb(product_id, active, category):
    b = InlineKeyboardBuilder()
    b.button(text="Название", callback_data=f"editfield:{product_id}:name")
    b.button(text="Описание", callback_data=f"editfield:{product_id}:description")
    b.button(text="Цена", callback_data=f"editfield:{product_id}:price")
    b.button(text="Остаток", callback_data=f"editfield:{product_id}:stock")
    b.button(text="Фото", callback_data=f"editfield:{product_id}:photo")
    b.button(text="Перенести в раздел", callback_data=f"editfield:{product_id}:category")
    b.button(text="Выше", callback_data=f"pmove:{product_id}:up")
    b.button(text="Ниже", callback_data=f"pmove:{product_id}:down")
    if active:
        b.button(text="Выключить", callback_data=f"ptoggle:{product_id}")
    else:
        b.button(text="Включить", callback_data=f"ptoggle:{product_id}")
    b.button(text="Удалить товар", callback_data=f"pdel:{product_id}")
    back_cb = f"section:{category}" if category else "catalog"
    b.button(text="Назад", callback_data=back_cb)
    b.adjust(2, 2, 1, 2, 1, 1, 1)
    return b.as_markup()


def admin_categories_kb(categories):
    b = InlineKeyboardBuilder()
    for key, game, name, order, active in categories:
        mark = "✅" if active else "🚫"
        b.button(text=f"{mark} {GAME_NAMES.get(game, game)} · {name}", callback_data=f"catset:{key}")
    b.button(text="Добавить категорию", callback_data="admin:add_category")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def category_game_pick_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Brawl Stars", callback_data="catgame:bs")
    b.button(text="Clash Royale", callback_data="catgame:clash")
    b.button(text="Clash of Clans", callback_data="catgame:coc")
    b.button(text="Отмена", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def category_settings_kb(key, active):
    b = InlineKeyboardBuilder()
    b.button(text="Переименовать", callback_data=f"catrename:{key}")
    b.button(text="Выше", callback_data=f"catmove:{key}:up")
    b.button(text="Ниже", callback_data=f"catmove:{key}:down")
    if active:
        b.button(text="Выключить", callback_data=f"cattoggle:{key}")
    else:
        b.button(text="Включить", callback_data=f"cattoggle:{key}")
    b.button(text="Удалить категорию", callback_data=f"catdel:{key}")
    b.button(text="К категориям", callback_data="admin:categories")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def promo_admin_kb(promocodes):
    b = InlineKeyboardBuilder()
    for code, discount_type, value, active in promocodes:
        mark = "✅" if active else "🚫"
        suffix = "%" if discount_type == "percent" else "₽"
        b.button(text=f"{mark} {code} (-{value}{suffix})", callback_data=f"promoset:{code}")
    b.button(text="Добавить промокод", callback_data="admin:add_promo")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def promo_settings_kb(code, active):
    b = InlineKeyboardBuilder()
    if active:
        b.button(text="Выключить", callback_data=f"promotoggle:{code}")
    else:
        b.button(text="Включить", callback_data=f"promotoggle:{code}")
    b.button(text="Удалить", callback_data=f"promodel:{code}")
    b.button(text="К промокодам", callback_data="admin:promocodes")
    b.adjust(1)
    return b.as_markup()


def purchase_promo_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Без промокода", callback_data="promo_skip")
    b.button(text="Отмена покупки", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def edit_field_kb(product_id):
    b = InlineKeyboardBuilder()
    b.button(text="Название", callback_data=f"editfield:{product_id}:name")
    b.button(text="Описание", callback_data=f"editfield:{product_id}:description")
    b.button(text="Цена", callback_data=f"editfield:{product_id}:price")
    b.button(text="Остаток", callback_data=f"editfield:{product_id}:stock")
    b.button(text="Фото", callback_data=f"editfield:{product_id}:photo")
    b.button(text="Раздел", callback_data=f"editfield:{product_id}:category")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def cancel_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Отмена", callback_data="cancel")
    return b.as_markup()


def user_found_kb(user_id):
    b = InlineKeyboardBuilder()
    b.button(text="Написать", callback_data=f"chat:{user_id}")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def order_admin_kb(order_id):
    b = InlineKeyboardBuilder()
    b.button(text="Принять заказ", callback_data=f"order_ok:{order_id}")
    b.button(text="Отклонить", callback_data=f"order_no:{order_id}")
    b.button(text="Написать покупателю", callback_data=f"order_chat:{order_id}")
    b.adjust(1)
    return b.as_markup()


def _site_chat_button(b, order_id, text="Открыть заказ и чат"):
    """Кнопка на сайт магазина: страница заказа с чатом. Внутри Telegram открывается как мини-апп."""
    site = (getattr(config, "SITE_URL", "") or "").rstrip("/")
    if not site or not order_id:
        return
    url = f"{site}/?order={order_id}"
    if site.startswith("https://"):
        b.button(text=text, web_app=WebAppInfo(url=url))
    else:
        b.button(text=text, url=url)


def order_confirm_kb(order_id):
    b = InlineKeyboardBuilder()
    b.button(text="Подтверждаю получение", callback_data=f"order_done:{order_id}")
    _site_chat_button(b, order_id)
    b.button(text="Написать продавцу", callback_data="chat_admin")
    b.adjust(1)
    return b.as_markup()


def order_wait_kb(order_id=None):
    b = InlineKeyboardBuilder()
    _site_chat_button(b, order_id)
    b.button(text="Написать продавцу", callback_data="chat_admin")
    b.button(text="В меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def order_paid_admin_kb(order_id):
    b = InlineKeyboardBuilder()
    b.button(text="Товар выдан", callback_data=f"order_deliv:{order_id}")
    _site_chat_button(b, order_id, "Чат на сайте")
    b.button(text="Написать покупателю", callback_data=f"order_chat:{order_id}")
    b.adjust(1)
    return b.as_markup()


def admin_orders_kb(rows, todo):
    b = InlineKeyboardBuilder()
    for order_id, name, price, status, delivered, _uid, username, _created in rows:
        mark = {"pending": "⏳", "confirmed": "📬" if delivered else "📦", "completed": "✅", "rejected": "❌"}.get(status, "")
        who = f"@{username}" if username else ""
        b.button(text=f"{mark} №{order_id} {name} {price}₽ {who}".strip(), callback_data=f"aorder:{order_id}")
    if todo:
        b.button(text="Все заказы", callback_data="admin:orders")
    else:
        b.button(text="Ждут выдачи", callback_data="admin:orders_todo")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def admin_order_view_kb(order_id, status, delivered):
    b = InlineKeyboardBuilder()
    if status == "pending":
        b.button(text="Принять заказ", callback_data=f"order_ok:{order_id}")
        b.button(text="Отклонить", callback_data=f"order_no:{order_id}")
    elif status == "confirmed" and not delivered:
        b.button(text="Товар выдан", callback_data=f"order_deliv:{order_id}")
    b.button(text="Написать покупателю", callback_data=f"order_chat:{order_id}")
    b.button(text="К заказам", callback_data="admin:orders")
    b.adjust(1)
    return b.as_markup()


def order_chat_kb(order_id):
    b = InlineKeyboardBuilder()
    b.button(text="Написать покупателю", callback_data=f"order_chat:{order_id}")
    return b.as_markup()


def review_offer_kb(order_id):
    b = InlineKeyboardBuilder()
    b.button(text="Оставить отзыв", callback_data=f"review_start:{order_id}")
    b.button(text="В меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def my_orders_kb(actions, is_admin=False):
    b = InlineKeyboardBuilder()
    for text, cb in actions:
        b.button(text=text, callback_data=cb)
    b.adjust(1)
    rows = b.as_markup().inline_keyboard + main_menu_kb(is_admin).inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def giveaway_kb(user_id):
    b = InlineKeyboardBuilder()
    b.button(text="Объявить всем", callback_data=f"giveaway_announce:{user_id}")
    b.button(text="Выбрать заново", callback_data="admin:giveaway")
    b.adjust(1)
    return b.as_markup()


def requisites_kb(has_requisites):
    b = InlineKeyboardBuilder()
    b.button(text="Задать / изменить", callback_data="admin:set_requisites")
    if has_requisites:
        b.button(text="Убрать", callback_data="admin:clear_requisites")
    b.button(text="Назад", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def topup_method_kb():
    b = InlineKeyboardBuilder()
    b.button(text="По реквизитам", callback_data="topup_method:card")
    b.button(text="Telegram Stars", callback_data="topup_method:stars")
    b.button(text="Отмена", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def topup_approve_kb(topup_id):
    b = InlineKeyboardBuilder()
    b.button(text="Подтвердить", callback_data=f"topup_ok:{topup_id}")
    b.button(text="Отклонить", callback_data=f"topup_no:{topup_id}")
    b.adjust(2)
    return b.as_markup()


def buy_donate_kb():
    b = InlineKeyboardBuilder()
    b.button(
        text="Купить дешевый донат 👇",
        url=f"https://t.me/{SHOP_BOT_USERNAME}",
    )
    return b.as_markup()


def format_review_post(order_id, username, product_name,
                        price, review_text):
    return (
        f"Новый отзыв о покупке №{order_id}!\n\n"
        f"• Покупатель: {username}\n"
        f"• Товар: {product_name}\n"
        f"• Стоимость: {price}₽\n\n"
        f"✉️ Отзыв покупателя: {review_text}"
    )


def review_preview_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Опубликовать", callback_data="review_pub")
    b.button(text="Изменить текст", callback_data="review_edit_text")
    b.button(text="Изменить фото", callback_data="review_edit_photo")
    b.button(text="Не публиковать", callback_data="review_drop")
    b.adjust(1)
    return b.as_markup()


DOC_TITLES = {
    "account_check": "🔍 Проверка аккаунта перед покупкой",
    "terms": "📜 Пользовательское соглашение",
    "privacy": "🔒 Политика конфиденциальности",
    "support": "📞 Контакты поддержки",
    "prices": "💰 Цены и тарифы",
}


def docs_kb(urls, back_cb="menu"):
    b = InlineKeyboardBuilder()
    for key, title in DOC_TITLES.items():
        if urls.get(key):
            b.button(text=title, url=urls[key])
        else:
            b.button(text=title, callback_data=f"doc:{key}:menu")
    b.button(text="Назад", callback_data=back_cb)
    b.adjust(1)
    return b.as_markup()


def doc_back_kb(back_cb):
    b = InlineKeyboardBuilder()
    b.button(text="Назад", callback_data=back_cb)
    return b.as_markup()


def pay_notice_kb(urls):
    b = InlineKeyboardBuilder()
    for key in ("account_check", "terms", "privacy"):
        if urls.get(key):
            b.button(text=DOC_TITLES[key], url=urls[key])
        else:
            b.button(text=DOC_TITLES[key], callback_data=f"doc:{key}:notice")
    b.button(text="Продолжить", callback_data="pay_continue")
    b.button(text="Отмена", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def pay_methods_kb(methods):
    b = InlineKeyboardBuilder()
    for code, label in methods:
        b.button(text=label, callback_data=f"pay:{code}")
    b.button(text="Отмена", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def pay_done_kb(url):
    b = InlineKeyboardBuilder()
    if url:
        b.button(text="Перейти к оплате", url=url)
    b.button(text="Я оплатил", callback_data="pay_paid")
    b.button(text="Другой способ", callback_data="pay_continue_methods")
    b.button(text="Отмена", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def pay_auto_kb(url, tx_id):
    b = InlineKeyboardBuilder()
    b.button(text="Перейти к оплате", url=url)
    b.button(text="Проверить оплату", callback_data=f"pgcheck:{tx_id}")
    b.button(text="Другой способ", callback_data="pay_continue_methods")
    b.button(text="Отмена", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


PAY_METHODS = {
    "stars": "⭐ Telegram Stars",
    "crypto": "🪙 Криптовалюта",
    "sbp": "🏦 СБП",
}


def admin_payments_kb(status):
    b = InlineKeyboardBuilder()
    for code, label in PAY_METHODS.items():
        mark = "✅" if status.get(code) else "🚫"
        b.button(text=f"{mark} {label}", callback_data=f"payset:{code}")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def admin_pay_method_kb(code, enabled):
    b = InlineKeyboardBuilder()
    if code in ("crypto", "sbp"):
        b.button(text="Задать / изменить ссылку", callback_data=f"paylink:{code}")
        b.button(text="Убрать ссылку", callback_data=f"paylinkdel:{code}")
    else:
        b.button(text="Выключить" if enabled else "🟢 Включить", callback_data="paytoggle:stars")
    b.button(text="К способам оплаты", callback_data="admin:payments")
    b.adjust(1)
    return b.as_markup()


def admin_docs_kb():
    b = InlineKeyboardBuilder()
    for key in ("account_check", "terms", "privacy", "support"):
        b.button(text=DOC_TITLES[key], callback_data=f"docedit:{key}")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def admin_doc_edit_kb(key):
    b = InlineKeyboardBuilder()
    b.button(text="Задать текст или ссылку", callback_data=f"docset:{key}")
    b.button(text="Вернуть стандартный текст", callback_data=f"docreset:{key}")
    b.button(text="К документам", callback_data="admin:docs")
    b.adjust(1)
    return b.as_markup()


def admin_users_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Выгрузить список (CSV)", callback_data="admin:users_export")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def admins_kb(admins):
    b = InlineKeyboardBuilder()
    b.button(text="Добавить админа", callback_data="adm:add")
    for uid, uname in admins:
        b.button(text=f"{'@' + uname if uname else uid}", callback_data=f"adm:del:{uid}")
    b.button(text="В админку", callback_data="admin_open")
    b.adjust(1)
    return b.as_markup()


def bcast_confirm_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Отправить всем", callback_data="bcast:send")
    b.button(text="Добавить кнопки", callback_data="bcast:button")
    b.button(text="Отмена", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def cart_kb(items):
    """items: (product_id, name, price, qty, stock, active)"""
    b = InlineKeyboardBuilder()
    sizes = []
    for pid, name, _price, qty, _stock, _active in items:
        short = name if len(name) <= 20 else name[:19] + "…"
        b.button(text="", callback_data=f"cart_dec:{pid}")
        b.button(text=f"{short} ×{qty}", callback_data="noop")
        b.button(text="", callback_data=f"cart_inc:{pid}")
        sizes.append(3)
    if items:
        b.button(text="Оформить заказ", callback_data="cart_checkout")
        b.button(text="Очистить", callback_data="cart_clear")
        sizes += [1, 1]
    b.button(text="В каталог", callback_data="catalog")
    b.button(text="Назад", callback_data="menu")
    sizes += [2] if items else [1, 1]
    b.adjust(*sizes)
    return b.as_markup()


def profile_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Мои заказы", callback_data="my_orders")
    b.button(text="Очередь", callback_data="queue")
    b.button(text="Корзина", callback_data="cart")
    b.button(text="Назад", callback_data="menu")
    b.adjust(2, 1, 1)
    return b.as_markup()


def queue_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Обновить", callback_data="queue")
    b.button(text="Назад", callback_data="profile")
    b.adjust(1)
    return b.as_markup()
