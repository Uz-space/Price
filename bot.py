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
BOT_TOKEN = "8627453491:AAFEpPXTg-uT_wLCQ--8--7XkQPYoj_ZXuE"  # @BotFather dan oling
ADMIN_ID = 7399101034  # Telegram ID ingiz (admin)

# ========== BAZA ==========
conn = sqlite3.connect("hookah_bot.db")
cursor = conn.cursor()

# Mahsulotlar jadvali (bo'sh)
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    price INTEGER,
    category TEXT
)
""")

# Savatcha
cursor.execute("""
CREATE TABLE IF NOT EXISTS cart (
    user_id INTEGER,
    product_id INTEGER,
    quantity INTEGER
)
""")

# Buyurtmalar
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

conn.commit()

# ========== BOT ==========
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ========== FSM HOLATLARI ==========
class AddProduct(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_category = State()

class DeleteProduct(StatesGroup):
    waiting_id = State()

class EditProduct(StatesGroup):
    waiting_id = State()
    waiting_field = State()  # name, price, category
    waiting_value = State()

class ChangeOrderStatus(StatesGroup):
    waiting_order_id = State()
    waiting_new_status = State()

# ========== TUGMALAR ==========
user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍽 Menyu"), KeyboardButton(text="🛒 Savatcha")],
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="📞 Aloqa")]
    ],
    resize_keyboard=True
)

# Admin panel asosiy tugmalari (oddiy matnli tugmalar)
admin_main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="📋 Buyurtmalar ro'yxati")],
        [KeyboardButton(text="➕ Mahsulot qo'shish")],
        [KeyboardButton(text="❌ Mahsulot o'chirish")],
        [KeyboardButton(text="✏️ Mahsulot tahrirlash")],
        [KeyboardButton(text="📦 Mahsulotlar ro'yxati")],
        [KeyboardButton(text="✅ Holat o'zgartirish")]
    ],
    resize_keyboard=True
)

# ========== KOMANDALAR ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        await message.answer("👑 Admin panelga xush kelibsiz!", reply_markup=admin_main)
    else:
        await message.answer("🍃 AlphaHookah bar botiga xush kelibsiz!\nMenyuni tanlang:", reply_markup=user_menu)

# ========== FOYDALANUVCHI FUNKSIYALARI ==========
@dp.message(lambda msg: msg.text == "🍽 Menyu")
async def show_menu(message: types.Message):
    cursor.execute("SELECT id, name, price, category FROM products")
    products = cursor.fetchall()
    if not products:
        await message.answer("❌ Hozircha mahsulot yo‘q. Admin tomonidan qo‘shiladi.")
        return

    # Kategoriyalar bo‘yicha guruhlash
    cats = {}
    for pid, name, price, cat in products:
        cats.setdefault(cat, []).append((pid, name, price))

    text = "📋 *Menyu:*\n"
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat, items in cats.items():
        text += f"\n*{cat.upper()}:*\n"
        for pid, name, price in items:
            text += f"• {name} - {price} so'm\n"
            inline_kb.inline_keyboard.append([
                InlineKeyboardButton(text=f"➕ {name}", callback_data=f"add_{pid}")
            ])
    await message.answer(text, parse_mode="Markdown", reply_markup=inline_kb)

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    # agar savatchada shu mahsulot bo‘lsa, quantity+1
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
    # Ochirish tugmasi
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order_now")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=inline_kb)

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
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
    # buyurtma yaratish
    cursor.execute("""
        SELECT p.name, p.price, c.quantity 
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, (user_id,))
    items = cursor.fetchall()
    total = sum(price * qty for _, price, qty in items)
    products_text = ", ".join([f"{name} x{qty}" for name, _, qty in items])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO orders (user_id, products, total, status, date) VALUES (?, ?, ?, 'yangi', ?)",
                   (user_id, products_text, total, now))
    conn.commit()
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    await callback.message.answer(f"✅ Buyurtma qabul qilindi! Jami: {total} so'm. Admin tez orada bog'lanadi.")
    # Admin xabar
    await bot.send_message(ADMIN_ID, f"🆕 Yangi buyurtma!\nFoydalanuvchi: {user_id}\n{products_text}\nJami: {total} so'm")
    await callback.answer()

