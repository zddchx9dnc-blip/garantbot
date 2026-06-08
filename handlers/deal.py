from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import database as db
from config import ADMIN_ID, MAX_DEAL_PER_USER
from database import STATUSES
from keyboards.inline import (
    cancel_kb, deal_seller_kb, deal_buyer_kb,
    join_deal_kb, back_to_menu_kb, main_menu_kb,
)
from utils.logger import logger

router = Router()


class DealForm(StatesGroup):
    item        = State()
    amount      = State()
    payment     = State()
    description = State()


def _deal_card(deal: dict, viewer_id: int) -> str:
    status_label = STATUSES.get(deal["status"], deal["status"])
    role = "🧑‍💼 Продавец" if deal["seller_id"] == viewer_id else "🛒 Покупатель"
    buyer_line = f"Покупатель: {'ожидается' if not deal['buyer_id'] else '✅ подтверждён'}"
    return (
        f"🔖 <b>Сделка #{deal['deal_id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Товар/услуга: <b>{deal['item']}</b>\n"
        f"💰 Сумма: <b>{deal['amount']:,.2f}</b>\n"
        f"💳 Оплата: <b>{deal['payment']}</b>\n"
        f"📝 Описание: {deal['description'] or '—'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Статус: {status_label}\n"
        f"👤 Ваша роль: {role}\n"
        f"{buyer_line}\n"
        f"🕒 Создана: {deal['created_at'][:16]}"
    )


