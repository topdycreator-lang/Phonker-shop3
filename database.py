import aiosqlite
from config import DB_PATH


_LD = chr(8212)


def clean_text(value):
    return value.replace(_LD, "-") if isinstance(value, str) else value


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur = await db.execute("PRAGMA table_info(users)")
        user_cols = [r[1] for r in await cur.fetchall()]
        if "first_name" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
        if "last_seen" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
        if "balance" in user_cols:
            try:
                await db.execute("ALTER TABLE users DROP COLUMN balance")
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                stock INTEGER NOT NULL DEFAULT -1,  -- -1 = безлимит
                active INTEGER NOT NULL DEFAULT 1,
                photo TEXT,  -- file_id фото в Telegram, может быть NULL
                category TEXT,  -- ключ из таблицы categories, может быть NULL (без раздела)
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur = await db.execute("PRAGMA table_info(products)")
        cols = [row[1] for row in await cur.fetchall()]
        if "photo" not in cols:
            await db.execute("ALTER TABLE products ADD COLUMN photo TEXT")
        if "category" not in cols:
            await db.execute("ALTER TABLE products ADD COLUMN category TEXT")
        if "sort_order" not in cols:
            await db.execute("ALTER TABLE products ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
            await db.execute("UPDATE products SET sort_order = product_id")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                key TEXT PRIMARY KEY,
                game TEXT NOT NULL,       -- 'bs' / 'clash'
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)
        cur = await db.execute("SELECT COUNT(*) FROM categories")
        if (await cur.fetchone())[0] == 0:
            await db.executemany(
                "INSERT INTO categories (key, game, name, sort_order, active) VALUES (?, ?, ?, ?, 1)",
                [
                    ("bs_pass", "bs", "🎟 Пассы", 1),
                    ("bs_gems", "bs", "💎 Гемы", 2),
                    ("bs_pin", "bs", "📌 Пины", 3),
                ],
            )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS platega_tx (
                tx_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                promo TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                order_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                discount_type TEXT NOT NULL,  -- 'percent' / 'amount'
                value INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',  -- pending/confirmed/rejected/completed
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur = await db.execute("PRAGMA table_info(orders)")
        cols = [row[1] for row in await cur.fetchall()]
        if "status" not in cols:
            await db.execute(
                "ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'"
            )
        if "delivered" not in cols:
            # delivered = 1, когда продавец отметил, что товар выдан. Старые заказы считаем выданными.
            await db.execute("ALTER TABLE orders ADD COLUMN delivered INTEGER NOT NULL DEFAULT 0")
            await db.execute("UPDATE orders SET delivered = 1 WHERE status IN ('confirmed', 'completed')")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS topups (
                topup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', -- pending/approved/rejected
                method TEXT NOT NULL DEFAULT 'card',    -- card / stars
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur = await db.execute("PRAGMA table_info(topups)")
        cols = [row[1] for row in await cur.fetchall()]
        if "method" not in cols:
            await db.execute(
                "ALTER TABLE topups ADD COLUMN method TEXT NOT NULL DEFAULT 'card'"
            )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_chats (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                type TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS screens (
                user_id INTEGER PRIMARY KEY,
                message_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requisites (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                text TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                product_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                text TEXT NOT NULL,
                photo TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur = await db.execute("PRAGMA table_info(reviews)")
        cols = [row[1] for row in await cur.fetchall()]
        if "photo" not in cols:
            await db.execute("ALTER TABLE reviews ADD COLUMN photo TEXT")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL DEFAULT 1,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart_snaps (
                snap_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                items TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                user_id INTEGER PRIMARY KEY,      -- привязанный Telegram ID
                login TEXT NOT NULL UNIQUE,       -- в нижнем регистре
                email TEXT NOT NULL UNIQUE,       -- в нижнем регистре
                pass_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def get_or_create_user(user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await db.execute(
            "UPDATE users SET username = ? WHERE user_id = ?", (username, user_id)
        )
        await db.commit()
        cur = await db.execute(
            "SELECT user_id, username FROM users WHERE user_id = ?",
            (user_id,),
        )
        return await cur.fetchone()


async def touch_user(user_id, username, first_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, first_name, last_seen) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, "
            "first_name = excluded.first_name, last_seen = CURRENT_TIMESTAMP",
            (user_id, username, first_name),
        )
        await db.commit()


async def user_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async def one(q):
            cur = await db.execute(q)
            return (await cur.fetchone())[0]
        return {
            "total": await one("SELECT COUNT(*) FROM users"),
            "new_24h": await one("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')"),
            "new_7d": await one("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 day')"),
            "active_24h": await one("SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-1 day')"),
            "active_7d": await one("SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-7 day')"),
        }


async def list_users_full():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, username, first_name, created_at, last_seen FROM users ORDER BY created_at DESC"
        )
        return await cur.fetchall()


async def all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        return (await cur.fetchone())[0]


async def find_user(query):
    q = query.strip().lstrip("@")
    async with aiosqlite.connect(DB_PATH) as db:
        if q.isdigit():
            cur = await db.execute(
                "SELECT user_id, username FROM users WHERE user_id = ?",
                (int(q),),
            )
        else:
            cur = await db.execute(
                "SELECT user_id, username FROM users WHERE username = ? COLLATE NOCASE",
                (q,),
            )
        return await cur.fetchone()


async def random_user():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, username FROM users ORDER BY RANDOM() LIMIT 1"
        )
        return await cur.fetchone()


async def add_product(name, description, price, stock=-1,
                       photo=None, category=None):
    async with aiosqlite.connect(DB_PATH) as db:
        name, description = clean_text(name), clean_text(description)
        cur = await db.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM products")
        next_order = (await cur.fetchone())[0]
        cur = await db.execute(
            "INSERT INTO products (name, description, price, stock, photo, category, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, description, price, stock, photo, category, next_order),
        )
        await db.commit()
        return cur.lastrowid


async def remove_product(product_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE products SET active = 0 WHERE product_id = ?", (product_id,)
        )
        await db.commit()


async def set_product_active(product_id, active):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE products SET active = ? WHERE product_id = ?", (int(active), product_id)
        )
        await db.commit()


async def list_products(active_only=True, category=None):
    async with aiosqlite.connect(DB_PATH) as db:
        q = "SELECT product_id, name, description, price, stock, photo, category FROM products"
        conditions = []
        params = []
        if active_only:
            conditions.append("active = 1")
        if category is not None:
            conditions.append("category = ?")
            params.append(category)
        if conditions:
            q += " WHERE " + " AND ".join(conditions)
        q += " ORDER BY sort_order ASC, product_id ASC"
        cur = await db.execute(q, params)
        return await cur.fetchall()


async def get_product(product_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT product_id, name, description, price, stock, active, photo, category "
            "FROM products WHERE product_id = ?",
            (product_id,),
        )
        return await cur.fetchone()


async def decrement_stock(product_id):
    if product_id < 0:  # заказ из корзины: product_id = -номер снимка корзины
        snap = await snap_get(-product_id)
        async with aiosqlite.connect(DB_PATH) as db:
            for pid, _name, _price, qty in (snap["items"] if snap else []):
                await db.execute(
                    "UPDATE products SET stock = MAX(stock - ?, 0) WHERE product_id = ? AND stock > 0",
                    (qty, pid),
                )
            await db.commit()
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE products SET stock = stock - 1 WHERE product_id = ? AND stock > 0",
            (product_id,),
        )
        await db.commit()


async def update_product_field(product_id, field, value):
    assert field in ("name", "description", "price", "stock", "photo", "category")
    value = clean_text(value)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE products SET {field} = ? WHERE product_id = ?", (value, product_id)
        )
        await db.commit()


async def move_product(product_id, direction):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT sort_order, category FROM products WHERE product_id = ?", (product_id,)
        )
        row = await cur.fetchone()
        if not row:
            return False
        order, category = row
        cmp = "<" if direction == "up" else ">"
        order_by = "DESC" if direction == "up" else "ASC"
        if category is None:
            cur = await db.execute(
                f"SELECT product_id, sort_order FROM products WHERE category IS NULL AND sort_order {cmp} ? "
                f"ORDER BY sort_order {order_by} LIMIT 1",
                (order,),
            )
        else:
            cur = await db.execute(
                f"SELECT product_id, sort_order FROM products WHERE category = ? AND sort_order {cmp} ? "
                f"ORDER BY sort_order {order_by} LIMIT 1",
                (category, order),
            )
        neighbor = await cur.fetchone()
        if not neighbor:
            return False
        neighbor_id, neighbor_order = neighbor
        await db.execute("UPDATE products SET sort_order = ? WHERE product_id = ?", (neighbor_order, product_id))
        await db.execute("UPDATE products SET sort_order = ? WHERE product_id = ?", (order, neighbor_id))
        await db.commit()
        return True


