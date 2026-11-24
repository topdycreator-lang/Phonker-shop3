import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "7849577469:AAEYFQorGhQrHYlGFAR4948-s_4mFTdOp7M")
ADMIN_IDS = [1610643320, 8023234522, 5611207337, 1855984224]

CURRENCY = "RUB"
STARS_TO_RUB = 1.5

WORK_HOURS_START = 0
WORK_HOURS_END = 24

CHANNEL_URL = "https://t.me/Phonker_Shop"  # ссылка на канал магазина (https://t.me/...); пусто = берём ссылку на канал отзывов
# Объявление, которое приходит покупателю в бот сразу после оплаты (текст и ссылку можно менять в админке мини-аппа)
POST_PAY_DEFAULT = "📢 Подпишись на наш канал, чтобы не пропускать новости, акции и скидки!"
REVIEWS_CHANNEL = os.getenv("REVIEWS_CHANNEL", "@PhonkerOt")  # @username или -100... ID канала для отзывов
REVIEWS_URL = os.getenv("REVIEWS_URL", "https://t.me/PhonkerOt")
REVIEWS_USERNAME = os.getenv("REVIEWS_USERNAME", "@PhonkerOt")

# ---- Мини-приложение ----
# Публичный https-адрес, по которому открывается сайт бота (то, что отдаёт web_api на порту PORT).
# Задаётся переменной SITE_URL, например https://shop.example.com . Пока пусто - кнопки мини-приложения не показываются.
def _pick_site_url():
    """SITE_URL главнее; иначе пробуем адрес, который хостинг выдаёт сам."""
    u = os.getenv("SITE_URL", "").strip()
    if not u:
        for name in ("RENDER_EXTERNAL_URL", "RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL", "KOYEB_PUBLIC_DOMAIN",
                     "FLY_APP_NAME", "SPACE_HOST", "WEBSITE_HOSTNAME", "HEROKU_APP_DEFAULT_DOMAIN_NAME"):
            v = os.getenv(name, "").strip()
            if v:
                u = f"{v}.fly.dev" if name == "FLY_APP_NAME" else v
                break
    if u and not u.startswith("http"):
        u = "https://" + u
    return u.rstrip("/")


SITE_URL = _pick_site_url()

WEB_PORT = 1230  # Порт веб-сервера и Cloudflare Tunnel


# ---- База ----
# Переменная DB_PATH главнее. Если у хостинга есть постоянная папка /data, база лежит там
# (файл свой для каждого бота), иначе рядом с ботом (shop.db). Обычные файлы хостинг при обновлении стирает.
def _pick_db_path():
    custom = os.getenv("DB_PATH")
    if custom:
        return custom
    if os.path.isdir("/data") and os.access("/data", os.W_OK):
        bot_id = BOT_TOKEN.split(":")[0]
        return os.path.join("/data", f"shop_{bot_id}.db" if bot_id.isdigit() else "shop.db")
    return "shop.db"


DB_PATH = _pick_db_path()


# ---- Базовый каталог ----
# При каждом запуске бота недостающие разделы и товары из этого списка
# добавляются в базу сами. Уже существующие товары и цены не перезаписываются.
# (key, game, name, sort_order)
BASE_CATEGORIES = [
    ("bs_gems", "bs", "💎 Гемы", 1),
    ("bs_pass", "bs", "🎟 Пассы", 2),
    ("bs_special", "bs", "🟢 Особые акции", 3),
    ("clash_gems", "clash", "💎 Гемы", 1),
    ("clash_pass", "clash", "🎟 Пассы", 2),
    ("coc_gems", "coc", "💎 Гемы", 1),
    ("coc_pass", "coc", "🎫 Золотой пропуск", 2),
]