@dp.message(lambda msg: msg.text == "📦 Buyurtma berish")
async def quick_order(message: types.Message):
    await show_cart(message)

@dp.message(lambda msg: msg.text == "📞 Aloqa")
async def contact(message: types.Message):
    await message.answer("📞 AlphaHookah bar: +998 90 123 45 67\nManzil: Toshkent, ...")

# ========== ADMIN FUNKSIYALARI ==========
@dp.message(lambda msg: msg.text == "📊 Statistika" and msg.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(total) FROM orders WHERE status != 'bekor qilingan'")
    total_revenue = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    await message.answer(
        f"📊 *Statistika*\n"
        f"📦 Jami buyurtmalar: {total_orders}\n"
        f"💰 Umumiy daromad: {total_revenue} so'm\n"
        f"🍽 Mahsulotlar soni: {total_products}",
        parse_mode="Markdown"
    )

@dp.message(lambda msg: msg.text == "📋 Buyurtmalar ro'yxati" and msg.from_user.id == ADMIN_ID)
async def list_orders_admin(message: types.Message):
    cursor.execute("SELECT id, user_id, products, total, status, date FROM orders ORDER BY id DESC LIMIT 20")
    orders = cursor.fetchall()
    if not orders:
        await message.answer("Hech qanday buyurtma yo'q.")
        return
    text = "📋 *Oxirgi 20 buyurtma:*\n\n"
    for oid, uid, prods, total, status, date in orders:
        text += f"#{oid} | Foydalanuvchi: {uid} | {status}\n{prods}\nJami: {total} so'm | {date}\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "➕ Mahsulot qo'shish" and msg.from_user.id == ADMIN_ID)
async def add_product_start(message: types.Message, state: FSMContext):
    await message.answer("Yangi mahsulot **nomini** yuboring:")
    await state.set_state(AddProduct.waiting_name)

@dp.message(AddProduct.waiting_name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Narxini yuboring (faqat raqam):")
    await state.set_state(AddProduct.waiting_price)

@dp.message(AddProduct.waiting_price)
async def add_product_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam yuboring.")
        return
    await state.update_data(price=int(message.text))
    await message.answer("Kategoriyasini yuboring (masalan: nargile, aroma, ichimlik):")
    await state.set_state(AddProduct.waiting_category)

@dp.message(AddProduct.waiting_category)
async def add_product_category(message: types.Message, state: FSMContext):
    cat = message.text.strip().lower()
    data = await state.get_data()
    try:
        cursor.execute("INSERT INTO products (name, price, category) VALUES (?, ?, ?)",
                       (data['name'], data['price'], cat))
        conn.commit()
        await message.answer(f"✅ Mahsulot qo'shildi:\n{data['name']} - {data['price']} so'm (kategoriya: {cat})")
    except sqlite3.IntegrityError:
        await message.answer("❌ Bunday nomli mahsulot allaqachon mavjud.")
    await state.clear()

@dp.message(lambda msg: msg.text == "❌ Mahsulot o'chirish" and msg.from_user.id == ADMIN_ID)
async def delete_product_start(message: types.Message, state: FSMContext):
    cursor.execute("SELECT id, name FROM products")
    prods = cursor.fetchall()
    if not prods:
        await message.answer("Hech qanday mahsulot yo'q.")
        return
    text = "O'chirish uchun mahsulot ID sini yuboring:\n"
    for pid, name in prods:
        text += f"ID {pid}: {name}\n"
    await message.answer(text)
    await state.set_state(DeleteProduct.waiting_id)

@dp.message(DeleteProduct.waiting_id)
async def delete_product_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID raqam bo'lishi kerak.")
        return
    pid = int(message.text)
    cursor.execute("DELETE FROM products WHERE id=?", (pid,))
    if cursor.rowcount == 0:
        await message.answer("Bunday ID topilmadi.")
    else:
        conn.commit()
        await message.answer(f"✅ Mahsulot ID {pid} o'chirildi.")
    await state.clear()

@dp.message(lambda msg: msg.text == "✏️ Mahsulot tahrirlash" and msg.from_user.id == ADMIN_ID)
async def edit_product_start(message: types.Message, state: FSMContext):
    cursor.execute("SELECT id, name, price, category FROM products")
    prods = cursor.fetchall()
    if not prods:
        await message.answer("Hech qanday mahsulot yo'q.")
        return
    text = "Tahrirlash uchun mahsulot ID sini yuboring:\n"
    for pid, name, price, cat in prods:
        text += f"ID {pid}: {name} - {price} so'm ({cat})\n"
    await message.answer(text)
    await state.set_state(EditProduct.waiting_id)

@dp.message(EditProduct.waiting_id)
async def edit_product_field(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID raqam bo'lishi kerak.")
        return
    pid = int(message.text)
    cursor.execute("SELECT id FROM products WHERE id=?", (pid,))
    if not cursor.fetchone():
        await message.answer("Bunday ID topilmadi.")
        await state.clear()
        return
    await state.update_data(pid=pid)
    await message.answer("Nimani tahrirlamoqchisiz? (name / price / category)")
    await state.set_state(EditProduct.waiting_field)

@dp.message(EditProduct.waiting_field)
async def edit_product_value(message: types.Message, state: FSMContext):
    field = message.text.lower()
    if field not in ['name', 'price', 'category']:
        await message.answer("Faqat name, price yoki category yozing.")
        return
    await state.update_data(field=field)
    await message.answer(f"Yangi {field} qiymatini yuboring:")
    await state.set_state(EditProduct.waiting_value)

@dp.message(EditProduct.waiting_value)
async def edit_product_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    pid = data['pid']
    field = data['field']
    new_val = message.text.strip()
    if field == 'price':
        if not new_val.isdigit():
            await message.answer("Narx faqat raqam bo'lishi kerak.")
            return
        new_val = int(new_val)
    try:
        cursor.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (new_val, pid))
        conn.commit()
        await message.answer(f"✅ Mahsulot ID {pid} ning {field} qiymati o'zgartirildi: {new_val}")
    except sqlite3.IntegrityError:
        await message.answer("❌ Bunday nom allaqachon mavjud (name noyob bo'lishi kerak).")
    await state.clear()

@dp.message(lambda msg: msg.text == "📦 Mahsulotlar ro'yxati" and msg.from_user.id == ADMIN_ID)
async def list_products_admin(message: types.Message):
    cursor.execute("SELECT id, name, price, category FROM products")
    prods = cursor.fetchall()
    if not prods:
        await message.answer("Mahsulotlar mavjud emas.")
        return
    text = "📦 *Barcha mahsulotlar:*\n"
    for pid, name, price, cat in prods:
        text += f"ID {pid}: {name} - {price} so'm ({cat})\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "✅ Holat o'zgartirish" and msg.from_user.id == ADMIN_ID)
async def change_status_start(message: types.Message, state: FSMContext):
    await message.answer("Buyurtma ID sini yuboring:")
    await state.set_state(ChangeOrderStatus.waiting_order_id)

@dp.message(ChangeOrderStatus.waiting_order_id)
async def change_status_order_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID raqam bo'lishi kerak.")
        return
    oid = int(message.text)
    cursor.execute("SELECT status FROM orders WHERE id=?", (oid,))
    row = cursor.fetchone()
    if not row:
        await message.answer("Bunday ID topilmadi.")
        await state.clear()
        return
    await state.update_data(oid=oid)
    await message.answer(f"Hozirgi holat: {row[0]}\nYangi holatni yuboring (yangi / qabul qilingan / yetkazilgan / bekor qilingan):")
    await state.set_state(ChangeOrderStatus.waiting_new_status)

@dp.message(ChangeOrderStatus.waiting_new_status)
async def change_status_save(message: types.Message, state: FSMContext):
    new_status = message.text.strip().lower()
    valid = ['yangi', 'qabul qilingan', 'yetkazilgan', 'bekor qilingan']
    if new_status not in valid:
        await message.answer(f"Faqat: {', '.join(valid)}")
        return
    data = await state.get_data()
    cursor.execute("UPDATE orders SET status=? WHERE id=?", (new_status, data['oid']))
    conn.commit()
    await message.answer(f"✅ Buyurtma #{data['oid']} holati '{new_status}' ga o'zgartirildi.")
    await state.clear()

# ========== ISHGA TUSHIRISH ==========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
