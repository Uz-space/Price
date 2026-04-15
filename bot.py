import logging
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import BaseMiddleware
from aiogram.types import Update

from database import Database

# ===================== CONFIGURATION =====================
BOT_TOKEN = "8776678535:AAHAJJQunvKAjx0zhmWvU0cGmE_STAZ5VBU"
ADMIN_IDS = [7399101034]               # Replace with your Telegram ID
WALLET_ADDRESS = "TDwNz8zRsL9oQqw7c8UTe3cS3neiZLo3ay"
MIN_DEPOSIT = 10

TZ = ZoneInfo("Asia/Tashkent")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================== INITIALISATION =====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()


# ===================== MIDDLEWARE FOR LOGGING (does NOT block handlers) =====================
class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        # Log incoming updates without interfering
        if event.message:
            user = event.message.from_user
            logger.info(f"📩 Update | User: {user.id} ({user.full_name}) | Text: {event.message.text}")
        elif event.callback_query:
            user = event.callback_query.from_user
            logger.info(f"🔘 Callback | User: {user.id} | Data: {event.callback_query.data}")
        return await handler(event, data)

dp.message.middleware(LoggingMiddleware())
dp.callback_query.middleware(LoggingMiddleware())


# ===================== STATES =====================
class DepositState(StatesGroup):
    waiting_amount = State()
    waiting_txid = State()

class WithdrawState(StatesGroup):
    waiting_address = State()
    waiting_amount = State()

class BroadcastState(StatesGroup):
    waiting_message = State()


# ===================== KEYBOARDS =====================
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


# ===================== SAFE USER INITIALISATION =====================
async def get_or_create_user(message: types.Message) -> Optional[Dict[str, Any]]:
    """Safely get user from DB, create if not exists. Returns user dict or None on error."""
    user_id = message.from_user.id
    username = message.from_user.username or "Nomsiz"
    full_name = message.from_user.full_name
    try:
        user = db.get_user(user_id)
        if not user:
            db.add_user(user_id, username, full_name, None)
            user = db.get_user(user_id)
            if user:
                logger.info(f"✅ New user created: {user_id} ({full_name})")
            else:
                logger.error(f"❌ Failed to create user: {user_id}")
                await message.answer("❌ Xatolik yuz berdi. Iltimos, /start bosing.")
                return None
        return user
    except Exception as e:
        logger.error(f"Database error in get_or_create_user: {e}", exc_info=True)
        await message.answer("❌ Texnik xatolik. Iltimos, keyinroq urinib ko'ring.")
        return None


# ===================== GLOBAL ERROR HANDLER =====================
@dp.errors()
async def global_error_handler(update: types.Update, exception: Exception):
    logger.error(f"Global handler caught exception: {exception}", exc_info=True)
    # Try to notify the user if possible
    if update.message:
        try:
            await update.message.answer("⚠️ Kutilmagan xatolik. Admin xabar qilindi.")
        except:
            pass
    return True  # suppress exception


# ===================== START COMMAND =====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info("START command")
    user_id = message.from_user.id
    username = message.from_user.username or "Nomsiz"
    full_name = message.from_user.full_name
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    try:
        db.add_user(user_id, username, full_name, referrer_id)
    except Exception as e:
        logger.error(f"Error adding user on start: {e}")
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


# ===================== BALANCE HANDLER =====================
@dp.message(F.text == "📊 Balans")
async def show_balance(message: types.Message):
    logger.info("BALANCE handler")
    user = await get_or_create_user(message)
    if not user:
        return
    try:
        active = db.get_active_deposits(message.from_user.id) or []
        active_text = ""
        now = datetime.now(TZ)
        for dep in active:
            if dep.get('approved_at'):
                approved_at = datetime.strptime(dep['approved_at'], '%Y-%m-%d %H:%M:%S')
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
    except Exception as e:
        logger.error(f"Balance handler error: {e}", exc_info=True)
        await message.answer("❌ Balansni ko'rsatishda xatolik. Iltimos, keyinroq urinib ko'ring.")


# ===================== INFO HANDLER =====================
@dp.message(F.text == "ℹ️ Ma'lumot")
async def info(message: types.Message):
    logger.info("INFO handler")
    user = await get_or_create_user(message)
    if not user:
        return
    try:
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
    except Exception as e:
        logger.error(f"Info handler error: {e}", exc_info=True)
        await message.answer("❌ Ma'lumot olishda xatolik.")


