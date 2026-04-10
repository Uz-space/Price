import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== SOZLAMALAR ==========
BOT_TOKEN = "8627453491:AAFEpPXTg-uT_wLCQ--8--7XkQPYoj_ZXuE"
ADMIN_ID = 7399101034 
CHANNEL_ID = "@AlphaHookahOrders"

# ========== BAZA ==========
DB_PATH = "hookah_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                price INTEGER,
                category TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                PRIMARY KEY (user_id, product_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                products TEXT,
                total INTEGER,
                status TEXT,
                table_number TEXT,
                date TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_messages (
                order_id INTEGER PRIMARY KEY,
                message_id INTEGER
            )
        """)
        await db.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== FSM ==========
class AddProduct(StatesGroup):
    name = State()
    price = State()
    category = State()

class DeleteProduct(StatesGroup):
    pid = State()

class OrderTable(StatesGroup):
    table_number = State()

# ========== TUGMALAR ==========
user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍽 Menyu"), KeyboardButton(text="🛒 Savatcha")],
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="📜 Mening buyurtmalarim")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Mahsulot qo'shish"), KeyboardButton(text="❌ Mahsulot o'chirish")],
        [KeyboardButton(text="📋 Buyurtmalar"), KeyboardButton(text="📊 Statistika")]
    ],
    resize_keyboard=True
)

# ========== KANAL XABARI ==========
async def update_channel_message(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT o.user_id, o.products, o.total, o.table_number, o.date, o.status, u.first_name 
            FROM orders o LEFT JOIN users u ON o.user_id = u.user_id WHERE o.id = ?
        """, (order_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return
        user_id, products, total, table, date, status, first_name = row
        user_name = first_name or str(user_id)
        date_f = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        
        if status == "toʻlov_kutilmoqda":
            title = "🆕 YANGI BUYURTMA"
            status_text = "⏳ Toʻlov kutilmoqda"
        elif status == "qabul_qilingan":
            title = "💰 TOʻLOV TASDIQLANDI"
            status_text = "✅ Tasdiqlangan"
        elif status == "yetkazilgan":
            title = "✅ BUYURTMA YETKAZILDI"
            status_text = "🚚 Yetkazildi"
        elif status == "bekor_qilingan":
            title = "❌ BUYURTMA BEKOR QILINDI"
            status_text = "❌ Bekor qilingan"
        else:
            title = "📦 BUYURTMA"
            status_text = status
        
        text = f"<b>{title}</b>\n━━━━━━━━━━━━━━━━━━━━\n🆔 #{order_id}\n👤 {user_name}\n🪑 {table}-stol\n📦 {products}\n💰 {total:,} so'm\n━━━━━━━━━━━━━━━━━━━━\n{status_text}\n📝 {date_f}"
        
        async with db.execute("SELECT message_id FROM channel_messages WHERE order_id=?", (order_id,)) as cur:
            msg_row = await cur.fetchone()
        
        try:
            if msg_row:
                await bot.edit_message_text(chat_id=CHANNEL_ID, message_id=msg_row[0], text=text, parse_mode="HTML")
            else:
                sent = await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
                await db.execute("INSERT INTO channel_messages (order_id, message_id) VALUES (?, ?)", (order_id, sent.message_id))
                await db.commit()
        except Exception as e:
            print(f"Kanal xatosi: {e}")

# ========== START ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or ""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (user_id, first_name))
        await db.commit()
    if user_id == ADMIN_ID:
        await message.answer("👑 Admin panel", reply_markup=admin_menu)
    else:
        await message.answer("🍃 AlphaHookah bar botiga xush kelibsiz!", reply_markup=user_menu)

# ========== MENYU ==========
@dp.message(lambda msg: msg.text == "🍽 Menyu")
async def show_menu(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products") as cur:
            cats = await cur.fetchall()
    if not cats:
        await message.answer("❌ Hozircha mahsulot yo‘q.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📁 {cat[0].upper()}", callback_data=f"cat_{cat[0]}")] for cat in cats])
    await message.answer("📋 Kategoriyani tanlang:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat = callback.data.split("_")[1]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price FROM products WHERE category=?", (cat,)) as cur:
            prods = await cur.fetchall()
    if not prods:
        await callback.answer("Bu kategoriyada mahsulot yo'q")
        return
    text = f"📋 <b>{cat.upper()}</b>\n\n" + "\n".join([f"🍃 {name} — {price:,} so'm" for _, name, price in prods])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"➕ {name}", callback_data=f"add_{pid}")] for pid, name, _ in prods] + [[InlineKeyboardButton(text="◀️ Ortga", callback_data="back_cat")]])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_cat")
