import logging
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from database import Database

# ===================== SOZLAMALAR =====================
BOT_TOKEN = "8776678535:AAHMhBYxqHDwJBhnHuJ4v_hgsGRUA9T59EA"          # @BotFather dan oling
ADMIN_IDS = [7399101034]               # O'zingizning Telegram ID (@userinfobot)
WALLET_ADDRESS = "TQ4juFaqcHfhKR5vLSfFUjiyyqvsSCscP6"   # TRX TRC20 manzilingiz
MIN_DEPOSIT = 10                      # Minimal depozit (TRX)

# Vaqt zonasi (Toshkent UTC+5)
TZ = ZoneInfo("Asia/Tashkent")

# ===================== SETUP =====================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()


# ===================== STATES =====================
class DepositState(StatesGroup):
    waiting_amount = State()
    waiting_txid = State()

class WithdrawState(StatesGroup):
    waiting_address = State()
    waiting_amount = State()

class BroadcastState(StatesGroup):
    waiting_message = State()


# ===================== KLAVIATURALAR =====================
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Depozit"), KeyboardButton(text="📊 Balans")],
        [KeyboardButton(text="📜 Tarix"), KeyboardButton(text="👥 Referal")],
        [KeyboardButton(text="ℹ️ Ma'lumot"), KeyboardButton(text="💸 Yechib olish")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Foydalanuvchilar"), KeyboardButton(text="💳 Kutayotgan depozitlar")],
        [KeyboardButton(text="📢 Xabar yuborish"), KeyboardButton(text="📈 Statistika")],
        [KeyboardButton(text="🔙 Asosiy menyu")]
    ], resize_keyboard=True)