async def seed_products_if_empty():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM products")
        count = (await cur.fetchone())[0]
        if count > 0:
            return
        starter_items = [
            ("Гемы x33", "33 гема", 100, -1, "bs_gems", 1),
            ("Гемы x88", "88 гемов", 149, -1, "bs_gems", 2),
            ("Гемы x187", "187 гемов", 289, -1, "bs_gems", 3),
            ("Гемы x396", "396 гемов", 399, -1, "bs_gems", 4),
            ("Гемы x1045", "1045 гемов", 799, -1, "bs_gems", 5),
            ("Гемы x2200", "2200 гемов", 1349, -1, "bs_gems", 6),
            ("Brawl Pass", "Обычный Brawl Pass", 299, -1, "bs_pass", 1),
            ("Brawl Pass Plus", "Brawl Pass Plus", 349, -1, "bs_pass", 2),
            ("Pro Pass", "Pro Pass", 549, -1, "bs_pass", 3),
            ("Улучшение до BP+", "Улучшение текущего пропуска до BP+", 499, -1, "bs_pass", 4),
            ("Матчерино пин", "Пин из Matcherino", 800, -1, "bs_pin", 1),
        ]
        await db.executemany(
            "INSERT INTO products (name, description, price, stock, category, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
            starter_items,
        )
        await db.commit()