# ===================== DEPOSIT HANDLERS =====================
@dp.message(F.text == "💰 Depozit")
async def deposit_start(message: types.Message, state: FSMContext):
    logger.info("DEPOSIT start")
    user = await get_or_create_user(message)
    if not user:
        return
    try:
        await message.answer(
            f"💳 *Depozit qilish*\n\n"
            f"📌 Minimal miqdor: *{MIN_DEPOSIT} TRX*\n\n"
            f"Qancha TRX kiritmoqchisiz? (Faqat raqam)",
            parse_mode="Markdown"
        )
        await state.set_state(DepositState.waiting_amount)
    except Exception as e:
        logger.error(f"Deposit start error: {e}", exc_info=True)
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urining.")


@dp.message(DepositState.waiting_amount)
async def deposit_amount(message: types.Message, state: FSMContext):
    logger.info("Deposit amount input")
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
            f"💡 To'lov qilgandan so'ng *Transaction ID (TXID)*ni yuboring:",
            parse_mode="Markdown"
        )
        await state.set_state(DepositState.waiting_txid)
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Faqat raqam kiriting.")
    except Exception as e:
        logger.error(f"Deposit amount error: {e}", exc_info=True)
        await message.answer("❌ Xatolik. Qaytadan /start bosing.")


@dp.message(DepositState.waiting_txid)
async def deposit_txid(message: types.Message, state: FSMContext):
    logger.info("Deposit TXID submitted")
    try:
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
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        await message.answer(
            "✅ *So'rovingiz qabul qilindi!*\n\n⏳ Admin tasdiqlashini kuting.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Deposit TXID error: {e}", exc_info=True)
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urining.")


# ===================== REFERRAL HANDLER =====================
@dp.message(F.text == "👥 Referal")
async def show_referral(message: types.Message):
    logger.info("REFERRAL handler")
    user = await get_or_create_user(message)
    if not user:
        return
    try:
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
    except Exception as e:
        logger.error(f"Referral handler error: {e}", exc_info=True)
        await message.answer("❌ Referal ma'lumotlarini olishda xatolik.")


# ===================== HISTORY HANDLER =====================
@dp.message(F.text == "📜 Tarix")
async def show_history(message: types.Message):
    logger.info("HISTORY handler")
    user = await get_or_create_user(message)
    if not user:
        return
    try:
        history = db.get_user_history(message.from_user.id, limit=10)
        if not history:
            await message.answer("📭 Hali hech qanday tranzaksiya yo'q.")
            return
        text = "📜 *So'nggi 10 ta tranzaksiya:*\n\n"
        status_map = {"pending": "⏳", "approved": "✅", "paid": "💰", "rejected": "❌"}
        for h in history:
            emoji = status_map.get(h['status'], "•")
            dt = h['created_at'].replace(tzinfo=TZ)
            date_str = dt.strftime('%d.%m %H:%M')
            text += f"{emoji} {h['amount']:.2f} TRX — {date_str} — {h['status']}\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"History handler error: {e}", exc_info=True)
        await message.answer("❌ Tarixni ko'rsatishda xatolik.")


# ===================== WITHDRAWAL HANDLERS =====================
@dp.message(F.text == "💸 Yechib olish")
async def withdraw_start(message: types.Message, state: FSMContext):
    logger.info("WITHDRAW start")
    user = await get_or_create_user(message)
    if not user:
        return
    try:
        if user['balance'] < 10:
            await message.answer(f"❌ Minimal yechish miqdori *10 TRX*.\nSizning balansingiz: *{user['balance']:.2f} TRX*", parse_mode="Markdown")
            return
        await message.answer(
            f"💸 *Pul yechish*\n\n💰 Mavjud balans: *{user['balance']:.2f} TRX*\n\nTRX (TRC20) wallet manzilingizni kiriting:",
            parse_mode="Markdown"
        )
        await state.set_state(WithdrawState.waiting_address)
    except Exception as e:
        logger.error(f"Withdraw start error: {e}", exc_info=True)
        await message.answer("❌ Xatolik yuz berdi.")


@dp.message(WithdrawState.waiting_address)
async def withdraw_address(message: types.Message, state: FSMContext):
    logger.info("Withdraw address input")
    await state.update_data(address=message.text.strip())
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Iltimos, /start bosing.")
        return
    await message.answer(
        f"💰 Qancha yechmoqchisiz?\n_(Max: {user['balance']:.2f} TRX)_",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawState.waiting_amount)