# ===================== START =====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Nomsiz"
    full_name = message.from_user.full_name

    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    db.add_user(user_id, username, full_name, referrer_id)

    await message.answer(
        f"👋 Xush kelibsiz, *{full_name}*!\n\n"
        f"🤖 *1.2X Crypto Bot*ga xush kelibsiz!\n\n"
        f"💡 Qanday ishlaydi:\n"
        f"• Istalgan miqdorda pul kiriting\n"
        f"• 12 soat kuting\n"
        f"• Pulingiz 1.2 barobarga ko'payadi! 🚀\n\n"
        f"📌 Minimal depozit: *{MIN_DEPOSIT} TRX*",
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
    now = datetime.now(TZ)
    for dep in active:
        # dep['approved_at'] - string, masalan '2025-04-15 14:30:00'
        approved_at = datetime.strptime(dep['approved_at'], '%Y-%m-%d %H:%M:%S')
        # approved_at naive, uni Toshkent vaqti deb belgilaymiz
        approved_at = approved_at.replace(tzinfo=TZ)
        finish = approved_at + timedelta(hours=12)
        remaining = finish - now
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            active_text += f"\n• {dep['amount']:.2f} TRX → {dep['amount']*1.2:.2f} TRX | ⏳ {hours}s {minutes}m qoldi"
        else:
            active_text += f"\n• {dep['amount']:.2f} TRX → {dep['amount']*1.2:.2f} TRX | ✅ Tayyor"

    await message.answer(
        f"💼 *Sizning hisobingiz*\n\n"
        f"💰 Balans: *{user['balance']:.2f} TRX*\n"
        f"📥 Jami kiritilgan: *{user['total_deposited']:.2f} TRX*\n"
        f"📤 Jami yechilgan: *{user['total_withdrawn']:.2f} TRX*\n"
        f"\n⚡ Aktiv depozitlar:{active_text if active_text else ' Yo`q'}",
        parse_mode="Markdown"
    )


# ===================== DEPOZIT =====================
@dp.message(F.text == "💰 Depozit")
async def deposit_start(message: types.Message, state: FSMContext):
    await message.answer(
        f"💳 *Depozit qilish*\n\n"
        f"📌 Minimal miqdor: *{MIN_DEPOSIT} TRX*\n\n"
        f"Qancha TRX kiritmoqchisiz? (Faqat raqam)",
        parse_mode="Markdown"
    )
    await state.set_state(DepositState.waiting_amount)


@dp.message(DepositState.waiting_amount)
async def deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount < MIN_DEPOSIT:
            await message.answer(f"❌ Minimal miqdor {MIN_DEPOSIT} TRX! Qayta kiriting:")
            return

        await state.update_data(amount=amount)
        await message.answer(
            f"✅ Miqdor: *{amount:.2f} TRX*\n\n"
            f"📤 Quyidagi manzilga *TRX (TRC20)* yuboring:\n"
            f"`{WALLET_ADDRESS}`\n\n"
            f"💡 To'lov qilgandan so'ng *Transaction ID (TXID)*ni yuboring:\n"
            f"_(TXID ni blockchain explorer dan topishingiz mumkin)_",
            parse_mode="Markdown"
        )
        await state.set_state(DepositState.waiting_txid)
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Faqat raqam kiriting.")


@dp.message(DepositState.waiting_txid)
async def deposit_txid(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data['amount']
    txid = message.text.strip()
    user_id = message.from_user.id

    dep_id = db.create_deposit(user_id, amount, txid)

    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{dep_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{dep_id}")
            ]])
            user = message.from_user
            await bot.send_message(
                admin_id,
                f"🆕 *Yangi depozit so'rovi*\n\n"
                f"👤 Foydalanuvchi: [{user.full_name}](tg://user?id={user_id})\n"
                f"🆔 ID: `{user_id}`\n"
                f"💰 Miqdor: *{amount:.2f} TRX*\n"
                f"🔗 TXID: `{txid}`\n"
                f"🕐 Vaqt: {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}",
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"Admin xabari yuborilmadi: {e}")

    await message.answer(
        "✅ *So'rovingiz qabul qilindi!*\n\n"
        "⏳ Admin tasdiqlashini kuting (odatda 5-30 daqiqa).\n"
        "Tasdiqlangandan so'ng *12 soat* ichida pulingiz 1.2x bo'ladi!",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    await state.clear()


# ===================== TASDIQLASH / RAD ETISH =====================
@dp.callback_query(F.data.startswith("approve_"))
async def approve_deposit(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!")
        return

    dep_id = int(callback.data.split("_")[1])
    deposit = db.get_deposit(dep_id)

    if not deposit:
        await callback.answer("Depozit topilmadi!")
        return

    if deposit['status'] != 'pending':
        await callback.answer("Bu depozit allaqachon ko'rib chiqilgan!")
        return

    db.approve_deposit(dep_id)

    finish_time = datetime.now(TZ) + timedelta(hours=12)
    try:
        await bot.send_message(
            deposit['user_id'],
            f"🎉 *Depozitingiz tasdiqlandi!*\n\n"
            f"💰 Miqdor: *{deposit['amount']:.2f} TRX*\n"
            f"🚀 12 soatdan keyin *{deposit['amount']*1.2:.2f} TRX* olasiz!\n"
            f"⏰ Tugash vaqti: {finish_time.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Foydalanuvchiga xabar yuborilmadi: {e}")

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *TASDIQLANDI*",
        parse_mode="Markdown"
    )
    await callback.answer("✅ Tasdiqlandi!")

    asyncio.create_task(auto_payout(deposit['user_id'], deposit['amount'] * 1.2, dep_id))


@dp.callback_query(F.data.startswith("reject_"))
async def reject_deposit(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!")
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
            "❌ *Depozitingiz rad etildi.*\n\nIltimos, admin bilan bog'laning.",
            parse_mode="Markdown"
        )
    except:
        pass

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ *RAD ETILDI*",
        parse_mode="Markdown"
    )
    await callback.answer("❌ Rad etildi!")


