import asyncio
import sqlite3
import csv
from datetime import datetime
from io import StringIO
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== SOZLAMALAR ==========
BOT_TOKEN = "8627453491:AAFEpPXTg-uT_wLCQ--8--7XkQPYoj_ZXuE"
ADMIN_ID = 7399101034 
CHANNEL_ID = "@AlphaHookahOrders"

# ========== BAZA (yangilangan) ==========
conn = sqlite3.connect("hookah_bot.db", check_same_thread=False)
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
    status TEXT,
    address TEXT,
    delivery_time TEXT,
    date TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    blocked INTEGER DEFAULT 0
)
""")
conn.commit()

# ========== BOT ==========
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ========== FSM ==========
class AddProduct(StatesGroup):
    name = State()
    price = State()
    category = State()

class DeleteProduct(StatesGroup):
    id = State()

class EditProduct(StatesGroup):
    id = State()
    field = State()
    value = State()

class OrderAddress(StatesGroup):
    address = State()
    delivery_time = State()

class Broadcast(StatesGroup):
    message = State()

# ========== TUGMALAR ==========
user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍽 Menyu"), KeyboardButton(text="🛒 Savatcha")],
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="📞 Aloqa")],
        [KeyboardButton(text="📜 Mening buyurtmalarim")]
    ],
    resize_keyboard=True
)

admin_main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📋 Buyurtmalar")],
        [KeyboardButton(text="➕ Mahsulot qo'shish"), KeyboardButton(text="❌ O'chirish")],
        [KeyboardButton(text="✏️ Tahrirlash"), KeyboardButton(text="📦 Mahsulotlar")],
        [KeyboardButton(text="💰 To'lovni tasdiqlash"), KeyboardButton(text="🚫 Bloklash/Unblock")],
        [KeyboardButton(text="📢 Reklama yuborish"), KeyboardButton(text="📎 Excel yuklab olish")]
    ],
    resize_keyboard=True
)

# ========== YORDAMCHI ==========
def is_blocked(user_id):
    cursor.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] == 1

async def send_to_user(user_id, text, reply_markup=None):
    if not is_blocked(user_id):
        try:
            await bot.send_message(user_id, text, reply_markup=reply_markup)
        except:
            pass

async def send_to_channel(order_id, event_type):
    """Kanalga chiroyli xabar yuboradi (get_chat chaqirmaydi)"""
    cursor.execute("""
        SELECT o.user_id, o.products, o.total, o.address, o.delivery_time, o.date, u.first_name
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.id = ?
    """, (order_id,))
    row = cursor.fetchone()
    if not row:
        return
    user_id, products, total, address, delivery_time, date, first_name = row
    user_name = first_name or str(user_id)

    date_formatted = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")

    if event_type == "new":
        title = "🍃 AlphaHookah - Yangi buyurtma"
        status_icon = "⏳ To‘lov kutilmoqda"
    elif event_type == "paid":
        title = "🍃 AlphaHookah - To‘lov tasdiqlandi"
        status_icon = "✅ To‘lov tasdiqlandi"
    elif event_type == "delivered":
        title = "🍃 AlphaHookah - Buyurtma yetkazildi"
        status_icon = "🚚 Yetkazildi"
    else:
        return

    text = f"""<b>{title}</b>
