import json
from typing import Any, Dict, Optional

import aiosqlite
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path="fsm.db"):
        self.db_path = db_path
        self._ready = False

    @staticmethod
    def _key(key):
        destiny = getattr(key, "destiny", "default")
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id}:{destiny}"

    async def _ensure_table(self):
        if self._ready:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS fsm (key TEXT PRIMARY KEY, state TEXT, data TEXT)"
            )
            await db.commit()
        self._ready = True

    async def close(self):
        pass

    async def set_state(self, key, state=None):
        await self._ensure_table()
        state_str = state.state if hasattr(state, "state") else state
        k = self._key(key)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT data FROM fsm WHERE key = ?", (k,))
            row = await cur.fetchone()
            data = row[0] if row else "{}"
            await db.execute(
                "INSERT OR REPLACE INTO fsm (key, state, data) VALUES (?, ?, ?)",
                (k, state_str, data),
            )
            await db.commit()

    async def get_state(self, key):
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT state FROM fsm WHERE key = ?", (self._key(key),))
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_data(self, key, data):
        await self._ensure_table()
        k = self._key(key)
        payload = json.dumps(data)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT state FROM fsm WHERE key = ?", (k,))
            row = await cur.fetchone()
            state_str = row[0] if row else None
            await db.execute(
                "INSERT OR REPLACE INTO fsm (key, state, data) VALUES (?, ?, ?)",
                (k, state_str, payload),
            )
            await db.commit()

    async def get_data(self, key):
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT data FROM fsm WHERE key = ?", (self._key(key),))
            row = await cur.fetchone()
            return json.loads(row[0]) if row and row[0] else {}