async def back_cat(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products") as cur:
            cats = await cur.fetchall()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📁 {cat[0].upper()}", callback_data=f"cat_{cat[0]}")] for cat in cats])
    await callback.message.edit_text("📋 Kategoriyani tanlang:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO cart (user_id, product_id, quantity) 
            VALUES (?, ?, 1) 
            ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1
        """, (user_id, pid))
        await db.commit()
    await callback.answer("✅ Savatchaga qo'shildi!", show_alert=True)

# ========== SAVATCHA (TO'LIQ TUZATILGAN) ==========
async def get_cart_html(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, p.name, p.price, c.quantity 
            FROM cart c JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ?
        """, (user_id,)) as cur:
            items = await cur.fetchall()
    
    if not items:
        return None, None
    
    total = 0
    text = "🛍 <b>Savatchangiz</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for pid, name, price, qty in items:
        subtotal = price * qty
        total += subtotal
        text += f"• {name} x{qty} = {subtotal:,} so'm\n"
    
    text += f"━━━━━━━━━━━━━━━━━━━━\n💰 <b>Jami: {total:,} so'm</b>"
    return text, items

@dp.message(lambda msg: msg.text == "🛒 Savatcha")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    text, items = await get_cart_html(user_id)
    
    if not items:
        await message.answer("🛒 Savatcha bo'sh.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pid, name, price, qty in items:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="➖", callback_data=f"dec_{pid}"),
            InlineKeyboardButton(text=f"{qty}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{pid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_{pid}")
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear")])
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("inc_"))
async def inc_cart(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE cart SET quantity = quantity + 1 WHERE user_id=? AND product_id=?", (user_id, pid))
        await db.commit()
    await refresh_cart_message(callback)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("dec_"))
async def dec_cart(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT quantity FROM cart WHERE user_id=? AND product_id=?", (user_id, pid)) as cur:
            row = await cur.fetchone()
        if row and row[0] > 1:
            await db.execute("UPDATE cart SET quantity = quantity - 1 WHERE user_id=? AND product_id=?", (user_id, pid))
        else:
            await db.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (user_id, pid))
        await db.commit()
    await refresh_cart_message(callback)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("del_"))
async def del_cart_item(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (user_id, pid))
        await db.commit()
    await refresh_cart_message(callback)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "clear")
async def clear_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        await db.commit()
    await callback.answer("🗑 Savatcha tozalandi!", show_alert=True)
    await refresh_cart_message(callback)

