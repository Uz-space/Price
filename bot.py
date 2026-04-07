import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== SOZLAMALAR ==========
BOT_TOKEN = "8627453491:AAFEpPXTg-uT_wLCQ--8--7XkQPYoj_ZXuE"
ADMIN_ID = 7399101034  # Telegram ID-ingiz
PAYMENT_INFO = "💳 To‘lov uchun: 4073420033908264\n📞 (MyUzcard / Humo)\n📝 Summa: {total} so‘m. To‘lov qilgach “To‘lov qildim” tugmasini bosing."

# ========== BAZA ==========
conn = sqlite3.connect("hookah_bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
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
    status TEXT,   -- to‘lov_kutilmoqda, qabul_qilingan, bekor_qilingan, yetkazilgan
    date TEXT
)
""")
conn.commit()

# ========== BOT ==========
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ========== FSM ==========
class AddProduct(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_category = State()

class DeleteProduct(StatesGroup):
    waiting_id = State()

class EditProduct(StatesGroup):
    waiting_id = State()
    waiting_field = State()
    waiting_value = State()

# ========== TUGMALAR ==========
user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍽 Menyu"), KeyboardButton(text="🛒 Savatcha")],
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="📞 Aloqa")]
    ],
    resize_keyboard=True
)

admin_main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="📋 Buyurtmalar ro'yxati")],
        [KeyboardButton(text="➕ Mahsulot qo'shish")],
        [KeyboardButton(text="❌ Mahsulot o'chirish")],
        [KeyboardButton(text="✏️ Mahsulot tahrirlash")],
        [KeyboardButton(text="📦 Mahsulotlar ro'yxati")],
        [KeyboardButton(text="💰 To‘lovni tasdiqlash")]
    ],
    resize_keyboard=True
)

# ========== START ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Admin panel", reply_markup=admin_main)
    else:
        await message.answer("🍃 AlphaHookah bar botiga xush kelibsiz!", reply_markup=user_menu)

# ========== FOYDALANUVCHI ==========
@dp.message(lambda msg: msg.text == "🍽 Menyu")
async def show_menu(message: types.Message):
    cursor.execute("SELECT id, name, price, category FROM products")
    products = cursor.fetchall()
    if not products:
        await message.answer("❌ Hozircha mahsulot yo‘q. Admin tomonidan qo‘shiladi.")
        return
    cats = {}
    for pid, name, price, cat in products:
        cats.setdefault(cat, []).append((pid, name, price))
    text = "📋 *Menyu:*\n"
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat, items in cats.items():
        text += f"\n*{cat.upper()}:*\n"
        for pid, name, price in items:
            text += f"• {name} - {price} so'm\n"
            inline_kb.inline_keyboard.append([InlineKeyboardButton(text=f"➕ {name}", callback_data=f"add_{pid}")])
    await message.answer(text, parse_mode="Markdown", reply_markup=inline_kb)

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    cursor.execute("SELECT quantity FROM cart WHERE user_id=? AND product_id=?", (user_id, product_id))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE cart SET quantity=? WHERE user_id=? AND product_id=?", (row[0]+1, user_id, product_id))
    else:
        cursor.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)", (user_id, product_id))
    conn.commit()
    await callback.answer("✅ Savatchaga qo'shildi!", show_alert=True)

@dp.message(lambda msg: msg.text == "🛒 Savatcha")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("""
        SELECT p.id, p.name, p.price, c.quantity 
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, (user_id,))
    items = cursor.fetchall()
    if not items:
        await message.answer("🛒 Savatcha bo'sh.")
        return
    text = "🛍 *Savatchangiz:*\n"
    total = 0
    for pid, name, price, qty in items:
        text += f"{name} x{qty} = {price * qty} so'm\n"
        total += price * qty
    text += f"\n*Jami: {total} so'm*"
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order_now")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=inline_kb)

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    cursor.execute("DELETE FROM cart WHERE user_id=?", (callback.from_user.id,))
    conn.commit()
    await callback.answer("Savatcha tozalandi!", show_alert=True)
    await callback.message.delete()