🆔: #{order_id}
👤: {user_name}
📦: {products}
💰: {total} so'm
📍: {address}
⏰: {delivery_time}
🔎 Holat: {status_icon}
📝: {date_formatted}"""

    try:
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    except Exception as e:
        print(f"Kanalga xabar yuborilmadi: {e}")

# ========== START ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or ""
    username = message.from_user.username or ""
    cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
                   (user_id, first_name, username))
    conn.commit()
    if user_id == ADMIN_ID:
        await message.answer("👑 Admin panel", reply_markup=admin_main)
    else:
        await message.answer("🍃 AlphaHookah bar botiga xush kelibsiz!", reply_markup=user_menu)

# ========== MENYU ==========
@dp.message(lambda msg: msg.text == "🍽 Menyu")
async def show_categories(message: types.Message):
    cursor.execute("SELECT DISTINCT category FROM products")
    cats = cursor.fetchall()
    if not cats:
        await message.answer("❌ Hozircha mahsulot yo‘q.")
        return
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in cats:
        inline_kb.inline_keyboard.append([InlineKeyboardButton(text=f"📂 {cat[0].upper()}", callback_data=f"cat_{cat[0]}")])
    await message.answer("Kategoriyani tanlang:", reply_markup=inline_kb)

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products_by_category(callback: types.CallbackQuery):
    category = callback.data.split("_")[1]
    cursor.execute("SELECT id, name, price FROM products WHERE category=?", (category,))
    products = cursor.fetchall()
    if not products:
        await callback.answer("Bu kategoriyada mahsulot yo'q", show_alert=True)
        return
    text = f"📋 *{category.upper()}*:\n"
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pid, name, price in products:
        text += f"• {name} - {price} so'm\n"
        inline_kb.inline_keyboard.append([InlineKeyboardButton(text=f"➕ {name}", callback_data=f"add_{pid}")])
    inline_kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_categories")])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_categories")
async def back_to_categories(callback: types.CallbackQuery):
    cursor.execute("SELECT DISTINCT category FROM products")
    cats = cursor.fetchall()
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in cats:
        inline_kb.inline_keyboard.append([InlineKeyboardButton(text=f"📂 {cat[0].upper()}", callback_data=f"cat_{cat[0]}")])
    await callback.message.edit_text("Kategoriyani tanlang:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    if is_blocked(callback.from_user.id):
        await callback.answer("Siz bloklangansiz!", show_alert=True)
        return
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    # Mahsulot mavjudligini tekshirish
    cursor.execute("SELECT id FROM products WHERE id=?", (product_id,))
    if not cursor.fetchone():
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return
    cursor.execute("SELECT quantity FROM cart WHERE user_id=? AND product_id=?", (user_id, product_id))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE cart SET quantity=? WHERE user_id=? AND product_id=?", (row[0]+1, user_id, product_id))
    else:
        cursor.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)", (user_id, product_id))
    conn.commit()
    await callback.answer("✅ Savatchaga qo'shildi!", show_alert=True)

# ========== SAVATCHA (xatoliklarni tekshirish bilan) ==========
@dp.message(lambda msg: msg.text == "🛒 Savatcha")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    try:
        cursor.execute("""
            SELECT p.id, p.name, p.price, c.quantity 
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
        """, (user_id,))
        items = cursor.fetchall()
    except Exception as e:
        await message.answer(f"Xatolik: {e}")
        return

    if not items:
        await message.answer("🛒 Savatcha bo'sh.")
        return

    text = "🛍 *Savatchangiz:*\n"
    total = 0
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pid, name, price, qty in items:
        text += f"{name} x{qty} = {price * qty} so'm\n"
        total += price * qty
        inline_kb.inline_keyboard.append([
            InlineKeyboardButton(text="➖", callback_data=f"dec_{pid}"),
            InlineKeyboardButton(text=f"{qty}", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{pid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"remove_{pid}")
        ])
    text += f"\n*Jami: {total} so'm*"
    inline_kb.inline_keyboard.append([InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order_now")])
    inline_kb.inline_keyboard.append([InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")])
    await message.answer(text, parse_mode="Markdown", reply_markup=inline_kb)

@dp.callback_query(lambda c: c.data.startswith("inc_"))
async def inc_qty(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    cursor.execute("UPDATE cart SET quantity = quantity + 1 WHERE user_id=? AND product_id=?", (user_id, pid))
    conn.commit()
    await show_cart(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("dec_"))
async def dec_qty(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    cursor.execute("SELECT quantity FROM cart WHERE user_id=? AND product_id=?", (user_id, pid))
    row = cursor.fetchone()
    if row and row[0] > 1:
        cursor.execute("UPDATE cart SET quantity = quantity - 1 WHERE user_id=? AND product_id=?", (user_id, pid))
    else:
        cursor.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (user_id, pid))
    conn.commit()
    await show_cart(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("remove_"))
async def remove_item(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    cursor.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (user_id, pid))
    conn.commit()
    await show_cart(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    cursor.execute("DELETE FROM cart WHERE user_id=?", (callback.from_user.id,))
    conn.commit()
    await callback.answer("Savatcha tozalandi!", show_alert=True)
    await callback.message.delete()

# ========== BUYURTMA ==========
@dp.callback_query(lambda c: c.data == "order_now")
async def order_now(callback: types.CallbackQuery, state: FSMContext):
    if is_blocked(callback.from_user.id):
        await callback.answer("Siz bloklangansiz!", show_alert=True)
        return
    user_id = callback.from_user.id
    cursor.execute("SELECT COUNT(*) FROM cart WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] == 0:
        await callback.answer("Savatcha bo'sh!", show_alert=True)
        return
    await callback.message.answer("🏠 Yetkazib berish manzilingizni yuboring:")
    await state.set_state(OrderAddress.address)

@dp.message(OrderAddress.address)
async def get_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await message.answer("⏰ Yetkazib berish vaqti (masalan: 19:00-20:00):")
    await state.set_state(OrderAddress.delivery_time)

@dp.message(OrderAddress.delivery_time)
async def get_delivery_time(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    address = data['address']
    delivery_time = message.text.strip()
    cursor.execute("""
        SELECT p.name, p.price, c.quantity 
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, (user_id,))
    items = cursor.fetchall()
    if not items:
        await message.answer("Savatcha bo'sh, buyurtma bekor qilindi.")
        await state.clear()
        return
    total = sum(price * qty for _, price, qty in items)
    products_text = ", ".join([f"{name} x{qty}" for name, _, qty in items])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO orders (user_id, products, total, status, address, delivery_time, date)
        VALUES (?, ?, ?, 'to‘lov_kutilmoqda', ?, ?, ?)
    """, (user_id, products_text, total, address, delivery_time, now))
    conn.commit()
    order_id = cursor.lastrowid
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()

    await message.answer(
        f"📦 Buyurtma #{order_id} qabul qilindi.\n"
        f"Manzil: {address}\nVaqt: {delivery_time}\nJami: {total} so'm\n\n"
        f"💳 To‘lov uchun: 8600 1234 5678 9012 (Humo/MyUzcard)\n"
        f"To‘lov qilganingizdan so‘ng tugmani bosing.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ To‘lov qildim", callback_data=f"paid_{order_id}")]
        ])
    )
    await bot.send_message(ADMIN_ID, f"🆕 Yangi buyurtma #{order_id}\nFoydalanuvchi: {user_id}\n{products_text}\nJami: {total}\nManzil: {address}\nVaqt: {delivery_time}")
    await send_to_channel(order_id, "new")
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def user_paid(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    cursor.execute("SELECT status FROM orders WHERE id=? AND user_id=?", (order_id, user_id))
    row = cursor.fetchone()
    if not row or row[0] != "to‘lov_kutilmoqda":
        await callback.answer("Xatolik", show_alert=True)
        return
    cursor.execute("SELECT products, total FROM orders WHERE id=?", (order_id,))
    prods, total = cursor.fetchone()
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_payment_{order_id}"),
         InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_payment_{order_id}")]
    ])
    await bot.send_message(ADMIN_ID, f"💳 To‘lov bildirildi #{order_id}\n{prods}\nJami: {total}", reply_markup=admin_kb)
    await callback.message.answer("To‘lov ma'lumotingiz adminga yuborildi.")
    await callback.answer()

# ========== ADMIN TASDIQLASH ==========
@dp.callback_query(lambda c: c.data.startswith("confirm_payment_"))
async def confirm_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[-1])
    cursor.execute("SELECT user_id, status FROM orders WHERE id=?", (order_id,))
    row = cursor.fetchone()
    if not row or row[1] != "to‘lov_kutilmoqda":
        await callback.answer("Xatolik")
        return
    user_id = row[0]
    cursor.execute("UPDATE orders SET status='qabul_qilingan' WHERE id=?", (order_id,))
    conn.commit()
    await send_to_user(user_id, f"✅ #{order_id} buyurtmangiz to‘lovi tasdiqlandi. Admin buyurtmani tayyorlaydi.")
    await send_to_channel(order_id, "paid")
    ready_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔧 Tayyor", callback_data=f"ready_{order_id}"),
         InlineKeyboardButton(text="🚚 Yetkazildi", callback_data=f"delivered_{order_id}")]
    ])
    await callback.message.edit_text(f"✅ Buyurtma #{order_id} to‘lovi tasdiqlandi.", reply_markup=ready_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("ready_"))
async def order_ready(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    cursor.execute("SELECT user_id, status FROM orders WHERE id=?", (order_id,))
    row = cursor.fetchone()
    if not row or row[1] != "qabul_qilingan":
        await callback.answer("Faqat tasdiqlangan buyurtmani tayyorlash mumkin")
        return
    user_id = row[0]
    await send_to_user(user_id, f"🍳 #{order_id} buyurtmangiz tayyorlanmoqda. Tez orada yetkaziladi.")
    await callback.message.edit_text(f"🟡 Buyurtma #{order_id} tayyor holatiga o‘tkazildi.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delivered_"))
async def order_delivered(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    cursor.execute("SELECT user_id, status FROM orders WHERE id=?", (order_id,))
    row = cursor.fetchone()
    if not row or (row[1] != "qabul_qilingan" and row[1] != "tayyor"):
        await callback.answer("Buyurtma yetkazib berish uchun tayyor emas")
        return
    user_id = row[0]
    cursor.execute("UPDATE orders SET status='yetkazilgan' WHERE id=?", (order_id,))
    conn.commit()
    await send_to_user(user_id, f"✅ Buyurtma #{order_id} yetkazildi. Rahmat!")
    await send_to_channel(order_id, "delivered")
    await callback.message.edit_text(f"✅ Buyurtma #{order_id} yetkazilgan deb belgilandi.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("reject_payment_"))
async def reject_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[-1])
    cursor.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
    row = cursor.fetchone()
    if row:
        user_id = row[0]
        cursor.execute("UPDATE orders SET status='bekor_qilingan' WHERE id=?", (order_id,))
        conn.commit()
        await send_to_user(user_id, f"❌ #{order_id} buyurtmangiz to‘lovi rad etildi.")
    await callback.message.edit_text(f"❌ Buyurtma #{order_id} rad etildi.")
    await callback.answer()

# ========== FOYDALANUVCHI BUYURTMA TARIXI ==========
@dp.message(lambda msg: msg.text == "📜 Mening buyurtmalarim")
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT id, products, total, status, date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
    orders = cursor.fetchall()
    if not orders:
        await message.answer("Siz hali buyurtma bermagansiz.")
        return
    text = "📜 *So‘nggi buyurtmalaringiz:*\n\n"
    for oid, prods, total, status, date in orders:
        text += f"#{oid} | {status}\n{prods}\nJami: {total} so'm\n{date}\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "📞 Aloqa")
async def contact(message: types.Message):
    await message.answer("📞 +998 90 123 45 67\n📍 Toshkent, Chilonzor")

# ========== ADMIN FUNKSIYALARI (qisqartirilgan, lekin to‘liq) ==========
@dp.message(lambda msg: msg.text == "📊 Statistika" and msg.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(total) FROM orders WHERE status='yetkazilgan'")
    revenue = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE blocked=0")
    active_users = cursor.fetchone()[0]
    await message.answer(f"📊 *Statistika*\nBuyurtmalar: {total_orders}\nDaromad: {revenue} so'm\nMahsulotlar: {total_products}\nAktiv foydalanuvchilar: {active_users}", parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "📋 Buyurtmalar" and msg.from_user.id == ADMIN_ID)
async def list_orders_admin(message: types.Message):
    cursor.execute("SELECT id, user_id, products, total, status, address, delivery_time, date FROM orders ORDER BY id DESC LIMIT 20")
    orders = cursor.fetchall()
    if not orders:
        await message.answer("Hech qanday buyurtma yo'q.")
        return
    text = "📋 Oxirgi 20 buyurtma:\n\n"
    for oid, uid, prods, total, status, addr, dtime, date in orders:
        text += f"#{oid} | {uid} | {status}\n{prods}\nJami: {total} so'm\nManzil: {addr}\nVaqt: {dtime}\n{date}\n\n"
    await message.answer(text)

# Mahsulot qo'shish, o'chirish, tahrirlash (oldingi kod bilan bir xil, qisqartirilgan)
@dp.message(lambda msg: msg.text == "➕ Mahsulot qo'shish" and msg.from_user.id == ADMIN_ID)
async def add_product_start(message: types.Message, state: FSMContext):
    await message.answer("Nomi:")
    await state.set_state(AddProduct.name)

@dp.message(AddProduct.name)
async def add_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer("Narxi (raqam):")
    await state.set_state(AddProduct.price)

@dp.message(AddProduct.price)
async def add_price(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("Raqam!")
        return
    await state.update_data(price=int(msg.text))
    await msg.answer("Kategoriya:")
    await state.set_state(AddProduct.category)

@dp.message(AddProduct.category)
async def add_cat(msg: types.Message, state: FSMContext):
    cat = msg.text.strip().lower()
    data = await state.get_data()
    try:
        cursor.execute("INSERT INTO products (name, price, category) VALUES (?, ?, ?)", (data['name'], data['price'], cat))
        conn.commit()
        await msg.answer(f"✅ {data['name']} qo'shildi!")
    except:
        await msg.answer("❌ Xatolik (nomi takrorlanishi mumkin)")
    await state.clear()

@dp.message(lambda msg: msg.text == "❌ O'chirish" and msg.from_user.id == ADMIN_ID)
async def delete_start(msg: types.Message, state: FSMContext):
    cursor.execute("SELECT id, name FROM products")
    prods = cursor.fetchall()
    if not prods:
        await msg.answer("Mahsulot yo'q.")
        return
    text = "ID:\n" + "\n".join([f"ID {pid}: {name}" for pid, name in prods])
    await msg.answer(text)
    await state.set_state(DeleteProduct.id)

@dp.message(DeleteProduct.id)
async def delete_id(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("ID raqam!")
        return
    pid = int(msg.text)
    cursor.execute("DELETE FROM products WHERE id=?", (pid,))
    if cursor.rowcount:
        conn.commit()
        await msg.answer(f"✅ ID {pid} o'chirildi.")
    else:
        await msg.answer("Topilmadi.")
    await state.clear()

@dp.message(lambda msg: msg.text == "✏️ Tahrirlash" and msg.from_user.id == ADMIN_ID)
async def edit_start(msg: types.Message, state: FSMContext):
    cursor.execute("SELECT id, name, price, category FROM products")
    prods = cursor.fetchall()
    if not prods:
        await msg.answer("Mahsulot yo'q.")
        return
    text = "ID:\n" + "\n".join([f"ID {pid}: {name} - {price} ({cat})" for pid, name, price, cat in prods])
    await msg.answer(text)
    await state.set_state(EditProduct.id)

@dp.message(EditProduct.id)
async def edit_field(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("ID raqam!")
        return
    pid = int(msg.text)
    cursor.execute("SELECT id FROM products WHERE id=?", (pid,))
    if not cursor.fetchone():
        await msg.answer("Topilmadi.")
        await state.clear()
        return
    await state.update_data(id=pid)
    await msg.answer("Nimani o'zgartirish? name / price / category")
    await state.set_state(EditProduct.field)

@dp.message(EditProduct.field)
async def edit_value(msg: types.Message, state: FSMContext):
    field = msg.text.lower()
    if field not in ['name', 'price', 'category']:
        await msg.answer("Faqat name, price, category")
        return
    await state.update_data(field=field)
    await msg.answer(f"Yangi {field}:")
    await state.set_state(EditProduct.value)

@dp.message(EditProduct.value)
async def edit_save(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    pid = data['id']
    field = data['field']
    new_val = msg.text.strip()
    if field == 'price':
        if not new_val.isdigit():
            await msg.answer("Raqam!")
            return
        new_val = int(new_val)
    try:
        cursor.execute(f"UPDATE products SET {field}=? WHERE id=?", (new_val, pid))
        conn.commit()
        await msg.answer("✅ O'zgartirildi!")
    except:
        await msg.answer("❌ Xatolik")
    await state.clear()

@dp.message(lambda msg: msg.text == "📦 Mahsulotlar" and msg.from_user.id == ADMIN_ID)
async def list_products(msg: types.Message):
    cursor.execute("SELECT id, name, price, category FROM products")
    prods = cursor.fetchall()
    if not prods:
        await msg.answer("Mahsulot yo'q.")
        return
    text = "📦 Mahsulotlar:\n" + "\n".join([f"ID {pid}: {name} - {price} ({cat})" for pid, name, price, cat in prods])
    await msg.answer(text)

@dp.message(lambda msg: msg.text == "💰 To'lovni tasdiqlash" and msg.from_user.id == ADMIN_ID)
async def payment_help(msg: types.Message):
    await msg.answer("To'lov haqida xabar kelganda tugmalar chiqadi.")

@dp.message(lambda msg: msg.text == "🚫 Bloklash/Unblock" and msg.from_user.id == ADMIN_ID)
async def block_menu(msg: types.Message):
    await msg.answer("/block USER_ID\n/unblock USER_ID")

@dp.message(Command("block"))
async def block_user(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    parts = msg.text.split()
    if len(parts)!=2 or not parts[1].isdigit():
        await msg.answer("/block ID")
        return
    uid = int(parts[1])
    cursor.execute("UPDATE users SET blocked=1 WHERE user_id=?", (uid,))
    conn.commit()
    await msg.answer(f"✅ Bloklandi {uid}")

@dp.message(Command("unblock"))
async def unblock_user(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    parts = msg.text.split()
    if len(parts)!=2 or not parts[1].isdigit():
        await msg.answer("/unblock ID")
        return
    uid = int(parts[1])
    cursor.execute("UPDATE users SET blocked=0 WHERE user_id=?", (uid,))
    conn.commit()
    await msg.answer(f"✅ Unblock {uid}")

@dp.message(lambda msg: msg.text == "📢 Reklama yuborish" and msg.from_user.id == ADMIN_ID)
async def broadcast_start(msg: types.Message, state: FSMContext):
    await msg.answer("Reklama matnini yuboring:")
    await state.set_state(Broadcast.message)

@dp.message(Broadcast.message)
async def broadcast_send(msg: types.Message, state: FSMContext):
    text = msg.text
    cursor.execute("SELECT user_id FROM users WHERE blocked=0")
    users = cursor.fetchall()
    success = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, f"📢 *Reklama*\n{text}", parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await msg.answer(f"✅ {success} ta foydalanuvchiga yuborildi.")
    await state.clear()

@dp.message(lambda msg: msg.text == "📎 Excel yuklab olish" and msg.from_user.id == ADMIN_ID)
async def export_excel(msg: types.Message):
    cursor.execute("SELECT id, user_id, products, total, status, address, delivery_time, date FROM orders ORDER BY id DESC")
    orders = cursor.fetchall()
    if not orders:
        await msg.answer("Buyurtma yo'q.")
        return
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "User ID", "Mahsulotlar", "Jami", "Holat", "Manzil", "Yetkazish vaqti", "Sana"])
    writer.writerows(orders)
    output.seek(0)
    with open("buyurtmalar.csv", "w", encoding="utf-8") as f:
        f.write(output.getvalue())
    await msg.answer_document(FSInputFile("buyurtmalar.csv"), caption="📎 Buyurtmalar")
    import os
    os.remove("buyurtmalar.csv")

@dp.message(lambda msg: msg.text == "📦 Buyurtma berish")
async def quick_order(msg: types.Message):
    await show_cart(msg)

# ========== ISHGA TUSHIRISH ==========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
