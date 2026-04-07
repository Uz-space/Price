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
CHANNEL_ID = "@AlphaHookahOrders"  # Kanal username yoki ID

# ========== BAZA ==========
DB_PATH = "hookah_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, price INTEGER, category TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS cart (user_id INTEGER, product_id INTEGER, quantity INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, products TEXT, total INTEGER, status TEXT, table_number TEXT, date TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT)")
        await db.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM
class AddProduct(StatesGroup):
    name = State()
    price = State()
    category = State()

class DeleteProduct(StatesGroup):
    pid = State()

class OrderTable(StatesGroup):
    table_number = State()

# Tugmalar
user_menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🍽 Menyu"), KeyboardButton(text="🛒 Savatcha")], [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="📜 Mening buyurtmalarim")]], resize_keyboard=True)
admin_menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="➕ Mahsulot qo'shish"), KeyboardButton(text="❌ Mahsulot o'chirish")], [KeyboardButton(text="📋 Buyurtmalar"), KeyboardButton(text="📊 Statistika")]], resize_keyboard=True)

# Kanalga xabar yuborish
async def send_to_channel(order_id, event_type):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT o.user_id, o.products, o.total, o.table_number, o.date, u.first_name FROM orders o LEFT JOIN users u ON o.user_id = u.user_id WHERE o.id=?", (order_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return
    user_id, products, total, table, date, first_name = row
    user_name = first_name or str(user_id)
    date_f = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    
    if event_type == "new":
        title = "🍃 Yangi buyurtma"
        status_icon = "⏳ To‘lov kutilmoqda"
    elif event_type == "paid":
        title = "🍃 To‘lov tasdiqlandi"
        status_icon = "✅ Tasdiqlangan"
    elif event_type == "delivered":
        title = "🍃 Buyurtma yetkazildi"
        status_icon = "🚚 Yetkazildi"
    else:
        return
    
    text = f"<b>{title}</b>\n🆔: #{order_id}\n👤: {user_name}\n📦: {products}\n💰: {total} so'm\n🪑: {table}\n🔎 Holat: {status_icon}\n📝: {date_f}"
    try:
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    except:
        pass

# ========== START ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or ""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (user_id, first_name))
        await db.commit()
    await message.answer("🍃 AlphaHookah bar botiga xush kelibsiz!", reply_markup=admin_menu if user_id == ADMIN_ID else user_menu)

# ========== MENYU ==========
@dp.message(lambda msg: msg.text == "🍽 Menyu")
async def show_menu(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products") as cur:
            cats = await cur.fetchall()
    if not cats:
        await message.answer("❌ Mahsulot yo‘q.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📂 {cat[0].upper()}", callback_data=f"cat_{cat[0]}")] for cat in cats])
    await message.answer("Kategoriya tanlang:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat = callback.data.split("_")[1]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price FROM products WHERE category=?", (cat,)) as cur:
            prods = await cur.fetchall()
    if not prods:
        await callback.answer("Mahsulot yo'q")
        return
    text = f"📋 *{cat.upper()}*:\n" + "\n".join([f"• {name} - {price} so'm" for _, name, price in prods])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"➕ {name}", callback_data=f"add_{pid}")] for pid, name, _ in prods] + [[InlineKeyboardButton(text="🔙 Ortga", callback_data="back_cat")]])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_cat")
async def back_cat(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products") as cur:
            cats = await cur.fetchall()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📂 {cat[0].upper()}", callback_data=f"cat_{cat[0]}")] for cat in cats])
    await callback.message.edit_text("Kategoriya tanlang:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1) ON CONFLICT DO UPDATE SET quantity = quantity + 1", (user_id, pid))
        await db.commit()
    await callback.answer("✅ Qo'shildi!", show_alert=True)

# ========== SAVATCHA ==========
@dp.message(lambda msg: msg.text == "🛒 Savatcha")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT p.id, p.name, p.price, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (user_id,)) as cur:
            items = await cur.fetchall()
    if not items:
        await message.answer("🛒 Savatcha bo'sh.")
        return
    text = "🛍 *Savatcha:*\n" + "\n".join([f"{name} x{qty} = {price*qty} so'm" for _, name, price, qty in items])
    total = sum(price*qty for _, _, price, qty in items)
    text += f"\n*Jami: {total} so'm*"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order_now")], [InlineKeyboardButton(text="🗑 Tozalash", callback_data="clear_cart")]])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id=?", (callback.from_user.id,))
        await db.commit()
    await callback.answer("Savatcha tozalandi!", show_alert=True)
    await callback.message.delete()