async def add_category(key, game, name):
    name = clean_text(name)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM categories WHERE game = ?", (game,))
        next_order = (await cur.fetchone())[0]
        await db.execute(
            "INSERT INTO categories (key, game, name, sort_order, active) VALUES (?, ?, ?, ?, 1)",
            (key, game, name, next_order),
        )
        await db.commit()


async def category_exists(key):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM categories WHERE key = ?", (key,))
        return (await cur.fetchone()) is not None


async def list_categories(game=None, active_only=False):
    async with aiosqlite.connect(DB_PATH) as db:
        q = "SELECT key, game, name, sort_order, active FROM categories"
        conditions = []
        params = []
        if game is not None:
            conditions.append("game = ?")
            params.append(game)
        if active_only:
            conditions.append("active = 1")
        if conditions:
            q += " WHERE " + " AND ".join(conditions)
        q += " ORDER BY sort_order ASC"
        cur = await db.execute(q, params)
        return await cur.fetchall()


async def get_category(key):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT key, game, name, sort_order, active FROM categories WHERE key = ?", (key,)
        )
        return await cur.fetchone()


async def rename_category(key, new_name):
    new_name = clean_text(new_name)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE categories SET name = ? WHERE key = ?", (new_name, key))
        await db.commit()


async def toggle_category(key):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE categories SET active = 1 - active WHERE key = ?", (key,))
        await db.commit()


async def delete_category(key):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM products WHERE category = ?", (key,))
        affected = (await cur.fetchone())[0]
        await db.execute("UPDATE products SET category = NULL WHERE category = ?", (key,))
        await db.execute("DELETE FROM categories WHERE key = ?", (key,))
        await db.commit()
        return affected


async def move_category(key, direction):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT sort_order, game FROM categories WHERE key = ?", (key,))
        row = await cur.fetchone()
        if not row:
            return False
        order, game = row
        cmp = "<" if direction == "up" else ">"
        order_by = "DESC" if direction == "up" else "ASC"
        cur = await db.execute(
            f"SELECT key, sort_order FROM categories WHERE game = ? AND sort_order {cmp} ? "
            f"ORDER BY sort_order {order_by} LIMIT 1",
            (game, order),
        )
        neighbor = await cur.fetchone()
        if not neighbor:
            return False
        neighbor_key, neighbor_order = neighbor
        await db.execute("UPDATE categories SET sort_order = ? WHERE key = ?", (neighbor_order, key))
        await db.execute("UPDATE categories SET sort_order = ? WHERE key = ?", (order, neighbor_key))
        await db.commit()
        return True


