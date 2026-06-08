from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from typing import Callable, Awaitable, Any
import time

from config import SPAM_INTERVAL


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self):
        self._last: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()
        last = self._last.get(user_id, 0)
        if now - last < SPAM_INTERVAL:
            await event.answer("⚠️ Пожалуйста, не спамьте. Подождите немного.")
            return
        self._last[user_id] = now
        return await handler(event, data)
