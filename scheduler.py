"""
Background scheduler: sends reminders for stalled deals.

Thresholds (configurable in config.py):
  - REMIND_WAITING_HOURS  — deal stuck in "waiting" (no buyer)
  - REMIND_CHECK_HOURS    — deal stuck in "check" (seller hasn't confirmed)
  - REMIND_PAYMENT_HOURS  — deal stuck in "payment" (buyer hasn't paid)
  - SCHEDULER_INTERVAL    — how often the loop runs (seconds)
"""

import asyncio
from datetime import datetime, timezone

import aiosqlite
from aiogram import Bot

from database import DB_PATH
from utils.logger import logger


# How many hours before we remind
REMIND_WAITING_HOURS  = 24   # seller created deal, no buyer for 24 h
REMIND_PAYMENT_HOURS  = 6    # buyer joined but hasn't paid for 6 h
REMIND_CHECK_HOURS    = 6    # buyer marked paid, seller hasn't confirmed for 6 h

SCHEDULER_INTERVAL    = 3600  # check every 60 minutes


def _hours_since(ts_str: str) -> float:
    """Return hours elapsed since a UTC datetime string."""
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 3600


async def _send_safe(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
    except Exception as exc:
        logger.warning("Reminder send failed to %s: %s", chat_id, exc)


async def _run_once(bot: Bot):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM deals
            WHERE status IN ('waiting', 'payment', 'check')
        """) as cur:
            deals = await cur.fetchall()

    for deal in deals:
        deal = dict(deal)
        deal_id   = deal["deal_id"]
        status    = deal["status"]
        hours     = _hours_since(deal["updated_at"])

        if status == "waiting" and hours >= REMIND_WAITING_HOURS:
            logger.info("Reminder: deal %s waiting %.1fh", deal_id, hours)
            await _send_safe(
                bot, deal["seller_id"],
                f"⏳ <b>Напоминание по сделке #{deal_id}</b>\n\n"
                f"Покупатель ещё не присоединился уже <b>{int(hours)} ч.</b>\n"
                f"Отправьте ссылку ещё раз или отмените сделку, если она не актуальна.",
            )

        elif status == "payment" and hours >= REMIND_PAYMENT_HOURS:
            logger.info("Reminder: deal %s payment %.1fh", deal_id, hours)
            if deal["buyer_id"]:
                await _send_safe(
                    bot, deal["buyer_id"],
                    f"💸 <b>Напоминание по сделке #{deal_id}</b>\n\n"
                    f"Вы ещё не отметили оплату (<b>{int(hours)} ч.</b>).\n"
                    f"Отправьте средства и нажмите «Отметить оплату», или откройте спор.",
                )
            await _send_safe(
                bot, deal["seller_id"],
                f"⏳ <b>Напоминание по сделке #{deal_id}</b>\n\n"
                f"Покупатель ещё не отметил оплату (<b>{int(hours)} ч.</b>).",
            )

        elif status == "check" and hours >= REMIND_CHECK_HOURS:
            logger.info("Reminder: deal %s check %.1fh", deal_id, hours)
            await _send_safe(
                bot, deal["seller_id"],
                f"🔍 <b>Напоминание по сделке #{deal_id}</b>\n\n"
                f"Покупатель отметил оплату <b>{int(hours)} ч.</b> назад.\n"
                f"Пожалуйста, проверьте поступление средств и подтвердите получение.",
            )
            if deal["buyer_id"]:
                await _send_safe(
                    bot, deal["buyer_id"],
                    f"🔍 <b>Напоминание по сделке #{deal_id}</b>\n\n"
                    f"Продавец ещё не подтвердил получение (<b>{int(hours)} ч.</b>).\n"
                    f"Если есть проблема — откройте спор.",
                )


async def start_scheduler(bot: Bot):
    """Run indefinitely, checking for stalled deals every SCHEDULER_INTERVAL seconds."""
    logger.info("Scheduler started (interval=%ds)", SCHEDULER_INTERVAL)
    while True:
        try:
            await _run_once(bot)
        except Exception as exc:
            logger.error("Scheduler error: %s", exc, exc_info=True)
        await asyncio.sleep(SCHEDULER_INTERVAL)