# ========== BUYURTMA (faqat stol raqami) ==========
@dp.callback_query(lambda c: c.data == "order_now")
async def order_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM cart WHERE user_id=?", (user_id,)) as cur:
            count = (await cur.fetchone())[0]
    if count == 0:
        await callback.answer("Savatcha bo'sh!", show_alert=True)
        return
    await callback.message.answer("🪑 Iltimos, stol raqamingizni yozing (masalan: 15 yoki 15-stol):")
    await state.set_state(OrderTable.table_number)
    await callback.answer()

@dp.message(OrderTable.table_number)
async def get_table_number(message: types.Message, state: FSMContext):
    table_number = message.text.strip()
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT p.name, p.price, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (user_id,)) as cur:
            items = await cur.fetchall()
    
    if not items:
        await message.answer("Savatcha bo'sh. Buyurtma bekor qilindi.")
        await state.clear()
        return
    
    total = sum(price * qty for _, price, qty in items)
    products_text = ", ".join([f"{name} x{qty}" for name, _, qty in items])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO orders (user_id, products, total, status, table_number, date) VALUES (?, ?, ?, 'toʻlov_kutilmoqda', ?, ?)", (user_id, products_text, total, table_number, now))
        await db.commit()
        order_id = cur.lastrowid
        await db.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        await db.commit()
    
    await message.answer(f"📦 Buyurtma #{order_id} qabul qilindi.\n🪑 Stol: {table_number}\n💰 Jami: {total} so'm\n\n💳 To‘lov: 8600 1234 5678 9012\nTo‘lov qilgach tugmani bosing.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ To‘lov qildim", callback_data=f"paid_{order_id}")]]))
    
    # Kanalga xabar
    await send_to_channel(order_id, "new")
    
    # Adminga xabar
    await bot.send_message(ADMIN_ID, f"🆕 Yangi buyurtma #{order_id}\n👤: {user_id}\n🪑: {table_number}\n📦: {products_text}\n💰: {total} so'm")
    
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def user_paid(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT products, total FROM orders WHERE id=? AND user_id=? AND status='toʻlov_kutilmoqda'", (order_id, user_id)) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Xatolik!", show_alert=True)
            return
    
    await bot.send_message(ADMIN_ID, f"💳 To‘lov bildirildi #{order_id}\n📦: {row[0]}\n💰: {row[1]} so'm", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_{order_id}"), InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{order_id}")]]))
    await callback.message.answer("✅ To‘lov ma'lumotingiz adminga yuborildi.")
    await callback.answer()

# ========== ADMIN: TASDIQLASH VA YETKAZISH ==========
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
    
    await bot.send_message(user_id, f"✅ #{order_id} buyurtmangiz to‘lovi tasdiqlandi. Tayyorlanmoqda.")
    await send_to_channel(order_id, "paid")
    
    await callback.message.edit_text(f"✅ Buyurtma #{order_id} tasdiqlandi.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚚 Yetkazildi", callback_data=f"deliver_{order_id}")]]))
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
    
    await bot.send_message(user_id, f"✅ #{order_id} buyurtmangiz yetkazildi. Rahmat!")
    await send_to_channel(order_id, "delivered")
    
    await callback.message.edit_text(f"✅ Buyurtma #{order_id} yetkazildi.")
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
            user_id = row[0]
            await db.execute("UPDATE orders SET status='bekor_qilingan' WHERE id=?", (order_id,))
            await db.commit()
            await bot.send_message(user_id, f"❌ #{order_id} buyurtmangiz to‘lovi rad etildi.")
    
    await callback.message.edit_text(f"❌ Buyurtma #{order_id} rad etildi.")
    await callback.answer()

