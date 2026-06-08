from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import database as db
from utils.logger import logger

router = Router()

CURRENCY_LABELS = {
    "руб":    "🇷🇺 Рублей",
    "usdt":   "💵 USDT",
    "звезды": "⭐ Звёзд",
}


def _balance_card(user_id: int, full_name: str, balances: dict) -> str:
    rub   = balances["руб"]
    usdt  = balances["usdt"]
    stars = balances["звезды"]
    return (
        "╔══════════════════════╗\n"
        "       💼  МОЙ БАЛАНС\n"
        "╚══════════════════════╝\n\n"
        f"👤 <b>{full_name}</b>\n"
        f"🆔 <code>{user_id}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🇷🇺  Рубли:    <b>{rub:>12,.2f} ₽</b>\n"
        f"💵  USDT:     <b>{usdt:>12,.2f} $</b>\n"
        f"⭐  Звёзды:   <b>{stars:>12,.0f} ★</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💬 Для пополнения: @skippersupport"
    )


# ── /balance ─────────────────────────────────────────────────────────────────

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    user = message.from_user
    await db.upsert_user(user.id, user.username, user.full_name)
    balances = await db.get_balances(user.id)
    await message.answer(
        _balance_card(user.id, user.full_name, balances),
        parse_mode="HTML",
    )


# ── /add command ─────────────────────────────────────────────────────────────
# Usage: /add <user_id> <amount> <currency>
# Currency: руб | usdt | звезды

@router.message(Command("add"))
async def cmd_add(message: Message):
    parts = message.text.strip().split()

    if len(parts) != 4:
        await message.answer(
            "❌ <b>Неверный формат.</b>\n\n"
            "Используй:\n<code>/add &lt;user_id&gt; &lt;сумма&gt; &lt;валюта&gt;</code>\n\n"
            "Валюты: <code>руб</code> · <code>usdt</code> · <code>звезды</code>\n\n"
            "Пример: <code>/add 123456789 500 руб</code>",
            parse_mode="HTML",
        )
        return

    _, raw_uid, raw_amount, raw_currency = parts
    currency = raw_currency.lower()

    try:
        target_id = int(raw_uid)
    except ValueError:
        await message.answer("❌ <code>user_id</code> должен быть числом.", parse_mode="HTML")
        return

    try:
        amount = float(raw_amount.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Сумма должна быть положительным числом.")
        return

    if currency not in db.CURRENCIES:
        await message.answer(
            f"❌ Неизвестная валюта <code>{raw_currency}</code>.\n"
            f"Доступные: <code>руб</code> · <code>usdt</code> · <code>звезды</code>",
            parse_mode="HTML",
        )
        return

    await db.ensure_balance_user(target_id)
    new_balance = await db.add_balance(target_id, currency, amount)
    label = CURRENCY_LABELS[currency]

    logger.info(
        "Balance +%.2f %s to user %s by user %s",
        amount, currency, target_id, message.from_user.id,
    )

    await message.answer(
        "╔══════════════════════╗\n"
        "    ✅  БАЛАНС ПОПОЛНЕН\n"
        "╚══════════════════════╝\n\n"
        f"👤 Пользователь: <code>{target_id}</code>\n\n"
        f"➕ Начислено:    <b>{amount:,.2f} {label}</b>\n"
        f"💼 Новый баланс: <b>{new_balance:,.2f} {label}</b>",
        parse_mode="HTML",
    )
