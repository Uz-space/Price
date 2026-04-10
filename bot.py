import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "8627453491:AAFEpPXTg-uT_wLCQ--8--7XkQPYoj_ZXuE"
ADMIN_ID = 7399101034 

DB_PATH = "hookah_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, category TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS cart (user_id INTEGER, product_id INTEGER, quantity INTEGER, PRIMARY KEY(user_id, product_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, products TEXT, total INTEGER, status TEXT, table_number TEXT, date TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT)")
        await db.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📋 Menyu"), KeyboardButton(text="🛒 Savatcha")], [KeyboardButton(text="📦 Buyurtma"), KeyboardButton(text="📜 Tarix")]], resize_keyboard=True)
admin_menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="➕ Mahsulot"), KeyboardButton(text="❌ O'chirish")], [KeyboardButton(text="📋 Buyurtmalar"), KeyboardButton(text="📊 Statistika")]], resize_keyboard=True)

class AddProduct(StatesGroup):
    name = State()
    price = State()
    category = State()

class DeleteProduct(StatesGroup):
    pid = State()

class OrderTable(StatesGroup):
    table = State()

@dp.message(Command("start"))
async def start(msg: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (msg.from_user.id, msg.from_user.first_name))
        await db.commit()
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("👑 Admin panel", reply_markup=admin_menu)
    else:
        await msg.answer("🍃 AlphaHookah bar botiga xush kelibsiz!", reply_markup=user_menu)

# ========== MENYU ==========
@dp.message(lambda m: m.text == "📋 Menyu")
async def menu(msg: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products") as cur:
            cats = await cur.fetchall()
    if not cats:
        await msg.answer("❌ Mahsulot yo'q. Admin qo'shsin.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📁 {c[0]}", callback_data=f"cat_{c[0]}")] for c in cats])
    await msg.answer("📋 Kategoriya tanlang:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products(call: types.CallbackQuery):
    cat = call.data.split("_")[1]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price FROM products WHERE category=?", (cat,)) as cur:
            prods = await cur.fetchall()
    text = f"📁 {cat.upper()}\n━━━━━━━━━━━━━━\n"
    for p in prods:
        text += f"🍃 {p[1]} — {p[2]:,} so'm\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"➕ {p[1]}", callback_data=f"add_{p[0]}")] for p in prods] + [[InlineKeyboardButton(text="◀️ Ortga", callback_data="back_menu")]])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

@dp.callback_query(lambda c: c.data == "back_menu")
async def back_menu(call: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products") as cur:
            cats = await cur.fetchall()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📁 {c[0]}", callback_data=f"cat_{c[0]}")] for c in cats])
    await call.message.edit_text("📋 Kategoriya tanlang:", reply_markup=kb)
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(call: types.CallbackQuery):
    pid = int(call.data.split("_")[1])
    uid = call.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1", (uid, pid))
        await db.commit()
    await call.answer("✅ Savatchaga qo'shildi!", show_alert=True)

# ========== SAVATCHA ==========
@dp.message(lambda m: m.text == "🛒 Savatcha")
async def show_cart(msg: types.Message):
    uid = msg.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT p.id, p.name, p.price, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (uid,)) as cur:
            items = await cur.fetchall()
    if not items:
        await msg.answer("🛒 Savatcha bo'sh")
        return
    total = 0
    text = "🛍 SAVATCHA\n━━━━━━━━━━━━━━\n"
    for it in items:
        total += it[2] * it[3]
        text += f"{it[1]} x{it[3]} = {it[2] * it[3]:,} so'm\n"
    text += f"━━━━━━━━━━━━━━\n💰 Jami: {total:,} so'm"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order_start")], [InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")]])
    await msg.answer(text, reply_markup=kb)

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(call: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id=?", (call.from_user.id,))
        await db.commit()
    await call.answer("🗑 Savatcha tozalandi!", show_alert=True)
    await call.message.delete()

@dp.callback_query(lambda c: c.data == "order_start")
async def order_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("🪑 Stol raqamingizni yozing (masalan: 15):")
    await state.set_state(OrderTable.table)
    await call.answer()

@dp.message(OrderTable.table)
async def order_table(msg: types.Message, state: FSMContext):
    table = msg.text.strip()
    uid = msg.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT p.name, p.price, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (uid,)) as cur:
            items = await cur.fetchall()
    if not items:
        await msg.answer("Savatcha bo'sh")
        await state.clear()
        return
    total = sum(i[1] * i[2] for i in items)
    prods = ", ".join([f"{i[0]} x{i[2]}" for i in items])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO orders (user_id, products, total, status, table_number, date) VALUES (?, ?, ?, 'kutilmoqda', ?, ?)", (uid, prods, total, table, now))
        await db.commit()
        oid = cur.lastrowid
        await db.execute("DELETE FROM cart WHERE user_id=?", (uid,))
        await db.commit()
    await bot.send_message(ADMIN_ID, f"🆕 YANGI BUYURTMA #{oid}\n👤 {msg.from_user.first_name}\n🪑 {table}\n📦 {prods}\n💰 {total:,} so'm")
    await msg.answer(f"✅ BUYURTMA #{oid} QABUL QILINDI!\n━━━━━━━━━━━━━━\n🪑 Stol: {table}\n💰 Jami: {total:,} so'm\n\n💳 To'lov: 8600 1234 5678 9012\n\nTo'lov qilgach bosing:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ To'lov qildim", callback_data=f"paid_{oid}")]]))
    await state.clear()