# ===================== AVTOMATIK 1.2X TO'LOV =====================
async def auto_payout(user_id: int, amount: float, dep_id: int):
    await asyncio.sleep(12 * 3600)
    db.add_balance(user_id, amount)
    db.mark_paid(dep_id)

    try:
        await bot.send_message(
            user_id,
            f"🎊 *Tabriklaymiz! Pulingiz 1.2x bo'ldi!*\n\n"
            f"💰 Hisobingizga *{amount:.2f} TRX* qo'shildi!\n"
            f"💸 Yechib olish uchun: /start",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Payout xabari yuborilmadi: {e}")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ Avtomatik to'lov bajarildi\n"
                f"👤 User: {user_id}\n"
                f"💰 Miqdor: {amount:.2f} TRX"
            )
        except:
            pass


# ===================== REFERAL =====================
@dp.message(F.text == "👥 Referal")
async def show_referral(message: types.Message):
    user_id = message.from_user.id
    count = db.get_referral_count(user_id)
    earnings = db.get_referral_earnings(user_id)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user_id}"

    await message.answer(
        f"👥 *Referal tizimi*\n\n"
        f"🔗 Sizning havolangiz:\n`{link}`\n\n"
        f"👤 Taklif qilganlar: *{count}* kishi\n"
        f"💰 Referal daromad: *{earnings:.2f} TRX*\n\n"
        f"💡 Har bir do'stingiz depozit qilganda *5%* bonus olasiz!",
        parse_mode="Markdown"
    )


# ===================== TARIX =====================
@dp.message(F.text == "📜 Tarix")
async def show_history(message: types.Message):
    history = db.get_user_history(message.from_user.id, limit=10)
    if not history:
        await message.answer("📭 Hali hech qanday tranzaksiya yo'q.")
        return

    text = "📜 *So'nggi 10 ta tranzaksiya:*\n\n"
    status_map = {"pending": "⏳", "approved": "✅", "paid": "💰", "rejected": "❌"}
    for h in history:
        emoji = status_map.get(h['status'], "•")
        # created_at datetime obyekti (naive), uni Toshkent vaqti deb belgilaymiz
        dt = h['created_at'].replace(tzinfo=TZ)
        date_str = dt.strftime('%d.%m %H:%M')
        text += f"{emoji} {h['amount']:.2f} TRX — {date_str} — {h['status']}\n"

    await message.answer(text, parse_mode="Markdown")


