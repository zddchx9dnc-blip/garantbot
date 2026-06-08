from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import ADMIN_ID
from database import STATUSES
from keyboards.inline import admin_panel_kb, admin_deal_action_kb, admin_user_action_kb, back_to_menu_kb
from utils.logger import logger

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ── Admin panel ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:panel")
async def cb_admin_panel(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return
    await call.message.edit_text(
        "🔧 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )
    await call.answer()


@router.callback_query(lambda c: c.data == "admin:back")
async def cb_admin_back(call: CallbackQuery):
    from keyboards.inline import main_menu_kb
    await call.message.edit_text(
        "🏠 <b>Главное меню</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(is_admin=True),
    )
    await call.answer()


# ── Stats ────────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:stats")
async def cb_admin_stats(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    s = await db.get_stats()
    text = (
        "📊 <b>Статистика бота</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: <b>{s['total_users']}</b>\n"
        f"📋 Всего сделок: <b>{s['total_deals']}</b>\n"
        f"✅ Завершено: <b>{s['done_deals']}</b>\n"
        f"⚠️ Споров: <b>{s['disputes']}</b>\n"
        f"💰 Оборот: <b>{s['volume']:,.2f}</b>\n"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🔙 Назад", callback_data="admin:panel")
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())
    await call.answer()


# ── All deals ────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:deals")
async def cb_admin_deals(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    deals = await db.get_all_deals()
    if not deals:
        b = InlineKeyboardBuilder()
        b.button(text="🔙 Назад", callback_data="admin:panel")
        await call.message.edit_text("📋 Сделок нет.", reply_markup=b.as_markup())
        await call.answer()
        return

    b = InlineKeyboardBuilder()
    for deal in deals[:15]:
        icon = {"waiting": "⏳", "payment": "💸", "check": "🔍",
                "done": "✅", "dispute": "⚠️", "cancelled": "❌"}.get(deal["status"], "❓")
        b.button(
            text=f"{icon} #{deal['deal_id']} {deal['item'][:18]} | {deal['amount']:,.0f}",
            callback_data=f"admin:deal_view:{deal['deal_id']}",
        )
    b.button(text="🔙 Назад", callback_data="admin:panel")
    b.adjust(1)

    await call.message.edit_text(
        f"📋 <b>Все сделки</b> ({len(deals)} шт.):",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:deal_view:"))
async def cb_admin_deal_view(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    deal_id = call.data.split(":", 2)[2]
    deal = await db.get_deal(deal_id)
    if not deal:
        await call.answer("❌ Не найдено.", show_alert=True)
        return

    status_label = STATUSES.get(deal["status"], deal["status"])
    text = (
        f"🔖 <b>Сделка #{deal['deal_id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Товар: <b>{deal['item']}</b>\n"
        f"💰 Сумма: <b>{deal['amount']:,.2f}</b>\n"
        f"💳 Оплата: <b>{deal['payment']}</b>\n"
        f"📝 Описание: {deal['description'] or '—'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧑‍💼 Продавец ID: <code>{deal['seller_id']}</code>\n"
        f"🛒 Покупатель ID: <code>{deal['buyer_id'] or '—'}</code>\n"
        f"📊 Статус: {status_label}\n"
        f"🕒 Создана: {deal['created_at'][:16]}\n"
        f"🔄 Обновлена: {deal['updated_at'][:16]}"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_deal_action_kb(deal_id),
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:force_done:"))
async def cb_force_done(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    deal_id = call.data.split(":", 2)[2]
    deal = await db.get_deal(deal_id)
    if not deal:
        await call.answer("❌ Не найдено.", show_alert=True)
        return
    if deal["status"] in ("done", "cancelled"):
        await call.answer("⚠️ Сделка уже закрыта.", show_alert=True)
        return

    await db.update_deal_status(deal_id, "done", ADMIN_ID)
    logger.info("Deal %s: force-done by admin", deal_id)

    msg = (
        f"✅ <b>Сделка #{deal_id} принудительно завершена администратором.</b>"
    )
    for uid in filter(None, [deal["seller_id"], deal["buyer_id"]]):
        try:
            await bot.send_message(uid, msg, parse_mode="HTML", reply_markup=back_to_menu_kb())
        except Exception:
            pass

    await call.message.edit_text(msg, parse_mode="HTML", reply_markup=admin_panel_kb())
    await call.answer("Завершено!")


@router.callback_query(lambda c: c.data and c.data.startswith("admin:force_cancel:"))
async def cb_force_cancel(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    deal_id = call.data.split(":", 2)[2]
    deal = await db.get_deal(deal_id)
    if not deal:
        await call.answer("❌ Не найдено.", show_alert=True)
        return
    if deal["status"] in ("done", "cancelled"):
        await call.answer("⚠️ Сделка уже закрыта.", show_alert=True)
        return

    await db.update_deal_status(deal_id, "cancelled", ADMIN_ID)
    logger.info("Deal %s: force-cancelled by admin", deal_id)

    msg = f"❌ <b>Сделка #{deal_id} отменена администратором.</b>"
    for uid in filter(None, [deal["seller_id"], deal["buyer_id"]]):
        try:
            await bot.send_message(uid, msg, parse_mode="HTML", reply_markup=back_to_menu_kb())
        except Exception:
            pass

    await call.message.edit_text(msg, parse_mode="HTML", reply_markup=admin_panel_kb())
    await call.answer("Отменено!")


# ── Users ────────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:users")
async def cb_admin_users(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    users = await db.get_all_users()
    if not users:
        b = InlineKeyboardBuilder()
        b.button(text="🔙 Назад", callback_data="admin:panel")
        await call.message.edit_text("👥 Пользователей нет.", reply_markup=b.as_markup())
        await call.answer()
        return

    b = InlineKeyboardBuilder()
    for u in users[:15]:
        blocked_mark = "🚫" if u["is_blocked"] else "✅"
        name = u["full_name"] or f"id:{u['user_id']}"
        b.button(
            text=f"{blocked_mark} {name[:25]} (@{u['username'] or '—'})",
            callback_data=f"admin:user_view:{u['user_id']}",
        )
    b.button(text="🔙 Назад", callback_data="admin:panel")
    b.adjust(1)

    await call.message.edit_text(
        f"👥 <b>Пользователи</b> ({len(users)} чел.):",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:user_view:"))
async def cb_admin_user_view(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    uid = int(call.data.split(":", 2)[2])
    users = await db.get_all_users()
    user = next((u for u in users if u["user_id"] == uid), None)
    if not user:
        await call.answer("❌ Пользователь не найден.", show_alert=True)
        return

    status = "🚫 Заблокирован" if user["is_blocked"] else "✅ Активен"
    text = (
        f"👤 <b>Пользователь</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Имя: {user['full_name'] or '—'}\n"
        f"Username: @{user['username'] or '—'}\n"
        f"Статус: {status}\n"
        f"Зарегистрирован: {user['created_at'][:16]}"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_user_action_kb(uid, bool(user["is_blocked"])),
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:block:"))
async def cb_block(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    uid = int(call.data.split(":", 2)[2])
    await db.block_user(uid)
    logger.info("Admin blocked user %s", uid)
    await call.answer("✅ Пользователь заблокирован.", show_alert=True)
    await cb_admin_user_view(call)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:unblock:"))
async def cb_unblock(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    uid = int(call.data.split(":", 2)[2])
    await db.unblock_user(uid)
    logger.info("Admin unblocked user %s", uid)
    await call.answer("✅ Пользователь разблокирован.", show_alert=True)
    await cb_admin_user_view(call)