# ========== TO'LOV ==========
@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def user_paid(call: types.CallbackQuery):
    oid = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT products, total FROM orders WHERE id=?", (oid,)) as cur:
            row = await cur.fetchone()
    await bot.send_message(ADMIN_ID, f"💳 TO'LOV BILDIRILDI #{oid}\n📦 {row[0]}\n💰 {row[1]:,} so'm", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_{oid}"), InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{oid}")]]))
    await call.message.answer("✅ To'lov ma'lumotingiz adminga yuborildi!")
    await call.answer()

# ========== ADMIN ==========
@dp.callback_query(lambda c: c.data.startswith("confirm_"))
async def confirm_payment(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Faqat admin!", show_alert=True)
        return
    oid = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM orders WHERE id=?", (oid,)) as cur:
            uid = (await cur.fetchone())[0]
        await db.execute("UPDATE orders SET status='tasdiqlangan' WHERE id=?", (oid,))
        await db.commit()
    await bot.send_message(uid, f"✅ #{oid} buyurtmangiz to'lovi tasdiqlandi!")
    await call.message.edit_text(f"✅ #{oid} TASDIQLANDI", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚚 Yetkazildi", callback_data=f"deliver_{oid}")]]))
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_payment(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Faqat admin!", show_alert=True)
        return
    oid = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM orders WHERE id=?", (oid,)) as cur:
            uid = (await cur.fetchone())[0]
        await db.execute("UPDATE orders SET status='rad etilgan' WHERE id=?", (oid,))
        await db.commit()
    await bot.send_message(uid, f"❌ #{oid} buyurtmangiz to'lovi rad etildi!")
    await call.message.edit_text(f"❌ #{oid} RAD ETILDI")
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("deliver_"))
async def deliver_order(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Faqat admin!", show_alert=True)
        return
    oid = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM orders WHERE id=?", (oid,)) as cur:
            uid = (await cur.fetchone())[0]
        await db.execute("UPDATE orders SET status='yetkazilgan' WHERE id=?", (oid,))
        await db.commit()
    await bot.send_message(uid, f"✅ #{oid} buyurtmangiz yetkazildi! Rahmat!")
    await call.message.edit_text(f"✅ #{oid} YETKAZILDI")
    await call.answer()

# ========== TARIX ==========
@dp.message(lambda m: m.text == "📜 Tarix")
async def history(msg: types.Message):
    uid = msg.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, products, total, status, table_number, date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,)) as cur:
            orders = await cur.fetchall()
    if not orders:
        await msg.answer("📭 Siz hali buyurtma bermagansiz")
        return
    text = "📜 BUYURTMA TARIXI\n━━━━━━━━━━━━━━\n"
    for o in orders:
        d = datetime.strptime(o[5], "%Y-%m-%d %H:%M:%S").strftime("%d.%m %H:%M")
        emoji = "⏳" if o[3] == "kutilmoqda" else "✅" if o[3] == "tasdiqlangan" else "🚚" if o[3] == "yetkazilgan" else "❌"
        text += f"#{o[0]} {emoji} {o[3]} | {d}\n🪑 {o[4]}\n{o[1]}\n💰 {o[2]:,} so'm\n━━━━━━━━━━━━━━\n"
    await msg.answer(text)

@dp.message(lambda m: m.text == "📦 Buyurtma")
async def fast_order(msg: types.Message):
    await show_cart(msg)

# ========== ADMIN MAHSULOT ==========
@dp.message(lambda m: m.text == "➕ Mahsulot" and m.from_user.id == ADMIN_ID)
async def add_start(msg: types.Message, state: FSMContext):
    await msg.answer("📦 Mahsulot nomi:")
    await state.set_state(AddProduct.name)

@dp.message(AddProduct.name)
async def add_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await msg.answer("💰 Narxi (faqat son):")
    await state.set_state(AddProduct.price)

@dp.message(AddProduct.price)
async def add_price(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("❌ Faqat son yozing!")
        return
    await state.update_data(price=int(msg.text))
    await msg.answer("📁 Kategoriya (nargile/aroma/ichimlik):")
    await state.set_state(AddProduct.category)

@dp.message(AddProduct.category)
async def add_category(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO products (name, price, category) VALUES (?, ?, ?)", (data['name'], data['price'], msg.text))
        await db.commit()
    await msg.answer(f"✅ {data['name']} qo'shildi!")
    await state.clear()

@dp.message(lambda m: m.text == "❌ O'chirish" and m.from_user.id == ADMIN_ID)
async def delete_start(msg: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM products") as cur:
            prods = await cur.fetchall()
    if not prods:
        await msg.answer("Mahsulot yo'q")
        return
    text = "🗑 O'chirish uchun ID yuboring:\n" + "\n".join([f"ID {p[0]}: {p[1]}" for p in prods])
    await msg.answer(text)
    await state.set_state(DeleteProduct.pid)

@dp.message(DeleteProduct.pid)
async def delete_pid(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("❌ ID son bo'lishi kerak!")
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id=?", (int(msg.text),))
        await db.commit()
    await msg.answer("✅ Mahsulot o'chirildi!")
    await state.clear()

@dp.message(lambda m: m.text == "📋 Buyurtmalar" and m.from_user.id == ADMIN_ID)
async def all_orders(msg: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, user_id, products, total, status, table_number, date FROM orders ORDER BY id DESC LIMIT 10") as cur:
            orders = await cur.fetchall()
    if not orders:
        await msg.answer("Buyurtma yo'q")
        return
    text = "📋 BUYURTMALAR\n━━━━━━━━━━━━━━\n"
    for o in orders:
        d = datetime.strptime(o[6], "%Y-%m-%d %H:%M:%S").strftime("%d.%m %H:%M")
        text += f"#{o[0]} | {o[3]} | {d}\n👤 {o[1]} | 🪑 {o[4]}\n{o[2]}\n💰 {o[3]:,} so'm\n━━━━━━━━━━━━━━\n"
    await msg.answer(text)

@dp.message(lambda m: m.text == "📊 Statistika" and m.from_user.id == ADMIN_ID)
async def stats(msg: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(total) FROM orders WHERE status='yetkazilgan'") as cur:
            revenue = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM products") as cur:
            prods = (await cur.fetchone())[0]
    await msg.answer(f"📊 STATISTIKA\n━━━━━━━━━━━━━━\n📦 Jami buyurtma: {total}\n💰 Daromad: {revenue:,} so'm\n🍽 Mahsulotlar: {prods}")

async def main():
    await init_db()
    print("🤖 AlphaHookah bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