# ===================== YECHISH =====================
@dp.message(F.text == "💸 Yechib olish")
async def withdraw_start(message: types.Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user or user['balance'] < 10:
        bal = user['balance'] if user else 0
        await message.answer(
            f"❌ Minimal yechish miqdori *10 TRX*.\n"
            f"Sizning balansigiz: *{bal:.2f} TRX*",
            parse_mode="Markdown"
        )
        return

    await message.answer(
        f"💸 *Pul yechish*\n\n"
        f"💰 Mavjud balans: *{user['balance']:.2f} TRX*\n\n"
        f"TRX (TRC20) wallet manzilingizni kiriting:",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawState.waiting_address)


@dp.message(WithdrawState.waiting_address)
async def withdraw_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    user = db.get_user(message.from_user.id)
    await message.answer(
        f"💰 Qancha yechmoqchisiz?\n"
        f"_(Max: {user['balance']:.2f} TRX)_",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawState.waiting_amount)


@dp.message(WithdrawState.waiting_amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        user = db.get_user(message.from_user.id)

        if amount > user['balance']:
            await message.answer("❌ Yetarli mablag' yo'q!")
            return
        if amount < 10:
            await message.answer("❌ Minimal yechish 10 TRX!")
            return

        data = await state.get_data()
        address = data['address']
        db.create_withdrawal(message.from_user.id, amount, address)
        db.deduct_balance(message.from_user.id, amount)

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"💸 *Yangi yechish so'rovi*\n\n"
                    f"👤 User ID: `{message.from_user.id}`\n"
                    f"👤 Ism: {message.from_user.full_name}\n"
                    f"💰 Miqdor: *{amount:.2f} TRX*\n"
                    f"📍 Manzil: `{address}`",
                    parse_mode="Markdown"
                )
            except:
                pass

        await message.answer(
            "✅ *Yechish so'rovi qabul qilindi!*\n\n"
            "Admin ko'rib chiqib, 1-24 soat ichida yuboradi.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto'g'ri raqam! Qayta kiriting:")


# ===================== ADMIN PANEL =====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Ruxsat yo'q!")
        return
    stats = db.get_stats()
    await message.answer(
        f"🔐 *Admin Panel*\n\n"
        f"👤 Jami foydalanuvchilar: *{stats['users']}*\n"
        f"💰 Jami depozit: *{stats['total_deposits']:.2f} TRX*\n"
        f"📤 Jami 1.2x to'lovlar: *{stats['total_payouts']:.2f} TRX*\n"
        f"⏳ Kutayotgan: *{stats['pending']}*\n"
        f"✅ Aktiv: *{stats['approved']}*",
        parse_mode="Markdown",
        reply_markup=admin_menu()
    )


@dp.message(F.text == "👤 Foydalanuvchilar")
async def admin_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = db.get_all_users(limit=20)
    if not users:
        await message.answer("Foydalanuvchilar yo'q.")
        return
    text = "👤 *So'nggi 20 foydalanuvchi:*\n\n"
    for u in users:
        text += f"• {u['full_name']} | 💰{u['balance']:.2f} TRX | {u['created_at'][:10]}\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "💳 Kutayotgan depozitlar")
async def admin_pending(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    deposits = db.get_pending_deposits()
    if not deposits:
        await message.answer("✅ Kutayotgan depozit yo'q!")
        return
    for dep in deposits:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{dep['id']}"),
            InlineKeyboardButton(text="❌ Rad", callback_data=f"reject_{dep['id']}")
        ]])
        await message.answer(
            f"💳 *Depozit #{dep['id']}*\n"
            f"👤 User: `{dep['user_id']}`\n"
            f"💰 Miqdor: *{dep['amount']:.2f} TRX*\n"
            f"🔗 TXID: `{dep['txid']}`\n"
            f"🕐 Vaqt: {dep['created_at'][:16]}",   # created_at string (Toshkent vaqti)
            parse_mode="Markdown",
            reply_markup=kb
        )


@dp.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:")
    await state.set_state(BroadcastState.waiting_message)


@dp.message(BroadcastState.waiting_message)
async def broadcast_send(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = db.get_all_users(limit=10000)
    sent = 0
    failed = 0
    for user in users:
        try:
            await bot.send_message(user['user_id'], message.text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1

    await message.answer(
        f"📢 Xabar yuborildi!\n✅ Muvaffaqiyatli: {sent}\n❌ Xato: {failed}",
        reply_markup=admin_menu()
    )
    await state.clear()


@dp.message(F.text == "📈 Statistika")
async def admin_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    stats = db.get_stats()
    await message.answer(
        f"📈 *Bot statistikasi*\n\n"
        f"👤 Foydalanuvchilar: {stats['users']}\n"
        f"💰 Jami depozit: {stats['total_deposits']:.2f} TRX\n"
        f"📤 Jami 1.2x to'lovlar: {stats['total_payouts']:.2f} TRX\n"
        f"⏳ Kutayotganlar: {stats['pending']}\n"
        f"✅ Aktiv depozitlar: {stats['approved']}",
        parse_mode="Markdown"
    )


@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Asosiy menyu:", reply_markup=main_menu())


# ===================== MA'LUMOT =====================
@dp.message(F.text == "ℹ️ Ma'lumot")
async def info(message: types.Message):
    await message.answer(
        "ℹ️ *Bot haqida*\n\n"
        "🤖 1.2X Crypto Bot — kripto investitsiya platformasi\n\n"
        "📌 Qoidalar:\n"
        f"• Minimal depozit: {MIN_DEPOSIT} TRX\n"
        "• 12 soatdan keyin 1.2x qaytarish\n"
        "• TRX (TRC20) qabul qilinadi\n"
        "• Referal bonus: 5%\n\n"
        "📞 Admin: @admin_username",
        parse_mode="Markdown"
    )


# ===================== MAIN =====================
async def main():
    db.create_tables()
    print("✅ Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