# (name, description, price, category_key, sort_order)
BASE_PRODUCTS = [
    ("Гемы x33", "33 гема", 100, "bs_gems", 1),
    ("Гемы x88", "88 гемов", 149, "bs_gems", 2),
    ("Гемы x187", "187 гемов", 289, "bs_gems", 3),
    ("Гемы x396", "396 гемов", 399, "bs_gems", 4),
    ("Гемы x1045", "1045 гемов", 799, "bs_gems", 5),
    ("Гемы x2200", "2200 гемов", 1349, "bs_gems", 6),
    ("Pass Case", "Откройте кейс и получите Brawl Pass, Brawl Pass Plus или Pro Pass. Шансы равные: по 33,3% на каждый", 359, "bs_pass", 0),
    ("Brawl Pass", "Обычный Brawl Pass", 299, "bs_pass", 1),
    ("Brawl Pass Plus", "Brawl Pass Plus", 349, "bs_pass", 2),
    ("Pro Pass", "Pro Pass", 549, "bs_pass", 3),
    ("Brawl Pass Plus (8шт)", "Brawl Pass Plus, 8 штук", 1499, "bs_pass", 4),
    ("Гемы x500", "500 гемов", 199, "clash_gems", 1),
    ("Гемы x1200", "1200 гемов", 249, "clash_gems", 2),
    ("Гемы x2500", "2500 гемов", 349, "clash_gems", 3),
    ("Гемы x6500", "6500 гемов", 749, "clash_gems", 4),
    ("Гемы x14000", "14000 гемов", 1299, "clash_gems", 5),
    ("Гемы x42000", "42000 гемов", 2799, "clash_gems", 6),
    ("🔵 Синий Френк", "Синий Френк", 2199, "bs_special", 1),
    ("🔴 Красный Френк", "Красный Френк", 2199, "bs_special", 2),
    ("🔵🔴 Оба Френка", "Оба Френка", 3999, "bs_special", 3),
    ("Пасс Рояль", "Pass Royale", 349, "clash_pass", 1),
    ("Пасс Рояль (8 штук)", "Pass Royale, 8 штук", 1499, "clash_pass", 2),
    # Clash of Clans
    ("Гемы x500", "500 гемов", 199, "coc_gems", 1),
    ("Гемы x1200", "1200 гемов", 249, "coc_gems", 2),
    ("Гемы x2500", "2500 гемов", 349, "coc_gems", 3),
    ("Гемы x6500", "6500 гемов", 749, "coc_gems", 4),
    ("Гемы x14000", "14000 гемов", 1299, "coc_gems", 5),
    ("Гемы x42000", "42000 гемов", 2799, "coc_gems", 6),
    ("Золотой пропуск", "Gold Pass", 249, "coc_pass", 1),
    ("Золотой пропуск (8 штук)", "Gold Pass, 8 штук", 1199, "coc_pass", 2),
]

# Разделы, которые убираем при запуске (товары в них скрываются)
REMOVED_CATEGORIES = ["bs_pin"]

# Товары, которые убираем при запуске (скрываются из каталога)
# (category_key, name)
REMOVED_PRODUCTS = [("bs_pass", "Улучшение до BP+")]

# ---- Platega (оплата рублями) ----
PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID", "").strip()
PLATEGA_SECRET = "m1IYx5HC6EHct7x5jBCIKF3AtM2mvwWgGqDZSn15FfvJKZ67DIq106U1PFhqyESfRVuONLPZV4R71IErnCN1NQkIurdjZUlE63IL"


# ---- Премиум-эмодзи ----
# Как добавить: админ отправляет боту /emojiid, потом присылает сообщение с нужными премиум-эмодзи.
# Бот ответит готовыми строками - вставь их сюда. Обычный эмодзи в тексте и на кнопках
# заменится на премиум, если Telegram это разрешает (бот проверяет при запуске и сам откатывается на обычные).
PREMIUM_EMOJI = {
    "🎮": "5938413566624272793",
    # "🛒": "ID",
    # "👤": "ID",
    # "💎": "ID",
}


# ---- Лимит оплаты ----
# СБП в Platega не принимает платёж больше 20000 RUB вместе с комиссией. Держим запас.
PLATEGA_MAX_AMOUNT = int(os.getenv("PLATEGA_MAX_AMOUNT", "18500"))
