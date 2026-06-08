import asyncio
import sys
import os

# Make sure imports work from this directory
sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
from config import BOT_TOKEN
from handlers import start, deal, admin, balance
from middlewares.anti_spam import AntiSpamMiddleware
from scheduler import start_scheduler
from utils.logger import logger


async def main():
    logger.info("Initialising database...")
    await db.init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware
    dp.message.middleware(AntiSpamMiddleware())

    # Routers (order matters)
    dp.include_router(balance.router)
    dp.include_router(start.router)
    dp.include_router(deal.router)
    dp.include_router(admin.router)

    logger.info("Bot is starting...")
    await bot.delete_webhook(drop_pending_updates=True)

    # Start background reminder scheduler
    scheduler_task = asyncio.create_task(start_scheduler(bot))

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
