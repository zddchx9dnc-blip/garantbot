from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Создать сделку",   callback_data="deal:create")
    b.button(text="📋 Мои сделки",       callback_data="deal:list")
    b.button(text="💰 Пополнение баланса", callback_data="menu:topup")
    if is_admin:
        b.button(text="🔧 Панель администратора", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="deal:cancel_create")
    return b.as_markup()


def deal_seller_kb(deal_id: str, status: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if status == "check":
        b.button(text="✅ Подтвердить получение", callback_data=f"deal:confirm:{deal_id}")
        b.button(text="⚠️ Открыть спор",          callback_data=f"deal:dispute:{deal_id}")
    elif status not in ("done", "cancelled", "dispute"):
        b.button(text="❌ Отменить сделку", callback_data=f"deal:cancel_deal:{deal_id}")
    b.button(text="📋 Мои сделки", callback_data="deal:list")
    b.adjust(1)
    return b.as_markup()


def deal_buyer_kb(deal_id: str, status: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if status == "payment":
        b.button(text="💸 Отметить оплату",  callback_data=f"deal:paid:{deal_id}")
        b.button(text="⚠️ Открыть спор",     callback_data=f"deal:dispute:{deal_id}")
        b.button(text="❌ Отменить сделку",   callback_data=f"deal:cancel_deal:{deal_id}")
    elif status == "check":
        b.button(text="⚠️ Открыть спор", callback_data=f"deal:dispute:{deal_id}")
    b.button(text="📋 Мои сделки", callback_data="deal:list")
    b.adjust(1)
    return b.as_markup()


def join_deal_kb(deal_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🤝 Присоединиться к сделке", callback_data=f"deal:join:{deal_id}")
    return b.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика",      callback_data="admin:stats")
    b.button(text="📋 Все сделки",      callback_data="admin:deals")
    b.button(text="👥 Пользователи",    callback_data="admin:users")
    b.button(text="🔙 Главное меню",    callback_data="admin:back")
    b.adjust(2)
    return b.as_markup()


def admin_deal_action_kb(deal_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Завершить принудительно", callback_data=f"admin:force_done:{deal_id}")
    b.button(text="❌ Отменить",                callback_data=f"admin:force_cancel:{deal_id}")
    b.button(text="🔙 Назад",                   callback_data="admin:deals")
    b.adjust(1)
    return b.as_markup()


def admin_user_action_kb(uid: int, blocked: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if blocked:
        b.button(text="✅ Разблокировать", callback_data=f"admin:unblock:{uid}")
    else:
        b.button(text="🚫 Заблокировать",  callback_data=f"admin:block:{uid}")
    b.button(text="🔙 Назад", callback_data="admin:users")
    b.adjust(1)
    return b.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Главное меню", callback_data="menu:main")
    return b.as_markup()
