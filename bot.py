import logging
import asyncio
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from database import Database

# ===================== SOZLAMALAR =====================


BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]

# ===================== SETUP =====================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()



def fmt(n):
    try:
        return f"{float(n):.8f}"
    except:
        return str(n)

# ===================== STATES =====================
class DepositState(StatesGroup):
    choose_crypto = State()
    waiting_amount = State()
    waiting_screenshot = State()

class WithdrawState(StatesGroup):
    choose_crypto = State()
    waiting_address = State()
    waiting_amount = State()

class BroadcastState(StatesGroup):
    waiting_message = State()

class SettingsState(StatesGroup):
    edit_refbonus = State()

class AddCryptoState(StatesGroup):
    symbol = State()
    name = State()
    wallet = State()
    min_deposit = State()
    multiplier = State()
    wait_hours = State()

class EditCryptoState(StatesGroup):
    choose_field = State()
    enter_value = State()


# ===================== KLAVIATURALAR =====================
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Depozit"), KeyboardButton(text="📊 Balans")],
        [KeyboardButton(text="📜 Tarix"), KeyboardButton(text="👥 Referal")],
        [KeyboardButton(text="ℹ️ Malumot"), KeyboardButton(text="💸 Yechib olish")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🪙 Cryptolar"), KeyboardButton(text="💳 Kutayotganlar")],
        [KeyboardButton(text="👤 Foydalanuvchilar"), KeyboardButton(text="📈 Statistika")],
        [KeyboardButton(text="⚙️ Sozlamalar"), KeyboardButton(text="📢 Xabar yuborish")],
        [KeyboardButton(text="🔙 Asosiy menyu")]
    ], resize_keyboard=True)

def crypto_list_kb(cryptos, prefix="dep_crypto"):
    """Depozit uchun - koeff va min ko'rsatadi"""
    buttons = []
    for c in cryptos:
        label = f"{'✅' if c['is_active'] else '❌'} {c['symbol']} | x{fmt(c['multiplier'])} | min: {fmt(c['min_deposit'])}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"{prefix}_{c['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def withdraw_crypto_kb(cryptos):
    """Yechish uchun - faqat crypto nomi"""
    buttons = []
    for c in cryptos:
        label = f"💎 {c['symbol']} - {c['name']}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"wd_crypto_{c['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_crypto_kb(cryptos):
    buttons = []
    for c in cryptos:
        icon = "🟢" if c['is_active'] else "🔴"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {c['symbol']} ({c['name']})",
            callback_data=f"acrypto_{c['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Yangi crypto qo'shish", callback_data="add_crypto")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_crypto_actions_kb(crypto_id, is_active):
    toggle_text = "🔴 O'chirish" if is_active else "🟢 Yoqish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_crypto_{crypto_id}"),
            InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_crypto_{crypto_id}")
        ],
        [
            InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"delete_crypto_{crypto_id}"),
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_cryptos")
        ]
    ])


