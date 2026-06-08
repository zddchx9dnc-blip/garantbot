import aiosqlite
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "bot.db"
DB_PATH.parent.mkdir(exist_ok=True)

STATUSES = {
    "waiting":   "⏳ Ожидание",
    "payment":   "💸 Оплата отправлена",
    "check":     "🔍 Проверка",
    "done":      "✅ Завершено",
    "dispute":   "⚠️ Спор",
    "cancelled": "❌ Отменено",
}


CURRENCIES = ("руб", "usdt", "звезды")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                is_blocked  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS balances (
                user_id   INTEGER NOT NULL,
                currency  TEXT NOT NULL,
                amount    REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, currency)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                deal_id     TEXT PRIMARY KEY,
                seller_id   INTEGER NOT NULL,
                buyer_id    INTEGER,
                item        TEXT NOT NULL,
                amount      REAL NOT NULL,
                payment     TEXT NOT NULL,
                description TEXT,
                status      TEXT DEFAULT 'waiting',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deal_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id     TEXT NOT NULL,
                actor_id    INTEGER,
                action      TEXT NOT NULL,
                ts          TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()


# ── Users ────────────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: str | None, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
        """, (user_id, username, full_name))
        await db.commit()


async def is_blocked(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT is_blocked FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])


async def block_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def unblock_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ) as cur:
            return await cur.fetchall()


# ── Deals ────────────────────────────────────────────────────────────────────

def _new_deal_id() -> str:
    return uuid.uuid4().hex[:8].upper()


async def create_deal(
    seller_id: int,
    item: str,
    amount: float,
    payment: str,
    description: str,
) -> str:
    deal_id = _new_deal_id()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO deals (deal_id, seller_id, item, amount, payment, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (deal_id, seller_id, item, amount, payment, description))
        await db.execute("""
            INSERT INTO deal_history (deal_id, actor_id, action)
            VALUES (?, ?, 'created')
        """, (deal_id, seller_id))
        await db.commit()
    return deal_id


async def get_deal(deal_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM deals WHERE deal_id = ?", (deal_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def join_deal(deal_id: str, buyer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE deals SET buyer_id = ?, status = 'payment',
                updated_at = datetime('now')
            WHERE deal_id = ? AND buyer_id IS NULL
        """, (buyer_id, deal_id))
        await db.execute("""
            INSERT INTO deal_history (deal_id, actor_id, action)
            VALUES (?, ?, 'buyer_joined')
        """, (deal_id, buyer_id))
        await db.commit()


async def update_deal_status(deal_id: str, status: str, actor_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE deals SET status = ?, updated_at = datetime('now')
            WHERE deal_id = ?
        """, (status, deal_id))
        await db.execute("""
            INSERT INTO deal_history (deal_id, actor_id, action)
            VALUES (?, ?, ?)
        """, (deal_id, actor_id, f"status:{status}"))
        await db.commit()


async def get_user_deals(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM deals
            WHERE seller_id = ? OR buyer_id = ?
            ORDER BY created_at DESC
        """, (user_id, user_id)) as cur:
            return await cur.fetchall()


async def get_all_deals():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM deals ORDER BY created_at DESC"
        ) as cur:
            return await cur.fetchall()


async def count_active_deals(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM deals
            WHERE (seller_id = ? OR buyer_id = ?)
              AND status NOT IN ('done', 'cancelled')
        """, (user_id, user_id)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM deals") as cur:
            total_deals = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM deals WHERE status = 'done'"
        ) as cur:
            done_deals = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM deals WHERE status = 'dispute'"
        ) as cur:
            disputes = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM deals WHERE status = 'done'"
        ) as cur:
            volume = (await cur.fetchone())[0]
    return {
        "total_users": total_users,
        "total_deals": total_deals,
        "done_deals": done_deals,
        "disputes": disputes,
        "volume": volume,
    }


# ── Balances ─────────────────────────────────────────────────────────────────

async def ensure_balance_user(user_id: int):
    """Make sure the user row exists so foreign-key-like inserts work."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, full_name)
            VALUES (?, '—')
        """, (user_id,))
        await db.commit()


async def add_balance(user_id: int, currency: str, amount: float) -> float:
    """Add amount to user's balance for given currency. Returns new balance."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO balances (user_id, currency, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, currency) DO UPDATE SET
                amount = amount + excluded.amount
        """, (user_id, currency, amount))
        await db.commit()
        async with db.execute(
            "SELECT amount FROM balances WHERE user_id = ? AND currency = ?",
            (user_id, currency),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else amount


async def get_balances(user_id: int) -> dict[str, float]:
    """Return {currency: amount} for all currencies (0 if never set)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT currency, amount FROM balances WHERE user_id = ?", (user_id,)
        ) as cur:
            rows = await cur.fetchall()
    result = {c: 0.0 for c in CURRENCIES}
    for currency, amount in rows:
        result[currency] = amount
    return result