async def add_promocode(code, discount_type, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO promocodes (code, discount_type, value, active) VALUES (?, ?, ?, 1)",
            (code, discount_type, value),
        )
        await db.commit()


async def get_promocode(code):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT code, discount_type, value, active FROM promocodes WHERE code = ?", (code.upper(),)
        )
        return await cur.fetchone()


async def list_promocodes():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT code, discount_type, value, active FROM promocodes ORDER BY created_at DESC"
        )
        return await cur.fetchall()


async def toggle_promocode(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE promocodes SET active = 1 - active WHERE code = ?", (code,))
        await db.commit()


async def delete_promocode(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promocodes WHERE code = ?", (code,))
        await db.commit()


async def create_order(user_id, product_id, product_name, price,
                        status="pending"):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, product_id, product_name, price, status) VALUES (?, ?, ?, ?, ?)",
            (user_id, product_id, product_name, price, status),
        )
        await db.commit()
        return cur.lastrowid


async def get_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT order_id, user_id, product_id, product_name, price, status FROM orders WHERE order_id = ?",
            (order_id,),
        )
        return await cur.fetchone()


async def set_order_status(order_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id)
        )
        await db.commit()


async def create_topup(user_id, amount, method="card", status="pending"):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO topups (user_id, amount, method, status) VALUES (?, ?, ?, ?)",
            (user_id, amount, method, status),
        )
        await db.commit()
        return cur.lastrowid


async def set_topup_status(topup_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE topups SET status = ? WHERE topup_id = ?", (status, topup_id)
        )
        await db.commit()


async def get_topup(topup_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT topup_id, user_id, amount, status FROM topups WHERE topup_id = ?",
            (topup_id,),
        )
        return await cur.fetchone()


async def register_chat(chat_id, title, chat_type):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO broadcast_chats (chat_id, title, type) VALUES (?, ?, ?)",
            (chat_id, title, chat_type),
        )
        await db.commit()


async def unregister_chat(chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM broadcast_chats WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def all_broadcast_chats():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT chat_id FROM broadcast_chats")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def set_requisites(text):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO requisites (id, text) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET text = excluded.text",
            (text,),
        )
        await db.commit()


async def get_requisites():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT text FROM requisites WHERE id = 1")
        row = await cur.fetchone()
        return row[0] if row else None


async def clear_requisites():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM requisites WHERE id = 1")
        await db.commit()


async def user_orders(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT order_id, product_name, price, created_at, status FROM orders "
            "WHERE user_id = ? ORDER BY order_id DESC",
            (user_id,),
        )
        return await cur.fetchall()


async def user_orders_ext(user_id, limit=20):
    # order_id, product_name, price, created_at, status, delivered, есть ли отзыв
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT o.order_id, o.product_name, o.price, o.created_at, o.status, COALESCE(o.delivered, 0), "
            "EXISTS(SELECT 1 FROM reviews r WHERE r.order_id = o.order_id) "
            "FROM orders o WHERE o.user_id = ? ORDER BY o.order_id DESC LIMIT ?",
            (user_id, limit),
        )
        return await cur.fetchall()


async def admin_orders(todo=False, limit=20):
    where = "WHERE o.status = 'pending' OR (o.status = 'confirmed' AND COALESCE(o.delivered, 0) = 0) " if todo else ""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT o.order_id, o.product_name, o.price, o.status, COALESCE(o.delivered, 0), o.user_id, u.username, o.created_at "
            "FROM orders o LEFT JOIN users u ON u.user_id = o.user_id " + where +
            "ORDER BY o.order_id DESC LIMIT ?", (limit,))
        return await cur.fetchall()


async def admin_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT o.order_id, o.product_name, o.price, o.status, COALESCE(o.delivered, 0), o.user_id, u.username, o.created_at "
            "FROM orders o LEFT JOIN users u ON u.user_id = o.user_id WHERE o.order_id = ?", (order_id,))
        return await cur.fetchone()