# ===================== START =====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    db.add_user(user_id, message.from_user.username or "", message.from_user.full_name, referrer_id)

    cryptos = db.get_all_cryptos(only_active=True)
    crypto_names = ", ".join(c['symbol'] for c in cryptos) if cryptos else "Hozircha yo'q"

    await message.answer(
        f"👋 Xush kelibsiz, *{message.from_user.full_name}*!\n\n"
        f"🤖 *Crypto Investment Bot*\n\n"
        f"💡 Qanday ishlaydi:\n"
        f"• Istalgan cryptoda depozit qiling\n"
        f"• Belgilangan vaqt kuting\n"
        f"• Pulingiz ko'paytirib qaytariladi! 🚀\n\n"
        f"🪙 Mavjud cryptolar: *{crypto_names}*",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


# ===================== BALANS =====================
@dp.message(F.text == "📊 Balans")
async def show_balance(message: types.Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start bosing.")
        return

    active = db.get_active_deposits(message.from_user.id)
    active_text = ""
    for dep in active:
        finish = dep['approved_at'] + timedelta(hours=dep['wait_hours'])
        remaining = finish - datetime.now()
        payout = dep['amount'] * dep['multiplier']
        if remaining.total_seconds() > 0:
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            active_text += f"\n• {dep['amount']:.8f} {dep['crypto_symbol']} → {payout:.8f} | ⏳ {h}s {m}m"
        else:
            active_text += f"\n• {dep['amount']:.8f} {dep['crypto_symbol']} → {payout:.8f} | ✅ Tayyor"

    await message.answer(
        f"💼 *Hisobingiz*\n\n"
        f"💰 Balans: *{user['balance_usd']:.8f}*\n"
        f"📥 Jami kiritilgan: *{user['total_deposited']:.8f}*\n"
        f"📤 Jami yechilgan: *{user['total_withdrawn']:.8f}*\n"
        f"\n⚡ Aktiv depozitlar:{active_text if active_text else ' Yoq'}",
        parse_mode="Markdown"
    )


# ===================== DEPOZIT =====================
@dp.message(F.text == "💰 Depozit")
async def deposit_start(message: types.Message, state: FSMContext):
    cryptos = db.get_all_cryptos(only_active=True)
    if not cryptos:
        await message.answer("❌ Hozircha aktiv crypto yo'q. Admin tez orada qo'shadi!")
        return
    await message.answer(
        "🪙 *Qaysi cryptoda depozit qilmoqchisiz?*\n\nPastdan tanlang:",
        parse_mode="Markdown",
        reply_markup=crypto_list_kb(cryptos, prefix="dep_crypto")
    )
    await state.set_state(DepositState.choose_crypto)


@dp.callback_query(F.data.startswith("dep_crypto_"), DepositState.choose_crypto)
async def deposit_choose_crypto(callback: types.CallbackQuery, state: FSMContext):
    crypto_id = int(callback.data.split("_")[2])
    crypto = db.get_crypto(crypto_id)
    if not crypto or not crypto['is_active']:
        await callback.answer("Bu crypto hozir mavjud emas!", show_alert=True)
        return
    await state.update_data(crypto_id=crypto_id, crypto=dict(crypto))
    await callback.message.edit_text(
        f"✅ Tanlandi: *{crypto['name']} ({crypto['symbol']})*\n\n"
        f"📌 Minimal miqdor: *{fmt(crypto['min_deposit'])} {crypto['symbol']}*\n"
        f"📈 Koeffitsient: *x{fmt(crypto['multiplier'])}*\n"
        f"⏰ Kutish vaqti: *{crypto['wait_hours']} soat*\n\n"
        f"Qancha *{crypto['symbol']}* kiritmoqchisiz?",
        parse_mode="Markdown"
    )
    await state.set_state(DepositState.waiting_amount)


@dp.message(DepositState.waiting_amount)
async def deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        crypto = data['crypto']
        if amount < crypto['min_deposit']:
            await message.answer(
                f"❌ Minimal miqdor *{fmt(crypto['min_deposit'])} {crypto['symbol']}*! Qayta kiriting:",
                parse_mode="Markdown"
            )
            return
        payout = amount * crypto['multiplier']
        await state.update_data(amount=amount)
        await message.answer(
            f"💳 *To'lov ma'lumotlari*\n\n"
            f"🪙 Crypto: *{crypto['symbol']}*\n"
            f"💰 Miqdor: *{amount:.8f} {crypto['symbol']}*\n"
            f"📈 Qaytariladigan: *{payout:.8f} {crypto['symbol']}*\n"
            f"⏰ {crypto['wait_hours']} soatdan keyin\n\n"
            f"📤 Quyidagi manzilga yuboring:\n"
            f"`{crypto['wallet_address']}`\n\n"
            f"📸 To'lovni amalga oshirgach *skrinshotini* yuboring!",
            parse_mode="Markdown"
        )
        await state.set_state(DepositState.waiting_screenshot)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting! Masalan: 0.005")


@dp.message(DepositState.waiting_screenshot)
async def deposit_screenshot(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer(
            "❌ Iltimos, *skrinshot rasm* yuboring!\n_(Matn emas, rasm bo'lishi kerak)_",
            parse_mode="Markdown"
        )
        return
    data = await state.get_data()
    crypto = data['crypto']
    amount = data['amount']
    crypto_id = data['crypto_id']
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    payout = amount * crypto['multiplier']

    dep_id = db.create_deposit(user_id, crypto_id, crypto['symbol'], amount, photo_id)

    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{dep_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{dep_id}")
            ]])
            u = message.from_user
            await bot.send_photo(
                admin_id,
                photo=photo_id,
                caption=(
                    f"🆕 *Yangi depozit #{dep_id}*\n\n"
                    f"👤 [{u.full_name}](tg://user?id={user_id}) | `{user_id}`\n"
                    f"🪙 *{crypto['symbol']}* ({crypto['name']})\n"
                    f"💰 Miqdor: *{amount:.8f} {crypto['symbol']}*\n"
                    f"📈 Qaytarish: *{payout:.8f} {crypto['symbol']}* (x{fmt(crypto['multiplier'])})\n"
                    f"⏰ {crypto['wait_hours']} soatdan keyin\n"
                    f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"Admin xabari xatosi: {e}")

    await message.answer(
        "✅ *So'rovingiz qabul qilindi!*\n\n"
        f"⏳ Admin skrinshotni ko'rib chiqadi.\n"
        f"Tasdiqlangach *{crypto['wait_hours']} soat*dan keyin "
        f"*{payout:.8f} {crypto['symbol']}* hisobingizga tushadi! 🚀",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    await state.clear()


# ===================== TASDIQLASH / RAD ETISH =====================
@dp.callback_query(F.data.startswith("approve_"))
async def approve_deposit(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yoq!")
        return
    dep_id = int(callback.data.split("_")[1])
    deposit = db.get_deposit(dep_id)
    if not deposit:
        await callback.answer("Depozit topilmadi!")
        return
    if deposit['status'] != 'pending':
        await callback.answer("Allaqachon korilib chiqilgan!")
        return

    db.approve_deposit(dep_id)
    payout = deposit['amount'] * deposit['multiplier']
    finish = datetime.now() + timedelta(hours=deposit['wait_hours'])

    try:
        await bot.send_message(
            deposit['user_id'],
            f"🎉 *Depozitingiz tasdiqlandi!*\n\n"
            f"🪙 {deposit['amount']:.8f} {deposit['crypto_symbol']}\n"
            f"📈 {deposit['wait_hours']} soatdan keyin: *{payout:.8f} {deposit['crypto_symbol']}*\n"
            f"⏰ Tugash vaqti: {finish.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(e)

    try:
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n✅ TASDIQLANDI",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await callback.answer("Tasdiqlandi!")
    asyncio.create_task(auto_payout(
        deposit['user_id'], payout, dep_id,
        deposit['crypto_symbol'], deposit['wait_hours']
    ))


@dp.callback_query(F.data.startswith("reject_"))
async def reject_deposit(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yoq!")
        return
    dep_id = int(callback.data.split("_")[1])
    deposit = db.get_deposit(dep_id)
    if not deposit:
        await callback.answer("Depozit topilmadi!")
        return
    db.reject_deposit(dep_id)
    try:
        await bot.send_message(
            deposit['user_id'],
            "❌ *Depozitingiz rad etildi.*\nAdmin bilan boglanang.",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    try:
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n❌ RAD ETILDI",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await callback.answer("Rad etildi!")


# ===================== AVTOMATIK TOLOV =====================
async def auto_payout(user_id, payout, dep_id, symbol, wait_hours):
    await asyncio.sleep(wait_hours * 3600)
    db.add_balance(user_id, payout)
    db.mark_paid(dep_id)
    try:
        await bot.send_message(
            user_id,
            f"🎊 *Tolovingiz tayyor!*\n\n"
            f"💰 Hisobingizga *{payout:.8f} {symbol}* qoshildi!\n"
            f"💸 Yechib olish uchun tugmani bosing.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(e)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ Avtomatik tolov: user {user_id} ga {payout:.8f} {symbol}"
            )
        except Exception:
            pass


# ===================== TARIX =====================
@dp.message(F.text == "📜 Tarix")
async def show_history(message: types.Message):
    history = db.get_user_history(message.from_user.id, limit=10)
    if not history:
        await message.answer("📭 Hali hech qanday tranzaksiya yoq.")
        return
    status_map = {"pending": "⏳", "approved": "✅", "paid": "💰", "rejected": "❌"}
    text = "📜 *Songgi 10 ta depozit:*\n\n"
    for h in history:
        emoji = status_map.get(h['status'], "•")
        payout = h['amount'] * h['multiplier']
        text += f"{emoji} {h['amount']:.8f} {h['crypto_symbol']} → {payout:.8f} | {h['created_at'].strftime('%d.%m %H:%M')} | {h['status']}\n"
    await message.answer(text, parse_mode="Markdown")


# ===================== REFERAL =====================
@dp.message(F.text == "👥 Referal")
async def show_referral(message: types.Message):
    user_id = message.from_user.id
    count = db.get_referral_count(user_id)
    earnings = db.get_referral_earnings(user_id)
    bonus = db.get_setting('referral_bonus') or '5'
    info = await bot.get_me()
    link = f"https://t.me/{info.username}?start={user_id}"
    await message.answer(
        f"👥 *Referal tizimi*\n\n"
        f"🔗 Havolangiz:\n`{link}`\n\n"
        f"👤 Taklif qilganlar: *{count}* kishi\n"
        f"💰 Referal daromad: *{earnings:.8f}*\n\n"
        f"💡 Har bir dostingiz depozit qilganda *{bonus}%* bonus!",
        parse_mode="Markdown"
    )


# ===================== YECHISH =====================
@dp.message(F.text == "💸 Yechib olish")
async def withdraw_start(message: types.Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user or user['balance_usd'] <= 0:
        await message.answer("❌ Hisobingizda mablag yoq!")
        return
    cryptos = db.get_all_cryptos(only_active=True)
    if not cryptos:
        await message.answer("❌ Hozircha aktiv crypto yoq!")
        return
    await message.answer(
        f"💸 *Pul yechish*\n\n"
        f"💰 Balans: *{user['balance_usd']:.8f}*\n\n"
        f"Qaysi cryptoda yechmoqchisiz?",
        parse_mode="Markdown",
        reply_markup=withdraw_crypto_kb(cryptos)
    )
    await state.set_state(WithdrawState.choose_crypto)


@dp.callback_query(F.data.startswith("wd_crypto_"), WithdrawState.choose_crypto)
async def withdraw_choose_crypto(callback: types.CallbackQuery, state: FSMContext):
    crypto_id = int(callback.data.split("_")[2])
    crypto = db.get_crypto(crypto_id)
    await state.update_data(crypto=dict(crypto))
    await callback.message.edit_text(
        f"✅ Tanlandi: *{crypto['symbol']}*\n\n"
        f"📍 {crypto['symbol']} wallet manzilingizni kiriting:",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawState.waiting_address)


@dp.message(WithdrawState.waiting_address)
async def withdraw_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    user = db.get_user(message.from_user.id)
    data = await state.get_data()
    crypto = data['crypto']
    await message.answer(
        f"💰 Qancha *{crypto['symbol']}* yechmoqchisiz?\n"
        f"_(Mavjud balans: {user['balance_usd']:.8f})_",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawState.waiting_amount)


@dp.message(WithdrawState.waiting_amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        user = db.get_user(message.from_user.id)
        if amount > user['balance_usd']:
            await message.answer("❌ Yetarli mablag yoq!")
            return
        if amount <= 0:
            await message.answer("❌ Miqdor 0 dan katta bolishi kerak!")
            return
        data = await state.get_data()
        crypto = data['crypto']
        address = data['address']
        db.create_withdrawal(message.from_user.id, crypto['symbol'], amount, address)
        db.deduct_balance(message.from_user.id, amount)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"💸 *Yechish sorovi*\n\n"
                    f"👤 [{message.from_user.full_name}](tg://user?id={message.from_user.id})\n"
                    f"🪙 Crypto: *{crypto['symbol']}*\n"
                    f"💰 Miqdor: *{amount:.8f} {crypto['symbol']}*\n"
                    f"📍 Manzil: `{address}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        await message.answer(
            "✅ *Yechish sorovi qabul qilindi!*\n\nAdmin 1-24 soat ichida yuboradi.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Notogri raqam!")


# ===================== MALUMOT =====================
@dp.message(F.text == "ℹ️ Malumot")
async def info(message: types.Message):
    try:
        cryptos = db.get_all_cryptos(only_active=True)
        bonus = db.get_setting('referral_bonus') or '5'
        lines = ["ℹ️ Bot haqida", "", "🤖 Crypto Investment Bot", ""]
        if cryptos:
            lines.append("🪙 Mavjud cryptolar:")
            for c in cryptos:
                lines.append(f"  {c['symbol']} - {c['name']}")
                lines.append(f"  Koeff: x{fmt(c['multiplier'])} | Vaqt: {c['wait_hours']}s | Min: {fmt(c['min_deposit'])}")
                lines.append("")
        else:
            lines.append("🪙 Hozircha aktiv crypto yoq")
            lines.append("")
        lines.append(f"👥 Referal bonus: {bonus}%")
        lines.append("📞 Admin: @admin_username")
        await message.answer("\n".join(lines))
    except Exception as e:
        logging.error(f"Info xatosi: {e}")
        await message.answer("Malumot yuklanmadi, qayta urining.")


# ==================== ADMIN PANEL ====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Ruxsat yoq!")
        return
    await state.clear()
    stats = db.get_stats()
    await message.answer(
        f"🔐 *Admin Panel*\n\n"
        f"👤 Foydalanuvchilar: *{stats['users']}*\n"
        f"💰 Jami depozit: *{stats['total_deposits']:.8f}*\n"
        f"📤 Jami tolovlar: *{stats['total_payouts']:.8f}*\n"
        f"⏳ Kutayotgan: *{stats['pending']}*\n"
        f"✅ Aktiv: *{stats['approved']}*",
        parse_mode="Markdown",
        reply_markup=admin_menu()
    )


@dp.message(F.text == "🪙 Cryptolar")
async def admin_cryptos(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    cryptos = db.get_all_cryptos()
    if not cryptos:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="➕ Yangi crypto qo'shish", callback_data="add_crypto")
        ]])
        await message.answer("🪙 Hozircha crypto yoq.", reply_markup=kb)
        return
    await message.answer(
        "🪙 *Cryptolar royxati*\nBoshqarish uchun tanlang:",
        parse_mode="Markdown",
        reply_markup=admin_crypto_kb(cryptos)
    )


@dp.callback_query(F.data == "back_cryptos")
async def back_to_cryptos(callback: types.CallbackQuery):
    cryptos = db.get_all_cryptos()
    await callback.message.edit_text(
        "🪙 *Cryptolar royxati*\nBoshqarish uchun tanlang:",
        parse_mode="Markdown",
        reply_markup=admin_crypto_kb(cryptos)
    )


@dp.callback_query(F.data.startswith("acrypto_"))
async def admin_crypto_detail(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    crypto_id = int(callback.data.split("_")[1])
    c = db.get_crypto(crypto_id)
    if not c:
        await callback.answer("Topilmadi!")
        return
    status = "🟢 Aktiv" if c['is_active'] else "🔴 Ochirilgan"
    await callback.message.edit_text(
        f"🪙 *{c['name']} ({c['symbol']})*\n\n"
        f"📍 Wallet: `{c['wallet_address']}`\n"
        f"📌 Min depozit: *{fmt(c['min_deposit'])} {c['symbol']}*\n"
        f"📈 Koeffitsient: *x{fmt(c['multiplier'])}*\n"
        f"⏰ Kutish: *{c['wait_hours']} soat*\n"
        f"🔘 Holat: {status}",
        parse_mode="Markdown",
        reply_markup=admin_crypto_actions_kb(crypto_id, bool(c['is_active']))
    )


@dp.callback_query(F.data.startswith("toggle_crypto_"))
async def toggle_crypto_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    crypto_id = int(callback.data.split("_")[2])
    new_active = db.toggle_crypto(crypto_id)
    await callback.answer("Yoqildi!" if new_active else "Ochirildi!")
    c = db.get_crypto(crypto_id)
    status = "🟢 Aktiv" if c['is_active'] else "🔴 Ochirilgan"
    await callback.message.edit_text(
        f"🪙 *{c['name']} ({c['symbol']})*\n\n"
        f"📍 Wallet: `{c['wallet_address']}`\n"
        f"📌 Min depozit: *{fmt(c['min_deposit'])} {c['symbol']}*\n"
        f"📈 Koeffitsient: *x{fmt(c['multiplier'])}*\n"
        f"⏰ Kutish: *{c['wait_hours']} soat*\n"
        f"🔘 Holat: {status}",
        parse_mode="Markdown",
        reply_markup=admin_crypto_actions_kb(crypto_id, bool(c['is_active']))
    )


@dp.callback_query(F.data.startswith("delete_crypto_"))
async def delete_crypto_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    crypto_id = int(callback.data.split("_")[2])
    c = db.get_crypto(crypto_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, ochir", callback_data=f"confirm_del_{crypto_id}"),
        InlineKeyboardButton(text="❌ Yoq", callback_data=f"acrypto_{crypto_id}")
    ]])
    await callback.message.edit_text(
        f"⚠️ *{c['symbol']}* ni ochirishni tasdiqlaysizmi?\n\nBu amalni qaytarib bolmaydi!",
        parse_mode="Markdown",
        reply_markup=kb
    )


@dp.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete_crypto(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    crypto_id = int(callback.data.split("_")[2])
    db.delete_crypto(crypto_id)
    await callback.answer("Ochirildi!")
    cryptos = db.get_all_cryptos()
    await callback.message.edit_text(
        "🪙 *Cryptolar royxati*",
        parse_mode="Markdown",
        reply_markup=admin_crypto_kb(cryptos)
    )


# ---- Crypto qoshish ----
@dp.callback_query(F.data == "add_crypto")
async def add_crypto_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer(
        "➕ *Yangi crypto qoshish*\n\n"
        "1️⃣ Crypto *symbol*ini kiriting (masalan: BTC, ETH, USDT):",
        parse_mode="Markdown"
    )
    await state.set_state(AddCryptoState.symbol)


@dp.message(AddCryptoState.symbol)
async def add_crypto_symbol(message: types.Message, state: FSMContext):
    await state.update_data(symbol=message.text.strip().upper())
    await message.answer("2️⃣ Crypto *toliq nomi*ni kiriting (masalan: Bitcoin):", parse_mode="Markdown")
    await state.set_state(AddCryptoState.name)


@dp.message(AddCryptoState.name)
async def add_crypto_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("3️⃣ *Wallet manzil*ini kiriting:", parse_mode="Markdown")
    await state.set_state(AddCryptoState.wallet)


@dp.message(AddCryptoState.wallet)
async def add_crypto_wallet(message: types.Message, state: FSMContext):
    await state.update_data(wallet=message.text.strip())
    await message.answer("4️⃣ *Minimal depozit* miqdorini kiriting (masalan: 0.001):", parse_mode="Markdown")
    await state.set_state(AddCryptoState.min_deposit)


@dp.message(AddCryptoState.min_deposit)
async def add_crypto_min(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        await state.update_data(min_deposit=val)
        await message.answer(
            "5️⃣ *Koeffitsient*ni kiriting (masalan: 1.5 = 50% foyda, 2 = 2x):",
            parse_mode="Markdown"
        )
        await state.set_state(AddCryptoState.multiplier)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")


@dp.message(AddCryptoState.multiplier)
async def add_crypto_multiplier(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 1:
            await message.answer("❌ Koeffitsient 1 dan katta bolishi kerak! (masalan: 1.5)")
            return
        await state.update_data(multiplier=val)
        await message.answer("6️⃣ *Kutish vaqti*ni soatda kiriting (masalan: 12):", parse_mode="Markdown")
        await state.set_state(AddCryptoState.wait_hours)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")


@dp.message(AddCryptoState.wait_hours)
async def add_crypto_hours(message: types.Message, state: FSMContext):
    try:
        hours = int(message.text.strip())
        if hours < 1:
            await message.answer("❌ Kamida 1 soat bolishi kerak!")
            return
        data = await state.get_data()
        success = db.add_crypto(
            data['symbol'], data['name'], data['wallet'],
            data['min_deposit'], data['multiplier'], hours
        )
        if success:
            await message.answer(
                f"✅ *{data['symbol']} ({data['name']})* qoshildi!\n\n"
                f"📌 Min: {fmt(data['min_deposit'])} {data['symbol']}\n"
                f"📈 Koeffitsient: x{fmt(data['multiplier'])}\n"
                f"⏰ Kutish: {hours} soat",
                parse_mode="Markdown",
                reply_markup=admin_menu()
            )
        else:
            await message.answer(f"❌ *{data['symbol']}* allaqachon mavjud!", parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("❌ Faqat butun son kiriting!")


# ---- Crypto tahrirlash ----
@dp.callback_query(F.data.startswith("edit_crypto_"))
async def edit_crypto_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    crypto_id = int(callback.data.split("_")[2])
    c = db.get_crypto(crypto_id)
    await state.update_data(edit_crypto_id=crypto_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📌 Min depozit", callback_data="ef_min_deposit"),
            InlineKeyboardButton(text="📈 Koeffitsient", callback_data="ef_multiplier")
        ],
        [
            InlineKeyboardButton(text="⏰ Kutish vaqti", callback_data="ef_wait_hours"),
            InlineKeyboardButton(text="📍 Wallet", callback_data="ef_wallet_address")
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"acrypto_{crypto_id}")]
    ])
    await callback.message.edit_text(
        f"✏️ *{c['symbol']}* ni tahrirlash\nQaysi maydonni ozgartirmoqchisiz?",
        parse_mode="Markdown",
        reply_markup=kb
    )
    await state.set_state(EditCryptoState.choose_field)


@dp.callback_query(F.data.startswith("ef_"), EditCryptoState.choose_field)
async def edit_crypto_field(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data[3:]
    field_names = {
        "min_deposit": "Minimal depozit (raqam)",
        "multiplier": "Koeffitsient (masalan: 1.5)",
        "wait_hours": "Kutish vaqti soatda (masalan: 12)",
        "wallet_address": "Wallet manzil"
    }
    await state.update_data(edit_field=field)
    await callback.message.answer(
        f"✏️ Yangi *{field_names.get(field, field)}*ni kiriting:",
        parse_mode="Markdown"
    )
    await state.set_state(EditCryptoState.enter_value)


@dp.message(EditCryptoState.enter_value)
async def edit_crypto_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data['edit_field']
    crypto_id = data['edit_crypto_id']
    raw = message.text.strip()
    try:
        if field in ('min_deposit', 'multiplier'):
            value = float(raw.replace(",", "."))
        elif field == 'wait_hours':
            value = int(raw)
        else:
            value = raw
        db.update_crypto(crypto_id, **{field: value})
        c = db.get_crypto(crypto_id)
        await message.answer(
            f"✅ *{c['symbol']}* yangilandi!\n\n"
            f"📌 Min: {fmt(c['min_deposit'])} {c['symbol']}\n"
            f"📈 Koeffitsient: x{fmt(c['multiplier'])}\n"
            f"⏰ Kutish: {c['wait_hours']} soat\n"
            f"📍 Wallet: `{c['wallet_address']}`",
            parse_mode="Markdown",
            reply_markup=admin_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Notogri qiymat! Qayta kiriting:")


# ---- Kutayotgan depozitlar ----
@dp.message(F.text == "💳 Kutayotganlar")
async def admin_pending(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    deposits = db.get_pending_deposits()
    if not deposits:
        await message.answer("✅ Kutayotgan depozit yoq!")
        return
    for dep in deposits:
        payout = dep['amount'] * dep['multiplier']
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{dep['id']}"),
            InlineKeyboardButton(text="❌ Rad", callback_data=f"reject_{dep['id']}")
        ]])
        try:
            await bot.send_photo(
                message.from_user.id,
                photo=dep['screenshot_file_id'],
                caption=(
                    f"💳 *Depozit #{dep['id']}*\n"
                    f"👤 User: `{dep['user_id']}`\n"
                    f"🪙 {dep['amount']:.8f} {dep['crypto_symbol']} → {payout:.8f}\n"
                    f"🕐 {dep['created_at'][:16]}"
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception:
            await message.answer(
                f"💳 *Depozit #{dep['id']}*\n"
                f"👤 User: `{dep['user_id']}`\n"
                f"🪙 {dep['amount']:.8f} {dep['crypto_symbol']} → {payout:.8f}\n"
                f"🕐 {dep['created_at'][:16]}",
                parse_mode="Markdown",
                reply_markup=kb
            )


# ---- Foydalanuvchilar ----
@dp.message(F.text == "👤 Foydalanuvchilar")
async def admin_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = db.get_all_users(limit=20)
    if not users:
        await message.answer("Foydalanuvchilar yoq.")
        return
    text = "👤 *Songgi 20 foydalanuvchi:*\n\n"
    for u in users:
        text += f"• {u['full_name']} | 💰{u['balance_usd']:.8f} | {u['created_at'][:10]}\n"
    await message.answer(text, parse_mode="Markdown")


# ---- Statistika ----
@dp.message(F.text == "📈 Statistika")
async def admin_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    stats = db.get_stats()
    cryptos = db.get_all_cryptos()
    crypto_text = "\n".join(
        f"  {'🟢' if c['is_active'] else '🔴'} {c['symbol']}: x{fmt(c['multiplier'])}, {c['wait_hours']}s"
        for c in cryptos
    ) or "  Yoq"
    await message.answer(
        f"📈 *Bot statistikasi*\n\n"
        f"👤 Foydalanuvchilar: {stats['users']}\n"
        f"💰 Jami depozit: {stats['total_deposits']:.8f}\n"
        f"📤 Jami tolovlar: {stats['total_payouts']:.8f}\n"
        f"⏳ Kutayotganlar: {stats['pending']}\n"
        f"✅ Aktiv depozitlar: {stats['approved']}\n\n"
        f"🪙 *Cryptolar:*\n{crypto_text}",
        parse_mode="Markdown"
    )


# ---- Sozlamalar ----
@dp.message(F.text == "⚙️ Sozlamalar")
async def admin_settings(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    bonus = db.get_setting('referral_bonus') or '5'
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✏️ Referal bonusni ozgartirish", callback_data="edit_refbonus")
    ]])
    await message.answer(
        f"⚙️ *Sozlamalar*\n\n"
        f"👥 Referal bonus: *{bonus}%*",
        parse_mode="Markdown",
        reply_markup=kb
    )


@dp.callback_query(F.data == "edit_refbonus")
async def edit_refbonus_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer("Yangi referal foizini kiriting (masalan: 5):")
    await state.set_state(SettingsState.edit_refbonus)


@dp.message(SettingsState.edit_refbonus)
async def save_refbonus(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        val = float(message.text.strip())
        db.set_setting('referral_bonus', str(val))
        await message.answer(
            f"✅ Referal bonus *{val}%* ga ozgartirildi!",
            parse_mode="Markdown",
            reply_markup=admin_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")


# ---- Xabar yuborish ----
@dp.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:")
    await state.set_state(BroadcastState.waiting_message)


@dp.message(BroadcastState.waiting_message)
async def broadcast_send(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = db.get_all_users()
    sent = failed = 0
    for u in users:
        try:
            await bot.send_message(u['user_id'], message.text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await message.answer(
        f"📢 Xabar yuborildi!\n✅ {sent} ta muvaffaqiyatli\n❌ {failed} ta xato",
        reply_markup=admin_menu()
    )
    await state.clear()


# ---- Asosiy menyu ----
@dp.message(F.text == "🔙 Asosiy menyu")
async def back_main(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=main_menu())


# ===================== MAIN =====================
async def main():
    db.create_tables()
    print("Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