@dp.message(WithdrawState.waiting_amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    logger.info("Withdraw amount input")
    try:
        amount = float(message.text.replace(",", "."))
        user = db.get_user(message.from_user.id)
        if not user:
            await message.answer("❌ Iltimos, /start bosing.")
            return
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
                    f"💸 *Yangi yechish so'rovi*\n\n👤 User ID: `{message.from_user.id}`\n👤 Ism: {message.from_user.full_name}\n💰 Miqdor: *{amount:.2f} TRX*\n📍 Manzil: `{address}`",
                    parse_mode="Markdown"
                )
            except:
                pass
        await message.answer(
            "✅ *Yechish so'rovi qabul qilindi!*\n\nAdmin ko'rib chiqib, 1-24 soat ichida yuboradi.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto'g'ri raqam! Qayta kiriting:")
    except Exception as e:
        logger.error(f"Withdraw amount error: {e}", exc_info=True)
        await message.answer("❌ Xatolik yuz berdi.")


# ===================== CALLBACKS (APPROVE/REJECT) =====================
@dp.callback_query(F.data.startswith("approve_"))
async def approve_deposit(callback: types.CallbackQuery):
    logger.info(f"Approve callback: {callback.data}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    try:
        dep_id = int(callback.data.split("_")[1])
        deposit = db.get_deposit(dep_id)
        if not deposit or deposit['status'] != 'pending':
            await callback.answer("Depozit topilmadi yoki allaqachon ko'rib chiqilgan!", show_alert=True)
            return
        db.approve_deposit(dep_id)
        finish_time = datetime.now(TZ) + timedelta(hours=12)
        await bot.send_message(
            deposit['user_id'],
            f"🎉 *Depozitingiz tasdiqlandi!*\n\n"
            f"💰 Miqdor: *{deposit['amount']:.2f} TRX*\n"
            f"🚀 12 soatdan keyin *{deposit['amount']*1.2:.2f} TRX* olasiz!\n"
            f"⏰ Tugash vaqti: {finish_time.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
        await callback.message.edit_text(callback.message.text + "\n\n✅ *TASDIQLANDI*", parse_mode="Markdown")
        await callback.answer("✅ Tasdiqlandi!")
        asyncio.create_task(auto_payout(deposit['user_id'], deposit['amount'] * 1.2, dep_id))
    except Exception as e:
        logger.error(f"Approve callback error: {e}", exc_info=True)
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)


@dp.callback_query(F.data.startswith("reject_"))
async def reject_deposit(callback: types.CallbackQuery):
    logger.info(f"Reject callback: {callback.data}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    try:
        dep_id = int(callback.data.split("_")[1])
        deposit = db.get_deposit(dep_id)
        if not deposit:
            await callback.answer("Depozit topilmadi!", show_alert=True)
            return
        db.reject_deposit(dep_id)
        await bot.send_message(deposit['user_id'], "❌ *Depozitingiz rad etildi.*", parse_mode="Markdown")
        await callback.message.edit_text(callback.message.text + "\n\n❌ *RAD ETILDI*", parse_mode="Markdown")
        await callback.answer("❌ Rad etildi!")
    except Exception as e:
        logger.error(f"Reject callback error: {e}", exc_info=True)
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)


async def auto_payout(user_id: int, amount: float, dep_id: int):
    await asyncio.sleep(12 * 3600)
    try:
        db.add_balance(user_id, amount)
        db.mark_paid(dep_id)
        await bot.send_message(
            user_id,
            f"🎊 *Tabriklaymiz! Pulingiz 1.2x bo'ldi!*\n\n💰 Hisobingizga *{amount:.2f} TRX* qo'shildi!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Auto payout error for user {user_id}: {e}")


# ===================== ADMIN COMMANDS (simple versions) =====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Ruxsat yo'q!")
        return
    stats = db.get_stats()
    await message.answer(
        f"🔐 *Admin Panel*\n\n👤 Foydalanuvchilar: {stats['users']}\n💰 Depozitlar: {stats['total_deposits']:.2f} TRX\n📤 To'lovlar: {stats['total_payouts']:.2f} TRX\n⏳ Kutilmoqda: {stats['pending']}\n✅ Aktiv: {stats['approved']}",
        parse_mode="Markdown",
        reply_markup=admin_menu()
    )

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Asosiy menyu:", reply_markup=main_menu())


# ===================== MAIN =====================
async def main():
    # Clear any old webhook and pending updates
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook cleared, pending updates dropped")
    db.create_tables()
    logger.info("Database tables ready")
    print("✅ Bot ishga tushdi! Barcha handlerlar ro'yxatdan o'tdi.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