# ========== FOYDALANUVCHI: BUYURTMA TARIXI ==========
@dp.message(lambda msg: msg.text == "📜 Mening buyurtmalarim")
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, products, total, status, table_number, date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,)) as cur:
            orders = await cur.fetchall()
    if not orders:
        await message.answer("Siz hali buyurtma bermagansiz.")
        return
    text = "📜 *So‘nggi buyurtmalaringiz:*\n\n"
    for oid, prods, total, status, table, date in orders:
        text += f"#{oid} | {status} | Stol: {table}\n{prods}\nJami: {total} so'm\n{date}\n\n"
    await message.answer(text, parse_mode="Markdown")

# ========== ADMIN: MAHSULOT BOSHQARISH ==========
@dp.message(lambda msg: msg.text == "➕ Mahsulot qo'shish" and msg.from_user.id == ADMIN_ID)
async def add_start(message: types.Message, state: FSMContext):
    await message.answer("Mahsulot nomini yuboring:")
    await state.set_state(AddProduct.name)

@dp.message(AddProduct.name)
async def add_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer("Narxi (faqat raqam):")
    await state.set_state(AddProduct.price)

@dp.message(AddProduct.price)
async def add_price(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("Raqam yuboring!")
        return
    await state.update_data(price=int(msg.text))
    await msg.answer("Kategoriyasi (nargile/aroma/ichimlik):")
    await state.set_state(AddProduct.category)

@dp.message(AddProduct.category)
async def add_category(msg: types.Message, state: FSMContext):
    cat = msg.text.strip().lower()
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO products (name, price, category) VALUES (?, ?, ?)", (data['name'], data['price'], cat))
            await db.commit()
            await msg.answer(f"✅ {data['name']} qo'shildi!")
        except:
            await msg.answer("❌ Bunday nomli mahsulot bor.")
    await state.clear()

@dp.message(lambda msg: msg.text == "❌ Mahsulot o'chirish" and msg.from_user.id == ADMIN_ID)
async def delete_start(msg: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM products") as cur:
            prods = await cur.fetchall()
    if not prods:
        await msg.answer("Mahsulot yo'q.")
        return
    text = "O'chirish uchun ID:\n" + "\n".join([f"ID {pid}: {name}" for pid, name in prods])
    await msg.answer(text)
    await state.set_state(DeleteProduct.pid)

@dp.message(DeleteProduct.pid)
async def delete_pid(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("ID raqam bo'lishi kerak.")
        return
    pid = int(msg.text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id=?", (pid,))
        if db.total_changes:
            await db.commit()
            await msg.answer(f"✅ ID {pid} o'chirildi.")
        else:
            await msg.answer("Topilmadi.")
    await state.clear()

@dp.message(lambda msg: msg.text == "📋 Buyurtmalar" and msg.from_user.id == ADMIN_ID)
async def list_orders(msg: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, user_id, products, total, status, table_number, date FROM orders ORDER BY id DESC LIMIT 20") as cur:
            orders = await cur.fetchall()
    if not orders:
        await msg.answer("Buyurtmalar yo'q.")
        return
    text = "📋 Oxirgi 20 buyurtma:\n\n"
    for oid, uid, prods, total, status, table, date in orders:
        text += f"#{oid} | {uid} | {status} | Stol: {table}\n{prods}\nJami: {total} so'm\n{date}\n\n"
    await msg.answer(text)

@dp.message(lambda msg: msg.text == "📊 Statistika" and msg.from_user.id == ADMIN_ID)
async def stats(msg: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total_orders = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(total) FROM orders WHERE status='yetkazilgan'") as cur:
            revenue = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM products") as cur:
            total_products = (await cur.fetchone())[0]
    await msg.answer(f"📊 *Statistika*\nBuyurtmalar: {total_orders}\nDaromad: {revenue} so'm\nMahsulotlar: {total_products}", parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "📦 Buyurtma berish")
async def quick_order(msg: types.Message):
    await show_cart(msg)

# ========== ISHGA TUSHIRISH ==========
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
