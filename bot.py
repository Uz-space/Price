import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ========== SOZLAMALAR ==========
BOT_TOKEN = "8627453491:AAFEpPXTg-uT_wLCQ--8--7XkQPYoj_ZXuE"  # O'zgartiring!
ADMIN_ID = 7399101034 # Admin Telegram ID si (o'zingiznikini qo'ying)

# ========== BAZA ==========
conn = sqlite3.connect("hookah_bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT,
    price INTEGER,
    category TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cart (
    user_id INTEGER,
    product_id INTEGER,
    quantity INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    products TEXT,
    total INTEGER,
    status TEXT,
    date TEXT
)
""")

# Mahsulotlar (agar bo'sh bo'lsa, qo'shamiz)
cursor.execute("SELECT COUNT(*) FROM products")
if cursor.fetchone()[0] == 0:
    sample_products = [
        ("Alpha Hookah Classic", 150000, "nargile"),
        ("Alpha Hookah Premium", 250000, "nargile"),
        ("Qovun aromati", 30000, "aroma"),
        ("Yalpiz aromati", 30000, "aroma"),
        ("Mojito", 50000, "ichimlik"),
        ("Choy", 20000, "ichimlik")
    ]
    cursor.executemany("INSERT INTO products (name, price, category) VALUES (?, ?, ?)", sample_products)
    conn.commit()

# ========== BOT ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# FSM (buyurtma jarayoni)
class OrderState(StatesGroup):
    waiting_for_confirmation = State()

# ========== TUGMALAR ==========
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍽 Menyu"), KeyboardButton(text="🛒 Savatcha")],
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="📞 Aloqa")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Buyurtmalar"), KeyboardButton(text="✅ Holatni o'zgartirish")]
    ],
    resize_keyboard=True
)

# ========== KOMANDALAR ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        await message.answer("Admin paneliga xush kelibsiz!", reply_markup=admin_menu)
    else:
        await message.answer("AlphaHookah bar botiga xush kelibsiz!\nMenyuni tanlang:", reply_markup=main_menu)

@dp.message(lambda msg: msg.text == "🍽 Menyu")
async def show_menu(message: types.Message):
    cursor.execute("SELECT category, name, price FROM products")
    rows = cursor.fetchall()
    categories = {}
    for cat, name, price in rows:
        categories.setdefault(cat, []).append(f"{name} - {price} so'm")
    
    text = "📋 *Bizning menyu:*\n\n"
    for cat, items in categories.items():
        text += f"*{cat.upper()}*:\n" + "\n".join(items) + "\n\n"
    
    # Har bir mahsulot uchun tugma
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    cursor.execute("SELECT id, name, price FROM products")
    for pid, name, price in cursor.fetchall():
        inline_kb.inline_keyboard.append([InlineKeyboardButton(text=f"➕ {name} ({price} so'm)", callback_data=f"add_{pid}")])
    await message.answer(text, parse_mode="Markdown", reply_markup=inline_kb)

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    cursor.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)", (user_id, product_id))
    conn.commit()
    await callback.answer("Savatchaga qo'shildi!", show_alert=True)

@dp.message(lambda msg: msg.text == "🛒 Savatcha")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("""
        SELECT p.name, p.price, c.quantity 
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, (user_id,))
    items = cursor.fetchall()
    if not items:
        await message.answer("Savatcha bo'sh.")
        return
    text = "🛍 *Savatchangiz:*\n"
    total = 0
    for name, price, qty in items:
        text += f"{name} x{qty} = {price * qty} so'm\n"
        total += price * qty
    text += f"\n*Jami: {total} so'm*"
    await message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order_now")]
    ]))

@dp.callback_query(lambda c: c.data == "order_now")
async def order_now(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cursor.execute("SELECT COUNT(*) FROM cart WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] == 0:
        await callback.answer("Savatcha bo'sh!", show_alert=True)
        return
    await callback.message.answer("Buyurtmangizni tasdiqlaysizmi? (Ha/Yo'q)")
    await state.set_state(OrderState.waiting_for_confirmation)
    await callback.answer()

@dp.message(OrderState.waiting_for_confirmation)
async def confirm_order(message: types.Message, state: FSMContext):
    if message.text.lower() != "ha":
        await message.answer("Buyurtma bekor qilindi.")
        await state.clear()
        return
    user_id = message.from_user.id
    cursor.execute("""
        SELECT p.name, p.price, c.quantity 
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, (user_id,))
    items = cursor.fetchall()
    total = sum(price * qty for _, price, qty in items)
    products_text = ", ".join([f"{name} x{qty}" for name, _, qty in items])
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO orders (user_id, products, total, status, date) VALUES (?, ?, ?, 'yangi', ?)",
                   (user_id, products_text, total, now))
    conn.commit()
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    await message.answer(f"✅ Buyurtma qabul qilindi! Jami: {total} so'm. Admin tez orada bog'lanadi.")
    # Admin xabari
    await bot.send_message(ADMIN_ID, f"🆕 Yangi buyurtma!\nFoydalanuvchi: {user_id}\nMahsulotlar: {products_text}\nJami: {total} so'm")
    await state.clear()

@dp.message(lambda msg: msg.text == "📦 Buyurtma berish")
async def quick_order(message: types.Message):
    await show_cart(message)  # xuddi savatchadan buyurtma

@dp.message(lambda msg: msg.text == "📞 Aloqa")
async def contact(message: types.Message):
    await message.answer("📞 AlphaHookah bar: +998 90 123 45 67\nManzil: Toshkent, ...")

# ========== ADMIN FUNKSIYALARI ==========
@dp.message(lambda msg: msg.text == "📋 Buyurtmalar" and msg.from_user.id == ADMIN_ID)
async def list_orders(message: types.Message):
    cursor.execute("SELECT id, user_id, products, total, status, date FROM orders ORDER BY id DESC LIMIT 10")
    orders = cursor.fetchall()
    if not orders:
        await message.answer("Buyurtmalar yo'q.")
        return
    text = "📋 So'nggi buyurtmalar:\n\n"
    for oid, uid, prods, total, status, date in orders:
        text += f"#{oid} | Foydalanuvchi: {uid} | {status}\n{prods}\nJami: {total} so'm | {date}\n\n"
    await message.answer(text)

@dp.message(lambda msg: msg.text == "✅ Holatni o'zgartirish" and msg.from_user.id == ADMIN_ID)
async def ask_order_id(message: types.Message):
    await message.answer("Buyurtma ID sini yuboring (masalan: 5)")

@dp.message(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.isdigit())
async def change_status(message: types.Message):
    order_id = int(message.text)
    cursor.execute("SELECT status FROM orders WHERE id=?", (order_id,))
    row = cursor.fetchone()
    if not row:
        await message.answer("Bunday ID topilmadi.")
        return
    current = row[0]
    new_status = "qabul qilingan" if current == "yangi" else "yetkazilgan" if current == "qabul qilingan" else "yangi"
    cursor.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
    conn.commit()
    await message.answer(f"Buyurtma #{order_id} holati '{new_status}' ga o'zgartirildi.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