async def refresh_cart_message(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    text, items = await get_cart_html(user_id)
    
    if not items:
        await callback.message.edit_text("🛒 Savatcha bo'sh.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pid, name, price, qty in items:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="➖", callback_data=f"dec_{pid}"),
            InlineKeyboardButton(text=f"{qty}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{pid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_{pid}")
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear")])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

# ========== BUYURTMA ==========
@dp.callback_query(lambda c: c.data == "order")
async def order_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM cart WHERE user_id=?", (user_id,)) as cur:
            count = (await cur.fetchone())[0]
    if count == 0:
        await callback.answer("Savatcha bo'sh!", show_alert=True)
        return
    await callback.message.answer("🪑 Stol raqamingizni yozing (masalan: 15):")
    await state.set_state(OrderTable.table_number)
    await callback.answer()

@dp.message(OrderTable.table_number)
async def get_table_number(message: types.Message, state: FSMContext):
    table_number = message.text.strip()
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.name, p.price, c.quantity 
            FROM cart c JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ?
        """, (user_id,)) as cur:
            items = await cur.fetchall()
    
    if not items:
        await message.answer("Savatcha bo'sh. Buyurtma bekor qilindi.")
        await state.clear()
        return
    
    total = sum(price * qty for _, price, qty in items)
    products_text = ", ".join([f"{name} x{qty}" for name, _, qty in items])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO orders (user_id, products, total, status, table_number, date) 
            VALUES (?, ?, ?, 'toʻlov_kutilmoqda', ?, ?)
        """, (user_id, products_text, total, table_number, now))
        await db.commit()
        order_id = cur.lastrowid
        await db.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        await db.commit()
    
    await update_channel_message(order_id)
    
    await bot.send_message(ADMIN_ID, f"🆕 Yangi buyurtma #{order_id}\n👤 ID: {user_id}\n🪑 Stol: {table_number}\n📦 {products_text}\n💰 {total:,} so'm")
    
    await message.answer(
        f"✅ <b>Buyurtma #{order_id} qabul qilindi!</b>\n\n"
        f"🪑 Stol: {table_number}\n"
        f"💰 Jami: {total:,} so'm\n\n"
        f"💳 <b>To‘lov uchun:</b>\n"
        f"🏦 8600 1234 5678 9012\n\n"
        f"To‘lov qilgach tugmani bosing.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ To‘lov qildim", callback_data=f"paid_{order_id}")]
        ])
    )
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def user_paid(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT products, total, status FROM orders WHERE id=? AND user_id=?", (order_id, user_id)) as cur:
            row = await cur.fetchone()
        if not row or row[2] != "toʻlov_kutilmoqda":
            await callback.answer("Xatolik!", show_alert=True)
            return
        prods, total = row[0], row[1]
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_{order_id}"),
         InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{order_id}")]
    ])
    
    await bot.send_message(ADMIN_ID, f"💳 To‘lov bildirildi #{order_id}\n👤 {user_id}\n📦 {prods}\n💰 {total:,} so'm", reply_markup=admin_kb)
    await callback.message.answer("✅ To‘lov ma'lumotingiz adminga yuborildi.")
    await callback.answer()

# ========== ADMIN ==========
@dp.callback_query(lambda c: c.data.startswith("confirm_"))
async def confirm_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM orders WHERE id=? AND status='toʻlov_kutilmoqda'", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Xatolik!")
            return
        user_id = row[0]
        await db.execute("UPDATE orders SET status='qabul_qilingan' WHERE id=?", (order_id,))
        await db.commit()
    
    await update_channel_message(order_id)
    await bot.send_message(user_id, f"✅ #{order_id} buyurtmangiz to‘lovi tasdiqlandi.")
    
    deliver_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚚 Yetkazildi", callback_data=f"deliver_{order_id}")]
    ])
    await callback.message.edit_text(f"✅ Buyurtma #{order_id} tasdiqlandi.", reply_markup=deliver_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
        if row:
            await db.execute("UPDATE orders SET status='bekor_qilingan' WHERE id=?", (order_id,))
            await db.commit()
            await update_channel_message(order_id)
            await bot.send_message(row[0], f"❌ #{order_id} buyurtmangiz to‘lovi rad etildi.")
    
    await callback.message.edit_text(f"❌ Buyurtma #{order_id} rad etildi.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("deliver_"))
async def deliver_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM orders WHERE id=? AND status='qabul_qilingan'", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Buyurtma yetkazib berishga tayyor emas!")
            return
        user_id = row[0]
        await db.execute("UPDATE orders SET status='yetkazilgan' WHERE id=?", (order_id,))
        await db.commit()
    
    await update_channel_message(order_id)
    await bot.send_message(user_id, f"✅ #{order_id} buyurtmangiz yetkazildi. Rahmat!")
    await callback.message.edit_text(f"✅ Buyurtma #{order_id} yetkazildi.")
    await callback.answer()

# ========== BUYURTMA TARIXI ==========
@dp.message(lambda msg: msg.text == "📜 Mening buyurtmalarim")
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, products, total, status, table_number, date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,)) as cur:
            orders = await cur.fetchall()
    if not orders:
        await message.answer("📭 Siz hali buyurtma bermagansiz.")
        return
    status_emoji = {"toʻlov_kutilmoqda": "⏳", "qabul_qilingan": "✅", "yetkazilgan": "🚚", "bekor_qilingan": "❌"}
    text = "📜 <b>So‘nggi buyurtmalaringiz</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for oid, prods, total, status, table, date in orders:
        date_f = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
        text += f"\n#{oid} | {status_emoji.get(status, '📦')} {status}\n🪑 {table}-stol | {date_f}\n{prods}\n💰 {total:,} so'm\n"
    await message.answer(text, parse_mode="HTML")