async def order_is_delivered(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(delivered, 0) FROM orders WHERE order_id = ?", (order_id,))
        row = await cur.fetchone()
        return bool(row and row[0])


async def set_order_delivered(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE orders SET delivered = 1 WHERE order_id = ? AND status = 'confirmed' AND COALESCE(delivered, 0) = 0",
            (order_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def has_review(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM reviews WHERE order_id = ? LIMIT 1", (order_id,))
        return (await cur.fetchone()) is not None


async def total_revenue():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'completed'"
        )
        return (await cur.fetchone())[0]


async def total_topped_up():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM topups WHERE status = 'approved'"
        )
        return (await cur.fetchone())[0]


async def order_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
        return (await cur.fetchone())[0]


async def add_review(order_id, user_id, username,
                      product_name, price, text, photo=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO reviews (order_id, user_id, username, product_name, price, text, photo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order_id, user_id, username, product_name, price, text, photo),
        )
        await db.commit()
        return cur.lastrowid


async def list_reviews(limit=5, offset=0):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT review_id, order_id, username, product_name, price, text, created_at "
            "FROM reviews ORDER BY review_id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return await cur.fetchall()


async def review_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM reviews")
        return (await cur.fetchone())[0]


async def get_setting(key, default=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row and row[0] is not None else default


async def set_setting(key, value):
    value = clean_text(value)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()


async def delete_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM settings WHERE key = ?", (key,))
        await db.commit()


async def get_screen(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT message_id FROM screens WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_screen(user_id, message_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO screens (user_id, message_id) VALUES (?, ?)", (user_id, message_id)
        )
        await db.commit()


async def clear_screen(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM screens WHERE user_id = ?", (user_id,))
        await db.commit()


async def seed_default_settings():
    defaults = {
        "doc_account_check": "https://telegra.ph/Proverka-akkaunta-pered-pokupkoj-09-29-4",
        "doc_terms": "https://telegra.ph/Polzovatelskoe-soglashenie-09-28-39",
        "doc_privacy": "https://telegra.ph/Politika-konfidencialnosti-09-28-107",
        "doc_support": "https://t.me/Phonker_sup",
    }
    async with aiosqlite.connect(DB_PATH) as db:
        for key, value in defaults.items():
            cur = await db.execute("SELECT 1 FROM settings WHERE key = ?", (key,))
            if await cur.fetchone() is None:
                await db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.execute(
            "UPDATE settings SET value = ? WHERE key = 'doc_account_check' AND value = ?",
            (defaults["doc_account_check"], "https://telegra.ph/Proverka-akkaunta-pered-pokupkoj-09-27"),
        )
        await db.commit()


CATALOG_MIGRATION_KEY = "catalog_update_2026_10"

_BS_GEMS = [
    (["Гемы x30", "Гемы x33"], "Гемы x33", "33 гема", 100, 1),
    (["Гемы x80", "Гемы x88"], "Гемы x88", "88 гемов", 149, 2),
    (["Гемы x170", "Гемы x187"], "Гемы x187", "187 гемов", 289, 3),
    (["Гемы x360", "Гемы x396"], "Гемы x396", "396 гемов", 399, 4),
    (["Гемы x950", "Гемы x1045"], "Гемы x1045", "1045 гемов", 799, 5),
    (["Гемы x2000", "Гемы x2200"], "Гемы x2200", "2200 гемов", 1349, 6),
]
_BS_PASSES = [
    (["Brawl Pass"], "Brawl Pass", "Обычный Brawl Pass", 299, 1),
    (["Brawl Pass Plus"], "Brawl Pass Plus", "Brawl Pass Plus", 349, 2),
    (["Pro Pass"], "Pro Pass", "Pro Pass", 549, 3),
]
_CLASH_GEMS = [
    ("Гемы x500", "500 гемов", 199, 1),
    ("Гемы x1200", "1200 гемов", 249, 2),
    ("Гемы x2500", "2500 гемов", 349, 3),
    ("Гемы x6500", "6500 гемов", 749, 4),
    ("Гемы x14000", "14000 гемов", 1299, 5),
    ("Гемы x42000", "42000 гемов", 2799, 6),
]
_CLASH_PASSES = [
    ("Пасс Рояль", "Pass Royale", 349, 1),
    ("Пасс Рояль (8 штук)", "Pass Royale, 8 штук", 1499, 2),
]


async def migrate_catalog_prices_and_clash():
    if await get_setting(CATALOG_MIGRATION_KEY):
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async def upsert_bs(category, items):
            for names, new_name, desc, price, order in items:
                marks = ",".join("?" * len(names))
                cur = await db.execute(
                    f"SELECT product_id FROM products WHERE category = ? AND name IN ({marks}) LIMIT 1",
                    (category, *names),
                )
                row = await cur.fetchone()
                if row:
                    await db.execute(
                        "UPDATE products SET name = ?, description = ?, price = ? WHERE product_id = ?",
                        (new_name, desc, price, row[0]),
                    )
                else:
                    await db.execute(
                        "INSERT INTO products (name, description, price, stock, category, sort_order) "
                        "VALUES (?, ?, ?, -1, ?, ?)",
                        (new_name, desc, price, category, order),
                    )

        for key, items in (("bs_gems", _BS_GEMS), ("bs_pass", _BS_PASSES)):
            cur = await db.execute("SELECT 1 FROM categories WHERE key = ?", (key,))
            if await cur.fetchone():
                await upsert_bs(key, items)

        cur = await db.execute("SELECT COUNT(*) FROM categories WHERE game = 'clash'")
        if (await cur.fetchone())[0] == 0:
            await db.executemany(
                "INSERT INTO categories (key, game, name, sort_order, active) VALUES (?, 'clash', ?, ?, 1)",
                [("clash_gems", "💎 Гемы", 1), ("clash_pass", "🎟 Пассы", 2)],
            )
            await db.executemany(
                "INSERT INTO products (name, description, price, stock, category, sort_order) "
                "VALUES (?, ?, ?, -1, 'clash_gems', ?)",
                _CLASH_GEMS,
            )
            await db.executemany(
                "INSERT INTO products (name, description, price, stock, category, sort_order) "
                "VALUES (?, ?, ?, -1, 'clash_pass', ?)",
                _CLASH_PASSES,
            )
        await db.commit()
    await set_setting(CATALOG_MIGRATION_KEY, "1")


async def normalize_saved_texts():
    if await get_setting("text_norm_2026_10"):
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE settings SET value = REPLACE(value, ?, '-') WHERE value LIKE ?", (_LD, "%" + _LD + "%"))
        await db.execute("UPDATE products SET name = REPLACE(name, ?, '-'), description = REPLACE(description, ?, '-')", (_LD, _LD))
        await db.execute("UPDATE categories SET name = REPLACE(name, ?, '-')", (_LD,))
        await db.commit()
    await set_setting("text_norm_2026_10", "1")


async def admin_list():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, username FROM admins ORDER BY added_at")
        return await cur.fetchall()


async def admin_add(user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO admins (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.commit()


async def admin_remove(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()


async def sync_catalog(base_categories, base_products, removed_categories, removed_products=()):
    """Восстанавливает базовые разделы и товары, если их нет. Существующее не трогает."""
    async with aiosqlite.connect(DB_PATH) as db:
        for key, game, name, order in base_categories:
            cur = await db.execute("SELECT 1 FROM categories WHERE key = ?", (key,))
            if await cur.fetchone() is None:
                await db.execute(
                    "INSERT INTO categories (key, game, name, sort_order, active) VALUES (?, ?, ?, ?, 1)",
                    (key, game, name, order),
                )
        for name, desc, price, category, order in base_products:
            cur = await db.execute(
                "SELECT product_id FROM products WHERE category = ? AND name = ?", (category, name)
            )
            row = await cur.fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO products (name, description, price, stock, category, sort_order) "
                    "VALUES (?, ?, ?, -1, ?, ?)",
                    (name, desc, price, category, order),
                )
            # существующий товар не трогаем: цены и описания, изменённые админом (в боте или мини-аппе),
            # не должны откатываться при перезапуске
        for category, name in removed_products:
            await db.execute(
                "UPDATE products SET active = 0 WHERE category = ? AND name = ?", (category, name)
            )
        for key in removed_categories:
            await db.execute("UPDATE products SET active = 0 WHERE category = ?", (key,))
            await db.execute("DELETE FROM categories WHERE key = ?", (key,))
        await db.commit()


async def pg_add(tx_id, user_id, product_id, price, promo):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO platega_tx (tx_id, user_id, product_id, price, promo, status) "
            "VALUES (?, ?, ?, ?, ?, 'pending')",
            (tx_id, user_id, product_id, price, promo),
        )
        await db.commit()


async def pg_get(tx_id):
    # (tx_id, user_id, product_id, price, promo, status, order_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT tx_id, user_id, product_id, price, promo, status, order_id "
            "FROM platega_tx WHERE tx_id = ?",
            (tx_id,),
        )
        return await cur.fetchone()


async def pg_claim(tx_id, new_status):
    """Меняет статус только с pending - чтобы заказ не оформился дважды."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE platega_tx SET status = ? WHERE tx_id = ? AND status = 'pending'",
            (new_status, tx_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def pg_set_order(tx_id, order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE platega_tx SET order_id = ? WHERE tx_id = ?", (order_id, tx_id))
        await db.commit()


async def pg_pending():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT tx_id FROM platega_tx WHERE status = 'pending'")
        return [r[0] for r in await cur.fetchall()]



# ---------------- Корзина ----------------
CART_MAX_QTY = 10
CART_MAX_LINES = 10


async def cart_items(user_id):
    """[(product_id, name, price, qty, stock, active)] - только существующие товары."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT p.product_id, p.name, p.price, c.qty, p.stock, p.active "
            "FROM cart c JOIN products p ON p.product_id = c.product_id "
            "WHERE c.user_id = ? ORDER BY c.added_at, p.product_id",
            (user_id,),
        )
        return await cur.fetchall()


async def cart_add(user_id, product_id):
    """Возвращает 'ok', 'max_qty' или 'max_lines'."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT qty FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        row = await cur.fetchone()
        if row:
            if row[0] >= CART_MAX_QTY:
                return "max_qty"
            await db.execute(
                "UPDATE cart SET qty = qty + 1 WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        else:
            cur = await db.execute("SELECT COUNT(*) FROM cart WHERE user_id = ?", (user_id,))
            if (await cur.fetchone())[0] >= CART_MAX_LINES:
                return "max_lines"
            await db.execute(
                "INSERT INTO cart (user_id, product_id, qty) VALUES (?, ?, 1)", (user_id, product_id))
        await db.commit()
        return "ok"


async def cart_change(user_id, product_id, delta):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE cart SET qty = MIN(qty + ?, ?) WHERE user_id = ? AND product_id = ?",
            (delta, CART_MAX_QTY, user_id, product_id),
        )
        await db.execute("DELETE FROM cart WHERE user_id = ? AND qty <= 0", (user_id,))
        await db.commit()


async def cart_remove(user_id, product_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        await db.commit()


async def cart_clear(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await db.commit()


async def snap_create(user_id, name, price, items):
    """items: [(product_id, name, price, qty)]. Возвращает snap_id."""
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO cart_snaps (user_id, name, price, items) VALUES (?, ?, ?, ?)",
            (user_id, name, price, json.dumps(items, ensure_ascii=False)),
        )
        await db.commit()
        return cur.lastrowid


async def snap_get(snap_id):
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT snap_id, user_id, name, price, items FROM cart_snaps WHERE snap_id = ?", (snap_id,))
        row = await cur.fetchone()
    if not row:
        return None
    return {"snap_id": row[0], "user_id": row[1], "name": row[2], "price": row[3], "items": json.loads(row[4])}


# ---------------- Очередь и профиль ----------------
# В очереди - оплаченные заказы, которые ещё не выданы. Порядок - по номеру заказа.
_QUEUE_WHERE = "status = 'confirmed' AND COALESCE(delivered, 0) = 0"


async def queue_total():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(f"SELECT COUNT(*) FROM orders WHERE {_QUEUE_WHERE}")
        return (await cur.fetchone())[0]


async def user_queue(user_id):
    """[(order_id, product_name, position)] - оплаченные невыданные заказы пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            f"SELECT o.order_id, o.product_name, "
            f"(SELECT COUNT(*) FROM orders q WHERE q.status = 'confirmed' AND COALESCE(q.delivered, 0) = 0 "
            f" AND q.order_id <= o.order_id) "
            f"FROM orders o WHERE o.user_id = ? AND o.{_QUEUE_WHERE} ORDER BY o.order_id",
            (user_id,),
        )
        return await cur.fetchall()


async def user_pending_orders(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT order_id, product_name FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY order_id",
            (user_id,),
        )
        return await cur.fetchall()


async def user_profile_stats(user_id):
    """(заказов, потрачено) по оплаченным заказам."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders "
            "WHERE user_id = ? AND status IN ('confirmed', 'completed')",
            (user_id,),
        )
        return await cur.fetchone()


# ---------------- Аккаунты мини-приложения (логин, почта, пароль) ----------------
async def account_get(user_id):
    """(user_id, login, email) или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, login, email FROM accounts WHERE user_id = ?", (user_id,))
        return await cur.fetchone()


async def account_user_ids():
    """Telegram ID всех, кто зарегистрировался в мини-аппе."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM accounts")
        return [r[0] for r in await cur.fetchall()]


async def account_by_login(login):
    """(user_id, login, email, pass_hash) или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, login, email, pass_hash FROM accounts WHERE login = ?", (login.lower(),))
        return await cur.fetchone()


async def account_create(user_id, login, email, pass_hash):
    """Возвращает None при успехе или 'user' / 'login' / 'email', что уже занято."""
    login, email = login.lower(), email.lower()
    async with aiosqlite.connect(DB_PATH) as db:
        for col, val, tag in (("user_id", user_id, "user"), ("login", login, "login"), ("email", email, "email")):
            cur = await db.execute(f"SELECT 1 FROM accounts WHERE {col} = ?", (val,))
            if await cur.fetchone():
                return tag
        await db.execute(
            "INSERT INTO accounts (user_id, login, email, pass_hash) VALUES (?, ?, ?, ?)",
            (user_id, login, email, pass_hash))
        await db.commit()
    return None


# ---------- чат по заказу (сайт) ----------
async def _chat_ensure(db):
    await db.execute(
        "CREATE TABLE IF NOT EXISTS order_messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, "
        "sender TEXT NOT NULL, text TEXT NOT NULL, created_at REAL NOT NULL)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_om_order ON order_messages(order_id, id)")


async def chat_add(order_id, sender, text):
    import time as _t
    async with aiosqlite.connect(DB_PATH) as db:
        await _chat_ensure(db)
        cur = await db.execute(
            "INSERT INTO order_messages (order_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
            (order_id, sender, text, _t.time()))
        await db.commit()
        return cur.lastrowid


async def chat_list(order_id, after=0, limit=200):
    async with aiosqlite.connect(DB_PATH) as db:
        await _chat_ensure(db)
        cur = await db.execute(
            "SELECT id, sender, text, created_at FROM order_messages "
            "WHERE order_id = ? AND id > ? ORDER BY id LIMIT ?", (order_id, after, limit))
        return await cur.fetchall()


async def chat_recent(limit=30):
    """Последние чаты по заказам: заказ, кто написал последним, текст, товар, статус, покупатель."""
    async with aiosqlite.connect(DB_PATH) as db:
        await _chat_ensure(db)
        cur = await db.execute(
            "SELECT m.order_id, m.sender, m.text, m.created_at, o.product_name, o.status, u.username, o.user_id "
            "FROM order_messages m "
            "JOIN (SELECT order_id, MAX(id) mid FROM order_messages GROUP BY order_id) x ON x.mid = m.id "
            "JOIN orders o ON o.order_id = m.order_id "
            "LEFT JOIN users u ON u.user_id = o.user_id "
            "ORDER BY m.id DESC LIMIT ?", (limit,))
        return await cur.fetchall()


async def reviews_list(offset=0, limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT review_id, username, product_name, text, photo IS NOT NULL AND photo != '', created_at "
            "FROM reviews ORDER BY review_id DESC LIMIT ? OFFSET ?", (limit, offset))
        return await cur.fetchall()


async def review_photo(review_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT photo FROM reviews WHERE review_id = ?", (review_id,))
        r = await cur.fetchone()
        return r[0] if r else None
