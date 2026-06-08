from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

import database as db
from config import ADMIN_ID
from keyboards.inline import main_menu_kb, back_to_menu_kb

router = Router()


async def _ensure_user(user):
    await db.upsert_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await _ensure_user(user)

    if await db.is_blocked(user.id):
        await message.answer("🚫 Вы заблокированы и не можете использовать бота.")
        return

    is_admin = user.id == ADMIN_ID
    text = (
        "👋 <b>Добро пожаловать в Гарант-бот!</b>\n\n"
        "Я помогу вам безопасно провести сделку между продавцом и покупателем.\n\n"
        "🔐 <b>Как это работает:</b>\n"
        "1. Продавец создаёт сделку\n"
        "2. Покупатель присоединяется по ссылке\n"
        "3. Обе стороны видят условия\n"
        "4. Покупатель отправляет оплату\n"
        "5. Продавец подтверждает получение\n"
        "6. Сделка закрывается ✅\n\n"
        "Выберите действие:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(is_admin))


@router.callback_query(lambda c: c.data == "menu:topup")
async def cb_topup(call: CallbackQuery):
    user = call.from_user
    balances = await db.get_balances(user.id)
    rub   = balances["руб"]
    usdt  = balances["usdt"]
    stars = balances["звезды"]

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="💬 Написать саппорту", url="https://t.me/skippersupport")
    b.button(text="🔄 Обновить", callback_data="menu:topup")
    b.button(text="🏠 Главное меню", callback_data="menu:main")
    b.adjust(1)

    await call.message.edit_text(
        "╔══════════════════════╗\n"
        "       💼  МОЙ БАЛАНС\n"
        "╚══════════════════════╝\n\n"
        f"👤 <b>{user.full_name}</b>\n"
        f"🆔 <code>{user.id}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🇷🇺  Рубли:    <b>{rub:>12,.2f} ₽</b>\n"
        f"💵  USDT:     <b>{usdt:>12,.2f} $</b>\n"
        f"⭐  Звёзды:   <b>{stars:>12,.0f} ★</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Для пополнения нажмите кнопку ниже\n"
        "или напишите: <b>@skippersupport</b>",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(lambda c: c.data == "menu:main")
async def cb_main_menu(call: CallbackQuery):
    user = call.from_user
    await _ensure_user(user)

    if await db.is_blocked(user.id):
        await call.answer("🚫 Вы заблокированы.", show_alert=True)
        return

    is_admin = user.id == ADMIN_ID
    text = (
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb(is_admin))
    await call.answer()