# ========== ADMIN MAHSULOT BOSHQARISH ==========
@dp.message(lambda msg: msg.text == "➕ Mahsulot qo'shish" and msg.from_user.id == ADMIN_ID)
async def add_start(message: types.Message, state: FSMContext):
    await message.answer("📦 Mahsulot nomi:")
    await state.set_state(AddProduct.name)

@dp.message(AddProduct.name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("💰 Narxi (faqat raqam):")
    await state.set_state(AddProduct.price)

@dp.message(AddProduct.price)
async def add_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam!")
        return
    await state.update_data(price=int(message.text))
    await message.answer("📁 Kategoriya (nargile/aroma/ichimlik):")
    await state.set_state(AddProduct.category)

@dp.message(AddProduct.category)
async def add_category(message: types.Message, state: FSMContext):
    cat = message.text.strip().lower()
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO products (name, price, category) VALUES (?, ?, ?)", (data['name'], data['price'], cat))
            await db.commit()
            await message.answer(f"✅ {data['name']} qo'shildi!")
        except:
            await message.answer("❌ Bunday nom bor.")
    await state.clear()

@dp.message(lambda msg: msg.text == "❌ Mahsulot o'chirish" and msg.from_user.id == ADMIN_ID)
async def delete_start(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM products") as cur:
            prods = await cur.fetchall()
    if not prods:
        await message.answer("Mahsulot yo'q.")
        return
    text = "🗑 O'chirish uchun ID:\n\n" + "\n".join([f"ID {pid}: {name}" for pid, name in prods])
    await message.answer(text)
    await state.set_state(DeleteProduct.pid)

@dp.message(DeleteProduct.pid)
async def delete_pid(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID raqam!")
        return
    pid = int(message.text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id=?", (pid,))
        if db.total_changes:
            await db.commit()
            await message.answer(f"✅ ID {pid} o'chirildi.")
        else:
            await message.answer("❌ Topilmadi.")
    await state.clear()

@dp.message(lambda msg: msg.text == "📋 Buyurtmalar" and msg.from_user.id == ADMIN_ID)
async def list_orders(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, user_id, products, total, status, table_number, date FROM orders ORDER BY id DESC LIMIT 20") as cur:
            orders = await cur.fetchall()
    if not orders:
        await message.answer("📭 Buyurtmalar yo'q.")
        return
    text = "📋 Oxirgi 20 buyurtma\n━━━━━━━━━━━━━━━━━━━━\n"
    for oid, uid, prods, total, status, table, date in orders:
        date_f = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        text += f"\n#{oid} | {status}\n👤 {uid} | 🪑 {table}\n📦 {prods}\n💰 {total:,} so'm\n📅 {date_f}\n"
    await message.answer(text)

@dp.message(lambda msg: msg.text == "📊 Statistika" and msg.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total_orders = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(total) FROM orders WHERE status='yetkazilgan'") as cur:
            revenue = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM products") as cur:
            total_products = (await cur.fetchone())[0]
    await message.answer(f"📊 Statistika\n━━━━━━━━━━━━━━━━━━━━\n📦 Buyurtmalar: {total_orders}\n💰 Daromad: {revenue:,} so'm\n🍽 Mahsulotlar: {total_products}")

@dp.message(lambda msg: msg.text == "📦 Buyurtma berish")
async def quick_order(message: types.Message):
    await show_cart(message)

@dp.callback_query(lambda c: c.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()

# ========== ISHGA TUSHIRISH ==========
async def main():
    await init_db()
    print("🤖 AlphaHookah bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