# ── Create deal FSM ──────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "deal:create")
async def cb_create_deal(call: CallbackQuery, state: FSMContext):
    user = call.from_user
    if await db.is_blocked(user.id):
        await call.answer("🚫 Вы заблокированы.", show_alert=True)
        return

    active = await db.count_active_deals(user.id)
    if active >= MAX_DEAL_PER_USER:
        await call.answer(
            f"⚠️ У вас уже {active} активных сделок. Завершите старые перед созданием новых.",
            show_alert=True,
        )
        return

    await state.set_state(DealForm.item)
    await call.message.edit_text(
        "📦 <b>Создание новой сделки</b>\n\n"
        "Шаг 1/4 — Что вы продаёте?\n"
        "Введите название товара или услуги:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.callback_query(lambda c: c.data == "deal:cancel_create")
async def cb_cancel_create(call: CallbackQuery, state: FSMContext):
    await state.clear()
    is_admin = call.from_user.id == ADMIN_ID
    await call.message.edit_text(
        "❌ Создание сделки отменено.\n\nВыберите действие:",
        reply_markup=main_menu_kb(is_admin),
    )
    await call.answer()


@router.message(DealForm.item)
async def fsm_item(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 2:
        await message.answer("⚠️ Слишком короткое название. Попробуйте ещё раз:", reply_markup=cancel_kb())
        return
    await state.update_data(item=text)
    await state.set_state(DealForm.amount)
    await message.answer(
        "💰 <b>Шаг 2/4 — Сумма сделки</b>\n\nВведите сумму (числом, например: 1500):",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(DealForm.amount)
async def fsm_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректную сумму (например: 500 или 1500.50):", reply_markup=cancel_kb())
        return
    await state.update_data(amount=amount)
    await state.set_state(DealForm.payment)
    await message.answer(
        "💳 <b>Шаг 3/4 — Способ оплаты</b>\n\nУкажите способ оплаты:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(DealForm.payment)
async def fsm_payment(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 2:
        await message.answer("⚠️ Укажите способ оплаты:", reply_markup=cancel_kb())
        return
    await state.update_data(payment=text)
    await state.set_state(DealForm.description)
    await message.answer(
        "📝 <b>Шаг 4/4 — Описание товара</b>\n\n"
        "Добавьте описание товара/услуги или напишите «-» чтобы пропустить:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(DealForm.description)
async def fsm_description(message: Message, state: FSMContext, bot: Bot):
    desc = message.text.strip()
    if desc == "-":
        desc = ""

    data = await state.get_data()
    await state.clear()

    deal_id = await db.create_deal(
        seller_id=message.from_user.id,
        item=data["item"],
        amount=data["amount"],
        payment=data["payment"],
        description=desc,
    )
    await db.upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )

    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=deal_{deal_id}"

    logger.info("Deal %s created by user %s", deal_id, message.from_user.id)

    await message.answer(
        f"✅ <b>Сделка создана!</b>\n\n"
        f"🔖 ID сделки: <code>{deal_id}</code>\n"
        f"📦 Товар: {data['item']}\n"
        f"💰 Сумма: {data['amount']:,.2f}\n"
        f"💳 Оплата: {data['payment']}\n\n"
        f"🔗 <b>Ссылка для покупателя:</b>\n"
        f"<code>{invite_link}</code>\n\n"
        f"Отправьте эту ссылку покупателю. Ожидаю подтверждения...",
        parse_mode="HTML",
        reply_markup=deal_seller_kb(deal_id, "waiting"),
    )


# ── Join deal via deep link ──────────────────────────────────────────────────

@router.message(CommandStart(deep_link=True))
async def cmd_start_deep(message: Message, bot: Bot):
    payload = message.text.split(maxsplit=1)[-1]  # e.g. "deal_ABCD1234"
    if not payload.startswith("deal_"):
        return

    deal_id = payload[5:]
    user = message.from_user
    await db.upsert_user(user.id, user.username, user.full_name)

    if await db.is_blocked(user.id):
        await message.answer("🚫 Вы заблокированы.")
        return

    deal = await db.get_deal(deal_id)
    if not deal:
        await message.answer("❌ Сделка не найдена.")
        return

    if deal["seller_id"] == user.id:
        await message.answer(
            "ℹ️ Вы являетесь продавцом этой сделки.\n\nВы не можете присоединиться как покупатель.",
            reply_markup=deal_seller_kb(deal_id, deal["status"]),
        )
        return

    if deal["buyer_id"]:
        if deal["buyer_id"] == user.id:
            deal_text = _deal_card(deal, user.id)
            await message.answer(
                f"ℹ️ Вы уже участвуете в этой сделке.\n\n{deal_text}",
                parse_mode="HTML",
                reply_markup=deal_buyer_kb(deal_id, deal["status"]),
            )
        else:
            await message.answer("❌ В этой сделке уже есть покупатель.")
        return

    if deal["status"] != "waiting":
        await message.answer("❌ Эта сделка уже не принимает участников.")
        return

    deal_text = _deal_card(deal, user.id)
    await message.answer(
        f"🤝 <b>Приглашение в сделку</b>\n\n{deal_text}\n\n"
        f"Хотите присоединиться как покупатель?",
        parse_mode="HTML",
        reply_markup=join_deal_kb(deal_id),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("deal:join:"))
async def cb_join_deal(call: CallbackQuery, bot: Bot):
    deal_id = call.data.split(":", 2)[2]
    user = call.from_user

    if await db.is_blocked(user.id):
        await call.answer("🚫 Вы заблокированы.", show_alert=True)
        return

    deal = await db.get_deal(deal_id)
    if not deal or deal["seller_id"] == user.id:
        await call.answer("❌ Невозможно присоединиться.", show_alert=True)
        return
    if deal["buyer_id"]:
        await call.answer("❌ Место покупателя уже занято.", show_alert=True)
        return
    if deal["status"] != "waiting":
        await call.answer("❌ Сделка уже не активна.", show_alert=True)
        return

    await db.join_deal(deal_id, user.id)
    await db.upsert_user(user.id, user.username, user.full_name)

    deal = await db.get_deal(deal_id)
    deal_text = _deal_card(deal, user.id)
    logger.info("User %s joined deal %s", user.id, deal_id)

    # Notify buyer
    await call.message.edit_text(
        f"✅ <b>Вы присоединились к сделке!</b>\n\n{deal_text}\n\n"
        f"Отправьте оплату и нажмите кнопку ниже:",
        parse_mode="HTML",
        reply_markup=deal_buyer_kb(deal_id, "payment"),
    )

    # Notify seller
    try:
        await bot.send_message(
            deal["seller_id"],
            f"🎉 <b>Покупатель присоединился к сделке #{deal_id}!</b>\n\n"
            f"Покупатель: {user.full_name} (@{user.username or 'нет'})\n\n"
            f"Ожидаю подтверждения оплаты от покупателя...",
            parse_mode="HTML",
            reply_markup=deal_seller_kb(deal_id, "payment"),
        )
    except Exception:
        pass

    await call.answer()


# ── Deal status actions ──────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("deal:paid:"))
async def cb_paid(call: CallbackQuery, bot: Bot):
    deal_id = call.data.split(":", 2)[2]
    user = call.from_user
    deal = await db.get_deal(deal_id)

    if not deal or deal["buyer_id"] != user.id:
        await call.answer("❌ Нет доступа.", show_alert=True)
        return
    if deal["status"] != "payment":
        await call.answer("⚠️ Действие недоступно для текущего статуса.", show_alert=True)
        return

    await db.update_deal_status(deal_id, "check", user.id)
    deal = await db.get_deal(deal_id)
    logger.info("Deal %s: payment sent by buyer %s", deal_id, user.id)

    await call.message.edit_text(
        f"💸 <b>Оплата отмечена!</b>\n\nСделка #{deal_id} перешла в статус: 🔍 Проверка\n\n"
        f"Ожидаем подтверждения продавца...",
        parse_mode="HTML",
        reply_markup=deal_buyer_kb(deal_id, "check"),
    )

    try:
        await bot.send_message(
            deal["seller_id"],
            f"💸 <b>Покупатель отметил оплату по сделке #{deal_id}!</b>\n\n"
            f"Проверьте поступление средств и подтвердите получение:",
            parse_mode="HTML",
            reply_markup=deal_seller_kb(deal_id, "check"),
        )
    except Exception:
        pass

    await call.answer("Оплата отмечена!")


@router.callback_query(lambda c: c.data and c.data.startswith("deal:confirm:"))
async def cb_confirm(call: CallbackQuery, bot: Bot):
    deal_id = call.data.split(":", 2)[2]
    user = call.from_user
    deal = await db.get_deal(deal_id)

    if not deal or deal["seller_id"] != user.id:
        await call.answer("❌ Нет доступа.", show_alert=True)
        return
    if deal["status"] != "check":
        await call.answer("⚠️ Действие недоступно.", show_alert=True)
        return

    await db.update_deal_status(deal_id, "done", user.id)
    logger.info("Deal %s: confirmed done by seller %s", deal_id, user.id)

    await call.message.edit_text(
        f"🎉 <b>Сделка #{deal_id} завершена!</b>\n\n"
        f"✅ Продавец подтвердил получение средств.\n"
        f"Спасибо за использование гарант-бота!",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )

    try:
        await bot.send_message(
            deal["buyer_id"],
            f"🎉 <b>Сделка #{deal_id} завершена!</b>\n\n"
            f"✅ Продавец подтвердил получение средств.\n"
            f"Спасибо за использование гарант-бота!",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
    except Exception:
        pass

    await call.answer("Сделка завершена!")


@router.callback_query(lambda c: c.data and c.data.startswith("deal:dispute:"))
async def cb_dispute(call: CallbackQuery, bot: Bot):
    deal_id = call.data.split(":", 2)[2]
    user = call.from_user
    deal = await db.get_deal(deal_id)

    if not deal or (deal["seller_id"] != user.id and deal["buyer_id"] != user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return
    if deal["status"] in ("done", "cancelled", "dispute"):
        await call.answer("⚠️ Спор уже открыт или сделка закрыта.", show_alert=True)
        return

    await db.update_deal_status(deal_id, "dispute", user.id)
    logger.info("Deal %s: dispute opened by user %s", deal_id, user.id)
    role = "продавца" if deal["seller_id"] == user.id else "покупателя"

    msg = (
        f"⚠️ <b>Спор открыт по сделке #{deal_id}</b>\n\n"
        f"Инициатор: {role}\n"
        f"Администратор рассмотрит ситуацию в ближайшее время."
    )

    await call.message.edit_text(msg, parse_mode="HTML", reply_markup=back_to_menu_kb())

    # Notify the other party
    other_id = deal["buyer_id"] if deal["seller_id"] == user.id else deal["seller_id"]
    if other_id:
        try:
            await bot.send_message(other_id, msg, parse_mode="HTML", reply_markup=back_to_menu_kb())
        except Exception:
            pass

    # Notify admin
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🚨 <b>Спор по сделке #{deal_id}</b>\n\n"
            f"Инициатор: user_id={user.id} ({role})\n"
            f"Товар: {deal['item']}\n"
            f"Сумма: {deal['amount']:,.2f}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await call.answer("Спор открыт. Администратор уведомлён.")


@router.callback_query(lambda c: c.data and c.data.startswith("deal:cancel_deal:"))
async def cb_cancel_deal(call: CallbackQuery, bot: Bot):
    deal_id = call.data.split(":", 2)[2]
    user = call.from_user
    deal = await db.get_deal(deal_id)

    if not deal or (deal["seller_id"] != user.id and deal["buyer_id"] != user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return
    if deal["status"] in ("done", "cancelled", "dispute", "check"):
        await call.answer("⚠️ Сделку в этом статусе нельзя отменить.", show_alert=True)
        return

    await db.update_deal_status(deal_id, "cancelled", user.id)
    logger.info("Deal %s: cancelled by user %s", deal_id, user.id)

    await call.message.edit_text(
        f"❌ <b>Сделка #{deal_id} отменена.</b>",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )

    other_id = deal["buyer_id"] if deal["seller_id"] == user.id else deal["seller_id"]
    if other_id:
        try:
            await bot.send_message(
                other_id,
                f"❌ <b>Сделка #{deal_id} была отменена.</b>",
                parse_mode="HTML",
                reply_markup=back_to_menu_kb(),
            )
        except Exception:
            pass

    await call.answer("Сделка отменена.")


# ── My deals list ────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "deal:list")
async def cb_deal_list(call: CallbackQuery):
    user = call.from_user
    deals = await db.get_user_deals(user.id)

    if not deals:
        await call.message.edit_text(
            "📋 У вас нет сделок.\n\nСоздайте первую!",
            reply_markup=main_menu_kb(user.id == ADMIN_ID),
        )
        await call.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for deal in deals[:10]:
        status_icon = {"waiting": "⏳", "payment": "💸", "check": "🔍",
                       "done": "✅", "dispute": "⚠️", "cancelled": "❌"}.get(deal["status"], "❓")
        role = "П" if deal["seller_id"] == user.id else "К"
        label = f"{status_icon} #{deal['deal_id']} [{role}] {deal['item'][:20]}"
        b.button(text=label, callback_data=f"deal:view:{deal['deal_id']}")
    b.button(text="🏠 Главное меню", callback_data="menu:main")
    b.adjust(1)

    await call.message.edit_text(
        f"📋 <b>Ваши сделки</b> ({len(deals)} шт.):\n\n"
        f"<i>П — продавец, К — покупатель</i>",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("deal:view:"))
async def cb_deal_view(call: CallbackQuery):
    deal_id = call.data.split(":", 2)[2]
    user = call.from_user
    deal = await db.get_deal(deal_id)

    if not deal:
        await call.answer("❌ Сделка не найдена.", show_alert=True)
        return

    deal_text = _deal_card(deal, user.id)
    is_seller = deal["seller_id"] == user.id
    kb = deal_seller_kb(deal_id, deal["status"]) if is_seller else deal_buyer_kb(deal_id, deal["status"])

    await call.message.edit_text(deal_text, parse_mode="HTML", reply_markup=kb)
    await call.answer()