@dp.callback_query(lambda c: c.data == "order_now")
async def order_now(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT COUNT(*) FROM cart WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] == 0:
        await callback.answer("Savatcha bo'sh!", show_alert=True)
        return
    # Savatcha ma'lumotlari
    cursor.execute("""
        SELECT p.name, p.price, c.quantity 
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, (user_id,))
    items = cursor.fetchall()
    total = sum(price * qty for _, price, qty in items)
    products_text = ", ".join([f"{name} x{qty}" for name, _, qty in items])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Buyurtmani "to‘lov_kutilmoqda" holatida saqlash
    cursor.execute("INSERT INTO orders (user_id, products, total, status, date) VALUES (?, ?, ?, 'to‘lov_kutilmoqda', ?)",
                   (user_id, products_text, total, now))
    conn.commit()
    order_id = cursor.lastrowid
    
    # Savatchani tozalash
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    
    # Foydalanuvchiga to'lov ma'lumotlari
    payment_text = PAYMENT_INFO.format(total=total)
    await callback.message.answer(
        f"📦 Buyurtma #{order_id} qabul qilindi.\n\n{payment_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ To‘lov qildim", callback_data=f"paid_{order_id}")]
        ])
    )
    # Adminga xabar (to'lov kutilmoqda)
    await bot.send_message(ADMIN_ID, f"🆕 Yangi buyurtma #{order_id}\nFoydalanuvchi: {user_id}\n{products_text}\nJami: {total} so'm\nHolat: to‘lov kutilmoqda")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def user_paid(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    cursor.execute("SELECT status FROM orders WHERE id=? AND user_id=?", (order_id, user_id))
    row = cursor.fetchone()
    if not row:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return
    if row[0] != "to‘lov_kutilmoqda":
        await callback.answer("Bu buyurtma allaqachon tasdiqlangan yoki bekor qilingan.", show_alert=True)
        return
    # Admin xabar beramiz
    cursor.execute("SELECT products, total FROM orders WHERE id=?", (order_id,))
    prods, total = cursor.fetchone()
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ To‘lovni tasdiqlash", callback_data=f"confirm_payment_{order_id}"),
         InlineKeyboardButton(text="❌ To‘lovni rad etish", callback_data=f"reject_payment_{order_id}")]
    ])
    await bot.send_message(ADMIN_ID, f"💳 Foydalanuvchi #{user_id} buyurtma #{order_id} uchun to‘lov qildim deb bildirdi.\n{prods}\nJami: {total} so'm", reply_markup=admin_kb)
    await callback.message.answer("To‘lov ma'lumotingiz adminga yuborildi. Tez orada tasdiqlanadi.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("confirm_payment_"))
async def confirm_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[-1])
    cursor.execute("SELECT user_id, status FROM orders WHERE id=?", (order_id,))
    row = cursor.fetchone()
    if not row:
        await callback.answer("Buyurtma topilmadi")
        return
    user_id, status = row
    if status != "to‘lov_kutilmoqda":
        await callback.answer(f"Holat allaqachon {status}")
        return
    cursor.execute("UPDATE orders SET status='qabul_qilingan' WHERE id=?", (order_id,))
    conn.commit()
    await bot.send_message(user_id, f"✅ #{order_id} buyurtmangiz to‘lovi tasdiqlandi! Buyurtma qabul qilingan.")
    await callback.message.edit_text(f"✅ Buyurtma #{order_id} to‘lovi tasdiqlandi.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("reject_payment_"))
async def reject_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[-1])
    cursor.execute("SELECT user_id, status FROM orders WHERE id=?", (order_id,))
    row = cursor.fetchone()
    if not row:
        await callback.answer("Topilmadi")
        return
    user_id, status = row
    if status != "to‘lov_kutilmoqda":
        await callback.answer(f"Holat {status}")
        return
    cursor.execute("UPDATE orders SET status='bekor_qilingan' WHERE id=?", (order_id,))
    conn.commit()
    await bot.send_message(user_id, f"❌ #{order_id} buyurtmangiz to‘lovi rad etildi. Iltimos, administrator bilan bog‘laning.")
    await callback.message.edit_text(f"❌ Buyurtma #{order_id} rad etildi.")
    await callback.answer()

@dp.message(lambda msg: msg.text == "📦 Buyurtma berish")
async def quick_order(message: types.Message):
    await show_cart(message)

@dp.message(lambda msg: msg.text == "📞 Aloqa")
async def contact(message: types.Message):
    await message.answer("📞 +998 90 123 45 67\n📍 Toshkent, ...")

# ========== ADMIN FUNKSIYALARI ==========
@dp.message(lambda msg: msg.text == "📊 Statistika" and msg.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(total) FROM orders WHERE status='qabul_qilingan' OR status='yetkazilgan'")
    total_revenue = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    await message.answer(f"📊 *Statistika*\nBuyurtmalar: {total_orders}\nDaromad: {total_revenue} so'm\nMahsulotlar: {total_products}", parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "📋 Buyurtmalar ro'yxati" and msg.from_user.id == ADMIN_ID)
async def list_orders_admin(message: types.Message):
    cursor.execute("SELECT id, user_id, products, total, status, date FROM orders ORDER BY id DESC LIMIT 20")
    orders = cursor.fetchall()
    if not orders:
        await message.answer("Hech qanday buyurtma yo'q.")
        return
    text = "📋 Oxirgi 20:\n\n"
    for oid, uid, prods, total, status, date in orders:
        text += f"#{oid} | {uid} | {status}\n{prods}\nJami: {total} so'm | {date}\n\n"
    await message.answer(text)

@dp.message(lambda msg: msg.text == "💰 To‘lovni tasdiqlash" and msg.from_user.id == ADMIN_ID)
async def payment_help(message: types.Message):
    await message.answer("Foydalanuvchi 'To‘lov qildim' tugmasini bosganida admin panelga tugmali xabar keladi. Shu yerdan tasdiqlaysiz.")

# Mahsulot qo'shish, o'chirish, tahrirlash funksiyalari (oldingi kod bilan bir xil, qisqartirib yozdim)
@dp.message(lambda msg: msg.text == "➕ Mahsulot qo'shish" and msg.from_user.id == ADMIN_ID)
async def add_product_start(message: types.Message, state: FSMContext):
    await message.answer("Mahsulot nomi:")
    await state.set_state(AddProduct.waiting_name)

@dp.message(AddProduct.waiting_name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Narxi (faqat raqam):")
    await state.set_state(AddProduct.waiting_price)

@dp.message(AddProduct.waiting_price)
async def add_product_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam!")
        return
    await state.update_data(price=int(message.text))
    await message.answer("Kategoriyasi (nargile/aroma/ichimlik):")
    await state.set_state(AddProduct.waiting_category)

@dp.message(AddProduct.waiting_category)
async def add_product_category(message: types.Message, state: FSMContext):
    cat = message.text.strip().lower()
    data = await state.get_data()
    try:
        cursor.execute("INSERT INTO products (name, price, category) VALUES (?, ?, ?)", (data['name'], data['price'], cat))
        conn.commit()
        await message.answer(f"✅ {data['name']} qo'shildi!")
    except sqlite3.IntegrityError:
        await message.answer("❌ Bunday nom bor.")
    await state.clear()

@dp.message(lambda msg: msg.text == "❌ Mahsulot o'chirish" and msg.from_user.id == ADMIN_ID)
async def delete_product_start(message: types.Message, state: FSMContext):
    cursor.execute("SELECT id, name FROM products")
    prods = cursor.fetchall()
    if not prods:
        await message.answer("Mahsulot yo'q.")
        return
    text = "ID yuboring:\n" + "\n".join([f"ID {pid}: {name}" for pid, name in prods])
    await message.answer(text)
    await state.set_state(DeleteProduct.waiting_id)

@dp.message(DeleteProduct.waiting_id)
async def delete_product_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID raqam!")
        return
    pid = int(message.text)
    cursor.execute("DELETE FROM products WHERE id=?", (pid,))
    if cursor.rowcount:
        conn.commit()
        await message.answer(f"✅ ID {pid} o'chirildi.")
    else:
        await message.answer("Topilmadi.")
    await state.clear()

@dp.message(lambda msg: msg.text == "✏️ Mahsulot tahrirlash" and msg.from_user.id == ADMIN_ID)
async def edit_product_start(message: types.Message, state: FSMContext):
    cursor.execute("SELECT id, name, price, category FROM products")
    prods = cursor.fetchall()
    if not prods:
        await message.answer("Mahsulot yo'q.")
        return
    text = "ID:\n" + "\n".join([f"ID {pid}: {name} - {price} ({cat})" for pid, name, price, cat in prods])
    await message.answer(text)
    await state.set_state(EditProduct.waiting_id)

@dp.message(EditProduct.waiting_id)
async def edit_product_field(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID raqam!")
        return
    pid = int(message.text)
    cursor.execute("SELECT id FROM products WHERE id=?", (pid,))
    if not cursor.fetchone():
        await message.answer("Topilmadi.")
        await state.clear()
        return
    await state.update_data(pid=pid)
    await message.answer("Nimani tahrirlaymiz? name / price / category")
    await state.set_state(EditProduct.waiting_field)

@dp.message(EditProduct.waiting_field)
async def edit_product_value(message: types.Message, state: FSMContext):
    field = message.text.lower()
    if field not in ['name', 'price', 'category']:
        await message.answer("Faqat name, price, category")
        return
    await state.update_data(field=field)
    await message.answer(f"Yangi {field}:")
    await state.set_state(EditProduct.waiting_value)

@dp.message(EditProduct.waiting_value)
async def edit_product_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    pid = data['pid']
    field = data['field']
    new_val = message.text.strip()
    if field == 'price':
        if not new_val.isdigit():
            await message.answer("Raqam kerak!")
            return
        new_val = int(new_val)
    try:
        cursor.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (new_val, pid))
        conn.commit()
        await message.answer(f"✅ O'zgartirildi: {field} -> {new_val}")
    except sqlite3.IntegrityError:
        await message.answer("❌ Bunday nom mavjud.")
    await state.clear()

@dp.message(lambda msg: msg.text == "📦 Mahsulotlar ro'yxati" and msg.from_user.id == ADMIN_ID)
async def list_products_admin(message: types.Message):
    cursor.execute("SELECT id, name, price, category FROM products")
    prods = cursor.fetchall()
    if not prods:
        await message.answer("Mahsulot yo'q.")
        return
    text = "📦 *Mahsulotlar:*\n" + "\n".join([f"ID {pid}: {name} - {price} ({cat})" for pid, name, price, cat in prods])
    await message.answer(text, parse_mode="Markdown")

# ========== ISHGA TUSHIRISH ==========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
